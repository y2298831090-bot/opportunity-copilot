from __future__ import annotations

from agents.extractor import EvidenceExtractor
from agents.validator import finalize_opportunity, sanitize_extraction
from rules.conflict_engine import (
    analyze_conflicts,
    apply_conflicts,
    stage_conflict_exists,
)
from rules.missing_info import analyze_missing_information, calculate_completeness
from rules.risk_engine import analyze_risks
from rules.stage_engine import determine_stage
from schemas.opportunity import OpportunityResult
from services.input_parser import ParsedInput


class OpportunityAgent:
    def __init__(self, extractor: EvidenceExtractor) -> None:
        self.extractor = extractor

    def analyze(self, parsed_input: ParsedInput) -> OpportunityResult:
        extraction = sanitize_extraction(
            self.extractor.extract(parsed_input),
            parsed_input.text,
            has_visual_source=parsed_input.has_visual_source,
        )
        conflicts = analyze_conflicts(extraction)
        extraction = apply_conflicts(extraction, conflicts)
        missing = analyze_missing_information(extraction)
        stage = determine_stage(
            extraction.stage_signals,
            extraction.initial_contact_evidence,
            has_stage_conflict=stage_conflict_exists(conflicts),
        )
        result = OpportunityResult(
            input_quality=extraction.input_quality,
            customer_needs=extraction.customer_needs,
            core_scenarios=extraction.core_scenarios,
            budget=extraction.budget,
            decision_maker=extraction.decision_maker,
            influencers=extraction.influencers,
            timeline=extraction.timeline,
            stage=stage,
            conflicts=conflicts,
            risks=analyze_risks(extraction, missing.missing_fields, conflicts),
            next_actions=extraction.agreed_actions + missing.ai_actions,
            unconfirmed_items=extraction.uncertain_items,
        )
        result.manual_review = result.stage.status.value == "needs_review"
        result = finalize_opportunity(result)
        confirmed, missing_fields, percentage = calculate_completeness(result)
        result.confirmed_dimensions = confirmed
        result.missing_dimensions = missing_fields
        result.completeness_percent = percentage
        return result
