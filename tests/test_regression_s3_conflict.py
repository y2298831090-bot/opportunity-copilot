import json
from pathlib import Path

from agents.opportunity_agent import OpportunityAgent
from agents.validator import sanitize_extraction
from schemas.opportunity import (
    Certainty,
    EvidenceItem,
    ExtractionResult,
    SignalType,
    StageSignal,
)
from services.input_parser import ParsedInput

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_TEXT = Path("samples/regression_s3_conflict_case.txt").read_text(encoding="utf-8")


class StubExtractor:
    def __init__(self, extraction: ExtractionResult) -> None:
        self.extraction = extraction

    def extract(self, _: ParsedInput) -> ExtractionResult:
        return self.extraction.model_copy(deep=True)


def regression_extraction() -> ExtractionResult:
    return ExtractionResult.model_validate(json.loads((FIXTURE_DIR / "s3_conflict_extraction.json").read_text(encoding="utf-8")))


def analyze_regression_case() -> object:
    agent = OpportunityAgent(StubExtractor(regression_extraction()))
    return agent.analyze(ParsedInput(text=SAMPLE_TEXT, image_data_urls=[], source_description="text"))


def test_timeline_conflict_does_not_downgrade_confirmed_s3() -> None:
    result = analyze_regression_case()
    assert result.stage.code == "S3"
    assert result.stage.status.value == "confirmed"
    assert result.timeline.status.value == "conflicting"


def test_need_invalidated_conflict_can_affect_stage() -> None:
    extraction = regression_extraction()
    extraction.conflict_candidates[0].affected_fields = ["need"]
    extraction.conflict_candidates[0].field = "需求有效性"
    extraction.stage_signals.append(StageSignal(
        type=SignalType.NEED_INVALIDATED,
        certainty=Certainty.EXPLICIT,
        evidence=[EvidenceItem(quote="项目已经取消，不再采购。", source="text")],
    ))
    result = OpportunityAgent(StubExtractor(extraction)).analyze(
        ParsedInput(text=f"{SAMPLE_TEXT}\n项目已经取消，不再采购。", image_data_urls=[], source_description="text")
    )
    assert result.stage.status.value == "needs_review"


def test_known_approver_does_not_mean_s4() -> None:
    extraction = regression_extraction()
    extraction.stage_signals.append(StageSignal(
        type=SignalType.APPROVAL_PROCESS_STARTED,
        certainty=Certainty.EXPLICIT,
        evidence=[EvidenceItem(quote="最终采购需要赵敏审批，她是这个项目最后拍板的人。", source="text")],
    ))
    result = OpportunityAgent(StubExtractor(extraction)).analyze(
        ParsedInput(text=SAMPLE_TEXT, image_data_urls=[], source_description="text")
    )
    assert result.stage.code == "S3"


def test_future_approval_step_does_not_mean_s4() -> None:
    extraction = regression_extraction()
    extraction.stage_signals.append(StageSignal(
        type=SignalType.APPROVAL_PROCESS_STARTED,
        certainty=Certainty.EXPLICIT,
        evidence=[EvidenceItem(quote="技术评审通过后进入采购比价，再提交最终审批。", source="text")],
    ))
    result = OpportunityAgent(StubExtractor(extraction)).analyze(
        ParsedInput(text=SAMPLE_TEXT, image_data_urls=[], source_description="text")
    )
    assert result.stage.code == "S3"


def test_explicit_agreed_actions_are_preserved() -> None:
    result = analyze_regression_case()
    agreed = [action for action in result.next_actions if action.source_type.value == "agreed"]
    assert len(agreed) >= 4
    assert {(action.action, action.time) for action in agreed} >= {
        ("发送正式报价，并拆分软件订阅、实施服务和运维费用", "本周五前"),
        ("进行产品Demo和技术交流", "下周二14:00"),
        ("准备20条脱敏FAQ和2份产品说明书", "下周一前"),
        ("Demo后确认是否进入正式POC，并讨论POC周期和验收指标", "待确认"),
    }
    assert {action.owner_side.value for action in agreed} == {"seller", "customer", "both"}
    assert not any(action.action == "确认下一步行动、负责人和时间" for action in result.next_actions)


def test_budget_exists_can_be_confirmed_while_final_amount_is_unconfirmed() -> None:
    result = analyze_regression_case()
    assert result.budget.exists_status.value == "confirmed"
    assert result.budget.amount == "约80万元"
    assert result.budget.amount_status.value == "unconfirmed"


def test_multiple_explicit_core_scenarios_are_preserved_without_knowledge_sources() -> None:
    result = analyze_regression_case()
    scenarios = {item.value for item in result.core_scenarios}
    assert {"售后客服知识库问答", "工单回复辅助"} <= scenarios
    assert "接入现有FAQ、产品说明书以及历史工单" not in scenarios


def test_explicit_business_and_information_risks_are_preserved() -> None:
    result = analyze_regression_case()
    descriptions = [risk.description for risk in result.risks]
    assert any("另外两家供应商" in description for description in descriptions)
    assert any("POC验收指标尚未量化" in description for description in descriptions)


def test_completeness_uses_validated_final_fields_and_s3_has_evidence() -> None:
    result = analyze_regression_case()
    assert result.completeness_percent == 88
    assert "下一步行动" in result.confirmed_dimensions
    assert "商机阶段证据" in result.confirmed_dimensions
    assert result.stage.evidence


def test_known_approval_phrases_are_removed_from_stage_signals() -> None:
    extraction = regression_extraction()
    extraction.stage_signals.append(StageSignal(
        type=SignalType.APPROVAL_PROCESS_STARTED,
        certainty=Certainty.EXPLICIT,
        evidence=[EvidenceItem(quote="技术评审通过后进入采购比价，再提交最终审批。", source="text")],
    ))
    sanitized = sanitize_extraction(extraction, SAMPLE_TEXT)
    assert not any(signal.type == SignalType.APPROVAL_PROCESS_STARTED for signal in sanitized.stage_signals)
