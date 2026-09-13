# Opportunity Copilot / 商机录入与分析助手

## 1. 项目简介

这是一个面试现场可演示的 Streamlit Agent，把非结构化销售拜访记录转成带证据、可追溯且保守的 CRM 商机信息。

## 2. 在线访问入口

在线 Demo：部署后填写

## 3. 支持的输入

粘贴文本、PNG、JPG、JPEG 和 PDF。PDF 优先提取原生文本；文本不足时会渲染 PDF 页面并交给支持视觉的模型分析。单文件最大 10 MB，PDF 最多 20 页。

## 4. Agent 工作原理

`Input -> Input Parser -> LLM Evidence Extractor -> Pydantic Structured Extraction -> Deterministic Stage Engine -> Conflict/Missing/Risk Analysis -> Validator -> CRM Opportunity Result -> Streamlit UI`

## 5. 规则如何使用

LLM 负责从拜访记录抽取带证据事实、说话主体所属方、候选风险与已约定行动；Python 确定性规则引擎根据题目给出的 S0-S5 条件判断销售阶段；Validator 再检查证据、模糊表述、来源可追溯性和缺失信息，防止没有依据的信息进入 CRM。

模糊、缺失、矛盾和无法识别的信息不会被自动补全。LLM 不输出最终阶段；双方已约定行动和 AI 建议在界面中分开展示。扫描 PDF 的视觉证据会保留页码来源；无法可靠读取时会返回“无法判断，建议人工复核”。

`config/crm_rules.yaml` 是实际读取的上传限制与信息完整度维度配置。`config/stage_rules.yaml` 是与 Python 确定性阶段引擎保持一致的可审查规则说明；最终阶段判断的运行时 source of truth 为 `rules/stage_engine.py` 与 `agents/validator.py`。

## 6. 输出字段

客户需求、核心场景、预算、决策人、影响人、时间计划、商机阶段、风险、下一步行动、未确认信息，以及原始证据、冲突信息、信息完整度和人工复核标识。

## 7. 本地运行方法

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## 8. 环境变量

复制 `.env.example` 的字段并在 shell 或部署平台中设置：

```text
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=
OPENAI_REASONING_EFFORT=
```

对于 Streamlit Community Cloud，在 App settings 的 Secrets 中配置同名键。不要提交 `.env` 或 Secrets 文件。

使用 AIMAPI 等 OpenAI-compatible 服务时，填写该服务提供的令牌和模型 ID。例如当前 AIMAPI 配置可使用：

```text
OPENAI_BASE_URL=https://www.aimapi.cloud/v1
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=medium
```

`OPENAI_API_KEY` 仍应只填写在 shell 环境变量或 Streamlit Secrets 中，不能写入代码、`.env.example` 或 Git。

## 9. Streamlit 部署方法

将仓库推送到 GitHub，在 Streamlit Community Cloud 选择 `app.py` 作为入口，填写 Secrets 后部署。若需要中国境内稳定访问，请使用有中国大陆节点的云平台或自有服务器，并通过该平台生成实际公网 URL；本仓库不虚构线上链接。

## 10. 自测样例

侧边栏内置 S0-S5、模糊表达和冲突信息八组样例，加载后可直接分析。

## 11. 测试命令

```bash
python -m compileall .
pytest -q
ruff check .
```

可选真实模型回归默认跳过，只有明确设置环境变量后才会访问模型服务：

```bash
RUN_LIVE_TESTS=1 pytest -m live
```

## 12. 已知限制

真实图片/PDF 视觉识别和 OpenAI 调用需要配置可用模型与网络，仓库的单元测试不调用外部服务。模型输出会经过 Pydantic 与确定性 Validator，但源文件严重模糊时仍会返回“无法判断，建议人工复核”。
