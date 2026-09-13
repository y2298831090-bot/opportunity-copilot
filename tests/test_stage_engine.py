from rules.stage_engine import determine_stage
from schemas.opportunity import (
    Certainty,
    EvidenceItem,
    SignalType,
    SpeakerSide,
    StageSignal,
)


def evidence(
    quote: str,
    certainty: Certainty = Certainty.EXPLICIT,
    speaker: str | None = None,
    speaker_side: SpeakerSide = SpeakerSide.UNKNOWN,
) -> EvidenceItem:
    return EvidenceItem(
        quote=quote,
        source="text",
        certainty=certainty,
        speaker=speaker,
        speaker_side=speaker_side,
    )


def signal(
    kind: SignalType,
    quote: str,
    speaker: str | None = None,
    speaker_side: SpeakerSide = SpeakerSide.UNKNOWN,
) -> StageSignal:
    return StageSignal(
        type=kind,
        certainty=Certainty.EXPLICIT,
        evidence=[evidence(quote, speaker=speaker, speaker_side=speaker_side)],
    )


def test_s0_for_initial_contact_without_need() -> None:
    result = determine_stage([], [evidence("第一次拜访客户，介绍了公司和产品")])
    assert result.code == "S0"
    assert result.evidence[0].quote == "第一次拜访客户，介绍了公司和产品"


def test_no_qualifying_signal_or_contact_stays_undetermined() -> None:
    result = determine_stage([])
    assert result.status.value == "undetermined"


def test_s1_for_explicit_business_problem() -> None:
    result = determine_stage([signal(SignalType.BUSINESS_PROBLEM, "客服有大量重复咨询")])
    assert result.code == "S1"


def test_customer_agreed_demo_reaches_s2() -> None:
    result = determine_stage([signal(
        SignalType.DEMO_AGREED,
        "下周你们可以过来做一次产品 Demo",
        "客户代表",
        SpeakerSide.CUSTOMER,
    )])
    assert result.code == "S2"


def test_salesperson_demo_signal_does_not_reach_s2() -> None:
    result = determine_stage([signal(SignalType.DEMO_AGREED, "我准备下周给客户演示", "销售")])
    assert result.code is None


def test_salesperson_demo_plan_does_not_reach_s2() -> None:
    result = determine_stage([signal(SignalType.BUSINESS_PROBLEM, "客服重复咨询很多")])
    assert result.code == "S1"


def test_commercial_discussion_requires_active_need_for_s3() -> None:
    signals = [
        signal(SignalType.NEED_ACTIVE, "客户确认需要建设知识库客服系统"),
        signal(SignalType.BUDGET_DISCUSSED, "今年预算大约 60 万"),
    ]
    assert determine_stage(signals).code == "S3"


def test_explicit_approval_reaches_s4() -> None:
    result = determine_stage([signal(SignalType.APPROVAL_PROCESS_STARTED, "正在走内部审批")])
    assert result.code == "S4"


def test_uncertain_evidence_cannot_promote_an_explicit_signal() -> None:
    uncertain = StageSignal(
        type=SignalType.APPROVAL_PROCESS_STARTED,
        certainty=Certainty.EXPLICIT,
        evidence=[evidence("可能要走内部审批", certainty=Certainty.UNCERTAIN)],
    )
    result = determine_stage([uncertain])
    assert result.code is None


def test_signed_contract_reaches_s5() -> None:
    result = determine_stage([signal(SignalType.CONTRACT_SIGNED, "合同已经签了")])
    assert result.code == "S5"


def test_commercial_signal_with_paused_project_needs_review() -> None:
    signals = [
        signal(SignalType.NEED_ACTIVE, "需求仍然存在"),
        signal(SignalType.QUOTATION_DISCUSSED, "请提供正式报价"),
        signal(SignalType.PROJECT_PAUSED, "项目已经暂停"),
    ]
    assert determine_stage(signals).status.value == "needs_review"
