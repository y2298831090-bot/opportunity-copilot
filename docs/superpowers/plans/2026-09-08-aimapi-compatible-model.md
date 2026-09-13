# AIMAPI Compatible Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable OpenAI-compatible base URL and reasoning effort support for AIMAPI while preserving the evidence-first CRM pipeline.

**Architecture:** Extend only `OpenAIExtractionService`'s configuration boundary. It passes an optional base URL to the official SDK client and an optional reasoning effort to the structured extraction request. Tests replace the SDK with a recording fake, so external credentials and networking remain unnecessary.

**Tech Stack:** Python 3.11, official OpenAI Python SDK, Pydantic, pytest, Streamlit.

---

### Task 1: Lock Provider Configuration Behavior With Tests

**Files:**
- Create: `tests/test_llm_service.py`
- Modify: `services/llm_service.py`

- [ ] **Step 1: Write the failing tests**

```python
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
        api_key="test-key", model="gpt-5.5", base_url="https://www.aimapi.cloud/v1"
    )
    assert _FakeOpenAI.created == {
        "api_key": "test-key", "base_url": "https://www.aimapi.cloud/v1"
    }


def test_reasoning_effort_is_sent_only_when_configured(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_FakeOpenAI))
    service = OpenAIExtractionService(
        api_key="test-key", model="gpt-5.5", reasoning_effort="medium"
    )
    service.extract("客户希望安排演示", [])
    assert _FakeOpenAI.responses.request["reasoning"] == {"effort": "medium"}
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run: `pytest tests/test_llm_service.py -q`

Expected: FAIL because `OpenAIExtractionService` does not accept `base_url` or `reasoning_effort`.

- [ ] **Step 3: Implement the minimal service extension**

```python
def __init__(
    self,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
) -> None:
    self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
    self.reasoning_effort = reasoning_effort or os.getenv("OPENAI_REASONING_EFFORT")
    client_options = {"api_key": self.api_key}
    if self.base_url:
        client_options["base_url"] = self.base_url.rstrip("/")
    self.client = OpenAI(**client_options)

def extract(self, text: str, image_data_urls: list[str]) -> ExtractionResult:
    request_options: dict[str, object] = {
        "model": self.model,
        "input": [{"role": "user", "content": content}],
        "text_format": ExtractionResult,
        "store": False,
    }
    if self.reasoning_effort:
        request_options["reasoning"] = {"effort": self.reasoning_effort}
    response = self.client.responses.parse(**request_options)
```

- [ ] **Step 4: Run the targeted test and verify it passes**

Run: `pytest tests/test_llm_service.py -q`

Expected: PASS.

### Task 2: Surface Configuration In App And Deployment Docs

**Files:**
- Modify: `app.py`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Extend Streamlit Secrets forwarding**

```python
try:
    api_key = st.secrets.get("OPENAI_API_KEY")
    model = st.secrets.get("OPENAI_MODEL")
    base_url = st.secrets.get("OPENAI_BASE_URL")
    reasoning_effort = st.secrets.get("OPENAI_REASONING_EFFORT")
except StreamlitSecretNotFoundError:
    api_key = model = base_url = reasoning_effort = None
return OpenAIExtractionService(
    api_key=api_key,
    model=model,
    base_url=base_url,
    reasoning_effort=reasoning_effort,
)
```

- [ ] **Step 2: Document the AIMAPI deployment values**

```text
OPENAI_BASE_URL=https://www.aimapi.cloud/v1
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=medium
```

State that the API key must be stored only in shell environment variables or Streamlit Secrets, never committed to the repository.

- [ ] **Step 3: Run static and full offline checks**

Run: `python -m compileall . && pytest -q && ruff check .`

Expected: all checks pass without a network request or a real API key.
