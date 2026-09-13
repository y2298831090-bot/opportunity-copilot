from schemas.opportunity import (
    Certainty,
    ConflictItem,
    ExtractionResult,
    Polarity,
    RiskItem,
    RiskType,
    SignalType,
)


def _is_explicit_positive(signal) -> bool:
    return signal.certainty == Certainty.EXPLICIT and signal.polarity == Polarity.POSITIVE and any(
        evidence.certainty == Certainty.EXPLICIT and evidence.polarity == Polarity.POSITIVE
        for evidence in signal.evidence
    )


def analyze_risks(
    extraction: ExtractionResult,
    missing_fields: list[str],
    conflicts: list[ConflictItem] | None = None,
) -> list[RiskItem]:
    risks: list[RiskItem] = list(extraction.risk_candidates)
    for signal in extraction.stage_signals:
        if signal.type in {SignalType.PROJECT_PAUSED, SignalType.PROCUREMENT_CANCELLED, SignalType.NEED_INVALIDATED} and _is_explicit_positive(signal):
            risks.append(RiskItem(
                category="business",
                risk_type=RiskType.PROJECT_PAUSE_OR_CANCEL,
                affected_fields=["need"],
                description="客户明确提到项目暂停、采购取消或需求失效。",
                evidence=signal.evidence,
            ))
    for conflict in conflicts or []:
        is_timeline = "timeline" in conflict.affected_fields or "时间" in conflict.field
        risks.append(RiskItem(
            category="business",
            risk_type=RiskType.TIMELINE_CONFLICT if is_timeline else RiskType.OTHER,
            affected_fields=conflict.affected_fields or [conflict.field],
            description=f"{conflict.field}存在冲突，需要人工确认。",
            evidence=conflict.evidence,
        ))
    risks.extend(
        RiskItem(
            category="information",
            risk_type=RiskType.INFORMATION_GAP,
            affected_fields=[field],
            description=f"{field}未确认，影响 CRM 信息完整度。",
        )
        for field in missing_fields
    )
    return _deduplicate_risks(risks)


def _deduplicate_risks(risks: list[RiskItem]) -> list[RiskItem]:
    grouped: dict[tuple[RiskType, tuple[str, ...], str], RiskItem] = {}
    for risk in risks:
        description_key = "" if risk.risk_type != RiskType.OTHER else risk.description
        key = (risk.risk_type, tuple(sorted(risk.affected_fields)), description_key)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = risk.model_copy(deep=True)
            continue
        quotes = {evidence.quote for evidence in existing.evidence}
        existing.evidence.extend(evidence for evidence in risk.evidence if evidence.quote not in quotes)
        if len(risk.description) > len(existing.description):
            existing.description = risk.description
    return list(grouped.values())
