# Opportunity Copilot / 商机录入与分析助手

## 1. Product objective

Build a live, interview-ready Agent that converts sales visit records into structured CRM opportunity information.

The system must be conservative and auditable.

The core pipeline is:

```text
Text / Image / PDF
        ↓
Input parsing
        ↓
LLM evidence extraction
        ↓
Structured Pydantic result
        ↓
Deterministic business-rule engine
        ↓
Conflict / missing / risk analysis
        ↓
Final validation
        ↓
CRM opportunity card
```

The application is not a generic conversational chatbot.

---

# 2. Required CRM fields

The final user-facing result must contain:

1. 客户需求
2. 核心场景
3. 预算
4. 决策人
5. 影响人
6. 时间计划
7. 商机阶段
8. 风险
9. 下一步行动
10. 未确认信息

Additional useful fields:

11. 原始证据
12. 阶段判断依据
13. 信息完整度
14. 冲突信息
15. 是否建议人工复核

---

# 3. Source-of-truth business rules

## 3.1 Fact boundary

Only information explicitly expressed by the customer or directly observable from the record may become a confirmed fact.

The system must not use general business knowledge to fill missing CRM information.

---

## 3.2 Inference handling

Statements containing speculative or uncertain language must not become confirmed facts.

Examples include:

* 可能
* 应该
* 大概
* 估计
* 感觉
* 看起来
* 挺感兴趣
* 或许
* probably
* maybe
* likely

Such statements may be retained as unconfirmed information.

---

## 3.3 Missing information

When amount, name, time, authority, responsibility, or other required information is absent, return:

`未确认`

Do not manufacture values.

---

## 3.4 Required evidence

The following fields require original source evidence:

* budget;
* decision maker;
* timeline;
* opportunity stage.

Evidence should preserve a short verbatim source quote.

Where possible also preserve a source locator:

* `text`
* `image`
* `PDF page N`

---

## 3.5 Contradictions

If the source contains conflicting statements:

* preserve both;
* do not choose one silently;
* mark conflict;
* expose it as risk or pending confirmation;
* if it affects stage determination, stage status becomes `needs_review`.

---

# 4. Sales-stage rules

The stage engine must evaluate the stages from strongest to weakest, but only when all required conditions for that stage are satisfied.

The final stage decision must be made by Python business logic, not by the LLM.

---

## S5 — 赢单/签约

Condition:

The source explicitly confirms at least one:

* contract signed;
* formal order confirmed.

Examples:

* “合同已经签了。”
* “正式订单已经确认。”
* “PO 已经下来了。”

Must NOT trigger from:

* “准备签合同”
* “应该会签”
* “合同在讨论”
* “预计下周签”

---

## S4 — 决策审批

Condition:

Explicitly entered at least one:

* internal project establishment;
* internal approval;
* supplier decision/selection.

Examples:

* “项目已经立项。”
* “现在正在走内部审批。”
* “已经进入供应商评选。”

Must NOT trigger from:

* “准备立项”
* “可能要走审批”
* “之后应该由领导审批”

unless another explicit statement independently confirms the status.

---

## S3 — 商务评估

Conditions:

### Condition A

At least one is explicitly being or has been discussed:

* budget;
* quotation;
* procurement process;
* contract terms.

### Condition B

The underlying customer need remains valid.

Examples:

* “今年这个项目预算大约 60 万。”
* “请你们本周提供正式报价。”
* “后面采购部门会走比价流程。”

Must NOT trigger merely from a speculative commercial statement.

If commercial discussion exists but the record also explicitly says the project is paused/cancelled or the requirement is no longer valid, mark the stage as requiring manual review rather than silently returning S3.

---

## S2 — 方案验证

Condition:

The customer explicitly agrees to at least one:

* demonstration;
* trial;
* POC;
* technical exchange;
* technical validation;
* solution evaluation.

Examples:

* “下周你们过来做个 Demo。”
* “可以先试用一周。”
* “我们安排技术团队跟你们交流一下。”

Important:

The salesperson's unilateral plan does NOT qualify.

