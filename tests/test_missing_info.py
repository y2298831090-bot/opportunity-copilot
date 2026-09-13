from rules.missing_info import analyze_missing_information
from schemas.opportunity import ExtractionResult, FactItem, FactStatus


def test_missing_critical_fields_generate_ai_actions() -> None:
    result = analyze_missing_information(ExtractionResult())
    assert "预算" in result.missing_fields
    assert any(item.action == "确认客户预算范围" for item in result.ai_actions)


def test_confirmed_need_is_not_missing() -> None:
    extraction = ExtractionResult(customer_needs=[FactItem(value="减少重复咨询", status=FactStatus.CONFIRMED)])
    result = analyze_missing_information(extraction)
    assert "客户需求" not in result.missing_fields
