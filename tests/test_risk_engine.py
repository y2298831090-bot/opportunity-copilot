import pytest

from rules.risk_engine import analyze_risks
from schemas.opportunity import (
    Certainty,
    EvidenceItem,
    ExtractionResult,
    RiskItem,
    RiskType,
    SignalType,
    StageSignal,
)


def test_uncertain_pause_signal_is_not_a_confirmed_business_risk() -> None:
    extraction = ExtractionResult(stage_signals=[StageSignal(
        type=SignalType.PROJECT_PAUSED,
        certainty=Certainty.EXPLICIT,
        evidence=[EvidenceItem(quote="项目可能暂停", source="text", certainty=Certainty.UNCERTAIN)],
    )])
    risks = analyze_risks(extraction, [])
    assert risks == []


@pytest.mark.parametrize("quote", ["客户还在比较几家供应商。", "目前同时评估多个厂商的方案。", "项目还有其他竞品参与。"])
def test_supplier_comparison_maps_to_competition_risk(quote: str) -> None:
    extraction = ExtractionResult(risk_candidates=[RiskItem(
        category="business", risk_type=RiskType.COMPETITION, description="客户存在供应商竞争。",
        evidence=[EvidenceItem(quote=quote)],
    )])

    risks = analyze_risks(extraction, [])

    assert [risk.risk_type for risk in risks] == [RiskType.COMPETITION]


def test_validation_gap_creates_validation_risk() -> None:
    extraction = ExtractionResult(risk_candidates=[RiskItem(
        category="business", risk_type=RiskType.VALIDATION, description="验收标准尚未量化。",
        evidence=[EvidenceItem(quote="测试成功条件尚未明确。")],
    )])

    assert analyze_risks(extraction, [])[0].risk_type == RiskType.VALIDATION


def test_semantic_risk_deduplication_merges_evidence() -> None:
    extraction = ExtractionResult(risk_candidates=[
        RiskItem(category="business", risk_type=RiskType.COMPETITION, affected_fields=["supplier"], description="供应商竞争。", evidence=[EvidenceItem(quote="在比较多家供应商。")]),
        RiskItem(category="business", risk_type=RiskType.COMPETITION, affected_fields=["supplier"], description="客户正在评估其他厂商。", evidence=[EvidenceItem(quote="正在评估其他厂商。")]),
    ])

    risks = analyze_risks(extraction, [])

    assert len(risks) == 1
    assert len(risks[0].evidence) == 2
