import os

import pytest

from schemas.opportunity import RiskType, SignalType, SpeakerSide
from services.llm_service import OpenAIExtractionService

pytestmark = pytest.mark.live


def _extract(record: str):
    if os.getenv("RUN_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_TESTS=1 to enable external model calls.")
    return OpenAIExtractionService().extract(record, [])


def test_live_customer_agreed_demo_has_customer_side_signal() -> None:
    result = _extract("客户客服负责人明确表示重复咨询很多，并同意下周安排产品 Demo。")
    signals = [signal for signal in result.stage_signals if signal.type == SignalType.DEMO_AGREED]
    assert signals
    assert any(evidence.speaker_side == SpeakerSide.CUSTOMER for signal in signals for evidence in signal.evidence)


def test_live_seller_planned_demo_does_not_create_demo_agreement() -> None:
    result = _extract("客户存在重复咨询问题。我准备下周向客户演示产品。")
    assert not any(signal.type == SignalType.DEMO_AGREED for signal in result.stage_signals)


def test_live_supplier_comparison_is_competition_not_supplier_decision() -> None:
    result = _extract("客户目前还在比较多个供应商，尚未确定最终选哪家。")
    assert any(risk.risk_type == RiskType.COMPETITION for risk in result.risk_candidates)
    assert not any(signal.type == SignalType.SUPPLIER_DECISION_STARTED for signal in result.stage_signals)


def test_live_uncertainties_are_preserved() -> None:
    result = _extract("预算金额尚未确定，部署方式待评估，测试通过标准尚未明确。")
    assert len(result.uncertain_items) >= 3


def test_live_multiple_core_scenarios_are_preserved() -> None:
    result = _extract("一期需要验证知识库问答和工单回复辅助两个业务场景。")
    assert len(result.core_scenarios) >= 2


def test_live_uncertain_timeline_evidence_is_marked_uncertain() -> None:
    result = _extract("客户表示可能年底采购。")
    assert any(
        evidence.certainty.value == "uncertain"
        for item in result.uncertain_items
        for evidence in item.evidence
    )