Example:

* “我准备下周给客户演示。”

This alone is not S2.

---

## S1 — 需求初探

Condition:

At least one explicit:

* business problem;
* use case.

Examples:

* “客服现在有大量重复咨询。”
* “希望 AI 自动处理售后问答。”

---

## S0 — 线索

Condition:

Initial contact exists, but no explicit qualifying need or use case exists.

Example:

* “第一次拜访客户，介绍了公司和产品。”

---

# 5. Stage result data model

Use a result similar to:

```json
{
  "status": "confirmed",
  "code": "S2",
  "name": "方案验证",
  "reason": "客户明确同意进行产品演示。",
  "evidence": [
    {
      "quote": "下周你们可以给我们做个 Demo。",
      "source": "text"
    }
  ],
  "candidate_stages": []
}
```

Allowed `status`:

```text
confirmed
needs_review
undetermined
```

If `needs_review` or `undetermined`, `code` may be null when a defensible stage cannot be selected.

Never fabricate a stage merely because CRM normally requires one.

---

# 6. Internal extraction model

The LLM should extract facts rather than generate the final CRM judgment.

Recommended core models:

```python
EvidenceItem
FactItem
BudgetInfo
PersonInfo
TimelineInfo
StageSignal
ConflictItem
NextActionCandidate
ExtractionResult
OpportunityResult
```

---

## 6.1 EvidenceItem

Conceptual schema:

```json
{
  "quote": "原始记录中的短原话",
  "source": "text | image | PDF page N",
  "speaker": "客户/销售/具体人物/未知",
  "certainty": "explicit | uncertain",
  "polarity": "positive | negative"
}
```

Do not require the model to invent a speaker name when the speaker is unclear.

---

## 6.2 Fact status

Use:

```text
confirmed
unconfirmed
conflicting
```

---

# 7. Stage signals

The extraction layer may identify only structured stage signals.

Suggested enum:

```text
business_problem
use_case

demo_agreed
trial_agreed
technical_exchange_agreed
solution_evaluation_agreed

budget_discussed
quotation_discussed
procurement_process_discussed
contract_terms_discussed

need_active
need_invalidated
project_paused
procurement_cancelled

internal_project_approved
approval_process_started
supplier_decision_started

contract_signed
order_confirmed
```

Each signal must contain:

```json
{
  "type": "demo_agreed",
  "certainty": "explicit",
  "polarity": "positive",
  "evidence": [...]
}
```

Only appropriate explicit positive signals may satisfy a stage rule.

---

# 8. Customer need

Extract the actual business need rather than a generic product category.

Good:

> “希望减少客服人工处理大量重复售后咨询。”

Bad:

> “需要 AI。”

Keep the source evidence.

---

# 9. Core scenario

Extract concrete use situations.

Examples:

* 售后客服自动问答
* 企业内部知识库问答
* 销售培训助手

Do not infer scenarios absent from the source.

---

# 10. Budget

Budget must distinguish between:

1. whether a budget exists;
2. whether an amount is confirmed.

Example:

Source:

> “预算已经批了，但具体额度我还不知道。”

Correct:

```text
预算状态：已确认存在预算
金额：未确认
```

Example:

> “预算应该有几十万。”

Correct:

```text
预算状态：未确认
预算线索：可能为几十万元
```

Do not convert this into a confirmed amount.

---

# 11. Decision maker

A person may be labeled a decision maker only if explicit authority evidence exists.

Valid evidence includes statements such as:

* 最终由王总决定
* 王总是最终拍板人
* 采购需要王总审批
* 最终审批人是王总

Invalid reasoning:

* title contains “总”
* senior job title
* attended meeting
* spoke most often
* salesperson thinks the person is important

If authority is not explicit:

```text
决策人：未确认
```

---

# 12. Influencer

An influencer requires evidence that the person's opinion, evaluation, technical selection, or recommendation materially affects the process.

Example:

> “李经理负责前期技术评估，他的意见会影响选型。”

This may identify 李经理 as an influencer.

A person appearing in the meeting alone is not enough.

---

