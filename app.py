from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from agents.extractor import EvidenceExtractor
from agents.opportunity_agent import OpportunityAgent
from schemas.opportunity import (
    ActionSourceType,
    FactItem,
    FactStatus,
    OpportunityResult,
)
from services.input_parser import parse_submission
from services.llm_service import ModelServiceError, OpenAIExtractionService

st.set_page_config(page_title="商机录入与分析助手", page_icon="OC", layout="wide")

FIELD_LABELS = {
    "timeline": "时间计划",
    "budget": "预算",
    "decision_maker": "决策人",
    "influencer": "影响人",
    "next_action": "下一步行动",
    "stage": "商机阶段",
}


def load_samples() -> list[dict[str, str]]:
    return json.loads(Path("samples/sample_cases.json").read_text(encoding="utf-8"))


def configured_model_service() -> OpenAIExtractionService:
    """Prefer Streamlit Secrets in hosted deployments, then environment variables."""
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        model = st.secrets.get("OPENAI_MODEL")
        base_url = st.secrets.get("OPENAI_BASE_URL")
        reasoning_effort = st.secrets.get("OPENAI_REASONING_EFFORT")
    except StreamlitSecretNotFoundError:
        api_key = None
        model = None
        base_url = None
        reasoning_effort = None
    return OpenAIExtractionService(
        api_key=api_key,
        model=model,
        base_url=base_url,
        reasoning_effort=reasoning_effort,
    )


def load_selected_sample(samples: list[dict[str, str]]) -> None:
    selected_name = st.session_state.sample_name
    st.session_state.visit_record = next(item["text"] for item in samples if item["name"] == selected_name)


def clear_current_task() -> None:
    """Remove the current submission and its validated result from the session."""
    st.session_state.visit_record = ""
    st.session_state.pop("result", None)
    st.session_state.upload_revision = st.session_state.get("upload_revision", 0) + 1


def status_text(status: FactStatus) -> str:
    return {FactStatus.CONFIRMED: "已确认", FactStatus.UNCONFIRMED: "未确认", FactStatus.CONFLICTING: "存在冲突"}[status]


def stage_status_text(status: str) -> str:
    return {
        "confirmed": "已确认",
        "needs_review": "需人工复核",
        "undetermined": "无法判断",
    }.get(status, "无法判断")


def evidence_source_text(source: str) -> str:
    return {"text": "文本", "image": "图片"}.get(source, source)


def certainty_text(value: str) -> str:
    return {"explicit": "明确", "uncertain": "不确定"}.get(value, "未确认")


def display_text(value: str) -> str:
    """Translate internal field identifiers in generated display text, never evidence."""
    for field, label in FIELD_LABELS.items():
        value = value.replace(field, label)
    return value


def fact_value(items: list[FactItem]) -> str:
    values = [item.value for item in items if item.status == FactStatus.CONFIRMED]
    return "；".join(values) if values else "未确认"


def budget_value(result: OpportunityResult) -> tuple[str, str]:
    budget = result.budget
    if budget.exists_status == FactStatus.CONFIRMED and budget.amount:
        if budget.amount_status == FactStatus.CONFIRMED:
            return f"已确认存在预算；金额 {budget.amount}", "已确认"
        return f"已确认存在预算；参考金额 {budget.amount}；最终额度待确认", "预算存在已确认 / 金额待确认"
    if budget.exists_status == FactStatus.CONFIRMED:
        return "已确认存在预算；金额未确认", "预算存在已确认 / 金额待确认"
    return "未确认", status_text(budget.exists_status)


