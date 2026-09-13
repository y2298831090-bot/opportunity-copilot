# Opportunity Copilot — Repository Instructions

## 1. Project mission

This repository implements a production-style interview demo named:

**Opportunity Copilot / 商机录入与分析助手**

The application converts unstructured sales visit records into structured CRM opportunity information.

The primary product requirement is **not summarization quality**. The primary requirement is:

> Produce structured CRM information that is evidence-backed, rule-constrained, explainable, and conservative under uncertainty.

Before changing product behavior, read:

* `docs/PRODUCT_SPEC.md`

Treat that document as the source of truth for product behavior and business rules.

---

## 2. Non-negotiable business principles

The following rules MUST NOT be weakened.

### 2.1 Evidence-first

Only information explicitly expressed by the customer or directly observable from the source may be stored as confirmed facts.

Do not convert assumptions, common sense, job titles, or model guesses into facts.

Examples:

* "王总参加了会议" does NOT imply 王总 is the decision maker.
* "客户挺感兴趣" does NOT imply purchase intent is confirmed.
* "可能年底采购" does NOT become a confirmed timeline.
* "预算应该有几十万" does NOT become a confirmed budget amount.

---

### 2.2 Uncertain statements

Expressions including, but not limited to:

* 可能
* 应该
* 感觉
* 大概会
* 估计
* 或许
* 挺感兴趣
* 看起来
* probably
* maybe
* likely

must not become confirmed CRM facts unless the surrounding text independently provides an explicit confirmation.

They may be retained as:

* unconfirmed information;
* uncertainty evidence;
* risk/context information.

---

### 2.3 Missing information

Never invent missing:

* names;
* amounts;
* dates;
* authority;
* responsibilities;
* customer intentions;
* procurement status.

Missing information must be represented as:

**未确认**

or, when the application cannot reasonably evaluate the source:

**无法判断 / 建议人工复核**

---

### 2.4 Critical evidence requirement

The following conclusions MUST contain original evidence:

* budget;
* decision maker;
* timeline;
* opportunity stage.

A critical conclusion without supporting evidence must fail closed and be downgraded to unconfirmed or undetermined.

---

### 2.5 Contradictions

Never resolve contradictory customer statements by silently selecting one.

Both statements must be preserved.

Contradictions must be surfaced as:

* a conflict;
* a risk or information-quality issue;
* an item requiring confirmation.

If a contradiction affects opportunity-stage eligibility, stage status must be marked as requiring review rather than silently selecting the more optimistic stage.

---

### 2.6 Opportunity stage

The LLM MUST NOT make the final S0–S5 decision.

The LLM may extract evidence and stage-relevant signals.

Final stage determination MUST be performed by deterministic Python business logic according to `docs/PRODUCT_SPEC.md`.

The stage engine must be independently unit-testable without an LLM or network connection.

---

### 2.7 Next actions

Every next action must distinguish between:

1. a customer-agreed action; and
2. an AI/system recommendation.

Never present an AI recommendation as something the customer agreed to.

Each action must contain:

* action;
* recommended owner;
* time.

If no time was agreed, use:

**待确认**

---

## 3. Required architecture boundaries

Keep responsibilities separated.

### Input parser

Responsible only for:

* text input;
* image preparation;
* PDF text extraction;
* PDF page rendering fallback;
* file validation.

It must not perform CRM business decisions.

### LLM extractor

Responsible for:

* extracting facts;
* preserving evidence;
* identifying uncertainty;
* identifying stage-relevant signals;
* identifying candidate contradictions.

It must not assign the final sales stage.

### Stage engine

Responsible only for deterministic S0–S5 evaluation.

It must not call the LLM.

### Conflict/risk/missing-information logic

Responsible for transforming extracted facts into:

* conflicts;
* CRM completeness gaps;
* risks;
* unconfirmed items.

### Validator

Acts as the final guardrail.

It MUST fail closed.

Examples:

* confirmed budget amount with no evidence -> downgrade;
* decision maker with no authority evidence -> downgrade;
* confirmed timeline supported only by uncertain wording -> downgrade;
* stage with no qualifying evidence -> downgrade or mark undetermined.

### UI

The Streamlit UI must call the orchestration/service layer.

Do not place core business logic directly inside Streamlit rendering code.

---

## 4. Technology constraints

Preferred stack:

* Python 3.11+
* Streamlit
* Pydantic
* PyMuPDF
* official OpenAI Python SDK
* pytest
* ruff

Avoid unnecessary frameworks.

