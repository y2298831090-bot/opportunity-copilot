from __future__ import annotations

import re

from rules.stage_engine import determine_stage
from schemas.opportunity import (
    BudgetInfo,
    Certainty,
    EvidenceItem,
    ExtractionResult,
    FactItem,
    FactStatus,
    InputQualityStatus,
    OpportunityResult,
    PersonInfo,
    SignalType,
    StageResult,
    StageSignal,
    StageStatus,
    TimelineInfo,
)

UNCERTAINTY_MARKERS = ("可能", "应该", "大概", "估计", "预计", "倾向", "或许", "似乎", "可能会")
UNCONFIRMED_MARKERS = (
    "尚未确定", "尚未确认", "待确认", "未讨论", "待讨论", "没有确认", "没有确定",
    "再确认", "还要确认", "后续评估", "需要评估", "待评估", "待审批",
    "未明确", "尚未量化", "未量化", "尚未给出标准", "需要后续确认",
)
CONDITIONAL_MARKERS = ("如果", "若", "视情况", "视评估", "取决于")
EXPLICIT_BUDGET_MARKERS = ("预算已批", "预算已经批", "有预算", "预留", "预算安排", "预算已获批")
PENDING_BUDGET_MARKERS = ("以后申请", "后续申请", "再申请", "需要申请")
EXPLICIT_BUDGET_EXISTENCE_PATTERNS = (
    re.compile(r"预算.{0,12}(?:已|已经).{0,8}(?:获批|批准|审批|预留|安排)"),
    re.compile(r"(?:已|已经|明确).{0,12}(?:获批|批准|审批|预留|安排).{0,12}预算"),
    re.compile(r"预留了.{0,16}预算"),
    re.compile(r"(?:客户|对方).{0,12}(?:确认|明确).{0,8}(?:已)?有.{0,8}预算"),
)
NEGATED_BUDGET_PATTERNS = (re.compile(r"(?:没有|无|未有).{0,8}预算"),)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value).lower()


def _is_traceable(
    evidence: EvidenceItem,
    source_text: str | None,
    has_visual_source: bool = False,
) -> bool:
    if source_text is None:
        return True
    if has_visual_source and evidence.source != "text":
        return True
    quote = _normalize_text(evidence.quote)
    return bool(quote) and quote in _normalize_text(source_text)


def _has_explicit_evidence(
    evidence: list[EvidenceItem],
    source_text: str | None = None,
    has_visual_source: bool = False,
) -> bool:
    return any(
        item.certainty == Certainty.EXPLICIT
        and item.polarity.value == "positive"
        and _is_traceable(item, source_text, has_visual_source)
        for item in evidence
    )


def _has_traceable_evidence(
    evidence: list[EvidenceItem],
    source_text: str | None = None,
    has_visual_source: bool = False,
) -> bool:
    return any(_is_traceable(item, source_text, has_visual_source) for item in evidence)


def _explicit_budget_evidence_from_source(source_text: str | None) -> EvidenceItem | None:
    """Recover only an explicit budget-existence statement omitted by extraction."""
    if not source_text:
        return None
    for sentence in re.split(r"(?<=[。！？!?；;])|\n+", source_text):
        quote = sentence.strip()
        if not quote or any(pattern.search(quote) for pattern in NEGATED_BUDGET_PATTERNS):
            continue
        if any(pattern.search(quote) for pattern in EXPLICIT_BUDGET_EXISTENCE_PATTERNS):
            return EvidenceItem(quote=quote, source="text", certainty=Certainty.EXPLICIT)
    return None


def _authority_evidence(
    person: PersonInfo,
    source_text: str | None = None,
    has_visual_source: bool = False,
) -> bool:
    if not _has_explicit_evidence(person.evidence, source_text, has_visual_source):
        return False
    for item in person.evidence:
        if any(term in item.quote for term in ("最终由", "最终拍板", "最终审批", "最终决定", "决定权")):
            return True
        if "审批" in item.quote and any(context in item.quote for context in ("采购", "项目", "合同", "供应商", "预算")):
            return True
    return False


def _influence_evidence(
    person: PersonInfo,
    source_text: str | None = None,
    has_visual_source: bool = False,
) -> bool:
    terms = ("技术评估", "选型", "推荐", "意见会影响", "意见影响", "会直接影响", "直接影响")
    return _has_explicit_evidence(person.evidence, source_text, has_visual_source) and any(term in item.quote for item in person.evidence for term in terms)