def crm_rows(result: OpportunityResult) -> list[dict[str, str]]:
    stage_label = f"{result.stage.code} · {result.stage.name}" if result.stage.code else result.stage.name
    needs = fact_value(result.customer_needs)
    scenarios = fact_value(result.core_scenarios)
    return [
        {"CRM字段": "客户需求", "结果": needs, "状态": "已确认" if needs != "未确认" else "未确认"},
        {"CRM字段": "核心场景", "结果": scenarios, "状态": "已确认" if scenarios != "未确认" else "未确认"},
        {"CRM字段": "预算", "结果": budget_value(result)[0], "状态": budget_value(result)[1]},
        {"CRM字段": "决策人", "结果": result.decision_maker.name or "未确认", "状态": status_text(result.decision_maker.status)},
        {"CRM字段": "影响人", "结果": "；".join(person.name or "未命名" for person in result.influencers if person.status == FactStatus.CONFIRMED) or "未确认", "状态": "已确认" if any(person.status == FactStatus.CONFIRMED for person in result.influencers) else "未确认"},
        {"CRM字段": "时间计划", "结果": result.timeline.value or "未确认", "状态": status_text(result.timeline.status)},
        {"CRM字段": "商机阶段", "结果": stage_label, "状态": stage_status_text(result.stage.status.value)},
        {"CRM字段": "风险", "结果": "；".join(display_text(risk.description) for risk in result.risks) or "未发现明确风险", "状态": "需关注" if result.risks else "无明确风险"},
        {"CRM字段": "下一步行动", "结果": "；".join(display_text(action.action) for action in result.next_actions) or "未确认", "状态": "已生成" if result.next_actions else "未确认"},
        {"CRM字段": "未确认信息", "结果": "；".join(display_text(item.value) for item in result.unconfirmed_items) or "无", "状态": "待确认" if result.unconfirmed_items else "无"},
    ]


def evidence_markdown(items: list) -> list[str]:
    if not items:
        return ["- 无可用原始证据"]
    lines: list[str] = []
    for item in items:
        speaker = f"；说话人：{item.speaker}" if item.speaker else ""
        lines.append(
            f"- {item.quote}（来源：{evidence_source_text(item.source)}{speaker}；{certainty_text(item.certainty.value)}）"
        )
    return lines


def build_markdown_report(result: OpportunityResult) -> str:
    """Build a human-readable export from the final validated result only."""
    stage_label = f"{result.stage.code} · {result.stage.name}" if result.stage.code else result.stage.name
    lines = [
        "# 商机分析报告",
        "",
        "## 当前商机阶段",
        "",
        f"- 阶段：{stage_label}",
        f"- 状态：{stage_status_text(result.stage.status.value)}",
        f"- 理由：{display_text(result.stage.reason)}",
        "",
        "### 关键证据",
    ]
    lines.extend(evidence_markdown(result.stage.evidence[:2]))
    lines.extend(
        [
            "",
            "### 信息完整度",
            f"- 已确认：{('、'.join(result.confirmed_dimensions) or '暂无')}",
            f"- 待补充：{('、'.join(result.missing_dimensions) or '暂无')}",
            f"- 完整度：{result.completeness_percent}%",
        ]
    )
    if result.manual_review:
        lines.append("- 商机阶段存在无法自动消解的关键信息冲突，建议人工复核。")
    elif result.conflicts:
        lines.append("- 部分字段存在冲突，已在风险与证据区域标记；其他已确认字段不受影响。")
    if result.input_quality.status.value == "unreadable":
        lines.append("- 无法判断，建议人工复核。")
    lines.extend(
        [
            "",
            "## CRM 商机卡",
            "",
            "| CRM字段 | 结果 | 状态 |",
            "| --- | --- | --- |",
        ]
    )
    lines.extend(f"| {row['CRM字段']} | {row['结果']} | {row['状态']} |" for row in crm_rows(result))
    lines.extend(["", "## 风险与待确认", "", "### 商机风险"])
    technical_requirements = [risk for risk in result.risks if risk.risk_type.value == "technical_requirement"]
    business_risks = [risk for risk in result.risks if risk.category == "business" and risk not in technical_requirements]
    information_gaps = [risk for risk in result.risks if risk.category == "information"]
    if business_risks:
        lines.extend(f"- {display_text(risk.description)}" for risk in business_risks)
    else:
        lines.append("- 未发现明确风险")
    lines.extend(["", "### 关键方案要求 / 技术关注项"])
    if technical_requirements:
        lines.extend(f"- {display_text(risk.description)}" for risk in technical_requirements)
    else:
        lines.append("- 暂无")
    lines.extend(["", "### CRM 信息缺口"])
    if information_gaps:
        lines.extend(f"- {display_text(risk.description)}" for risk in information_gaps)
    else:
        lines.append("- 暂无")
    lines.extend(["", "### 未确认信息"])
    if result.unconfirmed_items:
        lines.extend(f"- {display_text(item.value)}" for item in result.unconfirmed_items)
    else:
        lines.append("- 暂无")
    lines.extend(["", "### 已确认下一步"])
    agreed_actions = [action for action in result.next_actions if action.source_type == ActionSourceType.AGREED]
    if agreed_actions:
        lines.extend(f"- {action.action}｜Owner：{action.recommended_owner}｜时间：{action.time}" for action in agreed_actions)
    else:
        lines.append("- 暂无")
    lines.extend(["", "### AI 建议"])
    ai_actions = [action for action in result.next_actions if action.source_type == ActionSourceType.AI_RECOMMENDED]
    if ai_actions:
        lines.extend(f"- {action.action}｜Owner：{action.recommended_owner}｜时间：{action.time}" for action in ai_actions)
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 证据与规则", "", "### 商机阶段", f"- 命中规则：{result.stage.matched_rule or '无法可靠判断'}"])
    lines.extend(evidence_markdown(result.stage.evidence))
    for label, evidence in [("预算", result.budget.evidence), ("决策人", result.decision_maker.evidence), ("时间计划", result.timeline.evidence)]:
        lines.extend(["", f"### {label}"])
        lines.extend(evidence_markdown(evidence))
    return "\n".join(lines) + "\n"


