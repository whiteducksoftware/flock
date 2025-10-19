
import asyncio
from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from flock.registry import flock_type
from pydantic import (
    BaseModel,
    Field,
    EmailStr,
    HttpUrl,
    PastDatetime,
    PositiveInt,
    NonNegativeInt,
    field_validator,
    model_validator,
    ConfigDict,
)
from flock import Flock



# -------------------------------
# Basic Types
# -------------------------------



# -------------------------------
# Contacts & Stakeholders
# -------------------------------
@flock_type
class Contact(BaseModel):
    name: str = Field(..., max_length=200, description="Full name.")
    role: str = Field(..., max_length=120, description="Role/title in org.")
    email: Optional[EmailStr] = Field(None, description="Work email.")
    slack: Optional[str] = Field(None, description="Slack handle or channel.")
    phone: Optional[str] = Field(None, description="E.164 recommended if provided.")
    timezone: Optional[str] = Field(None, description="IANA tz database name (e.g., Europe/Berlin).")

@flock_type
class Stakeholder(BaseModel):
    contact: Contact = Field(..., description="Stakeholder contact details.")
    raci: str = Field(..., description="RACI role for this PRD.")
    responsibilities: List[str] = Field(
        default_factory=list,
        description="Scope/responsibilities for this stakeholder in context of the PRD.",
    )


# -------------------------------
# Business goals, metrics, risks
# -------------------------------

class MetricComparator(str, Enum):
    gte = ">="
    lte = "<="
    eq = "=="
    delta_abs_gte = "delta_abs>="
    delta_pct_gte = "delta_pct>="

@flock_type
class Metric(BaseModel):
    name: str = Field(..., max_length=120, description="Metric name (e.g., SignupConversion).")
    definition: str = Field(..., description="Definition & exact computation.")
    source: str = Field(..., description="Where it is measured (e.g., Amplitude, DBT model).")
    unit: Optional[str] = Field(None, description="Unit for target (e.g., %, ms, count).")
    comparator: MetricComparator = Field(..., description="How targets are compared.")
    target: float = Field(..., description="Target value aligned with comparator.")
    baseline: Optional[float] = Field(None, description="Current baseline for deltas.")
    guardrails: List[str] = Field(
        default_factory=list,
        description="Guardrail metrics that must not regress.",
    )

@flock_type
class BusinessGoal(BaseModel):
    id: str = Field(pattern=r"^G-[A-Z0-9_-]{2,40}$", description="Goal ID, e.g., G-ACQ-01.")
    description: str = Field(..., description="What outcome the business needs.")
    metrics: List[Metric] = Field(..., min_length=1, description="KPIs tied to this goal.")
    priority: str = Field(..., description="Relative business priority.")

@flock_type
class Risk(BaseModel):
    id: str = Field(pattern=r"^R-[A-Z0-9_-]{2,40}$", description="Risk ID, e.g., R-SEC-01.")
    description: str = Field(..., description="What could go wrong.")
    likelihood: str = Field(..., description="Probability category.")
    impact: str = Field(..., description="Impact severity category.")
    mitigation: str = Field(..., description="Mitigation/contingency plan.")


# -------------------------------
# Personas, use cases, stories
# -------------------------------
@flock_type
class Persona(BaseModel):
    name: str = Field(..., max_length=80, description="Persona label (unique within PRD).")
    archetype: str = Field(..., description="Short archetype: 'Ops Engineer', 'SMB Owner'.")
    goals: List[str] = Field(..., min_length=1, description="What success looks like for them.")
    pains: List[str] = Field(..., min_length=1, description="Key pain points to address.")
    environment: Optional[str] = Field(
        None, description="Operating environment: device, constraints, compliance, etc."
    )

@flock_type
class AcceptanceCriterion(BaseModel):
    given: str = Field(..., description="Preconditions.")
    when: str = Field(..., description="Action or trigger.")
    then: str = Field(..., description="Expected outcome (testable).")

@flock_type
class UseCase(BaseModel):
    id: str = Field(pattern=r"^UC-[A-Z0-9_-]{2,40}$", description="Use case ID, e.g., UC-LOGIN-01.")
    title: str = Field(..., description="Short label.")
    primary_persona: str = Field(..., description="Must match a Persona.name in this PRD.")
    preconditions: List[str] = Field(default_factory=list, description="What must be true before.")
    triggers: List[str] = Field(..., min_length=1, description="Events that start the flow.")
    main_flow: List[str] = Field(..., min_length=1, description="Numbered steps in the happy path.")
    alternative_flows: List[str] = Field(
        default_factory=list, description="Edges, exceptions, error handling."
    )
    postconditions: List[str] = Field(
        default_factory=list, description="End state guarantees after completion."
    )