def _sanitize_confirmed_facts(items: list, source_text: str | None, has_visual_source: bool) -> list:
    sanitized = []
    for item in items:
        copy = item.model_copy(deep=True)
        if copy.status == FactStatus.CONFIRMED and not _has_explicit_evidence(copy.evidence, source_text, has_visual_source):
            copy.status = FactStatus.UNCONFIRMED
        sanitized.append(copy)
    return sanitized


def _is_started_approval_signal(signal: StageSignal, evidence: EvidenceItem) -> bool:
    quote = evidence.quote
    if signal.type == SignalType.INTERNAL_PROJECT_APPROVED:
        return bool(re.search(r"项目.*(?:已|已经|正式).*(?:立项|获批)|(?:立项|项目).*(?:已|已经).*(?:通过|完成)", quote))
    if signal.type == SignalType.APPROVAL_PROCESS_STARTED:
        return bool(re.search(r"(?:正在|已|已经).*(?:进入|进行|走|启动).*(?:审批|审核)|(?:审批|审核).*(?:已|已经|正在|开始|启动|进行中)", quote))
    if signal.type == SignalType.SUPPLIER_DECISION_STARTED:
        return bool(re.search(r"(?:已|已经|正在).*(?:进入|进行|启动).*(?:供应商.*(?:评选|选择|决策)|采购委员会.*评审)|供应商.*(?:评选|选择|决策).*(?:已|已经|正在|开始|启动)|采购委员会.*(?:已|已经|正在).*(?:最终)?评审", quote))
    return True


def _is_completed_stage_signal(signal: StageSignal, evidence: EvidenceItem) -> bool:
    quote = evidence.quote
    if signal.type == SignalType.CONTRACT_SIGNED:
        return bool(re.search(r"合同.*(?:已|已经|正式).*(?:签署|签订|签了)|双方.*合同.*(?:已|已经).*(?:签署|签订|签了)", quote))
    if signal.type == SignalType.ORDER_CONFIRMED:
        return bool(re.search(r"(?:正式)?订单.*(?:已|已经|正式).*(?:确认|下达|下来了)|PO.*(?:已|已经).*(?:确认|下达)", quote, re.IGNORECASE))
    return True


def _sanitize_stage_signals(
    signals: list[StageSignal],
    source_text: str | None,
    has_visual_source: bool,
) -> list[StageSignal]:
    sanitized: list[StageSignal] = []
    for signal in signals:
        copy = signal.model_copy(deep=True)
        copy.evidence = [
            evidence
            for evidence in copy.evidence
            if _has_explicit_evidence([evidence], source_text, has_visual_source)
        ]
        if copy.type in {
            SignalType.INTERNAL_PROJECT_APPROVED,
            SignalType.APPROVAL_PROCESS_STARTED,
            SignalType.SUPPLIER_DECISION_STARTED,
        }:
            copy.evidence = [
                evidence for evidence in copy.evidence if _is_started_approval_signal(copy, evidence)
            ]
        if copy.type in {SignalType.CONTRACT_SIGNED, SignalType.ORDER_CONFIRMED}:
            copy.evidence = [
                evidence for evidence in copy.evidence if _is_completed_stage_signal(copy, evidence)
            ]
        if copy.evidence:
            sanitized.append(copy)
    return sanitized


def _knowledge_source_only(item) -> bool:
    value = item.value.lower()
    source_markers = ("faq", "产品说明书", "历史工单", "资料")
    scenario_markers = ("问答", "回复", "辅助", "助手", "处理")
    return any(marker in value for marker in source_markers) and not any(marker in value for marker in scenario_markers)


def _is_agreed_action(action, source_text: str | None, has_visual_source: bool) -> bool:
    explicit_evidence = [
        evidence
        for evidence in action.evidence
        if _has_explicit_evidence([evidence], source_text, has_visual_source)
    ]
    if not explicit_evidence:
        return False
    unilateral_sales_plan = any(
        evidence.speaker == "销售" and any(marker in evidence.quote for marker in ("我准备", "我计划", "我打算", "拟"))
        for evidence in explicit_evidence
    )
    conditional_action = any(
        any(marker in evidence.quote for marker in CONDITIONAL_MARKERS)
        for evidence in explicit_evidence
    )
    return not unilateral_sales_plan and not conditional_action


