"""
Lesson 11: The Performance Monitor

CONCEPTS: Advanced Orchestrator Components
- Global state tracking across all agents
- Performance metrics and monitoring
- Resource utilization tracking
- Real-time alerting and reporting
- Production-grade observability patterns

SCENARIO:
You're managing an AI service platform where multiple agents handle different types
of requests. You need to monitor performance, track resource usage, and alert when
things go wrong—all without coupling monitoring logic to individual agents.

ORCHESTRATOR COMPONENTS provide:
- Cross-cutting concerns (logging, metrics, monitoring)
- Global coordination without agent coupling
- Lifecycle hooks for every stage of execution
- Centralized state management

This example shows how to build a production-ready monitoring system.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import OrchestratorComponent
from flock.runtime import Context


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================


@flock_type(name="ServiceRequest")
class ServiceRequest(BaseModel):
    request_id: str
    service_type: str  # "analysis", "translation", "summarization"
    priority: str  # "low", "normal", "high", "critical"
    payload_size_kb: int = Field(description="Request size in KB")


@flock_type(name="ServiceResponse")
class ServiceResponse(BaseModel):
    request_id: str
    status: str  # "success", "failed"
    processing_time_ms: float
    tokens_used: int


@flock_type(name="PerformanceAlert")
class PerformanceAlert(BaseModel):
    alert_type: str
    severity: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# ORCHESTRATOR COMPONENT - Production Monitoring
# ============================================================================


class PerformanceMonitorComponent(OrchestratorComponent):
    """
    Monitors the entire Flock orchestration lifecycle.

    This component demonstrates:
    - Request tracking and timing
    - Resource usage monitoring
    - SLA violation detection
    - Real-time alerting
    - Performance reporting
    """

    # Global counters
    total_requests: int = Field(default=0)
    total_responses: int = Field(default=0)
    failed_requests: int = Field(default=0)

    # Performance tracking
    request_times: dict[str, datetime] = Field(default_factory=dict)
    total_processing_ms: float = Field(default=0.0)
    total_tokens: int = Field(default=0)

    # Priority tracking
    priority_counts: dict[str, int] = Field(default_factory=dict)
    high_priority_queue: int = Field(default=0)

    # SLA thresholds (in milliseconds)
    SLA_THRESHOLDS = {
        "critical": 500,  # 500ms for critical
        "high": 1000,  # 1s for high priority
        "normal": 3000,  # 3s for normal
        "low": 5000,  # 5s for low priority
    }

    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        """
        Track incoming requests and start timing.

        This hook fires BEFORE an artifact is published to the blackboard.
        Perfect for: initialization, validation, request counting.
        """
        if artifact.type_name == "ServiceRequest":
            request_id = artifact.payload.get("request_id")
            priority = artifact.payload.get("priority", "normal")
            service_type = artifact.payload.get("service_type")
            payload_size = artifact.payload.get("payload_size_kb", 0)

            # Start timing this request
            self.request_times[request_id] = datetime.now()
            self.total_requests += 1

            # Track priorities
            self.priority_counts[priority] = self.priority_counts.get(priority, 0) + 1
            if priority in ("high", "critical"):
                self.high_priority_queue += 1

            print(f"\n📥 [{priority.upper():8}] Request {request_id}")
            print(f"   Service: {service_type}, Size: {payload_size}KB")
            print(f"   Queue depth: {self.high_priority_queue} high-priority")

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        """
        Track responses and detect SLA violations.

        This hook fires AFTER an artifact is published to the blackboard.
        Perfect for: metrics collection, alerting, completion tracking.
        """
        if artifact.type_name == "ServiceResponse":
            request_id = artifact.payload.get("request_id")
            status = artifact.payload.get("status")
            tokens = artifact.payload.get("tokens_used", 0)

            # Calculate actual processing time
            if request_id in self.request_times:
                start_time = self.request_times[request_id]
                actual_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                del self.request_times[request_id]
            else:
                actual_time_ms = 0

            # Update metrics
            self.total_responses += 1
            self.total_processing_ms += actual_time_ms
            self.total_tokens += tokens

            if status == "failed":
                self.failed_requests += 1

            # Check SLA compliance
            # For demo purposes, we'll assume normal priority
            sla_threshold = self.SLA_THRESHOLDS.get("normal", 3000)

            if actual_time_ms > sla_threshold:
                violation_pct = ((actual_time_ms - sla_threshold) / sla_threshold) * 100
                print(f"⚠️  SLA VIOLATION! Request {request_id}")
                print(f"   Expected: <{sla_threshold}ms, Actual: {actual_time_ms:.0f}ms")
                print(f"   Overage: +{violation_pct:.1f}%")
            else:
                print(f"✅ Request {request_id} completed in {actual_time_ms:.0f}ms")

            print(f"   Tokens used: {tokens:,}")

    async def on_cycle_complete(self, ctx: Context) -> None:
        """
        Report overall system health after each processing cycle.

        This hook fires after all agents finish processing a batch.
        Perfect for: aggregation, reporting, health checks.
        """
        if self.total_responses == 0:
            return

        print("\n" + "=" * 70)
        print("📊 PERFORMANCE DASHBOARD")
        print("=" * 70)

        # Request statistics
        success_rate = (
            ((self.total_responses - self.failed_requests) / self.total_responses) * 100
            if self.total_responses > 0
            else 0
        )

        print(f"\n📈 Request Statistics:")
        print(f"   Total requests: {self.total_requests}")
        print(f"   Completed: {self.total_responses}")
        print(f"   Failed: {self.failed_requests}")
        print(f"   Success rate: {success_rate:.1f}%")
        print(f"   In-flight: {len(self.request_times)}")

        # Performance metrics
        avg_time = (
            self.total_processing_ms / self.total_responses
            if self.total_responses > 0
            else 0
        )
        print(f"\n⚡ Performance Metrics:")
        print(f"   Avg processing time: {avg_time:.0f}ms")
        print(f"   Total tokens consumed: {self.total_tokens:,}")
        print(f"   Avg tokens/request: {self.total_tokens / self.total_responses:.0f}")

        # Priority breakdown
        print(f"\n🎯 Priority Distribution:")
        for priority in ["critical", "high", "normal", "low"]:
            count = self.priority_counts.get(priority, 0)
            if count > 0:
                pct = (count / self.total_requests) * 100
                print(f"   {priority.capitalize():8}: {count:3} ({pct:5.1f}%)")

        # Health indicators
        print(f"\n🏥 System Health:")
        if success_rate >= 99:
            health = "🟢 EXCELLENT"
        elif success_rate >= 95:
            health = "🟡 GOOD"
        elif success_rate >= 90:
            health = "🟠 DEGRADED"
        else:
            health = "🔴 CRITICAL"

        print(f"   Overall: {health}")
        print(f"   High-priority queue: {self.high_priority_queue} pending")

        print("=" * 70 + "\n")


# ============================================================================
# MAIN DEMO
# ============================================================================


async def main() -> None:
    flock = Flock()

    # Install the performance monitor
    flock.with_components(PerformanceMonitorComponent())

    # Service agents
    (
        flock.agent("analysis_service")
        .description("Handles analysis requests")
        .consumes(ServiceRequest, where=lambda req: req.service_type == "analysis")
        .publishes(ServiceResponse)
        .system_prompt(
            "You analyze data. Reply with a ServiceResponse indicating success "
            "and simulated token usage (100-500 tokens)."
        )
    )

    (
        flock.agent("translation_service")
        .description("Handles translation requests")
        .consumes(ServiceRequest, where=lambda req: req.service_type == "translation")
        .publishes(ServiceResponse)
        .system_prompt(
            "You translate text. Reply with a ServiceResponse indicating success "
            "and simulated token usage (200-600 tokens)."
        )
    )

    (
        flock.agent("summarization_service")
        .description("Handles summarization requests")
        .consumes(ServiceRequest, where=lambda req: req.service_type == "summarization")
        .publishes(ServiceResponse)
        .system_prompt(
            "You summarize content. Reply with a ServiceResponse indicating success "
            "and simulated token usage (150-400 tokens)."
        )
    )

    (
        flock.agent("alert_generator")
        .description("Generates alerts for anomalies")
        .consumes(ServiceResponse, where=lambda resp: resp.status == "failed")
        .publishes(PerformanceAlert)
        .system_prompt("Create detailed alerts for failed requests.")
    )

    print("🚀 AI Service Platform - Performance Monitoring Demo")
    print("=" * 70)

    # Simulate a burst of requests
    requests = [
        ServiceRequest(
            request_id="req-001",
            service_type="analysis",
            priority="critical",
            payload_size_kb=45,
        ),
        ServiceRequest(
            request_id="req-002",
            service_type="translation",
            priority="high",
            payload_size_kb=120,
        ),
        ServiceRequest(
            request_id="req-003",
            service_type="summarization",
            priority="normal",
            payload_size_kb=80,
        ),
        ServiceRequest(
            request_id="req-004",
            service_type="analysis",
            priority="low",
            payload_size_kb=200,
        ),
        ServiceRequest(
            request_id="req-005",
            service_type="translation",
            priority="high",
            payload_size_kb=95,
        ),
        ServiceRequest(
            request_id="req-006",
            service_type="summarization",
            priority="critical",
            payload_size_kb=150,
        ),
    ]

    # Publish all requests
    for req in requests:
        await flock.publish(req)

    # Process everything
    await flock.run_until_idle()

    print("\n🎓 What Just Happened?")
    print("=" * 70)
    print("The PerformanceMonitorComponent tracked:")
    print("✅ Every request arrival (on_pre_publish)")
    print("✅ Every response completion (on_post_publish)")
    print("✅ SLA violations and performance metrics")
    print("✅ System health across all services (on_cycle_complete)")
    print()
    print("🔑 Key Insight:")
    print("Orchestrator components handle cross-cutting concerns WITHOUT")
    print("coupling monitoring logic to individual service agents!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