Do NOT add LangChain, CrewAI, AutoGen, a vector database, SQL database, authentication framework, or other major dependency unless the user explicitly requests it.

This project does not require multi-agent orchestration.

Use a simple, understandable pipeline.

---

## 5. LLM integration rules

All model access must live behind a provider/service abstraction.

Required environment variables:

* `OPENAI_API_KEY`
* `OPENAI_MODEL`

Never hard-code secrets.

Never commit `.env`.

Provide:

* `.env.example`
* Streamlit secrets instructions in README.

Use structured model output validated with Pydantic.

If the model returns invalid structured output:

1. retry safely at most once where appropriate;
2. otherwise return a clear application error;
3. never silently invent missing fields.

Do not guess unsupported SDK method signatures.

If external SDK behavior cannot be verified in the current environment, isolate it behind the adapter and clearly report that limitation.

---

## 6. Offline testability

Unit tests MUST NOT require:

* an OpenAI API key;
* internet access;
* a real LLM call.

Business logic must be tested using deterministic fixtures.

A real-model integration test may exist, but it must be optional and skipped unless explicitly enabled.

---

## 7. Input handling

Required inputs:

* pasted text;
* JPG;
* JPEG;
* PNG;
* PDF.

For PDF:

1. attempt native text extraction first;
2. if meaningful text cannot be extracted, use page-image fallback for vision analysis;
3. enforce reasonable file/page limits;
4. never execute uploaded content.

If image/PDF content is unreadable, incomplete, or heavily obscured, return:

**无法判断，建议人工复核**

and explain why.

---

## 8. User-interface requirements

The main application language is Chinese.

Required UI areas:

1. input area;
2. analyze button;
3. opportunity stage summary;
4. CRM information;
5. risk and unconfirmed information;
6. evidence and rules;
7. information completeness indicator;
8. JSON result download;
9. built-in example inputs.

Do not expose raw chain-of-thought.

Show concise rule explanations and source evidence instead.

---

## 9. Code quality

Prefer:

* small pure functions;
* typed Python;
* explicit enums;
* Pydantic schemas;
* dependency injection for the model provider;
* deterministic business logic;
* meaningful function names.

Avoid:

* giant `app.py`;
* duplicated stage logic;
* business rules embedded only in prompts;
* hidden magic constants;
* catch-all `except Exception: pass`;
* fake successful fallbacks.

---

## 10. Required repository structure

Use approximately this structure unless a technically necessary improvement is justified:

```text
.
├── AGENTS.md
├── app.py
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── config/
│   ├── stage_rules.yaml
│   └── crm_rules.yaml
│
├── docs/
│   └── PRODUCT_SPEC.md
│
├── prompts/
│   └── extraction_prompt.txt
│
├── schemas/
│   ├── __init__.py
│   └── opportunity.py
│
├── services/
│   ├── __init__.py
│   ├── llm_service.py
│   ├── input_parser.py
│   └── document_parser.py
│
├── agents/
│   ├── __init__.py
│   ├── extractor.py
│   ├── validator.py
│   └── opportunity_agent.py
│
├── rules/
│   ├── __init__.py
│   ├── stage_engine.py
│   ├── conflict_engine.py
│   ├── missing_info.py
│   └── risk_engine.py
│
├── samples/
│   └── sample_cases.json
│
└── tests/
    ├── test_stage_engine.py
    ├── test_validator.py
    ├── test_missing_info.py
    ├── test_conflicts.py
    └── test_samples.py
```

---

## 11. Mandatory validation commands

After implementation or any meaningful code change, run:

```bash
python -m compileall .
pytest -q
ruff check .
```

Fix failures caused by the implementation.

Do not claim that tests passed unless they actually ran and passed.

If a command cannot run because of an environment limitation, clearly report the limitation.

---

## 12. Definition of done

Do not consider the task complete until all of the following are true:

* the Streamlit application can start;
* text analysis works;
* image input is implemented;
* PDF input is implemented;
* CRM fields follow the required schema;
* S0–S5 decisions use deterministic rules;
* critical conclusions include evidence;
* vague statements are not converted into facts;
* missing information is marked unconfirmed;
* contradictions are surfaced;
* unreadable input can produce manual-review output;
* built-in samples are present;
* automated tests cover core rules;
* README explains local run and deployment;
* no secrets are committed;
* validation commands have been run.

When finishing a task, summarize:

1. what was implemented;
2. files changed;
3. tests actually run;
4. remaining limitations, if any.
