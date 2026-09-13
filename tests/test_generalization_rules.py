import pytest

from agents.validator import sanitize_extraction
from rules.risk_engine import analyze_risks
from rules.stage_engine import determine_stage
from schemas.opportunity import (
    ActionOwnerSide,
    ActionSourceType,
    BudgetInfo,
    Certainty,
    EvidenceItem,
    ExtractionResult,
    FactItem,
    FactStatus,
    NextAction,
    RiskItem,
    RiskType,
    SignalType,
    SpeakerSide,
    StageSignal,
    TimelineInfo,
)


def evidence(quote: str, side: SpeakerSide = SpeakerSide.CUSTOMER) -> EvidenceItem:
    return EvidenceItem(quote=quote, source="text", speaker="某参会人", speaker_side=side)


def signal(kind: SignalType, quote: str, side: SpeakerSide = SpeakerSide.CUSTOMER) -> StageSignal:
    return StageSignal(type=kind, certainty=Certainty.EXPLICIT, evidence=[evidence(quote, side)])


@pytest.mark.parametrize("quote", [
    "我们下周安排一次产品演示。",
    "技术团队同意进行一次技术交流。",
])
def test_named_customer_representative_can_trigger_s2(quote: str) -> None:
    result = determine_stage([signal(SignalType.DEMO_AGREED, quote)])
    assert result.code == "S2"


def test_seller_planned_demo_cannot_trigger_s2() -> None:
    result = determine_stage([
        signal(SignalType.DEMO_AGREED, "我方计划下周演示产品。", SpeakerSide.SELLER),
        signal(SignalType.BUSINESS_PROBLEM, "存在重复咨询。"),
    ])
    assert result.code == "S1"


@pytest.mark.parametrize("commercial", [
    SignalType.BUDGET_DISCUSSED,
    SignalType.QUOTATION_DISCUSSED,
    SignalType.PROCUREMENT_PROCESS_DISCUSSED,
    SignalType.CONTRACT_TERMS_DISCUSSED,
])
def test_each_commercial_signal_with_active_need_reaches_s3(commercial: SignalType) -> None:
    result = determine_stage([
        signal(SignalType.NEED_ACTIVE, "客户仍需要改善服务效率。"),
        signal(commercial, "客户正在讨论相应商务事项。"),
    ])
    assert result.code == "S3"


@pytest.mark.parametrize("quote", [
    "还在比较几家供应商。",
    "正在评估其他厂商。",
    "有多个竞品参与。",
    "尚未确定最终供应商。",
])
def test_supplier_comparison_is_not_supplier_decision_started(quote: str) -> None:
    extraction = ExtractionResult(stage_signals=[
        signal(SignalType.SUPPLIER_DECISION_STARTED, quote),
    ])
    sanitized = sanitize_extraction(extraction, quote)
    assert not sanitized.stage_signals


@pytest.mark.parametrize("quote", [
    "之后提交审批。",
    "通过技术评审后再走采购审批。",
    "最终需要领导批准。",
    "后续要进入供应商评选。",
])
def test_future_approval_is_not_approval_process_started(quote: str) -> None:
    extraction = ExtractionResult(stage_signals=[
        signal(SignalType.APPROVAL_PROCESS_STARTED, quote),
    ])
    sanitized = sanitize_extraction(extraction, quote)
    assert not sanitized.stage_signals


@pytest.mark.parametrize("kind, quote", [
    (SignalType.INTERNAL_PROJECT_APPROVED, "项目已经正式立项。"),
    (SignalType.APPROVAL_PROCESS_STARTED, "目前正在进行内部审批。"),
    (SignalType.SUPPLIER_DECISION_STARTED, "正式供应商决策已经开始。"),
    (SignalType.SUPPLIER_DECISION_STARTED, "采购委员会正在进行最终评审。"),
])
def test_explicit_formal_decision_states_reach_s4(kind: SignalType, quote: str) -> None:
    extraction = ExtractionResult(stage_signals=[signal(kind, quote)])
    sanitized = sanitize_extraction(extraction, quote)
    assert determine_stage(sanitized.stage_signals).code == "S4"


@pytest.mark.parametrize("budget, expected_exists, expected_amount_status", [
    (BudgetInfo(exists=True, exists_status=FactStatus.CONFIRMED, amount="100万", amount_status=FactStatus.CONFIRMED, evidence=[evidence("今年预算已经批了100万。")]), FactStatus.CONFIRMED, FactStatus.CONFIRMED),
    (BudgetInfo(exists=True, exists_status=FactStatus.CONFIRMED, amount=None, amount_status=FactStatus.UNCONFIRMED, evidence=[evidence("预算已经批了，但额度还不知道。")]), FactStatus.CONFIRMED, FactStatus.UNCONFIRMED),
    (BudgetInfo(exists=True, exists_status=FactStatus.CONFIRMED, amount="几十万", amount_status=FactStatus.CONFIRMED, evidence=[evidence("项目预留了预算，大概几十万。")]), FactStatus.CONFIRMED, FactStatus.UNCONFIRMED),
    (BudgetInfo(exists=True, exists_status=FactStatus.CONFIRMED, amount="几十万", amount_status=FactStatus.CONFIRMED, evidence=[evidence("可能有几十万预算。")]), FactStatus.UNCONFIRMED, FactStatus.UNCONFIRMED),
    (BudgetInfo(exists=False, exists_status=FactStatus.CONFIRMED, amount=None, amount_status=FactStatus.UNCONFIRMED, evidence=[evidence("今年没有这个项目预算。")]), FactStatus.CONFIRMED, FactStatus.UNCONFIRMED),
    (BudgetInfo(exists=True, exists_status=FactStatus.CONFIRMED, amount=None, amount_status=FactStatus.UNCONFIRMED, evidence=[evidence("预算需要后续再申请。")]), FactStatus.UNCONFIRMED, FactStatus.UNCONFIRMED),
])
def test_budget_existence_and_amount_certainty_are_independent(
    budget: BudgetInfo,
    expected_exists: FactStatus,
    expected_amount_status: FactStatus,
) -> None:
    extraction = sanitize_extraction(ExtractionResult(budget=budget), budget.evidence[0].quote)
    assert extraction.budget.exists_status == expected_exists
    assert extraction.budget.amount_status == expected_amount_status


