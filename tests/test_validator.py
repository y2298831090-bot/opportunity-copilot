import pytest

from agents.validator import sanitize_extraction, validate_extraction
from schemas.opportunity import (
    ActionSourceType,
    BudgetInfo,
    Certainty,
    EvidenceItem,
    ExtractionResult,
    FactItem,
    FactStatus,
    InputQuality,
    InputQualityStatus,
    NextAction,
    PersonInfo,
    TimelineInfo,
)


def test_vague_budget_amount_is_downgraded() -> None:
    extraction = ExtractionResult(
        budget=BudgetInfo(amount="几十万", amount_status=FactStatus.CONFIRMED, evidence=[
            EvidenceItem(quote="预算应该有几十万", source="text", certainty=Certainty.UNCERTAIN)
        ])
    )
    result = validate_extraction(extraction)
    assert result.budget.amount_status == FactStatus.UNCONFIRMED


def test_person_without_authority_is_not_decision_maker() -> None:
    extraction = ExtractionResult(decision_maker=PersonInfo(
        name="王总", status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="王总参加了会议", source="text", certainty=Certainty.EXPLICIT)],
    ))
    result = validate_extraction(extraction)
    assert result.decision_maker.status == FactStatus.UNCONFIRMED
    assert result.decision_maker.name is None


def test_non_authority_use_of_decide_does_not_create_decision_maker() -> None:
    extraction = ExtractionResult(decision_maker=PersonInfo(
        name="王总",
        status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="王总决定参加下周会议", source="text")],
    ))
    result = validate_extraction(extraction)
    assert result.decision_maker.status == FactStatus.UNCONFIRMED


def test_person_without_influence_evidence_is_not_confirmed_influencer() -> None:
    extraction = ExtractionResult(influencers=[PersonInfo(
        name="李经理",
        status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="李经理参加了会议", source="text")],
    )])
    result = validate_extraction(extraction)
    assert result.influencers[0].status == FactStatus.UNCONFIRMED


def test_uncertain_timeline_is_downgraded() -> None:
    extraction = ExtractionResult(timeline=TimelineInfo(
        value="年底采购", status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="可能年底采购", source="text", certainty=Certainty.UNCERTAIN)],
    ))
    result = validate_extraction(extraction)
    assert result.timeline.status == FactStatus.UNCONFIRMED


def test_unreadable_input_forces_manual_review() -> None:
    extraction = ExtractionResult(input_quality=InputQuality(
        status=InputQualityStatus.UNREADABLE, reason="图片严重模糊"
    ))
    result = validate_extraction(extraction)
    assert result.stage.status.value == "undetermined"
    assert result.manual_review is True


def test_unreadable_input_clears_critical_confirmations() -> None:
    extraction = ExtractionResult(
        input_quality=InputQuality(status=InputQualityStatus.UNREADABLE, reason="图片严重模糊"),
        budget=BudgetInfo(
            exists=True,
            exists_status=FactStatus.CONFIRMED,
            amount="60 万",
            amount_status=FactStatus.CONFIRMED,
            evidence=[EvidenceItem(quote="预算 60 万", source="image")],
        ),
        decision_maker=PersonInfo(
            name="王总",
            status=FactStatus.CONFIRMED,
            evidence=[EvidenceItem(quote="最终由王总决定", source="image")],
        ),
        timeline=TimelineInfo(
            value="10 月",
            status=FactStatus.CONFIRMED,
            evidence=[EvidenceItem(quote="10 月上线", source="image")],
        ),
    )
    result = validate_extraction(extraction)
    assert result.budget.exists_status == FactStatus.UNCONFIRMED
    assert result.decision_maker.status == FactStatus.UNCONFIRMED
    assert result.timeline.status == FactStatus.UNCONFIRMED


def test_budget_can_exist_when_amount_is_unknown() -> None:
    extraction = ExtractionResult(budget=BudgetInfo(
        exists=True,
        exists_status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="项目预算已经审批，但还没有具体额度", source="text")],
    ))
    result = validate_extraction(extraction)
    assert result.budget.exists_status == FactStatus.CONFIRMED
    assert result.budget.amount is None


def test_budget_existence_without_evidence_is_downgraded() -> None:
    extraction = ExtractionResult(budget=BudgetInfo(exists=True, exists_status=FactStatus.CONFIRMED))
    result = validate_extraction(extraction)
    assert result.budget.exists is None
    assert result.budget.exists_status == FactStatus.UNCONFIRMED


