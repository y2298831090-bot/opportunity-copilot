from schemas.opportunity import (
    Certainty,
    EvidenceItem,
    Polarity,
    SignalType,
    StageResult,
    StageSignal,
    StageStatus,
)

STAGE_NAMES = {
    "S0": "线索", "S1": "需求初探", "S2": "方案验证", "S3": "商务评估", "S4": "决策审批", "S5": "赢单/签约",
}


def _eligible(signal: StageSignal) -> bool:
    return signal.certainty == Certainty.EXPLICIT and signal.polarity == Polarity.POSITIVE


def _eligible_evidence(evidence: EvidenceItem) -> bool:
    return evidence.certainty == Certainty.EXPLICIT and evidence.polarity == Polarity.POSITIVE


def _matching(signals: list[StageSignal], kinds: set[SignalType]) -> list[EvidenceItem]:
    return [
        evidence
        for signal in signals
        if _eligible(signal) and signal.type in kinds
        for evidence in signal.evidence
        if _eligible_evidence(evidence)
    ]


def _customer_agreed_evidence(signals: list[StageSignal], kinds: set[SignalType]) -> list[EvidenceItem]:
    return [
        evidence
        for signal in signals
        if _eligible(signal) and signal.type in kinds
        for evidence in signal.evidence
        if evidence.speaker_side.value == "customer" and _eligible_evidence(evidence)
    ]


def _result(code: str, reason: str, evidence: list[EvidenceItem], rule: str) -> StageResult:
    return StageResult(status=StageStatus.CONFIRMED, code=code, name=STAGE_NAMES[code], reason=reason, evidence=evidence, matched_rule=rule)


def determine_stage(
    signals: list[StageSignal],
    initial_contact_evidence: list[EvidenceItem] | None = None,
    has_stage_conflict: bool = False,
) -> StageResult:
    if has_stage_conflict:
        return StageResult(status=StageStatus.NEEDS_REVIEW, name="需要人工复核", reason="阶段相关信息存在冲突，不能自动选择更乐观的阶段。")

    signed = _matching(signals, {SignalType.CONTRACT_SIGNED, SignalType.ORDER_CONFIRMED})
    if signed:
        return _result("S5", "客户明确确认合同已签署或正式订单已确认。", signed, "S5: 合同签署或正式订单确认")

    approval = _matching(signals, {SignalType.INTERNAL_PROJECT_APPROVED, SignalType.APPROVAL_PROCESS_STARTED, SignalType.SUPPLIER_DECISION_STARTED})
    if approval:
        return _result("S4", "客户明确进入立项、内部审批或供应商决策阶段。", approval, "S4: 立项、审批或供应商决策")

    invalid = _matching(signals, {SignalType.NEED_INVALIDATED, SignalType.PROJECT_PAUSED, SignalType.PROCUREMENT_CANCELLED})
    commercial = _matching(signals, {SignalType.BUDGET_DISCUSSED, SignalType.QUOTATION_DISCUSSED, SignalType.PROCUREMENT_PROCESS_DISCUSSED, SignalType.CONTRACT_TERMS_DISCUSSED})
    active_need = _matching(signals, {SignalType.NEED_ACTIVE, SignalType.BUSINESS_PROBLEM, SignalType.USE_CASE})
    if commercial and invalid:
        return StageResult(status=StageStatus.NEEDS_REVIEW, name="需要人工复核", reason="商务讨论与项目暂停、取消或需求失效信息并存。", evidence=commercial + invalid, matched_rule="S3: 商务讨论与需求有效性冲突")
    if commercial and active_need:
        commercial_types = {signal.type for signal in signals if _eligible(signal) and signal.type in {
            SignalType.BUDGET_DISCUSSED,
            SignalType.QUOTATION_DISCUSSED,
            SignalType.PROCUREMENT_PROCESS_DISCUSSED,
            SignalType.CONTRACT_TERMS_DISCUSSED,
        }}
        if {
            SignalType.BUDGET_DISCUSSED,
            SignalType.QUOTATION_DISCUSSED,
            SignalType.PROCUREMENT_PROCESS_DISCUSSED,
        } <= commercial_types:
            reason = "客户需求持续有效，且已明确讨论预算、正式报价和采购流程。"
        else:
            reason = "存在明确商务讨论，且客户需求仍然有效。"
        return _result("S3", reason, commercial + active_need, "S3: 商务讨论 + 有效需求")

    validation = _customer_agreed_evidence(
        signals,
        {
            SignalType.DEMO_AGREED,
            SignalType.TRIAL_AGREED,
            SignalType.TECHNICAL_EXCHANGE_AGREED,
            SignalType.SOLUTION_EVALUATION_AGREED,
        },
    )
    if validation:
        return _result("S2", "客户明确同意进行演示、试用、技术交流或方案评估。", validation, "S2: 客户明确同意方案验证")

    need = _matching(signals, {SignalType.BUSINESS_PROBLEM, SignalType.USE_CASE})
    if need:
        return _result("S1", "客户明确表达了业务问题或使用场景。", need, "S1: 明确业务问题或使用场景")

    contact = [
        evidence
        for evidence in initial_contact_evidence or []
        if _eligible_evidence(evidence)
    ]
    if contact:
        return _result("S0", "存在初步接触，但没有明确的业务需求或使用场景。", contact, "S0: 初步接触且无需求信号")
    return StageResult(status=StageStatus.UNDETERMINED, name="无法判断", reason="没有初步接触或阶段条件的明确证据。")