@flock_type
class UserStory(BaseModel):
    id: str = Field(pattern=r"^ST-[A-Z0-9_-]{2,40}$", description="Story ID, e.g., ST-PROF-02.")
    as_a: str = Field(..., description="Persona or role.")
    i_want: str = Field(..., description="Capability desired.")
    so_that: str = Field(..., description="Business/user value.")
    priority: str = Field(..., description="Delivery priority.")
    acceptance: List[AcceptanceCriterion] = Field(
        ..., min_length=1, description="Testable criteria (Given/When/Then)."
    )
    story_points: Optional[PositiveInt] = Field(None, description="Optional effort estimate.")


# -------------------------------
# Requirements
# -------------------------------
@flock_type
class RequirementBase(BaseModel):
    id: str = Field(pattern=r"^REQ-[A-Z0-9_-]{2,40}$", description="Requirement ID, e.g., REQ-AUTH-01.")
    title: str = Field(..., description="Short label.")
    description: str = Field(..., description="What/why at a high level.")
    rationale: Optional[str] = Field(None, description="Why it matters; link to goals/metrics.")
    priority: str = Field(..., description="Delivery priority.")
    owner: Optional[str] = Field(None, description="Directly responsible individual (DRI).")
    depends_on: List[str] = Field(
        default_factory=list, description="Other IDs (REQ-*, UC-*, ST-*) that must be delivered first."
    )
    acceptance: List[AcceptanceCriterion] = Field(
        ..., min_length=1, description="Testable acceptance criteria."
    )

@flock_type
class FunctionalRequirement(RequirementBase):
    affected_use_cases: List[str] = Field(
        default_factory=list,
        description="UseCase IDs (UC-*) this requirement impacts.",
    )
    data_classification: str = Field(
        "internal",
        description="Highest data classification touched by this requirement.",
    )

@flock_type
class SLO(BaseModel):
    objective: str = Field(..., description="E.g., 'P95 latency <= 250ms'.")
    metric: Metric = Field(..., description="Metric this SLO binds to.")
    error_budget_pct: float = Field(
        1.0, description="Allowed error budget in percent for the period."
    )
    measurement_window_days: PositiveInt = Field(
        28, description="Rolling window for evaluation."
    )

@flock_type
class NonFunctionalRequirement(BaseModel):
    id: str = Field(pattern=r"^NFR-[A-Z0-9_-]{2,40}$", description="NFR ID, e.g., NFR-PERF-01.")
    category: str = Field(..., description="Type/category of NFR.")
    description: str = Field(..., description="Statement of the constraint/quality.")
    acceptance: List[AcceptanceCriterion] = Field(
        ..., min_length=1, description="How we verify the NFR (benchmarks, audits, tests)."
    )
    slos: List[SLO] = Field(default_factory=list, description="Optional SLOs tying to metrics.")
    depends_on: List[str] = Field(
        default_factory=list, description="Other IDs (REQ-*, NFR-*, UC-*) that must exist/done."
    )


# -------------------------------
# Security, privacy, compliance
# -------------------------------
@flock_type
class DataPrivacyRequirement(BaseModel):
    data_classification: str = Field(..., description="Classification for processed data.")
    pii_types: List[str] = Field(
        default_factory=list,
        description="PII categories handled (e.g., email, phone, government_id).",
    )
    data_retention_days: Optional[NonNegativeInt] = Field(
        None, description="Retention policy; None = unlimited/not applicable."
    )
    dpa_required: bool = Field(
        False, description="Is a Data Processing Addendum required with vendors?"
    )
    compliance_frameworks: List[str] = Field(
        default_factory=list,
        description="Frameworks/regimes: GDPR, HIPAA, SOC2, ISO27001, PCI DSS, etc.",
    )
    encryption_at_rest: bool = Field(True, description="Encrypt data at rest.")
    encryption_in_transit: bool = Field(True, description="Encrypt data in transit.")
    access_controls: List[str] = Field(
        default_factory=list,
        description="RBAC/ABAC/attribute scopes required.",
    )
    audit_logging_required: bool = Field(
        True, description="Whether full audit logs must be captured."
    )


# -------------------------------
# Dependencies & externalities
# -------------------------------
@flock_type
class Dependency(BaseModel):
    id: str = Field(pattern=r"^DEP-[A-Z0-9_-]{2,40}$", description="Dependency ID, e.g., DEP-SSO-OKTA.")
    name: str = Field(..., description="Human-readable name.")
    type: str = Field(..., description="Type of dependency.")
    owner_team: Optional[str] = Field(None, description="Owning team or vendor.")
    url: Optional[HttpUrl] = Field(None, description="Docs, runbooks, vendor page, etc.")
    is_blocking: bool = Field(
        False, description="True if this must be available before release."
    )
    notes: Optional[str] = Field(None, description="Constraints, rate limits, SLAs, licensing.")