@pytest.mark.parametrize(
    "source_text",
    [
        "客户已为本项目预留预算，具体额度仍待确认。",
        "该项目预算已经获批，金额尚未最终确认。",
        "业务部门为一期项目预留了参考预算，最终额度待确认。",
    ],
)
def test_explicit_budget_existence_is_recovered_when_model_omits_budget(
    source_text: str,
) -> None:
    sanitized = sanitize_extraction(ExtractionResult(), source_text)

    assert sanitized.budget.exists is True
    assert sanitized.budget.exists_status == FactStatus.CONFIRMED
    assert sanitized.budget.amount_status == FactStatus.UNCONFIRMED
    assert sanitized.budget.evidence[0].quote == source_text


def test_speculative_budget_is_not_recovered_when_model_omits_budget() -> None:
    sanitized = sanitize_extraction(ExtractionResult(), "客户可能有几十万预算。")

    assert sanitized.budget.exists is None
    assert sanitized.budget.exists_status == FactStatus.UNCONFIRMED


@pytest.mark.parametrize("quote", ["验收标准尚未量化。", "部署方式待评估。", "合同条款未明确。"])
def test_uncertain_items_preserve_explicit_unresolved_information(quote: str) -> None:
    extraction = ExtractionResult(
        uncertain_items=[FactItem(value=quote, status=FactStatus.UNCONFIRMED, evidence=[EvidenceItem(quote=quote)])]
    )

    sanitized = sanitize_extraction(extraction, quote)

    assert [item.value for item in sanitized.uncertain_items] == [quote]


def test_confirmed_fact_is_not_duplicated_as_unconfirmed() -> None:
    quote = "客户明确关注数据安全。"
    extraction = ExtractionResult(
        uncertain_items=[FactItem(value=quote, status=FactStatus.CONFIRMED, evidence=[EvidenceItem(quote=quote)])]
    )

    assert sanitize_extraction(extraction, quote).uncertain_items == []


@pytest.mark.parametrize("source_text", ["合同条款尚未讨论。", "部署方式待评估。", "验收指标尚未量化。"])
def test_recovery_preserves_explicit_unresolved_items(source_text: str) -> None:
    sanitized = sanitize_extraction(ExtractionResult(), source_text)

    assert [item.value for item in sanitized.uncertain_items] == [source_text]
    assert sanitized.uncertain_items[0].evidence[0].quote == source_text


def test_recovery_does_not_turn_explicit_negative_fact_into_unconfirmed() -> None:
    assert sanitize_extraction(ExtractionResult(), "客户明确表示今年没有项目预算。 ").uncertain_items == []


@pytest.mark.parametrize("quote", ["可能年底采购", "预计下个月完成", "应该会有预算", "大概50万元", "倾向于私有化部署"])
def test_uncertain_wording_is_not_explicit_claim(quote: str) -> None:
    extraction = ExtractionResult(timeline=TimelineInfo(value="候选时间", status=FactStatus.CONFIRMED, evidence=[EvidenceItem(quote=quote)]))

    sanitized = sanitize_extraction(extraction, quote)

    assert sanitized.timeline.evidence[0].certainty == Certainty.UNCERTAIN


@pytest.mark.parametrize("text", ["客户表示可能年底采购。", "客户预计下个月上线。", "预算应该会有一些。", "预算大概几十万元。", "客户倾向于私有化部署。"])
def test_uncertain_item_with_uncertain_evidence_is_preserved(text: str) -> None:
    extraction = ExtractionResult(uncertain_items=[FactItem(
        value=text, status=FactStatus.UNCONFIRMED,
        evidence=[EvidenceItem(quote=text, certainty=Certainty.UNCERTAIN)],
    )])

    assert len(sanitize_extraction(extraction, text).uncertain_items) == 1


@pytest.mark.parametrize("text", ["预算金额尚未确认。", "采购时间还没有确定。", "合同条款尚未讨论。", "验收标准待确认。"])
def test_explicit_unresolved_item_is_preserved(text: str) -> None:
    extraction = ExtractionResult(uncertain_items=[FactItem(
        value=text, status=FactStatus.UNCONFIRMED, evidence=[EvidenceItem(quote=text)],
    )])

    assert len(sanitize_extraction(extraction, text).uncertain_items) == 1


def test_customer_action_without_date_keeps_pending_time() -> None:
    action = NextAction(
        action="提供详细技术方案",
        recommended_owner="销售/售前",
        source_type=ActionSourceType.AGREED,
    )
    assert action.time == "待确认"


def test_salesperson_plan_is_not_a_customer_agreed_action() -> None:
    extraction = ExtractionResult(customer_agreed_actions=[NextAction(
        action="安排产品 Demo",
        recommended_owner="销售/售前",
        source_type=ActionSourceType.AGREED,
        evidence=[EvidenceItem(quote="我准备下周给客户演示", source="text", speaker="销售")],
    )])
    result = validate_extraction(extraction)
    assert result.next_actions == []
