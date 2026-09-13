from dataclasses import dataclass

from config.settings import COMPLETENESS_DIMENSIONS
from schemas.opportunity import (
    ActionSourceType,
    ExtractionResult,
    FactStatus,
    NextAction,
    OpportunityResult,
    StageStatus,
)


@dataclass
class MissingInformationResult:
    missing_fields: list[str]
    ai_actions: list[NextAction]
    confirmed_fields: list[str]


def _has_confirmed(items: list) -> bool:
    return any(item.status == FactStatus.CONFIRMED for item in items)


def analyze_missing_information(extraction: ExtractionResult) -> MissingInformationResult:
    checks = [
        ("客户需求", _has_confirmed(extraction.customer_needs), "确认客户核心业务需求", "销售"),
        ("核心场景", _has_confirmed(extraction.core_scenarios), "确认具体使用场景", "销售/售前"),
        ("预算", extraction.budget.exists_status == FactStatus.CONFIRMED, "确认客户预算范围", "销售"),
        ("决策人", extraction.decision_maker.status == FactStatus.CONFIRMED, "确认最终决策人与审批权限", "销售"),
        ("影响人", _has_confirmed(extraction.influencers), "确认技术评估与选型影响人", "销售/售前"),
        ("时间计划", extraction.timeline.status == FactStatus.CONFIRMED, "确认项目与采购时间计划", "销售"),
        ("下一步行动", bool(extraction.agreed_actions), "确认下一步行动、负责人和时间", "销售"),
    ]
    missing = [label for label, confirmed, _, _ in checks if not confirmed]
    confirmed = [label for label, is_confirmed, _, _ in checks if is_confirmed]
    actions = [NextAction(action=action, recommended_owner=owner, source_type=ActionSourceType.AI_RECOMMENDED) for label, is_confirmed, action, owner in checks if not is_confirmed]
    return MissingInformationResult(missing_fields=missing, ai_actions=actions, confirmed_fields=confirmed)


def calculate_completeness(result: OpportunityResult) -> tuple[list[str], list[str], int]:
    checks = {
        "客户需求": _has_confirmed(result.customer_needs),
        "核心场景": _has_confirmed(result.core_scenarios),
        "预算": result.budget.exists_status == FactStatus.CONFIRMED,
        "决策人": result.decision_maker.status == FactStatus.CONFIRMED,
        "影响人": _has_confirmed(result.influencers),
        "时间计划": result.timeline.status == FactStatus.CONFIRMED,
        "下一步行动": any(action.source_type == ActionSourceType.AGREED for action in result.next_actions),
        "商机阶段证据": result.stage.status == StageStatus.CONFIRMED and bool(result.stage.evidence),
    }
    confirmed = [field for field in COMPLETENESS_DIMENSIONS if checks.get(field, False)]
    missing = [field for field in COMPLETENESS_DIMENSIONS if field not in confirmed]
    percentage = round(len(confirmed) / len(COMPLETENESS_DIMENSIONS) * 100)
    return confirmed, missing, percentage
