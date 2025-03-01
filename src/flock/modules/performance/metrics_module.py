"""Performance and metrics tracking for Flock agents."""

import json
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Literal

import numpy as np
import psutil
from pydantic import BaseModel, Field, validator

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_module import FlockModule, FlockModuleConfig


class MetricPoint(BaseModel):
    """Single metric measurement."""

    timestamp: datetime
    value: int | float | str
    tags: dict[str, str] = {}


class MetricsModuleConfig(FlockModuleConfig):
    """Configuration for performance metrics collection."""

    # Collection settings
    collect_timing: bool = Field(
        default=True, description="Collect timing metrics"
    )
    collect_memory: bool = Field(
        default=True, description="Collect memory usage"
    )
    collect_token_usage: bool = Field(
        default=True, description="Collect token usage stats"
    )
    collect_cpu: bool = Field(default=True, description="Collect CPU usage")

    # Storage settings
    storage_type: Literal["json", "prometheus", "memory"] = Field(
        default="json", description="Where to store metrics"
    )
    metrics_dir: str = Field(
        default="metrics/", description="Directory for metrics storage"
    )

    # Aggregation settings
    aggregation_interval: str = Field(
        default="1h", description="Interval for metric aggregation"
    )
    retention_days: int = Field(default=30, description="Days to keep metrics")

    # Alerting settings
    alert_on_high_latency: bool = Field(
        default=True, description="Alert on high latency"
    )
    latency_threshold_ms: int = Field(
        default=1000, description="Threshold for latency alerts"
    )

    @validator("aggregation_interval")
    def validate_interval(cls, v):
        """Validate time interval format."""
        if v[-1] not in ["s", "m", "h", "d"]:
            raise ValueError("Interval must end with s, m, h, or d")
        return v


