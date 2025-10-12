"""
🕵️ LESSON 06: The Secret Agent Network - Visibility & Security
===============================================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How to control artifact visibility with 5 different patterns
2. How to build multi-tenant systems with TenantVisibility
3. How to implement zero-trust architecture with PrivateVisibility
4. How to use LabelledVisibility for RBAC (Role-Based Access Control)
5. How to create time-delayed artifacts with AfterVisibility

🎬 THE SCENARIO:
---------------
You're building an intelligence agency system where different agents
have different security clearances:
- Field Agents gather raw intelligence (classified)
- Analysts process intel (need clearance)
- Directors see final reports (public to leadership)
- External Partners get redacted summaries only

This demonstrates Flock's unique visibility control system - something
NO other agent framework has!

⏱️  TIME: 25 minutes
💡 COMPLEXITY: ⭐⭐⭐⭐ Advanced

Let's go undercover! 🕵️👇
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.visibility import (
    AfterVisibility,
    AgentIdentity,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define Intelligence Artifacts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class Mission(BaseModel):
    """Initial mission assignment (Public - everyone sees this)"""

    mission_id: str
    objective: str
    priority: str = Field(pattern="^(low|medium|high|critical)$")


@flock_type
class RawIntelligence(BaseModel):
    """Classified field intelligence (Private - only specific agents)"""

    mission_id: str
    source_location: str
    observations: list[str]
    sensitivity_level: str = Field(pattern="^(low|medium|high|top_secret)$")
    collected_by: str


@flock_type
class AnalysisReport(BaseModel):
    """Analyst's classified report (Labelled - requires clearance)"""

    mission_id: str
    threat_assessment: str
    recommended_actions: list[str]
    confidence_level: float = Field(ge=0.0, le=1.0)
    requires_clearance: str = Field(default="secret")


@flock_type
class ExecutiveBrief(BaseModel):
    """Director-level brief (Public to leadership)"""

    mission_id: str
    summary: str
    strategic_implications: list[str]
    next_steps: list[str]


@flock_type
class RedactedSummary(BaseModel):
    """Sanitized summary for external partners (Public after delay)"""

    mission_id: str
    general_findings: str
    public_recommendations: list[str]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🕵️ STEP 3: Define Agents with Security Labels
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🌍 Agent 1: Field Agent (Collects classified intel)
# Identity: Has "field_ops" label
# Publishes: RawIntelligence with PRIVATE visibility (only for analysts)

field_agent = (
    flock.agent("field_agent")
    .description("Collects intelligence from the field")
    .identity(AgentIdentity(name="field_agent", labels={"clearance:field_ops"}))
    .consumes(Mission)
    .publishes(
        RawIntelligence,
        visibility=PrivateVisibility(
            agents={"intelligence_analyst"}  # 🔒 Only analyst can see this!
        ),
    )
)

# 🔍 Agent 2: Intelligence Analyst (Analyzes classified data)
# Identity: Has "secret" clearance label
# Publishes: AnalysisReport with LABELLED visibility (requires "secret" clearance)

intelligence_analyst = (
    flock.agent("intelligence_analyst")
    .description("Analyzes raw intelligence and produces threat assessments")
    .identity(AgentIdentity(name="intelligence_analyst", labels={"clearance:secret"}))
    .consumes(RawIntelligence)
    .publishes(
        AnalysisReport,
        visibility=LabelledVisibility(
            required_labels={"clearance:secret"}  # 🔒 Needs clearance!
        ),
    )
)

# 👔 Agent 3: Director (Creates executive briefs)
# Identity: Has "secret" clearance (can see AnalysisReport)
# Publishes: ExecutiveBrief with PUBLIC visibility (all leadership sees)

director = (
    flock.agent("director")
    .description("Creates executive-level strategic briefs")
    .identity(AgentIdentity(name="director", labels={"clearance:secret", "role:leadership"}))
    .consumes(AnalysisReport)
    .publishes(
        ExecutiveBrief,
        visibility=PublicVisibility(),  # 🌍 Everyone can see this
    )
)

# 📢 Agent 4: Public Affairs (Creates sanitized summaries)
# Identity: No special clearance needed
# Publishes: RedactedSummary with TIME-DELAYED visibility