# -------------------------------
# API surface (optional section)
# -------------------------------
@flock_type
class APIParam(BaseModel):
    name: str = Field(..., description="Parameter name.")
    type: str = Field(..., description="Logical type (e.g., string, int, uuid, enum Foo).")
    required: bool = Field(..., description="If omitted, server behavior must be defined.")
    description: Optional[str] = Field(None, description="What it does.")

@flock_type
class APIResponse(BaseModel):
    http_status: int = Field(ge=100, le=599, description="HTTP status code.")
    schema_ref: Optional[str] = Field(
        None, description="Reference to JSON schema / Pydantic model / OpenAPI $ref."
    )
    description: Optional[str] = Field(None, description="Human-readable semantics.")

@flock_type
class APIEndpoint(BaseModel):
    method: str = Field(..., description="HTTP method.")
    path: str = Field(..., description="Route path, e.g., /v1/users/{id}.")
    auth_required: bool = Field(..., description="Whether authentication is required.")
    scope: Optional[str] = Field(None, description="Auth scope (e.g., 'users:read').")
    request_params: List[APIParam] = Field(default_factory=list, description="Query/path params.")
    request_body_schema_ref: Optional[str] = Field(
        None, description="Ref to JSON schema / model for request body."
    )
    responses: List[APIResponse] = Field(
        ..., min_length=1, description="Expected responses."
    )
    rate_limit_per_min: Optional[PositiveInt] = Field(
        None, description="Per-minute rate limit if applicable."
    )


# -------------------------------
# UX, content, i18n
# -------------------------------
@flock_type
class ContentRequirement(BaseModel):

    id: str = Field(pattern=r"^CNT-[A-Z0-9_-]{2,40}$", description="Content ID.")
    location: str = Field(..., description="Where it appears (screen/flow).")
    text: str = Field(..., description="Exact copy or constraints.")
    i18n: bool = Field(False, description="Needs localization.")
    accessibility_notes: Optional[str] = Field(None, description="ARIA, semantics, contrast, etc.")

@flock_type
class UXRequirement(BaseModel):
    id: str = Field(pattern=r"^UX-[A-Z0-9_-]{2,40}$", description="UX ID.")
    description: str = Field(..., description="UX constraint or guideline.")
    acceptance: List[AcceptanceCriterion] = Field(
        default_factory=list,
        description="Optional testable acceptance for UX behaviors.",
    )


# -------------------------------
# Milestones, rollout, SLAs
# -------------------------------
@flock_type
class Milestone(BaseModel):
    id: str = Field(pattern=r"^MS-[A-Z0-9_-]{2,40}$", description="Milestone ID.")
    title: str = Field(..., description="Short label.")
    target_date: date = Field(..., description="Target delivery date.")
    scope_ids: List[str] = Field(
        default_factory=list,
        description="IDs (REQ/NFR/UC/ST/etc.) planned for this milestone.",
    )

@flock_type
class RolloutPlan(BaseModel):
    strategy: str = Field(..., description="Release strategy.")
    feature_flag_key: Optional[str] = Field(
        None, description="Feature flag identifier if applicable."
    )
    cohorts: List[str] = Field(
        default_factory=list,
        description="Cohorts/segments for phased/canary rollout.",
    )
    guardrails: List[str] = Field(
        default_factory=list,
        description="Kill-switch criteria, rollback triggers.",
    )
    monitoring_dashboards: List[HttpUrl] = Field(
        default_factory=list, description="Links to dashboards/alerts."
    )

@flock_type
class SupportSLA(BaseModel):
    severity: int = Field(ge=1, le=4, description="1=Critical, 4=Low.")
    response_time_minutes: PositiveInt = Field(..., description="Time to first response.")
    resolution_time_hours: PositiveInt = Field(..., description="Time to resolution target.")
    notes: Optional[str] = Field(None, description="Scope/details/exclusions.")


# -------------------------------
# Decision log, glossary, attachments
# -------------------------------
@flock_type
class DecisionLogEntry(BaseModel):
    title: str = Field(..., description="Decision title.")
    context: str = Field(..., description="Context and forces.")
    decision: str = Field(..., description="What was decided.")
    consequences: str = Field(..., description="Tradeoffs and consequences.")
    date: str = Field(default_factory=lambda: datetime.utcnow().date().isoformat(), description="Date of decision.")
    link: Optional[HttpUrl] = Field(None, description="Link to full ADR if external.")

@flock_type
class GlossaryTerm(BaseModel):
    term: str = Field(..., description="Term/acronym.")
    definition: str = Field(..., description="Concise definition.")
    link: Optional[HttpUrl] = Field(None, description="Optional reference link.")