@pytest.mark.parametrize(
    ("source_text", "scenarios"),
    [
        ("场景包括知识库问答和工单回复辅助。", ["知识库问答", "工单回复辅助"]),
        ("第一是知识库问答，第二是工单回复辅助。", ["知识库问答", "工单回复辅助"]),
        ("包含知识库问答、工单回复辅助、质检辅助三个场景。", ["知识库问答", "工单回复辅助", "质检辅助"]),
    ],
)
def test_multiple_explicit_scenarios_are_all_preserved(source_text: str, scenarios: list[str]) -> None:
    extraction = ExtractionResult(core_scenarios=[
        FactItem(value=scenario, status=FactStatus.CONFIRMED, evidence=[evidence(source_text)])
        for scenario in scenarios
    ])

    sanitized = sanitize_extraction(extraction, source_text)

    assert [item.value for item in sanitized.core_scenarios] == scenarios


@pytest.mark.parametrize("quote", ["可能年底采购。", "如果测试顺利，下月上线。"])
def test_uncertain_or_conditional_timeline_is_not_confirmed(quote: str) -> None:
    extraction = ExtractionResult(timeline=TimelineInfo(
        value="候选时间",
        status=FactStatus.CONFIRMED,
        evidence=[evidence(quote)],
    ))
    sanitized = sanitize_extraction(extraction, quote)
    assert sanitized.timeline.status == FactStatus.UNCONFIRMED


@pytest.mark.parametrize("owner_side", [
    ActionOwnerSide.SELLER,
    ActionOwnerSide.CUSTOMER,
    ActionOwnerSide.BOTH,
])
def test_agreed_actions_survive_each_owner_side(owner_side: ActionOwnerSide) -> None:
    action = NextAction(
        action="完成明确约定的后续事项",
        recommended_owner="相关负责人",
        owner_side=owner_side,
        source_type=ActionSourceType.AGREED,
        evidence=[evidence("会议已明确约定完成后续事项。", SpeakerSide.BOTH)],
    )
    result = sanitize_extraction(ExtractionResult(agreed_actions=[action]), "会议已明确约定完成后续事项。")
    assert result.agreed_actions == [action]
    assert result.agreed_actions[0].time == "待确认"


def test_conditional_action_is_not_treated_as_agreed() -> None:
    action = NextAction(
        action="开展后续试用",
        recommended_owner="销售/售前",
        owner_side=ActionOwnerSide.SELLER,
        source_type=ActionSourceType.AGREED,
        evidence=[evidence("如果演示效果符合预期，后续再安排试用。", SpeakerSide.CUSTOMER)],
    )
    result = sanitize_extraction(
        ExtractionResult(agreed_actions=[action]),
        "如果演示效果符合预期，后续再安排试用。",
    )
    assert result.agreed_actions == []


def test_confirmed_facts_do_not_survive_in_unconfirmed_items() -> None:
    extraction = ExtractionResult(uncertain_items=[
        FactItem(value="客户明确关注数据安全", status=FactStatus.CONFIRMED, evidence=[evidence("客户明确关注数据安全。")]),
        FactItem(value="部署方式尚未确定", status=FactStatus.UNCONFIRMED, evidence=[evidence("部署方式尚未确定。")]),
    ])
    sanitized = sanitize_extraction(extraction, "客户明确关注数据安全。部署方式尚未确定。")
    assert [item.value for item in sanitized.uncertain_items] == ["部署方式尚未确定"]


def test_risks_are_deduplicated_by_type_and_affected_field() -> None:
    first = RiskItem(
        category="business",
        risk_type=RiskType.COMPETITION,
        affected_fields=["supplier_selection"],
        description="客户正在比较其他供应商。",
        evidence=[evidence("客户正在比较其他供应商。")],
    )
    second = first.model_copy(update={"description": "客户同时评估多个供应商，存在竞争风险。"})
    risks = analyze_risks(ExtractionResult(risk_candidates=[first, second]), [])
    assert len(risks) == 1
    assert len(risks[0].evidence) == 1


@pytest.mark.parametrize("risk_type, field", [
    (RiskType.COMPETITION, "supplier_selection"),
    (RiskType.TECHNICAL_REQUIREMENT, "security"),
    (RiskType.VALIDATION, "acceptance_criteria"),
    (RiskType.PROCUREMENT, "procurement"),
])
def test_explicit_typed_risks_are_preserved(risk_type: RiskType, field: str) -> None:
    risk = RiskItem(
        category="business",
        risk_type=risk_type,
        affected_fields=[field],
        description="原始记录明确表达的业务风险或技术要求。",
        evidence=[evidence("原始记录明确表达的业务风险或技术要求。")],
    )
    result = analyze_risks(ExtractionResult(risk_candidates=[risk]), [])
    assert result == [risk]


def test_visual_pdf_evidence_is_traceable_without_native_text() -> None:
    extraction = ExtractionResult(customer_needs=[FactItem(
        value="明确业务需求",
        status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="页面可见的客户需求", source="PDF page 1", speaker_side=SpeakerSide.CUSTOMER)],
    )])
    sanitized = sanitize_extraction(extraction, "", has_visual_source=True)
    assert sanitized.customer_needs[0].status == FactStatus.CONFIRMED
