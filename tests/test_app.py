import streamlit as st
from streamlit.testing.v1 import AppTest

from app import build_markdown_report, certainty_text, display_text, stage_status_text
from schemas.opportunity import (
    ConflictItem,
    EvidenceItem,
    FactItem,
    FactStatus,
    InputQuality,
    OpportunityResult,
    RiskItem,
    RiskType,
    StageResult,
    StageStatus,
)


def _app() -> AppTest:
    return AppTest.from_file("app.py").run()


def test_sidebar_sample_populates_text_input() -> None:
    app = _app()
    sample_button = next(button for button in app.button if button.label == "加载到输入框")
    sample_button.click().run()
    assert "第一次拜访客户" in app.text_area[0].value


def test_missing_model_key_is_a_user_facing_error(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(st.secrets, "_secrets", {})
    app = _app()
    app.text_area[0].input("客户希望了解产品").run()
    analyze_button = next(button for button in app.button if button.label == "开始分析")
    analyze_button.click().run()
    assert "未配置模型服务，请设置 OPENAI_API_KEY。" in app.error[0].value


def test_ui_status_helpers_do_not_expose_internal_enums() -> None:
    assert stage_status_text("needs_review") == "需人工复核"
    assert stage_status_text("undetermined") == "无法判断"
    assert certainty_text("explicit") == "明确"


def test_clear_button_resets_prior_input_and_result() -> None:
    app = _app()
    app.text_area[0].input("上一条销售拜访记录").run()
    app.session_state["result"] = OpportunityResult(input_quality=InputQuality())

    clear_button = next(button for button in app.button if button.label == "清空")
    clear_button.click().run()

    assert app.text_area[0].value == ""
    assert "result" not in app.session_state


def test_markdown_export_uses_validated_opportunity_result() -> None:
    result = OpportunityResult(
        input_quality=InputQuality(),
        customer_needs=[FactItem(value="减少重复咨询", status=FactStatus.CONFIRMED)],
    )

    report = build_markdown_report(result)

    assert "# 商机分析报告" in report
    assert "## CRM 商机卡" in report
    assert "减少重复咨询" in report
    assert "## 风险与待确认" in report
    assert "## 证据与规则" in report


def test_markdown_export_includes_stage_summary_and_completeness_details() -> None:
    result = OpportunityResult(
        input_quality=InputQuality(),
        stage=StageResult(
            code="S3",
            name="商务评估",
            status=StageStatus.CONFIRMED,
            reason="需求持续有效，已讨论报价。",
            evidence=[EvidenceItem(quote="客户要求本周提供正式报价。", speaker="客户负责人")],
        ),
        completeness_percent=88,
        confirmed_dimensions=["客户需求", "下一步行动"],
        missing_dimensions=["时间计划"],
        conflicts=[ConflictItem(field="timeline", description="时间计划存在冲突。")],
    )

    report = build_markdown_report(result)

    assert "### 关键证据" in report
    assert "客户要求本周提供正式报价。" in report
    assert "### 信息完整度" in report
    assert "- 已确认：客户需求、下一步行动" in report
    assert "- 待补充：时间计划" in report
    assert "部分字段存在冲突，已在风险与证据区域标记；其他已确认字段不受影响。" in report


def test_markdown_separates_business_risks_and_information_gaps() -> None:
    result = OpportunityResult(
        input_quality=InputQuality(),
        risks=[
            RiskItem(category="business", risk_type=RiskType.COMPETITION, description="存在供应商竞争。"),
            RiskItem(category="information", risk_type=RiskType.INFORMATION_GAP, description="时间计划未确认。"),
        ],
    )

    report = build_markdown_report(result)

    risk_section = report.split("## 风险与待确认", maxsplit=1)[1]
    business_section, gap_section = risk_section.split("### CRM 信息缺口")
    assert "存在供应商竞争。" in business_section
    assert "时间计划未确认。" not in business_section
    assert "时间计划未确认。" in gap_section


def test_user_facing_output_has_no_internal_field_names() -> None:
    assert display_text("timeline存在冲突，需要确认decision_maker。") == "时间计划存在冲突，需要确认决策人。"
