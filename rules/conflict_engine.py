from schemas.opportunity import (
    ConflictItem,
    ExtractionResult,
    FactItem,
    FactStatus,
    PersonInfo,
    TimelineInfo,
)


def analyze_conflicts(extraction: ExtractionResult) -> list[ConflictItem]:
    return extraction.conflict_candidates


def apply_conflicts(extraction: ExtractionResult, conflicts: list[ConflictItem]) -> ExtractionResult:
    result = extraction.model_copy(deep=True)
    for conflict in conflicts:
        field = conflict.field
        scopes = set(conflict.affected_fields)
        if not scopes:
            field_text = field.lower()
            if "时间" in field or "timeline" in field_text:
                scopes.add("timeline")
            elif "预算" in field or "budget" in field_text:
                scopes.add("budget")
            elif "决策" in field or "审批人" in field or "decision_maker" in field_text:
                scopes.add("decision_maker")
        if "timeline" in scopes:
            result.timeline = TimelineInfo(status=FactStatus.CONFLICTING, evidence=conflict.evidence)
        elif "budget" in scopes:
            result.budget.exists = None
            result.budget.exists_status = FactStatus.CONFLICTING
            result.budget.amount = None
            result.budget.amount_status = FactStatus.CONFLICTING
            result.budget.evidence = conflict.evidence
        elif "decision_maker" in scopes:
            result.decision_maker = PersonInfo(status=FactStatus.CONFLICTING, evidence=conflict.evidence)
        result.uncertain_items.append(
            FactItem(value=f"{field}存在冲突，待确认", status=FactStatus.CONFLICTING, evidence=conflict.evidence)
        )
    return result


def stage_conflict_exists(conflicts: list[ConflictItem]) -> bool:
    stage_relevant_scopes = {"need", "stage"}
    legacy_scope = {
        "需求": {"need"},
        "阶段": {"stage"},
        "取消": {"need"},
        "暂停": {"need"},
    }
    for conflict in conflicts:
        scopes = set(conflict.affected_fields)
        if not scopes:
            scopes = {
                scope
                for keyword, mapped_scopes in legacy_scope.items()
                if keyword in conflict.field
                for scope in mapped_scopes
            }
        if scopes & stage_relevant_scopes:
            return True
    return False
