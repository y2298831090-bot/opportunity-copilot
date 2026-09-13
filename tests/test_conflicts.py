import pytest

from rules.conflict_engine import analyze_conflicts, apply_conflicts
from schemas.opportunity import (
    Certainty,
    ConflictItem,
    EvidenceItem,
    ExtractionResult,
    FactStatus,
)


def test_conflicting_timeline_is_preserved_and_marked_for_review() -> None:
    extraction = ExtractionResult(conflict_candidates=[ConflictItem(
        field="时间计划",
        description="上线与采购启动时间相互冲突",
        evidence=[
            EvidenceItem(quote="希望 10 月完成上线", source="text", certainty=Certainty.EXPLICIT),
            EvidenceItem(quote="今年可能不会启动采购", source="text", certainty=Certainty.UNCERTAIN),
        ],
    )])
    conflicts = analyze_conflicts(extraction)
    assert conflicts[0].field == "时间计划"
    assert len(conflicts[0].evidence) == 2


@pytest.mark.parametrize("field_text", ["timeline", "时间计划", "客户内部时间安排", "任意展示文案"])
def test_conflict_application_uses_affected_fields_for_timeline(field_text: str) -> None:
    result = apply_conflicts(ExtractionResult(), [ConflictItem(field=field_text, description="冲突", affected_fields=["timeline"])])

    assert result.timeline.status == FactStatus.CONFLICTING


def test_conflict_application_uses_affected_fields_for_budget() -> None:
    result = apply_conflicts(ExtractionResult(), [ConflictItem(field="任意展示文案", description="冲突", affected_fields=["budget"])])

    assert result.budget.exists_status == FactStatus.CONFLICTING


def test_conflict_application_uses_affected_fields_for_decision_maker() -> None:
    result = apply_conflicts(ExtractionResult(), [ConflictItem(field="任意展示文案", description="冲突", affected_fields=["decision_maker"])])

    assert result.decision_maker.status == FactStatus.CONFLICTING