# 13. Timeline

Only explicit customer timing statements become confirmed timelines.

Example:

> “希望 10 月完成测试。”

Confirmed.

Example:

> “可能年底采购。”

Unconfirmed.

Preserve the speculative statement under unconfirmed information.

---

# 14. Next actions

Every next action must contain:

```json
{
  "action": "",
  "recommended_owner": "",
  "time": "",
  "source_type": "customer_agreed | ai_recommended",
  "evidence": []
}
```

If no time is agreed:

```text
待确认
```

Examples of allowed recommended owners:

* 销售
* 售前
* 销售/售前

Do not invent a named employee.

---

## 14.1 Customer-agreed actions

Example:

> “下周三你们过来做 Demo。”

Output:

```text
动作：安排产品 Demo
负责人：销售/售前
时间：下周三
类型：客户已约定
```

---

## 14.2 AI recommendations

When required information is missing, generate practical follow-up actions.

Example:

```text
动作：确认客户预算范围
负责人：销售
时间：待确认
类型：AI 建议
```

The UI must visually distinguish recommended actions from customer commitments.

---

# 15. Risk model

Risks can contain two categories.

## 15.1 Business risks

These require explicit supporting evidence.

Examples:

* project paused;
* customer demand weakening;
* conflicting timeline;
* procurement cancelled;
* explicit competitor pressure.

Do not invent competitor information.

---

## 15.2 CRM information risks

These may be generated deterministically from missing fields.

Examples:

* 预算未确认
* 决策人未确认
* 时间计划未确认
* 采购流程未确认
* 下一步没有明确时间

These are information-quality risks, not claims about the customer.

Make that distinction clear in the UI.

---

# 16. Information completeness

Display a simple deterministic completeness percentage.

Recommended core completeness dimensions:

1. customer need
2. core scenario
3. budget
4. decision maker
5. influencer
6. timeline
7. next action
8. stage evidence

Calculate:

```text
confirmed dimensions / total dimensions × 100
```

Do not use an LLM to calculate this score.

Show which dimensions remain incomplete.

---

# 17. Conflict handling

Examples:

Source:

> “业务负责人希望 10 月上线。”

Later:

> “采购负责人说今年不一定启动采购。”

Correct behavior:

```text
时间计划：存在冲突 / 待确认
```

Conflict:

```text
证据 A：业务负责人希望 10 月上线。
证据 B：采购负责人表示今年不一定启动采购。
```

Add a recommended next action:

```text
动作：确认正式项目与采购时间计划
负责人：销售
时间：待确认
```

Never delete either statement.

---

# 18. Input-quality handling

The extraction result should include:

```json
{
  "input_quality": {
    "status": "readable | partially_readable | unreadable",
    "reason": ""
  }
}
```

For unreadable input:

* do not pretend analysis succeeded;
* mark critical fields unconfirmed;
* stage may be `undetermined`;
* display:

`无法判断，建议人工复核`

Examples:

* image too blurry;
* large parts obscured;
* PDF contains unreadable scanned pages;
* source extraction failed.

---

# 19. Input support

## Text

Use text directly.

Reject empty or nearly empty submissions with a clear validation message.

---

## Images

Support:

```text
.jpg
.jpeg
.png
```

Send visual input through the configured multimodal model.

Do not implement a separate fragile OCR pipeline unless technically necessary.

---

## PDF

Use PyMuPDF.

Process:

```text
PDF
 ↓
native text extraction
 ↓
meaningful text?
 ├─ yes → use extracted text
 └─ no  → render pages → multimodal analysis
```

Enforce reasonable limits, for example:

* maximum 10 MB upload;
* maximum 20 analyzed pages.

If a document exceeds the limit, tell the user rather than silently ignoring arbitrary content.

---

# 20. Exact LLM extraction prompt contract

Create `prompts/extraction_prompt.txt` containing a prompt following this specification.

The implementation may inject the structured schema separately, but the semantic instructions below must remain.

