from __future__ import annotations


"""Built-in utility components for metrics and logging."""

import asyncio
import contextlib
import json
import sys
import time
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.json import JSON
from rich.live import Live
from rich.panel import Panel
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text

from flock.components.agent import AgentComponent


if TYPE_CHECKING:
    from flock.utils.runtime import Context, EvalInputs, EvalResult


class MetricsUtility(AgentComponent):
    """Records simple runtime metrics per agent execution."""

    name: str | None = "metrics"

    async def on_pre_evaluate(
        self, agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        ctx.state.setdefault("metrics", {})[f"{agent.name}:start"] = time.perf_counter()
        return inputs

    async def on_post_evaluate(
        self, agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        metrics = ctx.state.setdefault("metrics", {})
        start = metrics.get(f"{agent.name}:start")
        if start:
            metrics[f"{agent.name}:duration_ms"] = (time.perf_counter() - start) * 1000
        result.metrics.update({
            k: v for k, v in metrics.items() if k.endswith("duration_ms")
        })
        return result


class LoggingUtility(AgentComponent):
    """Rich-powered logging with optional streaming previews."""

    name: str | None = "logs"

    def __init__(
        self,
        console: Console | None = None,
        *,
        highlight_json: bool = True,
        stream_tokens: bool = True,
    ) -> None:
        super().__init__()
        if console is None:
            console = Console(
                file=sys.stdout,
                force_terminal=True,
                highlight=False,
                log_time=True,
                log_path=False,
            )
        self._console = console
        self._highlight_json = highlight_json
        self._stream_tokens = stream_tokens
        self._stream_context: dict[str, tuple[asyncio.Queue, asyncio.Task]] = {}

    async def on_initialize(self, agent, ctx: Context) -> None:
        self._console.log(f"[{agent.name}] start task={ctx.task_id}")
        await super().on_initialize(agent, ctx)

    async def on_pre_consume(self, agent, ctx: Context, inputs: list[Any]):
        summary = ", ".join(self._summarize_artifact(art) for art in inputs) or "<none>"
        self._console.log(
            f"[{agent.name}] consume n={len(inputs)} artifacts -> {summary}"
        )
        self._render_artifacts(agent.name, inputs, role="input")
        return await super().on_pre_consume(agent, ctx, inputs)

    async def on_pre_evaluate(
        self, agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        if self._stream_tokens:
            self._maybe_start_stream(agent, ctx)
        return await super().on_pre_evaluate(agent, ctx, inputs)

    async def on_post_evaluate(
        self, agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        self._render_metrics(agent.name, result.metrics)
        self._render_artifacts(
            agent.name, result.artifacts or inputs.artifacts, role="output"
        )
        if result.logs:
            self._render_logs(agent.name, result.logs)
        awaited = await super().on_post_evaluate(agent, ctx, inputs, result)
        if self._stream_tokens:
            await self._finalize_stream(agent, ctx)
        return awaited

    async def on_post_publish(self, agent, ctx: Context, artifact):
        visibility = getattr(artifact.visibility, "kind", "Public")
        subtitle = f"visibility={visibility}"
        panel = self._build_artifact_panel(
            artifact, role="published", subtitle=subtitle
        )
        self._console.print(panel)
        await super().on_post_publish(agent, ctx, artifact)

    async def on_error(self, agent, ctx: Context, error: Exception) -> None:
        self._console.log(f"[{agent.name}] error {error!r}", style="bold red")
        if self._stream_tokens:
            await self._abort_stream(agent, ctx)
        await super().on_error(agent, ctx, error)

    async def on_terminate(self, agent, ctx: Context) -> None:
        if self._stream_tokens:
            await self._abort_stream(agent, ctx)
        self._console.log(f"[{agent.name}] end task={ctx.task_id}")
        await super().on_terminate(agent, ctx)

    # ------------------------------------------------------------------
    # Rendering helpers

    def _render_artifacts(
        self, agent_name: str, artifacts: Sequence[Any], *, role: str
    ) -> None:
        for artifact in artifacts:
            panel = self._build_artifact_panel(artifact, role=role)
            self._console.print(panel)

    def _build_artifact_panel(
        self, artifact: Any, *, role: str, subtitle: str | None = None
    ) -> Panel:
        title = f"{role} • {self._summarize_artifact(artifact)}"
        if subtitle is None:
            produced_by = getattr(artifact, "produced_by", None)
            visibility = getattr(artifact, "visibility", None)
            visibility_name = getattr(visibility, "kind", None)
            pieces = []
            if produced_by:
                pieces.append(f"from={produced_by}")
            if visibility_name:
                pieces.append(f"visibility={visibility_name}")
            subtitle = " | ".join(pieces)

        payload = getattr(artifact, "payload", None)
        renderable = self._render_payload(payload)
        return Panel(renderable, title=title, subtitle=subtitle, border_style="cyan")

    def _render_payload(self, payload: Any):
        if payload is None:
            return Pretty(payload)
        if isinstance(payload, Mapping):
            if self._highlight_json:
                try:
                    return JSON.from_data(payload, indent=2, sort_keys=True)
                except Exception:  # nosec B110 - pragma: no cover - serialization guard
                    pass
            return Pretty(dict(payload))
        if isinstance(payload, (list, tuple, set)):
            return Pretty(payload)
        if hasattr(payload, "model_dump"):
            model_dict = payload.model_dump()
            return JSON.from_data(model_dict, indent=2, sort_keys=True)
        return Pretty(payload)

    def _render_metrics(self, agent_name: str, metrics: Mapping[str, Any]) -> None:
        if not metrics:
            return
        table = Table(title=f"{agent_name} metrics", box=None, show_header=False)
        for key, value in metrics.items():
            display = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            table.add_row(key, display)
        self._console.print(table)

    def _render_logs(self, agent_name: str, logs: Iterable[str]) -> None:
        if not logs:
            return
        textual: list[str] = []
        json_sections: list[JSON] = []
        for line in logs:
            if line.startswith("dspy.output="):
                _, _, payload = line.partition("=")
                try:
                    json_sections.append(
                        JSON.from_data(json.loads(payload), indent=2, sort_keys=True)
                    )
                    continue
                except json.JSONDecodeError:
                    textual.append(line)
            else:
                textual.append(line)
        for payload in json_sections:
            panel = Panel(
                payload, title=f"{agent_name} ▸ dspy.output", border_style="green"
            )
            self._console.print(panel)
        if textual:
            body = Text("\n".join(textual) + "\n")
            panel = Panel(body, title=f"{agent_name} logs", border_style="magenta")
            self._console.print(panel)

    def _summarize_artifact(self, artifact: Any) -> str:
        try:
            art_id = getattr(artifact, "id", None)
            prefix = str(art_id)[:8] if art_id else "?"
            art_type = getattr(artifact, "type", type(artifact).__name__)
            return f"{art_type}@{prefix}"
        except Exception:  # pragma: no cover - defensive
            return repr(artifact)

    # ------------------------------------------------------------------
    # Streaming support

    def _maybe_start_stream(self, agent, ctx: Context) -> None:
        stream_key = self._stream_key(agent, ctx)
        if stream_key in self._stream_context:
            return
        queue: asyncio.Queue = asyncio.Queue()
        self._attach_stream_queue(ctx.state, queue)
        task = asyncio.create_task(self._consume_stream(agent.name, stream_key, queue))
        self._stream_context[stream_key] = (queue, task)

    async def _finalize_stream(self, agent, ctx: Context) -> None:
        stream_key = self._stream_key(agent, ctx)
        record = self._stream_context.pop(stream_key, None)
        self._detach_stream_queue(ctx.state)
        if not record:
            return
        queue, task = record
        if not task.done():
            await queue.put({"kind": "end"})
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except TimeoutError:  # pragma: no cover - defensive cancel
            task.cancel()

    async def _abort_stream(self, agent, ctx: Context) -> None:
        stream_key = self._stream_key(agent, ctx)
        record = self._stream_context.pop(stream_key, None)
        self._detach_stream_queue(ctx.state)
        if not record:
            return
        queue, task = record
        if not task.done():
            await queue.put({"kind": "end", "error": "aborted"})
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _consume_stream(
        self, agent_name: str, stream_key: str, queue: asyncio.Queue
    ) -> None:
        body = Text()
        live: Live | None = None
        try:
            while True:
                event = await queue.get()
                if event is None or event.get("kind") == "end":
                    break
                kind = event.get("kind")
                if live is None:
                    live_panel = Panel(
                        body, title=f"{agent_name} ▸ streaming", border_style="cyan"
                    )
                    live = Live(
                        live_panel,
                        console=self._console,
                        refresh_per_second=12,
                        transient=True,
                    )
                    live.__enter__()
                if kind == "chunk":
                    chunk = event.get("chunk") or ""
                    body.append(chunk)
                elif kind == "status":
                    message = event.get("message") or ""
                    stage = event.get("stage")
                    line = f"[{stage}] {message}" if stage else message
                    body.append(f"\n{line}\n", style="dim")
                elif kind == "error":
                    message = event.get("message") or ""
                    body.append(f"\n⚠ {message}\n", style="bold red")
                if live is not None:
                    live.update(
                        Panel(
                            body, title=f"{agent_name} ▸ streaming", border_style="cyan"
                        )
                    )
        finally:
            if live is not None:
                live.__exit__(None, None, None)
        if body.plain:
            self._console.print(
                Panel(
                    body, title=f"{agent_name} ▸ stream transcript", border_style="cyan"
                )
            )

    def _stream_key(self, agent, ctx: Context) -> str:
        return f"{ctx.task_id}:{agent.name}"

    def _attach_stream_queue(
        self, state: MutableMapping[str, Any], queue: asyncio.Queue
    ) -> None:
        state.setdefault("_logging", {})["stream_queue"] = queue

    def _detach_stream_queue(self, state: MutableMapping[str, Any]) -> None:
        try:
            logging_state = state.get("_logging")
            if isinstance(logging_state, MutableMapping):
                logging_state.pop("stream_queue", None)
        except Exception:  # nosec B110 - pragma: no cover - defensive
            pass


__all__ = ["LoggingUtility", "MetricsUtility"]