def _has_uncertainty_text(value: str) -> bool:
    return any(marker in value for marker in UNCERTAINTY_MARKERS + UNCONFIRMED_MARKERS)


def _normalize_evidence_certainty(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    normalized: list[EvidenceItem] = []
    for item in evidence:
        copy = item.model_copy(deep=True)
        if copy.certainty == Certainty.EXPLICIT and any(marker in copy.quote for marker in UNCERTAINTY_MARKERS):
            copy.certainty = Certainty.UNCERTAIN
        normalized.append(copy)
    return normalized


def _recover_unresolved_items(source_text: str | None, existing: list[FactItem]) -> list[FactItem]:
    if not source_text:
        return existing
    known_quotes = {_normalize_text(evidence.quote) for item in existing for evidence in item.evidence}
    recovered = list(existing)
    for sentence in re.split(r"(?<=[。！？!?；;])|\n+", source_text):
        quote = sentence.strip()
        normalized_quote = _normalize_text(quote)
        if not quote or normalized_quote in known_quotes or not any(marker in quote for marker in UNCONFIRMED_MARKERS):
            continue
        recovered.append(FactItem(
            value=quote,
            status=FactStatus.UNCONFIRMED,
            evidence=[EvidenceItem(quote=quote, source="text", certainty=Certainty.EXPLICIT)],
        ))
    return recovered


def _uncertain_item_is_supported(item: FactItem, source_text: str | None, has_visual_source: bool) -> bool:
    if item.status == FactStatus.CONFIRMED:
        return False
    if item.status == FactStatus.CONFLICTING:
        return bool(item.evidence)
    if not item.evidence or not _has_traceable_evidence(item.evidence, source_text, has_visual_source):
        return False
    values = [item.value, *(evidence.quote for evidence in item.evidence)]
    return any(_has_uncertainty_text(value) for value in values)


def sanitize_extraction(
    extraction: ExtractionResult,
    source_text: str | None = None,
    has_visual_source: bool = False,
) -> ExtractionResult:
    sanitized = extraction.model_copy(deep=True)
    for field_name in ("customer_needs", "core_scenarios", "uncertain_items"):
        for item in getattr(sanitized, field_name):
            item.evidence = _normalize_evidence_certainty(item.evidence)
    sanitized.budget.evidence = _normalize_evidence_certainty(sanitized.budget.evidence)
    sanitized.decision_maker.evidence = _normalize_evidence_certainty(sanitized.decision_maker.evidence)
    sanitized.timeline.evidence = _normalize_evidence_certainty(sanitized.timeline.evidence)
    for signal in sanitized.stage_signals:
        signal.evidence = _normalize_evidence_certainty(signal.evidence)
    if sanitized.input_quality.status == InputQualityStatus.UNREADABLE:
        sanitized.budget = BudgetInfo()
        sanitized.decision_maker = PersonInfo()
        sanitized.timeline = TimelineInfo()
        sanitized.customer_needs = []
        sanitized.core_scenarios = []
        sanitized.influencers = []
        sanitized.agreed_actions = []
        sanitized.stage_signals = []
        sanitized.initial_contact_evidence = []
        return sanitized
    budget = sanitized.budget
    decision_maker = sanitized.decision_maker
    timeline = sanitized.timeline
    if budget.exists_status == FactStatus.CONFIRMED and not _has_explicit_evidence(budget.evidence, source_text, has_visual_source):
        budget.exists = None
        budget.exists_status = FactStatus.UNCONFIRMED
    evidence_text = " ".join(evidence.quote for evidence in budget.evidence)
    if budget.exists is True and budget.exists_status == FactStatus.CONFIRMED and (
        any(marker in evidence_text for marker in PENDING_BUDGET_MARKERS)
        or (_has_uncertainty_text(evidence_text) and not any(marker in evidence_text for marker in EXPLICIT_BUDGET_MARKERS))
    ):
        budget.exists = None
        budget.exists_status = FactStatus.UNCONFIRMED
    if budget.amount_status == FactStatus.CONFIRMED and (
        not _has_explicit_evidence(budget.evidence, source_text, has_visual_source)
        or _has_uncertainty_text(evidence_text)
    ):
        budget.amount_status = FactStatus.UNCONFIRMED
    if budget.exists is False and budget.exists_status == FactStatus.CONFIRMED:
        budget.amount = None
        budget.amount_status = FactStatus.UNCONFIRMED
    if budget.exists_status == FactStatus.UNCONFIRMED and budget.exists is not False:
        source_evidence = _explicit_budget_evidence_from_source(source_text)
        if source_evidence is not None:
            budget.exists = True
            budget.exists_status = FactStatus.CONFIRMED
            budget.evidence = [*budget.evidence, source_evidence]
    if decision_maker.status == FactStatus.CONFIRMED and not _authority_evidence(decision_maker, source_text, has_visual_source):
        sanitized.decision_maker = PersonInfo(status=FactStatus.UNCONFIRMED, evidence=decision_maker.evidence)
    if timeline.status == FactStatus.CONFIRMED and (
        not _has_explicit_evidence(timeline.evidence, source_text, has_visual_source)
        or any(
            _has_uncertainty_text(evidence.quote)
            or any(marker in evidence.quote for marker in CONDITIONAL_MARKERS)
            for evidence in timeline.evidence
        )
    ):
        timeline.status = FactStatus.UNCONFIRMED
        timeline.value = None
    sanitized.customer_needs = _sanitize_confirmed_facts(sanitized.customer_needs, source_text, has_visual_source)
    sanitized.core_scenarios = [
        item
        for item in _sanitize_confirmed_facts(sanitized.core_scenarios, source_text, has_visual_source)
        if not _knowledge_source_only(item)
    ]
    sanitized.influencers = [
        PersonInfo(status=FactStatus.UNCONFIRMED, evidence=person.evidence)
        if person.status == FactStatus.CONFIRMED and not _influence_evidence(person, source_text, has_visual_source)
        else person
        for person in _sanitize_confirmed_facts(sanitized.influencers, source_text, has_visual_source)
    ]
    sanitized.stage_signals = _sanitize_stage_signals(sanitized.stage_signals, source_text, has_visual_source)
    sanitized.initial_contact_evidence = [
        evidence
        for evidence in sanitized.initial_contact_evidence
        if _has_explicit_evidence([evidence], source_text, has_visual_source)
    ]
    sanitized.agreed_actions = [
        action for action in sanitized.agreed_actions if _is_agreed_action(action, source_text, has_visual_source)
    ]
    sanitized.risk_candidates = [
        risk
        for risk in sanitized.risk_candidates
        if _has_explicit_evidence(risk.evidence, source_text, has_visual_source)
    ]
    sanitized.uncertain_items = [
        item
        for item in sanitized.uncertain_items
        if _uncertain_item_is_supported(item, source_text, has_visual_source)
    ]
    sanitized.uncertain_items = _recover_unresolved_items(source_text, sanitized.uncertain_items)
    return sanitized


def finalize_opportunity(result: OpportunityResult) -> OpportunityResult:
    if result.input_quality.status == InputQualityStatus.UNREADABLE:
        result.budget = BudgetInfo()
        result.decision_maker = PersonInfo()
        result.timeline = TimelineInfo()
        result.stage = StageResult(status=StageStatus.UNDETERMINED, name="无法判断", reason="输入内容无法可靠识别，建议人工复核。")
        result.manual_review = True
    elif result.stage.status == StageStatus.CONFIRMED and not _has_explicit_evidence(result.stage.evidence):
        result.stage = StageResult(status=StageStatus.UNDETERMINED, name="无法判断", reason="阶段结论缺少可核验的原始证据。")
        result.manual_review = True
    return result


def validate_extraction(extraction: ExtractionResult) -> OpportunityResult:
    sanitized = sanitize_extraction(extraction)
    if sanitized.input_quality.status == InputQualityStatus.UNREADABLE:
        stage = StageResult(status=StageStatus.UNDETERMINED, name="无法判断", reason="输入内容无法可靠识别，建议人工复核。")
        manual_review = True
    else:
        stage = determine_stage(sanitized.stage_signals, sanitized.initial_contact_evidence)
        manual_review = False
    result = OpportunityResult(
        input_quality=sanitized.input_quality,
        customer_needs=sanitized.customer_needs,
        core_scenarios=sanitized.core_scenarios,
        budget=sanitized.budget,
        decision_maker=sanitized.decision_maker,
        influencers=sanitized.influencers,
        timeline=sanitized.timeline,
        stage=stage,
        unconfirmed_items=sanitized.uncertain_items,
        manual_review=manual_review,
    )
    return finalize_opportunity(result)