```text
你是“商机录入与分析助手”中的事实抽取模块。

你的任务不是替销售做主观判断，也不是自由补全 CRM。
你的唯一任务是从销售拜访记录中提取能够被原始记录支持的信息，
并为后续确定性业务规则提供结构化事实与原始证据。

【最高优先级原则】

1. 事实边界
只有客户明确表达，或记录中可以直接观察到的信息，才能标记为 confirmed。

不得利用常识、职位高低、公司惯例或语言模型推测补全事实。

2. 推断与不确定表达
“可能、应该、估计、大概、感觉、看起来、挺感兴趣、或许、
probably、maybe、likely”等表述不得转换为确定事实。

这类信息应标记为 uncertain，并保留原文。

3. 缺失信息
没有出现姓名、金额、日期、权限、职责或采购状态时，不得补全。
应保持为空或 unconfirmed。

4. 原始证据
客户需求、核心场景以及所有候选事实应尽可能保留简短原话。
预算、决策人、时间计划以及销售阶段相关信号必须保留原始证据。

不得改写证据为比原文更确定的说法。

5. 决策人
只有原文明确说明某人拥有最终决定、审批、拍板等权限时，
才可以提取 decision-maker 候选。

职位为“总经理”“负责人”“总监”等本身不构成决策权限证据。

6. 影响人
只有原文明确说明某人负责技术评估、选型、推荐，
或其意见明确影响决策时，才可以提取 influencer 候选。

7. 预算
必须区分：
- 是否明确存在预算；
- 是否明确预算金额。

“预算批了但金额不知道”意味着预算存在，但金额未确认。
“应该有几十万预算”仍属于未确认。

8. 时间计划
只有明确的客户时间表达才能成为 confirmed timeline。
“可能年底”“预计可能”“应该下个月”等必须保持 uncertain。

9. 商机阶段
你不得输出最终 S0-S5 商机阶段结论。

你只能提取阶段判断需要的 stage signals，包括：

business_problem
use_case
demo_agreed
trial_agreed
technical_exchange_agreed
solution_evaluation_agreed
budget_discussed
quotation_discussed
procurement_process_discussed
contract_terms_discussed
need_active
need_invalidated
project_paused
procurement_cancelled
internal_project_approved
approval_process_started
supplier_decision_started
contract_signed
order_confirmed

特别注意：
“销售准备给客户做 Demo”不能提取 demo_agreed。
只有客户明确同意演示才能提取 demo_agreed。

10. 矛盾
如果原始记录中存在互相冲突的表述：
- 同时保留双方；
- 创建 conflict candidate；
- 不自行选择其中一个正确。

11. 下一步
区分：
- 客户明确约定的下一步；
- 后续系统可能生成的 AI 建议。

事实抽取阶段只把客户明确约定的行动作为 customer_agreed action。
不要把你自己的建议伪装成客户承诺。

12. 输入质量
如果图片、扫描件或记录内容无法可靠读取，
必须将 input_quality 标记为 partially_readable 或 unreadable，
并说明原因。

13. 输出
严格按照调用方提供的结构化 schema 输出。
不要输出额外解释文本。
不要输出 Markdown。
不要输出思维过程。
```

---

# 21. Validator rules

The final validator must enforce at least:

### Budget

If a budget amount is marked confirmed but has no explicit evidence:

```text
downgrade to unconfirmed
```

### Decision maker

If a decision maker has no explicit authority evidence:

```text
remove confirmed decision-maker classification
→ mark decision maker unconfirmed
```

### Timeline

If a confirmed timeline is supported only by uncertain evidence:

```text
downgrade to unconfirmed
```

### Stage

If a stage has no qualifying stage signals:

```text
do not return that confirmed stage
```

### Unreadable source

If input quality is unreadable:

```text
stage.status = undetermined
manual_review = true
```

The validator must fail closed.

---

# 22. UI specification

Use Streamlit.

Main page title:

```text
商机录入与分析助手
Opportunity Copilot
```

Subtitle:

```text
将非结构化销售拜访记录转换为有证据、可追溯、
符合业务规则的 CRM 商机信息。
```

---

## 22.1 Input section

Provide:

