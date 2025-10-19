from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone

from flock.dashboard.collector import AgentSnapshot, DashboardEventCollector
from flock.dashboard.models.graph import (
    GraphAgentMetrics,
    GraphArtifact,
    GraphEdge,
    GraphFilters,
    GraphMarker,
    GraphNode,
    GraphPosition,
    GraphRequest,
    GraphRun,
    GraphSnapshot,
    GraphState,
    GraphStatistics,
    GraphTimeRange,
    GraphTimeRangePreset,
)
from flock.logging.auto_trace import AutoTracedMeta
from flock.core import Flock
from flock.core.store import (
    Artifact,
    BlackboardStore,
    FilterConfig,
)
from flock.core.store import (
    ArtifactEnvelope as StoreArtifactEnvelope,
)


class GraphAssembler(metaclass=AutoTracedMeta):
    """Build graph snapshots for dashboard consumption."""

    def __init__(
        self,
        store: BlackboardStore,
        collector: DashboardEventCollector,
        orchestrator: Flock,
    ) -> None:
        self._store = store
        self._collector = collector
        self._orchestrator = orchestrator

    async def build_snapshot(self, request: GraphRequest) -> GraphSnapshot:
        filters = request.filters or GraphFilters()
        filter_config = self._to_filter_config(filters)
        limit = max(1, request.options.limit if request.options else 500)

        envelopes, total_available = await self._store.fetch_graph_artifacts(
            filter_config,
            limit=limit,
            offset=0,
        )

        graph_state: GraphState = await self._collector.snapshot_graph_state()
        agent_snapshots = await self._collector.snapshot_agent_registry()
        artifacts = self._convert_envelopes_to_artifacts(envelopes, graph_state.consumptions)

        produced_metrics, consumed_metrics = self._calculate_agent_metrics(artifacts.values())

        if request.view_mode == "agent":
            nodes = self._build_agent_nodes(
                artifacts,
                produced_metrics,
                consumed_metrics,
                graph_state,
                agent_snapshots,
            )
            edges = self._derive_agent_edges(artifacts)
            # Phase 1.5: Add pending edges for artifacts waiting in correlation/batch
            pending_edges = self._derive_pending_edges(artifacts)
            edges.extend(pending_edges)
        else:
            nodes = self._build_message_nodes(artifacts)
            edges = self._derive_blackboard_edges(artifacts, graph_state)

        statistics = None
        if request.options.include_statistics:
            artifact_summary = await self._store.summarize_artifacts(filter_config)
            statistics = GraphStatistics(
                produced_by_agent=produced_metrics,
                consumed_by_agent=consumed_metrics,
                artifact_summary=artifact_summary,
            )

        filters_copy = filters.model_copy(deep=True)
        generated_at = datetime.now(timezone.utc)

        return GraphSnapshot(
            generated_at=generated_at,
            view_mode=request.view_mode,
            filters=filters_copy,
            nodes=nodes,
            edges=edges,
            statistics=statistics,
            total_artifacts=total_available,
            truncated=total_available > len(artifacts),
        )

    def _convert_envelopes_to_artifacts(
        self,
        envelopes: Sequence[StoreArtifactEnvelope],
        runtime_consumptions: Mapping[str, Sequence[str]],
    ) -> dict[str, GraphArtifact]:
        artifacts: dict[str, GraphArtifact] = {}
        for envelope in envelopes:
            artifact: Artifact = envelope.artifact
            artifact_id = str(artifact.id)
            consumers = {record.consumer for record in envelope.consumptions}
            runtime = runtime_consumptions.get(artifact_id, [])
            consumers.update(runtime)

            correlation_id = (
                str(artifact.correlation_id) if artifact.correlation_id is not None else None
            )
            visibility_kind = getattr(artifact.visibility, "kind", None)
            if visibility_kind is None:
                cls_name = type(artifact.visibility).__name__
                visibility_kind = cls_name[:-10] if cls_name.endswith("Visibility") else cls_name

            artifacts[artifact_id] = GraphArtifact(
                artifact_id=artifact_id,
                artifact_type=artifact.type,
                produced_by=artifact.produced_by,
                consumed_by=sorted(consumers),
                published_at=artifact.created_at,
                payload=dict(artifact.payload),
                correlation_id=correlation_id,
                visibility_kind=visibility_kind,
                tags=sorted(artifact.tags),
            )
        return artifacts

    def _calculate_agent_metrics(
        self,
        artifacts: Iterable[GraphArtifact],
    ) -> tuple[dict[str, GraphAgentMetrics], dict[str, GraphAgentMetrics]]:
        produced_acc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        consumed_acc: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        produced_totals: dict[str, int] = defaultdict(int)
        consumed_totals: dict[str, int] = defaultdict(int)

        for artifact in artifacts:
            producer = artifact.produced_by or "external"
            produced_totals[producer] += 1
            produced_acc[producer][artifact.artifact_type] += 1

            for consumer in artifact.consumed_by:
                consumed_totals[consumer] += 1
                consumed_acc[consumer][artifact.artifact_type] += 1

        produced_metrics: dict[str, GraphAgentMetrics] = {}
        for agent, total in produced_totals.items():
            produced_metrics[agent] = GraphAgentMetrics(
                total=total,
                by_type=dict(produced_acc[agent]),
            )

        consumed_metrics: dict[str, GraphAgentMetrics] = {}
        for agent, total in consumed_totals.items():
            consumed_metrics[agent] = GraphAgentMetrics(
                total=total,
                by_type=dict(consumed_acc[agent]),
            )

        return produced_metrics, consumed_metrics

    def _build_agent_nodes(
        self,
        artifacts: Mapping[str, GraphArtifact],
        produced_metrics: Mapping[str, GraphAgentMetrics],
        consumed_metrics: Mapping[str, GraphAgentMetrics],
        graph_state: GraphState,
        agent_snapshots: Mapping[str, AgentSnapshot],
    ) -> list[GraphNode]:
        nodes: list[GraphNode] = []
        agent_status = graph_state.agent_status
        active_names: set[str] = set()

        existing_names: set[str] = set()

        for agent in self._orchestrator.agents:
            subscriptions = sorted(
                {type_name for sub in agent.subscriptions for type_name in sub.type_names}
            )
            output_types = sorted({output.spec.type_name for output in agent.outputs})

            produced = produced_metrics.get(agent.name)
            consumed = consumed_metrics.get(agent.name)
            snapshot = agent_snapshots.get(agent.name)

            # Phase 1.2: Build logic_operations from live agent subscriptions
            logic_operations = []
            for idx, subscription in enumerate(agent.subscriptions):
                if subscription.join or subscription.batch:
                    logic_config = self._build_logic_config_for_subscription(agent, subscription, idx)
                    if logic_config:
                        logic_operations.append(logic_config)

            node_data = {
                "name": agent.name,
                "status": agent_status.get(agent.name, "idle"),
                "subscriptions": subscriptions,
                "outputTypes": output_types,
                "sentCount": produced.total if produced else 0,
                "recvCount": consumed.total if consumed else 0,
                "sentByType": produced.by_type if produced else {},
                "receivedByType": consumed.by_type if consumed else {},
                "streamingTokens": [],
                "labels": sorted(agent.labels),
                "firstSeen": snapshot.first_seen.isoformat() if snapshot else None,
                "lastSeen": snapshot.last_seen.isoformat() if snapshot else None,
                "signature": snapshot.signature if snapshot else None,
                "logicOperations": logic_operations,  # Phase 1.2
            }

            nodes.append(
                GraphNode(
                    id=agent.name,
                    type="agent",
                    data=node_data,
                    position=GraphPosition(),
                    hidden=False,
                )
            )
            active_names.add(agent.name)
            existing_names.add(agent.name)

        for name, snapshot in agent_snapshots.items():
            if name in active_names:
                continue

            produced = produced_metrics.get(name)
            consumed = consumed_metrics.get(name)

            node_data = {
                "name": name,
                "status": "inactive",
                "subscriptions": list(snapshot.subscriptions),
                "outputTypes": list(snapshot.output_types),
                "sentCount": produced.total if produced else 0,
                "recvCount": consumed.total if consumed else 0,
                "sentByType": produced.by_type if produced else {},
                "receivedByType": consumed.by_type if consumed else {},
                "streamingTokens": [],
                "labels": list(snapshot.labels),
                "firstSeen": snapshot.first_seen.isoformat(),
                "lastSeen": snapshot.last_seen.isoformat(),
                "signature": snapshot.signature,
                "logicOperations": list(snapshot.logic_operations),  # Phase 1.2: From snapshot
            }

            nodes.append(
                GraphNode(
                    id=name,
                    type="agent",
                    data=node_data,
                    position=GraphPosition(),
                    hidden=False,
                )
            )
            existing_names.add(name)

        metric_names = set(produced_metrics.keys()) | set(consumed_metrics.keys())
        for name in metric_names:
            if name in existing_names:
                continue
            produced = produced_metrics.get(name)
            consumed = consumed_metrics.get(name)
            node_data = {
                "name": name,
                "status": "unknown",
                "subscriptions": [],
                "outputTypes": [],
                "sentCount": produced.total if produced else 0,
                "recvCount": consumed.total if consumed else 0,
                "sentByType": produced.by_type if produced else {},
                "receivedByType": consumed.by_type if consumed else {},
                "streamingTokens": [],
                "labels": [],
                "firstSeen": None,
                "lastSeen": None,
                "signature": None,
            }

            nodes.append(
                GraphNode(
                    id=name,
                    type="agent",
                    data=node_data,
                    position=GraphPosition(),
                    hidden=False,
                )
            )
            existing_names.add(name)

        return nodes

    def _build_message_nodes(
        self,
        artifacts: Mapping[str, GraphArtifact],
    ) -> list[GraphNode]:
        nodes: list[GraphNode] = []

        for artifact in artifacts.values():
            payload_preview = self._payload_preview(artifact.payload)
            timestamp_ms = int(artifact.published_at.timestamp() * 1000)

            node_data = {
                "artifactType": artifact.artifact_type,
                "payloadPreview": payload_preview,
                "payload": artifact.payload,
                "producedBy": artifact.produced_by,
                "consumedBy": list(artifact.consumed_by),
                "timestamp": timestamp_ms,
                "tags": artifact.tags,
                "visibilityKind": artifact.visibility_kind or "Unknown",
                "correlationId": artifact.correlation_id,
            }

            nodes.append(
                GraphNode(
                    id=artifact.artifact_id,
                    type="message",
                    data=node_data,
                    position=GraphPosition(),
                    hidden=False,
                )
            )

        return nodes

    def _derive_agent_edges(
        self,
        artifacts: Mapping[str, GraphArtifact],
    ) -> list[GraphEdge]:
        edge_payloads: dict[str, dict] = {}
        pair_group: dict[tuple[str, str], list[str]] = defaultdict(list)

        for artifact in artifacts.values():
            producer = artifact.produced_by or "external"
            message_type = artifact.artifact_type
            for consumer in artifact.consumed_by:
                edge_id = f"{producer}__{consumer}__{message_type}"
                payload = edge_payloads.setdefault(
                    edge_id,
                    {
                        "source": producer,
                        "target": consumer,
                        "message_type": message_type,
                        "artifact_ids": [],
                        "latest_timestamp": artifact.published_at,
                    },
                )
                payload["artifact_ids"].append(artifact.artifact_id)
                payload["latest_timestamp"] = max(payload["latest_timestamp"], artifact.published_at)
                pair_key = tuple(sorted((producer, consumer)))
                if edge_id not in pair_group[pair_key]:
                    pair_group[pair_key].append(edge_id)

        offsets = self._calculate_label_offsets(pair_group)
        edges: list[GraphEdge] = []
        for edge_id, payload in edge_payloads.items():
            message_type = payload["message_type"]
            artifact_ids = payload["artifact_ids"]
            label = f"{message_type} ({len(artifact_ids)})"
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=payload["source"],
                    target=payload["target"],
                    type="message_flow",
                    label=label,
                    data={
                        "messageType": message_type,
                        "messageCount": len(artifact_ids),
                        "artifactIds": artifact_ids,
                        "latestTimestamp": payload["latest_timestamp"].isoformat(),
                        "labelOffset": offsets.get(edge_id, 0.0),
                    },
                    marker_end=GraphMarker(),
                    hidden=False,
                )
            )

        return edges

    def _derive_pending_edges(
        self,
        artifacts: Mapping[str, GraphArtifact],
    ) -> list[GraphEdge]:
        """
        Phase 1.5: Build pending edges for artifacts waiting in correlation/batch.

        Creates visual edges (purple/orange dashed) from artifact producers to agents
        that have those artifacts waiting in JoinSpec/BatchSpec queues.

        Returns edges with type "pending_join" or "pending_batch".
        """
        edges: list[GraphEdge] = []
        edge_counter = 0

        # Build map of artifact_id -> artifact for quick lookup
        artifact_map = {art.artifact_id: art for art in artifacts.values()}

        # Iterate through all active agents with JoinSpec/BatchSpec subscriptions
        for agent in self._orchestrator.agents:
            for sub_idx, subscription in enumerate(agent.subscriptions):
                # JoinSpec pending edges
                if subscription.join:
                    pending_join_edges = self._build_pending_join_edges(
                        agent.name,
                        sub_idx,
                        subscription,
                        artifact_map,
                        edge_counter
                    )
                    edges.extend(pending_join_edges)
                    edge_counter += len(pending_join_edges)

                # BatchSpec pending edges
                if subscription.batch:
                    pending_batch_edges = self._build_pending_batch_edges(
                        agent.name,
                        sub_idx,
                        subscription,
                        artifact_map,
                        edge_counter
                    )
                    edges.extend(pending_batch_edges)
                    edge_counter += len(pending_batch_edges)

        return edges

    def _build_pending_join_edges(
        self,
        agent_name: str,
        sub_idx: int,
        subscription: "Subscription",  # noqa: F821
        artifact_map: Mapping[str, GraphArtifact],
        start_counter: int,
    ) -> list[GraphEdge]:
        """Build pending edges for JoinSpec correlation groups."""
        from flock.dashboard.routes.helpers import _get_correlation_groups

        edges: list[GraphEdge] = []
        correlation_groups = _get_correlation_groups(
            self._orchestrator._correlation_engine,
            agent_name,
            sub_idx
        )

        if not correlation_groups:
            return edges

        edge_counter = start_counter

        # For each correlation group, create edges for waiting artifacts
        for group in correlation_groups:
            # Get artifacts in this correlation group's waiting pool
            correlation_key = group.get("correlation_key")
            if not correlation_key:
                continue

            # Get the actual correlation group from engine
            pool_key = (agent_name, sub_idx)
            groups_dict = self._orchestrator._correlation_engine.correlation_groups.get(pool_key, {})
            corr_group = groups_dict.get(correlation_key)

            if not corr_group:
                continue

            # Build edges for each artifact type in the waiting pool
            for artifact_type, artifact_list in corr_group.waiting_artifacts.items():
                for artifact in artifact_list:
                    artifact_id = str(artifact.id)
                    graph_artifact = artifact_map.get(artifact_id)

                    if not graph_artifact:
                        continue

                    producer = graph_artifact.produced_by or "external"

                    # Create pending join edge
                    edge_id = f"pending_join__{producer}__{agent_name}__{artifact_id}__{edge_counter}"
                    edge_counter += 1

                    edges.append(
                        GraphEdge(
                            id=edge_id,
                            source=producer,
                            target=agent_name,
                            type="pending_join",
                            label=f"⋈ {correlation_key}",
                            data={
                                "artifactId": artifact_id,
                                "artifactType": artifact_type,
                                "correlationKey": correlation_key,
                                "subscriptionIndex": sub_idx,
                                "waitingFor": group.get("waiting_for", []),
                                "labelOffset": 0.0,
                            },
                            marker_end=GraphMarker(),
                            hidden=False,
                        )
                    )

        return edges

    def _build_pending_batch_edges(
        self,
        agent_name: str,
        sub_idx: int,
        subscription: "Subscription",  # noqa: F821
        artifact_map: Mapping[str, GraphArtifact],
        start_counter: int,
    ) -> list[GraphEdge]:
        """Build pending edges for BatchSpec accumulation."""
        from flock.dashboard.routes.helpers import _get_batch_state

        edges: list[GraphEdge] = []
        batch_state = _get_batch_state(
            self._orchestrator._batch_engine,
            agent_name,
            sub_idx,
            subscription.batch
        )

        if not batch_state:
            return edges

        # Get the batch accumulator
        batch_key = (agent_name, sub_idx)
        accumulator = self._orchestrator._batch_engine.batches.get(batch_key)

        if not accumulator or not accumulator.artifacts:
            return edges

        edge_counter = start_counter

        # Create edges for each artifact in the batch
        for artifact in accumulator.artifacts:
            artifact_id = str(artifact.id)
            graph_artifact = artifact_map.get(artifact_id)

            if not graph_artifact:
                continue

            producer = graph_artifact.produced_by or "external"
            artifact_type = graph_artifact.artifact_type

            # Create pending batch edge
            edge_id = f"pending_batch__{producer}__{agent_name}__{artifact_id}__{edge_counter}"
            edge_counter += 1

            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=producer,
                    target=agent_name,
                    type="pending_batch",
                    label=f"⊞ {batch_state['items_collected']}/{batch_state['items_target'] or '∞'}",
                    data={
                        "artifactId": artifact_id,
                        "artifactType": artifact_type,
                        "subscriptionIndex": sub_idx,
                        "itemsCollected": batch_state["items_collected"],
                        "itemsTarget": batch_state["items_target"],
                        "labelOffset": 0.0,
                    },
                    marker_end=GraphMarker(),
                    hidden=False,
                )
            )

        return edges

    def _derive_blackboard_edges(
        self,
        artifacts: Mapping[str, GraphArtifact],
        graph_state: GraphState,
    ) -> list[GraphEdge]:
        artifact_ids = set(artifacts.keys())
        edge_payloads: dict[str, dict] = {}
        pair_group: dict[tuple[str, str], list[str]] = defaultdict(list)

        for run in self._collect_runs_for_blackboard(artifacts, graph_state):
            if run.status == "active":
                continue
            consumed = [
                artifact_id for artifact_id in run.consumed_artifacts if artifact_id in artifact_ids
            ]
            produced = [
                artifact_id for artifact_id in run.produced_artifacts if artifact_id in artifact_ids
            ]
            if not consumed or not produced:
                continue
            for consumed_id in consumed:
                for produced_id in produced:
                    edge_id = f"{consumed_id}__{produced_id}__{run.run_id}"
                    payload = edge_payloads.setdefault(
                        edge_id,
                        {
                            "source": consumed_id,
                            "target": produced_id,
                            "agent_name": run.agent_name,
                            "run_id": run.run_id,
                            "duration_ms": run.duration_ms,
                        },
                    )
                    pair_key = tuple(sorted((consumed_id, produced_id)))
                    if edge_id not in pair_group[pair_key]:
                        pair_group[pair_key].append(edge_id)

        offsets = self._calculate_label_offsets(pair_group)
        edges: list[GraphEdge] = []
        for edge_id, payload in edge_payloads.items():
            edges.append(
                GraphEdge(
                    id=edge_id,
                    source=payload["source"],
                    target=payload["target"],
                    type="transformation",
                    label=payload["agent_name"],
                    data={
                        "transformerAgent": payload["agent_name"],
                        "runId": payload["run_id"],
                        "durationMs": payload["duration_ms"],
                        "labelOffset": offsets.get(edge_id, 0.0),
                    },
                    marker_end=GraphMarker(),
                    hidden=False,
                )
            )

        return edges

    def _payload_preview(self, payload: Mapping[str, object]) -> str:
        try:
            serialized = json.dumps(payload, ensure_ascii=False)
        except Exception:
            serialized = str(payload)
        return serialized[:120]

    def _to_filter_config(self, filters: GraphFilters) -> FilterConfig:
        start, end = self._resolve_time_bounds(filters.time_range)
        return FilterConfig(
            type_names=self._optional_set(filters.artifact_types),
            produced_by=self._optional_set(filters.producers),
            correlation_id=filters.correlation_id or None,
            tags=self._optional_set(filters.tags),
            visibility=self._optional_set(filters.visibility),
            start=start,
            end=end,
        )

    def _collect_runs_for_blackboard(
        self,
        artifacts: Mapping[str, GraphArtifact],
        graph_state: GraphState,
    ) -> list[GraphRun]:
        existing_runs = list(graph_state.runs)
        synthetic_runs = self._build_synthetic_runs(
            artifacts, graph_state.consumptions, existing_runs
        )
        return existing_runs + synthetic_runs

    def _build_synthetic_runs(
        self,
        artifacts: Mapping[str, GraphArtifact],
        consumptions: Mapping[str, Sequence[str]],
        existing_runs: Sequence[GraphRun],
    ) -> list[GraphRun]:
        existing_keys = {(run.agent_name, run.correlation_id or "") for run in existing_runs}

        produced_buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
        consumed_buckets: dict[tuple[str, str], list[str]] = defaultdict(list)

        for artifact in artifacts.values():
            correlation = artifact.correlation_id or ""
            producer = artifact.produced_by or "external"
            produced_buckets[(producer, correlation)].append(artifact.artifact_id)

            consumer_list = consumptions.get(artifact.artifact_id, artifact.consumed_by)
            for consumer in consumer_list:
                consumed_buckets[(consumer, correlation)].append(artifact.artifact_id)

        synthetic_runs: list[GraphRun] = []
        counter = 0
        for key, consumed in consumed_buckets.items():
            produced = produced_buckets.get(key)
            if not consumed or not produced:
                continue
            if key in existing_keys:
                continue

            agent_name, correlation = key
            run_id = f"synthetic_{agent_name}_{correlation or 'uncorrelated'}_{counter}"
            counter += 1

            synthetic_runs.append(
                GraphRun(
                    run_id=run_id,
                    agent_name=agent_name,
                    correlation_id=correlation or None,
                    status="completed",
                    consumed_artifacts=sorted(set(consumed)),
                    produced_artifacts=sorted(set(produced)),
                )
            )

        return synthetic_runs

    def _resolve_time_bounds(
        self, time_range: GraphTimeRange
    ) -> tuple[datetime | None, datetime | None]:
        now = datetime.now(timezone.utc)
        preset = time_range.preset

        if preset == GraphTimeRangePreset.ALL:
            return None, None
        if preset == GraphTimeRangePreset.CUSTOM:
            return self._ensure_timezone(time_range.start), self._ensure_timezone(time_range.end)

        if preset == GraphTimeRangePreset.LAST_5_MIN:
            delta = timedelta(minutes=5)
        elif preset == GraphTimeRangePreset.LAST_1_HOUR:
            delta = timedelta(hours=1)
        else:
            delta = timedelta(minutes=10)

        return now - delta, now

    @staticmethod
    def _ensure_timezone(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _optional_set(values: Sequence[str]) -> set[str] | None:
        cleaned = {value for value in values if value}
        return cleaned if cleaned else None

    @staticmethod
    def _calculate_label_offsets(groups: Mapping[tuple[str, str], list[str]]) -> dict[str, float]:
        offsets: dict[str, float] = {}
        for edge_ids in groups.values():
            total = len(edge_ids)
            if total <= 1:
                for edge_id in edge_ids:
                    offsets[edge_id] = 0.0
                continue
            offset_range = min(40.0, total * 15.0)
            step = offset_range / (total - 1)
            for index, edge_id in enumerate(edge_ids):
                offsets[edge_id] = index * step - offset_range / 2
        return offsets

    def _build_logic_config_for_subscription(self, agent, subscription, idx):
        """Build logic operations config for a subscription (Phase 1.2 + 1.2.1: with waiting_state)."""
        if not subscription.join and not subscription.batch:
            return None

        config = {
            "subscription_index": idx,
            "subscription_types": list(subscription.type_names),
        }

        # JoinSpec configuration
        if subscription.join:
            join_spec = subscription.join
            window_type = "time" if isinstance(join_spec.within, timedelta) else "count"
            window_value = (
                int(join_spec.within.total_seconds())
                if isinstance(join_spec.within, timedelta)
                else join_spec.within
            )

            config["join"] = {
                "correlation_strategy": "by_key",
                "window_type": window_type,
                "window_value": window_value,
                "window_unit": "seconds" if window_type == "time" else "artifacts",
                "required_types": list(subscription.type_names),
                "type_counts": dict(subscription.type_counts),
            }

            # Phase 1.2.1: Get waiting state from CorrelationEngine
            from flock.dashboard.routes.helpers import _get_correlation_groups
            correlation_groups = _get_correlation_groups(
                self._orchestrator._correlation_engine, agent.name, idx
            )
            if correlation_groups:
                config["waiting_state"] = {
                    "is_waiting": True,
                    "correlation_groups": correlation_groups,
                }

        # BatchSpec configuration
        if subscription.batch:
            batch_spec = subscription.batch
            strategy = (
                "hybrid"
                if batch_spec.size and batch_spec.timeout
                else "size"
                if batch_spec.size
                else "timeout"
            )

            config["batch"] = {
                "strategy": strategy,
            }
            if batch_spec.size:
                config["batch"]["size"] = batch_spec.size
            if batch_spec.timeout:
                config["batch"]["timeout_seconds"] = int(batch_spec.timeout.total_seconds())

            # Phase 1.2.1: Get waiting state from BatchEngine
            from flock.dashboard.routes.helpers import _get_batch_state
            batch_state = _get_batch_state(self._orchestrator._batch_engine, agent.name, idx, batch_spec)
            if batch_state:
                if "waiting_state" not in config:
                    config["waiting_state"] = {"is_waiting": True}
                config["waiting_state"]["batch_state"] = batch_state

        return config
