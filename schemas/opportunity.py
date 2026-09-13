from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class Certainty(str, Enum):
    EXPLICIT = "explicit"
    UNCERTAIN = "uncertain"


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class SpeakerSide(str, Enum):
    CUSTOMER = "customer"
    SELLER = "seller"
    BOTH = "both"
    UNKNOWN = "unknown"


class FactStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    CONFLICTING = "conflicting"


class InputQualityStatus(str, Enum):
    READABLE = "readable"
    PARTIALLY_READABLE = "partially_readable"
    UNREADABLE = "unreadable"


class StageStatus(str, Enum):
    CONFIRMED = "confirmed"
    NEEDS_REVIEW = "needs_review"
    UNDETERMINED = "undetermined"


class ActionSourceType(str, Enum):
    AGREED = "agreed"
    AI_RECOMMENDED = "ai_recommended"


class ActionOwnerSide(str, Enum):
    SELLER = "seller"
    CUSTOMER = "customer"
    BOTH = "both"
    UNKNOWN = "unknown"


class RiskType(str, Enum):
    TIMELINE_CONFLICT = "timeline_conflict"
    COMPETITION = "competition_risk"
    PROJECT_PAUSE_OR_CANCEL = "project_pause_or_cancel"
    BUDGET = "budget_risk"
    VALIDATION = "validation_risk"
    TECHNICAL_REQUIREMENT = "technical_requirement"
    PROCUREMENT = "procurement_risk"
    INFORMATION_GAP = "information_gap"
    OTHER = "other"


class EvidenceItem(BaseModel):
    quote: str = Field(min_length=1)
    source: str = "text"
    speaker: str | None = None
    speaker_side: SpeakerSide = SpeakerSide.UNKNOWN
    certainty: Certainty = Certainty.EXPLICIT
    polarity: Polarity = Polarity.POSITIVE


class InputQuality(BaseModel):
    status: InputQualityStatus = InputQualityStatus.READABLE
    reason: str = ""


class FactItem(BaseModel):
    value: str
    status: FactStatus = FactStatus.UNCONFIRMED
    evidence: list[EvidenceItem] = Field(default_factory=list)


class BudgetInfo(BaseModel):
    exists: bool | None = None
    exists_status: FactStatus = FactStatus.UNCONFIRMED
    amount: str | None = None
    amount_status: FactStatus = FactStatus.UNCONFIRMED
    description: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)


class PersonInfo(BaseModel):
    name: str | None = None
    role: str | None = None
    status: FactStatus = FactStatus.UNCONFIRMED
    evidence: list[EvidenceItem] = Field(default_factory=list)


class TimelineInfo(BaseModel):
    value: str | None = None
    status: FactStatus = FactStatus.UNCONFIRMED
    evidence: list[EvidenceItem] = Field(default_factory=list)


class SignalType(str, Enum):
    BUSINESS_PROBLEM = "business_problem"
    USE_CASE = "use_case"
    DEMO_AGREED = "demo_agreed"
    TRIAL_AGREED = "trial_agreed"
    TECHNICAL_EXCHANGE_AGREED = "technical_exchange_agreed"
    SOLUTION_EVALUATION_AGREED = "solution_evaluation_agreed"
    BUDGET_DISCUSSED = "budget_discussed"
    QUOTATION_DISCUSSED = "quotation_discussed"
    PROCUREMENT_PROCESS_DISCUSSED = "procurement_process_discussed"
    CONTRACT_TERMS_DISCUSSED = "contract_terms_discussed"
    NEED_ACTIVE = "need_active"
    NEED_INVALIDATED = "need_invalidated"
    PROJECT_PAUSED = "project_paused"
    PROCUREMENT_CANCELLED = "procurement_cancelled"
    INTERNAL_PROJECT_APPROVED = "internal_project_approved"
    APPROVAL_PROCESS_STARTED = "approval_process_started"
    SUPPLIER_DECISION_STARTED = "supplier_decision_started"
    CONTRACT_SIGNED = "contract_signed"
    ORDER_CONFIRMED = "order_confirmed"


class StageSignal(BaseModel):
    type: SignalType
    certainty: Certainty = Certainty.EXPLICIT
    polarity: Polarity = Polarity.POSITIVE
    evidence: list[EvidenceItem] = Field(default_factory=list)


class StageResult(BaseModel):
    status: StageStatus = StageStatus.UNDETERMINED
    code: Literal["S0", "S1", "S2", "S3", "S4", "S5"] | None = None
    name: str = "无法判断"
    reason: str = "缺少可用于判断阶段的明确证据。"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    candidate_stages: list[str] = Field(default_factory=list)
    matched_rule: str = ""


class ConflictItem(BaseModel):
    field: str
    description: str
    affected_fields: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class RiskItem(BaseModel):
    category: Literal["business", "information"]
    risk_type: RiskType = RiskType.OTHER
    affected_fields: list[str] = Field(default_factory=list)
    description: str
    evidence: list[EvidenceItem] = Field(default_factory=list)


class NextAction(BaseModel):
    action: str
    recommended_owner: str
    owner_side: ActionOwnerSide = ActionOwnerSide.UNKNOWN
    time: str = "待确认"
    source_type: ActionSourceType
    evidence: list[EvidenceItem] = Field(default_factory=list)

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_legacy_source_type(cls, value: object) -> object:
        return "agreed" if value == "customer_agreed" else value


class ExtractionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    input_quality: InputQuality = Field(default_factory=InputQuality)
    initial_contact_evidence: list[EvidenceItem] = Field(default_factory=list)
    customer_needs: list[FactItem] = Field(default_factory=list)
    core_scenarios: list[FactItem] = Field(default_factory=list)
    budget: BudgetInfo = Field(default_factory=BudgetInfo)
    decision_maker: PersonInfo = Field(default_factory=PersonInfo)
    influencers: list[PersonInfo] = Field(default_factory=list)
    timeline: TimelineInfo = Field(default_factory=TimelineInfo)
    stage_signals: list[StageSignal] = Field(default_factory=list)
    agreed_actions: list[NextAction] = Field(
        default_factory=list,
        validation_alias=AliasChoices("agreed_actions", "customer_agreed_actions"),
    )
    uncertain_items: list[FactItem] = Field(default_factory=list)
    conflict_candidates: list[ConflictItem] = Field(default_factory=list)
    risk_candidates: list[RiskItem] = Field(default_factory=list)

    @property
    def customer_agreed_actions(self) -> list[NextAction]:
        """Compatibility alias for extraction payloads created before agreed_actions."""
        return self.agreed_actions


class OpportunityResult(BaseModel):
    input_quality: InputQuality
    customer_needs: list[FactItem] = Field(default_factory=list)
    core_scenarios: list[FactItem] = Field(default_factory=list)
    budget: BudgetInfo = Field(default_factory=BudgetInfo)
    decision_maker: PersonInfo = Field(default_factory=PersonInfo)
    influencers: list[PersonInfo] = Field(default_factory=list)
    timeline: TimelineInfo = Field(default_factory=TimelineInfo)
    stage: StageResult = Field(default_factory=StageResult)
    risks: list[RiskItem] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    unconfirmed_items: list[FactItem] = Field(default_factory=list)
    conflicts: list[ConflictItem] = Field(default_factory=list)
    completeness_percent: int = 0
    confirmed_dimensions: list[str] = Field(default_factory=list)
    missing_dimensions: list[str] = Field(default_factory=list)
    manual_review: bool = False