### Text

Large text area.

### File upload

Accepted:

* PNG
* JPG
* JPEG
* PDF

Primary button:

```text
开始分析
```

---

# 23. Results layout

At the top show:

```text
当前商机阶段
S2 · 方案验证
```

Show a concise reason and primary evidence.

Also show:

```text
信息完整度：62%
```

---

## Tab 1 — CRM 商机卡

Display all required CRM fields clearly.

Recommended table:

| CRM字段 | 结果 | 状态 |
| ----- | -- | -- |

Use:

```text
已确认
未确认
存在冲突
无法判断
```

Do not use false green-success indicators for uncertain information.

---

## Tab 2 — 风险与待确认

Show separately:

### 商机风险

Evidence-backed business risks.

### CRM 信息缺口

Deterministically generated missing-information risks.

### 未确认信息

Include speculative statements and missing critical information.

### 下一步行动

Separate:

* 客户已约定
* AI 建议

---

## Tab 3 — 证据与规则

For critical conclusions show:

```text
结论
↓
原始证据
↓
命中规则
```

Example:

```text
商机阶段：S2 方案验证

原始证据：
“下周你们可以给我们做个 Demo。”

命中规则：
客户明确同意演示、试用、技术交流或方案评估之一。
```

This tab is essential for demonstrating rule-based reasoning during the interview.

---

# 24. JSON export

Provide a button:

```text
下载结构化 JSON
```

The downloaded result must be the validated final CRM object, not the raw LLM response.

---

# 25. Built-in sample cases

Add sample selector/buttons in the sidebar.

At minimum include:

* S0
* S1
* S2
* S3
* S4
* S5
* 模糊表达
* 冲突信息

---

# 26. Mandatory deterministic test cases

## Case A — S0

Input:

```text
今天第一次拜访客户，主要介绍了公司和产品。
客户表示先了解一下，目前没有讨论具体业务需求。
```

Expected:

```text
stage = S0
```

---

## Case B — S1

Input:

```text
客户目前售后团队每天需要人工处理大量重复咨询，
希望减少客服人员在重复问题上的工作量。
```

Expected:

```text
need = confirmed
stage = S1
```

---

## Case C — S2

Input:

```text
客户目前客服团队人工处理大量重复售后问题，
希望尝试使用 AI 自动回答常见问题。
客户表示：“下周你们可以过来做一次产品 Demo。”
```

Expected:

```text
stage = S2
```

Evidence must contain:

```text
下周你们可以过来做一次产品 Demo。
```

---

## Case D — salesperson plan is not S2

Input:

```text
客户提到客服重复咨询很多。
我准备下周给客户演示一下我们的产品。
```

Expected:

```text
stage = S1
```

Must NOT become S2.

---

## Case E — S3

Input:

```text
客户确认需要建设内部知识库客服系统。
上周已经完成产品演示。
客户说：“今年这个项目预算大约 60 万，
请你们本周提供正式报价，
之后采购部门会走比价流程。”
```

Expected:

```text
stage = S3
budget = confirmed
```

---

## Case F — S4

Input:

```text
客户的知识库项目已经正式立项，
目前正在公司内部走采购审批流程。
```

Expected:

```text
stage = S4
```

---

## Case G — S5

Input:

```text
客户确认双方合同已经签署，
正式采购订单也已经确认。
```

Expected:

```text
stage = S5
```

---

## Case H — vague information

Input:

```text
王总感觉挺感兴趣，
这个项目可能年底会采购，
预算应该有几十万。
```

Expected:

```text
budget amount = unconfirmed
timeline = unconfirmed
decision maker = unconfirmed
```

The statements must appear under unconfirmed information.

---

## Case I — decision-maker hallucination prevention

Input:

```text
今天王总、李经理和采购专员一起参加了会议。
李经理负责后续技术接口。
```

Expected:

```text
decision maker = unconfirmed
```

Do NOT infer 王总 as decision maker.

---

## Case J — budget exists but amount unknown

Input:

```text
客户表示项目预算已经审批，
但是目前还没有确认具体额度。
```

