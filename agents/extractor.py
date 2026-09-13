from schemas.opportunity import ExtractionResult
from services.input_parser import ParsedInput
from services.llm_service import OpenAIExtractionService


class EvidenceExtractor:
    def __init__(self, service: OpenAIExtractionService) -> None:
        self.service = service

    def extract(self, parsed_input: ParsedInput) -> ExtractionResult:
        return self.service.extract(
            parsed_input.text,
            parsed_input.image_data_urls,
            parsed_input.visual_source_labels,
        )
