import sys
from types import SimpleNamespace

from schemas.opportunity import ExtractionResult
from services.llm_service import OpenAIExtractionService


class _FakeResponses:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(output_parsed=ExtractionResult())


class _FakeOpenAI:
    created: dict[str, object] | None = None
    responses = _FakeResponses()

    def __init__(self, **kwargs: object) -> None:
        type(self).created = kwargs


def test_configured_base_url_is_passed_to_sdk(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))

    OpenAIExtractionService(
        api_key="test-key",
        model="gpt-5.5",
        base_url="https://www.aimapi.cloud/v1",
    )

    assert _FakeOpenAI.created == {
        "api_key": "test-key",
        "base_url": "https://www.aimapi.cloud/v1",
    }


def test_reasoning_effort_is_sent_when_configured(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))
    service = OpenAIExtractionService(
        api_key="test-key",
        model="gpt-5.5",
        reasoning_effort="medium",
    )

    service.extract("客户希望安排演示", [])

    assert _FakeOpenAI.responses.request is not None
    assert _FakeOpenAI.responses.request["reasoning"] == {"effort": "medium"}