class MetricsModule(FlockModule):
    """Module for collecting and analyzing agent performance metrics."""

    name: str = "performance_metrics"
    config: MetricsModuleConfig = Field(
        default_factory=MetricsModuleConfig,
        description="Performance metrics configuration",
    )

    def __init__(self, name, config):
        super().__init__(name=name, config=config)
        self._metrics = defaultdict(list)
        self._start_time: float | None = None
        self._start_memory: int | None = None

        # Set up storage
        if self.config.storage_type == "json":
            os.makedirs(self.config.metrics_dir, exist_ok=True)

        # Set up prometheus if needed
        if self.config.storage_type == "prometheus":
            try:
                from prometheus_client import Counter, Gauge, Histogram

                self._prom_latency = Histogram(
                    "flock_agent_latency_seconds",
                    "Time taken for agent evaluation",
                    ["agent_name"],
                )
                self._prom_memory = Gauge(
                    "flock_agent_memory_bytes",
                    "Memory usage by agent",
                    ["agent_name"],
                )
                self._prom_tokens = Counter(
                    "flock_agent_tokens_total",
                    "Token usage by agent",
                    ["agent_name", "type"],
                )
                self._prom_errors = Counter(
                    "flock_agent_errors_total",
                    "Error count by agent",
                    ["agent_name", "error_type"],
                )
            except ImportError:
                self.config.storage_type = "json"

    """Fixes for metrics summary calculation."""

    def _load_metrics_from_files(
        self, metric_name: str = None
    ) -> dict[str, list[MetricPoint]]:
        """Load metrics from JSON files."""
        metrics = defaultdict(list)

        try:
            # Get all metric files
            files = [
                f
                for f in os.listdir(self.config.metrics_dir)
                if f.endswith(".json") and not f.startswith("summary_")
            ]

            # Filter by metric name if specified
            if metric_name:
                files = [f for f in files if f.startswith(f"{metric_name}_")]

            for filename in files:
                filepath = os.path.join(self.config.metrics_dir, filename)
                with open(filepath) as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            point = MetricPoint(
                                timestamp=datetime.fromisoformat(
                                    data["timestamp"]
                                ),
                                value=data["value"],
                                tags=data["tags"],
                            )
                            name = filename.split("_")[
                                0
                            ]  # Get metric name from filename
                            metrics[name].append(point)
                        except json.JSONDecodeError:
                            continue

            return dict(metrics)
        except Exception as e:
            print(f"Error loading metrics from files: {e}")
            return {}

    def get_metrics(
        self,
        metric_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, list[MetricPoint]]:
        """Get recorded metrics with optional filtering."""
        # Get metrics from appropriate source
        if self.config.storage_type == "json":
            metrics = self._load_metrics_from_files(metric_name)
        else:
            metrics = self._metrics
            if metric_name:
                metrics = {metric_name: metrics[metric_name]}

        # Apply time filtering if needed
        if start_time or end_time:
            filtered_metrics = defaultdict(list)
            for name, points in metrics.items():
                filtered_points = [
                    p
                    for p in points
                    if (not start_time or p.timestamp >= start_time)
                    and (not end_time or p.timestamp <= end_time)
                ]
                filtered_metrics[name] = filtered_points
            metrics = filtered_metrics

        return dict(metrics)

    def get_statistics(
        self, metric_name: str, percentiles: list[float] = [50, 90, 95, 99]
    ) -> dict[str, float]:
        """Calculate statistics for a metric."""
        # Get all points for this metric
        metrics = self.get_metrics(metric_name=metric_name)
        points = metrics.get(metric_name, [])

        if not points:
            return {}

        values = [p.value for p in points if isinstance(p.value, (int, float))]
        if not values:
            return {}

        stats = {
            "min": min(values),
            "max": max(values),
            "mean": float(
                np.mean(values)
            ),  # Convert to float for JSON serialization
            "std": float(np.std(values)),
            "count": len(values),
            "last_value": values[-1],
        }

        for p in percentiles:
            stats[f"p{p}"] = float(np.percentile(values, p))

        return stats

    async def terminate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Clean up and final metric recording."""
        if self.config.storage_type == "json":
            # Save aggregated metrics
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = os.path.join(
                self.config.metrics_dir,
                f"summary_{agent.name}_{timestamp}.json",
            )

            # Calculate summary for all metrics
            summary = {
                "agent": agent.name,
                "timestamp": timestamp,
                "metrics": {},
            }

            # Get all unique metric names from files
            all_metrics = self._load_metrics_from_files()

            for metric_name in all_metrics.keys():
                stats = self.get_statistics(metric_name)
                if stats:  # Only include metrics that have data
                    summary["metrics"][metric_name] = stats

            with open(summary_file, "w") as f:
                json.dump(summary, f, indent=2)

    def _record_metric(
        self, name: str, value: int | float | str, tags: dict[str, str] = None
    ) -> None:
        """Record a single metric point."""
        point = MetricPoint(
            timestamp=datetime.now(), value=value, tags=tags or {}
        )

        # Store metric
        if self.config.storage_type == "memory":
            self._metrics[name].append(point)

        elif self.config.storage_type == "prometheus":
            if name == "latency":
                self._prom_latency.labels(**tags).observe(value)
            elif name == "memory":
                self._prom_memory.labels(**tags).set(value)
            elif name == "tokens":
                self._prom_tokens.labels(**tags).inc(value)

        elif self.config.storage_type == "json":
            self._save_metric_to_file(name, point)

    def _save_metric_to_file(self, name: str, point: MetricPoint) -> None:
        """Save metric to JSON file."""
        filename = f"{name}_{point.timestamp.strftime('%Y%m')}.json"
        filepath = os.path.join(self.config.metrics_dir, filename)

        data = {
            "timestamp": point.timestamp.isoformat(),
            "value": point.value,
            "tags": point.tags,
        }

        # Append to file
        with open(filepath, "a") as f:
            f.write(json.dumps(data) + "\n")

    def _get_tokenizer(self, model: str):
        """Get the appropriate tokenizer for the model."""
        try:
            import tiktoken

            # Handle different model naming conventions
            if model.startswith("openai/"):
                model = model[7:]  # Strip 'openai/' prefix

            try:
                return tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for unknown models
                return tiktoken.get_encoding("cl100k_base")

        except ImportError:
            return None

    def _calculate_token_usage(self, text: str, model: str = "gpt-4") -> int:
        """Calculate token count using tiktoken when available."""
        tokenizer = self._get_tokenizer(model)

        if tokenizer:
            # Use tiktoken for accurate count
            return len(tokenizer.encode(text))
        else:
            # Fallback to estimation if tiktoken not available
            # Simple estimation - words / 0.75 for average tokens per word
            token_estimate = int(len(text.split()) / 0.75)

            # Log warning about estimation
            print(
                f"Warning: Using estimated token count. Install tiktoken for accurate counting."
            )

    def _should_alert(self, metric: str, value: float) -> bool:
        """Check if metric should trigger alert."""
        if metric == "latency" and self.config.alert_on_high_latency:
            return value * 1000 > self.config.latency_threshold_ms
        return False

    async def initialize(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Initialize metrics collection."""
        self._start_time = time.time()

        if self.config.collect_memory:
            self._start_memory = psutil.Process().memory_info().rss
            self._record_metric(
                "memory",
                self._start_memory,
                {"agent": agent.name, "phase": "start"},
            )

    def _calculate_cost(
        self, text: str, model: str, is_completion: bool = False
    ) -> tuple[int, float]:
        """Calculate both token count and cost."""
        # Get token count
        try:
            from litellm import cost_per_token

            token_count = self._calculate_token_usage(text, model)
            # Calculate total cost
            if is_completion:
                total_cost = token_count * cost_per_token(
                    model, completion_tokens=token_count
                )
            else:
                total_cost = token_count * cost_per_token(
                    model, prompt_tokens=token_count
                )

            return token_count, total_cost
        except Exception:
            token_count = 0
            total_cost = 0.0
            return token_count, total_cost

    async def pre_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Record pre-evaluation metrics."""
        if self.config.collect_token_usage:
            # Calculate input tokens and cost
            total_input_tokens = 0
            total_input_cost = 0.0

            for v in inputs.values():
                tokens, cost = self._calculate_cost(
                    str(v), agent.model, is_completion=False
                )
                total_input_tokens += tokens
                if isinstance(cost, float):
                    total_input_cost += cost
                else:
                    total_input_cost += cost[1]

            self._record_metric(
                "tokens",
                total_input_tokens,
                {"agent": agent.name, "type": "input"},
            )
            self._record_metric(
                "cost", total_input_cost, {"agent": agent.name, "type": "input"}
            )

        if self.config.collect_cpu:
            cpu_percent = psutil.Process().cpu_percent()
            self._record_metric(
                "cpu",
                cpu_percent,
                {"agent": agent.name, "phase": "pre_evaluate"},
            )

        return inputs

    async def post_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Record post-evaluation metrics."""
        if self.config.collect_timing and self._start_time:
            latency = time.time() - self._start_time
            self._record_metric("latency", latency, {"agent": agent.name})

            # Check for alerts
            if self._should_alert("latency", latency):
                # In practice, you'd want to integrate with a proper alerting system
                print(f"ALERT: High latency detected: {latency * 1000:.2f}ms")

        if self.config.collect_token_usage:
            # Calculate output tokens and cost
            total_output_tokens = 0
            total_output_cost = 0.0

            for v in result.values():
                tokens, cost = self._calculate_cost(
                    str(v), agent.model, is_completion=True
                )
                total_output_tokens += tokens
                if isinstance(cost, float):
                    total_output_cost += cost
                else:
                    total_output_cost += cost[1]

            self._record_metric(
                "tokens",
                total_output_tokens,
                {"agent": agent.name, "type": "output"},
            )
            self._record_metric(
                "cost",
                total_output_cost,
                {"agent": agent.name, "type": "output"},
            )

            # Record total cost for this operation
            self._record_metric(
                "total_cost",
                total_output_cost + total_output_cost,
                {"agent": agent.name},
            )

        if self.config.collect_memory and self._start_memory:
            current_memory = psutil.Process().memory_info().rss
            memory_diff = current_memory - self._start_memory
            self._record_metric(
                "memory", memory_diff, {"agent": agent.name, "phase": "end"}
            )

        return result

    async def on_error(
        self,
        agent: FlockAgent,
        error: Exception,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Record error metrics."""
        self._record_metric(
            "errors",
            1,
            {"agent": agent.name, "error_type": type(error).__name__},
        )