def evidence_lines(items: list) -> None:
    if not items:
        st.caption("无可用原始证据")
        return
    for item in items:
        speaker = f" · {item.speaker}" if item.speaker else ""
        st.markdown(f"> {item.quote}\n\n`{evidence_source_text(item.source)}{speaker} · {certainty_text(item.certainty.value)}`")


def render_result(result: OpportunityResult) -> None:
    stage_label = f"{result.stage.code} · {result.stage.name}" if result.stage.code else result.stage.name
    top_left, top_right = st.columns([2, 1])
    with top_left:
        st.subheader("当前商机阶段")
        st.markdown(f"### {stage_label}")
        st.write(display_text(result.stage.reason))
        if result.stage.evidence:
            st.caption("关键证据")
            evidence_lines(result.stage.evidence[:2])
    with top_right:
        st.subheader("信息完整度")
        st.metric("已确认", f"{result.completeness_percent}%")
        st.progress(result.completeness_percent)
        st.caption("已确认：" + ("、".join(result.confirmed_dimensions) or "暂无"))
        st.caption("待补充：" + ("、".join(result.missing_dimensions) or "暂无"))
    if result.manual_review:
        st.warning("商机阶段存在无法自动消解的关键信息冲突，建议人工复核。")
    elif result.conflicts:
        st.info("部分字段存在冲突，已在风险与证据区域标记；其他已确认字段不受影响。")
    if result.input_quality.status.value == "unreadable":
        st.error("无法判断，建议人工复核。")

    crm_tab, risk_tab, evidence_tab = st.tabs(["CRM 商机卡", "风险与待确认", "证据与规则"])
    with crm_tab:
        st.dataframe(crm_rows(result), column_order=["CRM字段", "结果", "状态"], hide_index=True, use_container_width=True)
    with risk_tab:
        st.subheader("商机风险")
        technical_requirements = [risk for risk in result.risks if risk.risk_type.value == "technical_requirement"]
        business_risks = [risk for risk in result.risks if risk.category == "business" and risk not in technical_requirements]
        if business_risks:
            for risk in business_risks:
                st.error(display_text(risk.description))
                evidence_lines(risk.evidence)
        else:
            st.info("未提取到有原始证据支持的业务风险。")
        st.subheader("关键方案要求 / 技术关注项")
        if technical_requirements:
            for requirement in technical_requirements:
                st.info(display_text(requirement.description))
                evidence_lines(requirement.evidence)
        else:
            st.info("暂无明确技术关注项。")
        st.subheader("CRM 信息缺口")
        for risk in (risk for risk in result.risks if risk.category == "information"):
            st.warning(display_text(risk.description))
        st.subheader("未确认信息")
        if result.unconfirmed_items:
            for item in result.unconfirmed_items:
                st.write(display_text(item.value))
                evidence_lines(item.evidence)
        else:
            st.info("暂无明确的不确定信息。")
        st.subheader("下一步行动")
        customer_actions = [action for action in result.next_actions if action.source_type == ActionSourceType.AGREED]
        ai_actions = [action for action in result.next_actions if action.source_type == ActionSourceType.AI_RECOMMENDED]
        for label, actions in [("双方已确认 / 已约定行动", customer_actions), ("AI 建议", ai_actions)]:
            st.markdown(f"**{label}**")
            if not actions:
                st.caption("暂无")
            for action in actions:
                st.write(f"{display_text(action.action)}｜Owner：{action.recommended_owner}｜时间：{action.time}")
                evidence_lines(action.evidence)
    with evidence_tab:
        st.subheader("结论 → 原始证据 → 命中规则")
        st.markdown(f"**商机阶段：{stage_label}**")
        evidence_lines(result.stage.evidence)
        st.caption("命中规则：" + (result.stage.matched_rule or "无法可靠判断"))
        critical_fields = [
            (
                "预算",
                budget_value(result)[0],
                result.budget.evidence,
                "仅当存在明确原始证据时确认预算存在或金额；模糊金额必须降级。",
            ),
            (
                "决策人",
                result.decision_maker.name or status_text(result.decision_maker.status),
                result.decision_maker.evidence,
                "仅当原文明确说明最终决定、拍板或与项目/采购相关的审批权限时确认。",
            ),
            (
                "时间计划",
                result.timeline.value or status_text(result.timeline.status),
                result.timeline.evidence,
                "仅确认明确时间表达；不确定表述或冲突信息必须保留为待确认。",
            ),
        ]
        for label, conclusion, evidence, rule in critical_fields:
            st.markdown(f"**{label}：{conclusion}**")
            evidence_lines(evidence)
            st.caption("命中规则：" + rule)
        if result.conflicts:
            st.markdown("**冲突信息**")
            for conflict in result.conflicts:
                st.write(display_text(conflict.description))
                evidence_lines(conflict.evidence)
    payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    report_column, json_column = st.columns(2)
    with report_column:
        st.download_button(
            "导出分析报告（Markdown）",
            data=build_markdown_report(result),
            file_name="opportunity_analysis_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with json_column:
        st.download_button("下载结构化 JSON", data=payload, file_name="opportunity_result.json", mime="application/json", use_container_width=True)


def main() -> None:
    st.title("商机录入与分析助手")
    st.caption("Opportunity Copilot")
    st.write("将非结构化销售拜访记录转换为有证据、可追溯、符合业务规则的 CRM 商机信息。")
    samples = load_samples()
    with st.sidebar:
        st.header("样例入口")
        st.selectbox("加载示例", [sample["name"] for sample in samples], key="sample_name")
        st.button("加载到输入框", use_container_width=True, on_click=load_selected_sample, args=(samples,))
        st.divider()
        st.caption("支持文本、PNG、JPG、JPEG 与 PDF。文件最大 10 MB，PDF 最多 20 页。")
    text = st.text_area("销售拜访记录", key="visit_record", height=260, placeholder="粘贴客户拜访记录、会议纪要或沟通内容...")
    uploaded = st.file_uploader(
        "上传文件",
        type=["png", "jpg", "jpeg", "pdf"],
        accept_multiple_files=False,
        key=f"uploaded_file_{st.session_state.get('upload_revision', 0)}",
    )
    analyze_column, clear_column = st.columns([4, 1])
    with analyze_column:
        analyze_requested = st.button("开始分析", type="primary", use_container_width=True)
    with clear_column:
        st.button(
            "清空",
            use_container_width=True,
            on_click=clear_current_task,
            help="清空当前输入、上传文件和上一轮分析结果。",
        )
    if analyze_requested:
        try:
            parsed = parse_submission(text, uploaded)
            with st.spinner("正在提取证据并应用确定性 CRM 规则..."):
                agent = OpportunityAgent(EvidenceExtractor(configured_model_service()))
                result = agent.analyze(parsed)
            st.session_state.result = result
        except (ValueError, ModelServiceError) as exc:
            st.error(str(exc))
    if result := st.session_state.get("result"):
        render_result(result)


if __name__ == "__main__":
    main()