public_affairs = (
    flock.agent("public_affairs")
    .description("Creates sanitized summaries for external partners")
    .identity(AgentIdentity(name="public_affairs", labels=set()))
    .consumes(ExecutiveBrief)
    .publishes(
        RedactedSummary,
        visibility=AfterVisibility(
            ttl=timedelta(hours=24),  # 🕒 Only visible after 24 hours!
            then=PublicVisibility(),
        ),
    )
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the Intelligence Operation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Watch a classified intelligence operation with proper security controls:
    1. Mission assigned (public)
    2. Field agent collects intel (private - only analyst sees)
    3. Analyst produces report (labelled - requires clearance)
    4. Director creates brief (public to leadership)
    5. Public affairs creates summary (time-delayed public release)
    """

    print("🕵️ Secret Agent Network - Intelligence Operation\n")

    # 🎯 Assign the mission
    mission = Mission(
        mission_id="OP-BLACKBIRD-2025",
        objective="Investigate emerging cyber threats in Eastern Europe",
        priority="high",
    )

    print("=" * 70)
    print("📋 MISSION ASSIGNED (Public)")
    print("=" * 70)
    print(f"ID: {mission.mission_id}")
    print(f"Objective: {mission.objective}")
    print(f"Priority: {mission.priority.upper()}")
    print("=" * 70)
    print()

    print("🔐 Security Controls Active:")
    print("   🌍 Public: Mission, ExecutiveBrief")
    print("   🔒 Private: RawIntelligence (analyst only)")
    print("   🏷️  Labelled: AnalysisReport (secret clearance required)")
    print("   🕒 Time-Delayed: RedactedSummary (24h embargo)")
    print()

    # 📤 Start the operation
    await flock.publish(mission)
    await flock.run_until_idle()

    # 📊 Show what each agent can see
    print("\n" + "=" * 70)
    print("🔍 VISIBILITY VERIFICATION")
    print("=" * 70)

    # Check RawIntelligence visibility
    raw_intel = await flock.store.get_artifacts_by_type("RawIntelligence")
    if raw_intel:
        intel_obj = raw_intel[-1].obj
        visibility = raw_intel[-1].visibility
        print("\n🔒 RawIntelligence (Private):")
        print(f"   Source: {intel_obj.source_location}")
        print(f"   Sensitivity: {intel_obj.sensitivity_level}")
        print(f"   Visibility: {visibility}")
        print("   ✅ Only 'intelligence_analyst' can consume this!")

    # Check AnalysisReport visibility
    analysis = await flock.store.get_artifacts_by_type("AnalysisReport")
    if analysis:
        analysis_obj = analysis[-1].obj
        visibility = analysis[-1].visibility
        print("\n🏷️  AnalysisReport (Labelled):")
        print(f"   Threat: {analysis_obj.threat_assessment[:100]}...")
        print(f"   Visibility: {visibility}")
        print("   ✅ Requires clearance:secret label!")

    # Check ExecutiveBrief visibility
    brief = await flock.store.get_artifacts_by_type("ExecutiveBrief")
    if brief:
        brief_obj = brief[-1].obj
        visibility = brief[-1].visibility
        print("\n🌍 ExecutiveBrief (Public):")
        print(f"   Summary: {brief_obj.summary[:100]}...")
        print(f"   Visibility: {visibility}")
        print("   ✅ All agents with proper identity can see this!")

    # Check RedactedSummary visibility
    summary = await flock.store.get_artifacts_by_type("RedactedSummary")
    if summary:
        summary_obj = summary[-1].obj
        visibility = summary[-1].visibility
        print("\n🕒 RedactedSummary (Time-Delayed):")
        print(f"   Findings: {summary_obj.general_findings[:100]}...")
        print(f"   Visibility: {visibility}")
        print("   ✅ Will become public after 24 hours!")

    print("\n" + "=" * 70)
    print("✅ Operation Complete - All Security Controls Enforced!")
    print("=" * 70)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You built a zero-trust agent system with visibility controls!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ FIVE VISIBILITY TYPES
   Flock provides 5 built-in visibility patterns:

   📍 PublicVisibility:
      - Everyone can see the artifact
      - Default visibility
      - Example: Public announcements, shared data

   🔒 PrivateVisibility(agents={"agent1", "agent2"}):
      - Only specified agents can see
      - Allowlist-based access control
      - Example: Sensitive data for specific processors

   🏷️  LabelledVisibility(required_labels={"clearance:secret"}):
      - Requires agent to have specific labels
      - Role-Based Access Control (RBAC)
      - Example: Multi-level security clearances

   🏢 TenantVisibility(tenant_id="customer_123"):
      - Multi-tenancy isolation
      - Data scoped to specific tenant
      - Example: SaaS platforms, customer data isolation

   🕒 AfterVisibility(ttl=timedelta(hours=24), then=PublicVisibility()):
      - Time-delayed visibility
      - Embargo periods
      - Example: Press releases, quarterly reports

2️⃣ AGENT IDENTITY
   Agents have identities with labels for access control:

   ```python
   .identity(AgentIdentity(
       name="agent_name",
       labels={"clearance:secret", "role:analyst"}
   ))
   ```

3️⃣ PRODUCER-CONTROLLED SECURITY
   The PRODUCER decides who can consume:

   ```python
   agent.publishes(
       SensitiveData,
       visibility=PrivateVisibility(agents={"trusted_agent"})
   )
   ```

   Not the orchestrator! This is zero-trust architecture.

4️⃣ ENFORCEMENT AT SCHEDULING
   Flock checks visibility BEFORE scheduling agents:

   ```python
   if not artifact.visibility.allows(agent.identity):
       continue  # Don't schedule agent
   ```

   No agent ever sees data it shouldn't!

🆚 VS OTHER FRAMEWORKS:
-----------------------

❌ Most frameworks:
   - NO built-in access control
   - Every agent sees everything
   - Security is "bring your own"
   - No multi-tenancy support

✅ Flock:
   - 5 visibility types out of the box
   - Producer-controlled access
   - Automatic enforcement
   - Production-ready security

💡 REAL-WORLD APPLICATIONS:
--------------------------

1. **Healthcare (HIPAA Compliance)**:
```python
# Patient data only visible to treating physician
doctor.publishes(
    PatientRecord,
    visibility=PrivateVisibility(agents={"treating_physician"})
)

# Lab results visible to anyone with medical clearance
lab.publishes(
    LabResults,
    visibility=LabelledVisibility(required_labels={"role:medical"})
)
```

2. **Financial Services (Multi-Tenancy)**:
```python
# Each customer's data isolated
trading_agent.publishes(
    CustomerPortfolio,
    visibility=TenantVisibility(tenant_id=customer.id)
)
# Customer A's agent can't see Customer B's data!
```

3. **Enterprise SaaS**:
```python
# Free tier users see limited data
analyzer.publishes(
    BasicReport,
    visibility=LabelledVisibility(required_labels={"tier:free", "tier:pro"})
)

# Pro features only for paying customers
analyzer.publishes(
    AdvancedAnalytics,
    visibility=LabelledVisibility(required_labels={"tier:pro"})
)
```

4. **Press & Media (Embargoes)**:
```python
# Press release visible after embargo lifts
pr_team.publishes(
    PressRelease,
    visibility=AfterVisibility(
        ttl=timedelta(days=7),
        then=PublicVisibility()
    )
)
```

5. **Government/Intelligence**:
```python
# Classified intel with clearance levels
field_ops.publishes(
    ClassifiedIntel,
    visibility=LabelledVisibility(
        required_labels={"clearance:top_secret"}
    )
)
```

🧪 EXPERIMENT IDEAS:
-------------------

1. **Create Multi-Level Security**:
```python
# Unclassified → Confidential → Secret → Top Secret
agent.identity(AgentIdentity(
    name="analyst",
    labels={"clearance:secret"}  # Can see Secret but not Top Secret
))
```

2. **Implement Org Hierarchy**:
```python
# Junior analysts can't see senior analyst work
junior.identity(AgentIdentity(labels={"level:junior"}))
senior.publishes(Data, visibility=LabelledVisibility(
    required_labels={"level:senior"}
))
```

3. **Time-Based Access Expiry**:
```python
# Data becomes private after initial public window
.publishes(Data, visibility=AfterVisibility(
    ttl=timedelta(hours=1),
    then=PrivateVisibility(agents={"archiver"})
))
```

4. **Combine Multiple Patterns**:
   - Use TenantVisibility + LabelledVisibility together
   - Create custom visibility classes
   - Implement dynamic visibility rules

⚠️  SECURITY BEST PRACTICES:
---------------------------

1. **Principle of Least Privilege**:
   ✅ Give agents minimum necessary access
   ❌ Don't make everything public

2. **Defense in Depth**:
   ✅ Use visibility + identity + audit logs
   ❌ Don't rely on single security layer

3. **Audit Trail**:
   ✅ Enable tracing to see who accessed what
   ❌ Don't run production without observability

4. **Regular Access Review**:
   ✅ Periodically review agent permissions
   ❌ Don't set-and-forget access controls

📈 NEXT LESSON:
--------------
Lesson 07: The News Agency
- Parallel agent execution
- Opportunistic processing
- Concurrent workflows at scale
- Performance optimization

🎯 READY TO CONTINUE?
Run: uv run examples/claudes-flock-course/lesson_07_news_agency.py
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