Expected:

```text
budget exists = confirmed
budget amount = unconfirmed
```

---

## Case K — conflicting timeline

Input:

```text
业务负责人表示希望 10 月完成上线。
随后采购负责人说项目今年可能不会启动采购。
```

Expected:

```text
timeline status = conflicting or needs_review
conflict preserved
next action includes timeline confirmation
```

Do not silently select October.

---

## Case L — missing action time

Input:

```text
客户希望我们后续提供一份详细技术方案，
但双方没有约定具体日期。
```

Expected:

```text
action = 提供详细技术方案
time = 待确认
```

---

# 27. Configuration files

Create `config/stage_rules.yaml` so stage criteria are explicit and inspectable.

The actual deterministic stage logic may use typed constants/enums in Python, but YAML must reflect the business rules for transparency.

Do not let YAML and Python silently drift apart.

Create `config/crm_rules.yaml` for:

* required CRM fields;
* critical evidence fields;
* completeness dimensions;
* upload limits;
* other non-secret product configuration.

---

# 28. README requirements

README must contain exactly the practical information an interviewer needs.

Sections:

```text
1. 项目简介
2. 在线访问入口
3. 支持的输入
4. Agent 工作原理
5. 规则如何使用
6. 输出字段
7. 本地运行方法
8. 环境变量
9. Streamlit 部署方法
10. 自测样例
11. 测试命令
12. 已知限制
```

Clearly state:

> LLM 负责自然语言事实抽取；确定性 Python 规则引擎负责最终销售阶段判断。

Also explain:

> 模糊、缺失、矛盾和无法识别的信息不会被自动补全。

Do not claim that OCR/vision or LLM output is infallible.

---

# 29. Environment configuration

`.env.example` should contain only placeholders:

```text
OPENAI_API_KEY=
OPENAI_MODEL=
```

Never put a real API key into the repository.

For Streamlit deployment, README should explain using Streamlit Secrets.

---

# 30. Dependency behavior

Prefer a small dependency set.

Expected packages may include:

```text
streamlit
openai
pydantic
PyMuPDF
PyYAML
python-dotenv
pytest
ruff
```

Pin compatible version ranges when appropriate.

Do not add unnecessary dependencies.

---

# 31. Error handling

User-facing errors must be understandable Chinese messages.

Examples:

### Missing API key

```text
未配置模型服务，请设置 OPENAI_API_KEY。
```

### Empty input

```text
请输入销售拜访记录或上传文件后再开始分析。
```

### Unsupported file

```text
暂不支持该文件格式。
```

### Unreadable content

```text
当前内容无法可靠识别，建议重新上传更清晰的文件或人工复核。
```

### Model/service error

```text
分析服务暂时不可用，本次结果未生成，请稍后重试。
```

Never display stack traces to ordinary users.

---

# 32. Security and privacy basics

Do not:

* execute uploaded files;
* expose API keys;
* print secrets;
* persist uploaded customer data unless explicitly required;
* send data anywhere except the configured model provider.

The application does not need a database for this interview task.

---

# 33. Final acceptance criteria

The implementation is accepted only if:

### Functional

* text works;
* JPG/JPEG/PNG works;
* PDF works;
* all 10 CRM fields appear;
* evidence appears;
* stage appears;
* risks appear;
* next actions appear;
* unconfirmed information appears;
* JSON can be downloaded.

### Rule correctness

* speculative budget is not confirmed;
* speculative timeline is not confirmed;
* senior title does not imply decision maker;
* salesperson-planned Demo does not create S2;
* customer-agreed Demo creates S2;
* commercial discussion + valid need creates S3;
* explicit approval creates S4;
* contract/order creates S5;
* contradictions are preserved;
* missing information is not invented.

### Engineering

* business logic is separated from UI;
* stage engine is deterministic;
* Pydantic structured output is used;
* tests do not require a live LLM;
* secrets are not committed;
* README exists;
* `.env.example` exists;
* application can start.

### Validation

These commands should pass:

```bash
python -m compileall .
pytest -q
ruff check .
```
