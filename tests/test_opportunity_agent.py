from agents.opportunity_agent import OpportunityAgent
from schemas.opportunity import (
    BudgetInfo,
    Certainty,
    ConflictItem,
    EvidenceItem,
    ExtractionResult,
    FactStatus,
    InputQuality,
    InputQualityStatus,
    PersonInfo,
)
from services.input_parser import ParsedInput


class StubExtractor:
    def __init__(self, extraction: ExtractionResult) -> None:
        self.extraction = extraction

    def extract(self, _: ParsedInput) -> ExtractionResult:
        return self.extraction


def test_timeline_conflict_preserves_both_evidences_without_forcing_stage_review() -> None:
    conflict = ConflictItem(
        field="时间计划",
        description="上线时间与采购启动时间冲突",
        evidence=[
            EvidenceItem(quote="希望 10 月完成上线", source="text", certainty=Certainty.EXPLICIT),
            EvidenceItem(quote="今年可能不会启动采购", source="text", certainty=Certainty.UNCERTAIN),
        ],
    )
    agent = OpportunityAgent(StubExtractor(ExtractionResult(conflict_candidates=[conflict])))
    result = agent.analyze(ParsedInput(text="记录", image_data_urls=[], source_description="text"))
    assert result.stage.status.value == "undetermined"
    assert len(result.conflicts[0].evidence) == 2
    assert "时间计划" in result.missing_dimensions
    assert result.timeline.status == FactStatus.CONFLICTING
    assert any(action.action == "确认项目与采购时间计划" for action in result.next_actions)


def test_unreadable_input_does_not_count_budget_as_complete() -> None:
    extraction = ExtractionResult(
        input_quality=InputQuality(status=InputQualityStatus.UNREADABLE, reason="无法读取"),
        budget=BudgetInfo(
            exists=True,
            exists_status=FactStatus.CONFIRMED,
            evidence=[EvidenceItem(quote="预算 60 万", source="image")],
        ),
    )
    agent = OpportunityAgent(StubExtractor(extraction))
    result = agent.analyze(ParsedInput(text="", image_data_urls=[], source_description="image"))
    assert "预算" in result.missing_dimensions
    assert "预算" not in result.confirmed_dimensions


def test_untraceable_text_evidence_is_not_a_confirmed_decision_maker() -> None:
    extraction = ExtractionResult(decision_maker=PersonInfo(
        name="王总",
        status=FactStatus.CONFIRMED,
        evidence=[EvidenceItem(quote="最终由王总决定", source="text")],
    ))
    agent = OpportunityAgent(StubExtractor(extraction))
    result = agent.analyze(ParsedInput(text="客户只说还在了解产品。", image_data_urls=[], source_description="text"))
    assert result.decision_maker.status == FactStatus.UNCONFIRMED