@flock_type
class Attachment(BaseModel):
    name: str = Field(..., description="File or asset name.")
    url: HttpUrl = Field(..., description="Location of the attachment.")
    description: Optional[str] = Field(None, description="What it contains and why it matters.")


# -------------------------------
# Metadata & top-level PRD
# -------------------------------
@flock_type
class ProductMetadata(BaseModel):
    product_name: str = Field(..., description="Product or feature name.")
    doc_version: str = Field(..., description="Version of this PRD document.")
    status: str = Field("draft", description="Lifecycle status.")
    owners: List[Contact] = Field(..., min_length=1, description="Product owner(s) / DRI(s).")
    authors: List[Contact] = Field(default_factory=list, description="Contributors/authors.")
    stakeholders: List[Stakeholder] = Field(
        default_factory=list, description="Stakeholders with RACI assignments."
    )
    created_at: PastDatetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp (UTC)."
    )
    last_updated_at: PastDatetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp (UTC)."
    )
    target_release: Optional[date] = Field(None, description="Intended release date (if any).")

@flock_type
class Backlog(BaseModel):
    use_cases: List[UseCase] = Field(
        default_factory=list, description="Key flows captured as use cases."
    )
    user_stories: List[UserStory] = Field(
        default_factory=list, description="Story backlog."
    )

@flock_type
class Requirements(BaseModel):
    functional_requirements: List[FunctionalRequirement] = Field(
        default_factory=list, description="Functional requirements."
    )
    non_functional_requirements: List[NonFunctionalRequirement] = Field(
        default_factory=list, description="Quality attribute requirements."
    )

@flock_type
class PresentationLayer(BaseModel):
    ux_requirements: List[UXRequirement] = Field(
        default_factory=list, description="UX constraints and behaviors."
    )
    content_requirements: List[ContentRequirement] = Field(
        default_factory=list, description="Copy and content constraints."
    )
    api_endpoints: List[APIEndpoint] = Field(
        default_factory=list, description="Planned API endpoints."
    )


@flock_type
class Risks(BaseModel):
    risks: List[Risk] = Field(default_factory=list, description="Tracked risks with mitigations.")
    open_questions: List[str] = Field(
        default_factory=list, description="Unresolved questions that block clarity."
    )

@flock_type
class Milestones(BaseModel):
    milestones: List[Milestone] = Field(
        default_factory=list, description="Roadmap milestones/phases (chronological)."
    )


@flock_type
class ProjectSpecification( BaseModel):
    problem_statement: str = Field(
        ..., description="The problem to solve and who is affected."
    )
    elevator_pitch: str = Field(
        ..., description="A concise summary of the product/project."
    )
    scope_in: List[str] = Field(
        ..., min_length=1, description="In-scope items."
    )
    scope_out: List[str] = Field(
        default_factory=list, description="Explicitly out-of-scope items."
    )
    assumptions: List[str] = Field(
        default_factory=list, description="Assumptions that, if false, risk the plan."
    )
    constraints: List[str] = Field(
        default_factory=list, description="Hard constraints (tech, legal, budget, timeline)."
    )

@flock_type
class PRD(BaseModel):
    """
    Comprehensive Product Requirements Document schema.

    This model enforces:
    - Unique IDs across requirements/use-cases/stories/NFRs/dependencies/milestones.
    - Persona references in UseCases must exist.
    - Milestones must be in non-decreasing chronological order.
    """

    

    # Business alignment
    business_goals: List[BusinessGoal] = Field(
        ..., min_length=1, description="Business goals with KPIs."
    )

    # Users & behaviors
    personas: List[Persona] = Field(
        ..., min_length=1, description="Target personas."
    )
    

    # Requirements
    

    # UX/content/API
    

    # Security/privacy/compliance
    # data_privacy: Optional[DataPrivacyRequirement] = Field(
    #     None, description="Privacy/compliance posture."
    # )

    # Delivery
    dependencies: List[Dependency] = Field(
        default_factory=list, description="External/internal dependencies."
    )
    

    # # Docs
    # glossary: List[GlossaryTerm] = Field(
    #     default_factory=list, description="Glossary of terms."
    # )
    # attachments: List[Attachment] = Field(
    #     default_factory=list, description="Supplemental materials."
    # )

@flock_type
class ProjectIdea(BaseModel):
    idea: str



  
async def main() -> None:
    flock = Flock("openai/gpt-4.1")

    (
        flock.agent("prd_master")
        .consumes(ProjectIdea)
        .publishes(ProjectSpecification)
        .publishes(Backlog)
        .publishes(Requirements)
        .publishes(PresentationLayer)
        .publishes(Risks)
        .publishes(Milestones)
    )

    await flock.publish(ProjectIdea(idea="A modern user management dashboard"))

    await flock.run_until_idle()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)