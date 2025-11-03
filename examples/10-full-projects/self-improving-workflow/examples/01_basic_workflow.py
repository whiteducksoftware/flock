"""
Basic Self-Improving Workflow Example

Demonstrates a simple 3-phase workflow:
- Phase 1: Analysis
- Phase 2: Implementation  
- Phase 3: Validation

Agents can discover new work and spawn branches dynamically.
"""

import asyncio
from flock import Flock
from pydantic import BaseModel
from typing import Literal, Optional, List


# Define artifacts
class WorkDiscovery(BaseModel):
    """Work that needs to be done."""
    description: str
    phase: Literal["analysis", "implementation", "validation"]
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    done_definition: str
    discovered_by: str
    parent_work_id: Optional[str] = None
    tags: List[str] = []


class AnalysisResult(BaseModel):
    """Result from analysis phase."""
    plan: str
    approved: bool
    next_phase_work: List[WorkDiscovery] = []


class Implementation(BaseModel):
    """Result from implementation phase."""
    code_summary: str
    files_created: List[str]
    discovered_issues: List[WorkDiscovery] = []


class ValidationResult(BaseModel):
    """Result from validation phase."""
    passed: bool
    issues: List[str]
    optimizations_discovered: List[WorkDiscovery] = []


async def main():
    """Run basic self-improving workflow."""
    # Create flock
    flock = Flock("openai/gpt-4.1")
    
    # Phase 1: Analysis agent
    analyzer = (
        flock.agent("analyzer")
        .description("Analyzes work discoveries and creates implementation plans")
        .consumes(WorkDiscovery, where=lambda w: w.phase == "analysis")
        .publishes(AnalysisResult)
    )
    
    # Phase 2: Implementation agent
    implementer = (
        flock.agent("implementer")
        .description("Implements solutions based on analysis")
        .consumes(AnalysisResult, where=lambda a: a.approved)
        .publishes(Implementation)
    )
    
    # Phase 3: Validation agent (can discover new work!)
    validator = (
        flock.agent("validator")
        .description("Validates implementations and discovers optimizations")
        .consumes(Implementation)
        .publishes(ValidationResult, WorkDiscovery)  # Fan-out!
    )
    
    # Start workflow with initial discovery
    print("🚀 Starting Self-Improving Workflow...")
    print("📋 Initial work: Build authentication system")
    
    await flock.publish(WorkDiscovery(
        description="Build authentication system with OAuth and JWT",
        phase="analysis",
        priority="high",
        done_definition="Analysis complete with implementation plan for OAuth and JWT",
        discovered_by="user",
        tags=["auth", "security"]
    ))
    
    # Run workflow
    await flock.run_until_idle()
    
    print("\n✅ Workflow complete!")
    print("🔍 Check the blackboard for:")
    print("  - Analysis results")
    print("  - Implementation artifacts")
    print("  - Validation results")
    print("  - New work discoveries (if any optimizations found)")


if __name__ == "__main__":
    asyncio.run(main())



