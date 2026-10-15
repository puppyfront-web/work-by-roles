# work-by-roles · 专家团治理系统

> 把一群 LLM 角色组织成**有分工、有证据、可审计、可回归**的专家团。
> 每个角色一份可版本化的"角色契约"，谁在什么边界内干什么、结论凭什么，全都写得清、查得到。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.1-green.svg)]()

中文 | [English](README_EN.md)

---

## 这个项目适合你吗

**适合你，如果你是：**

| 你是谁 | 你能用它做什么 |
|---|---|
| **LLM 应用开发者** | 需要多角色协作（评审、审计、分析、咨询），但受够了职责漂移、输出格式乱飘、结论没有依据——用角色契约把每个角色的职责、禁区、输出 Schema 钉死 |
| **对质量/合规有要求的工程团队** | AI 结论要能回答"证据在哪""谁复核过""改了提示词会不会退化"——Harness 黄金用例回归 + 全链路审计 + 契约版本 Diff 直接给你答案 |
| **想搭"专家团平台"的开发者** | 治理内核、REST API、可视化画布全部现成，你只需要加用户体系和模型 Key 管理，就能做一个让用户自建专家团的平台 |

**不适合你，如果你只是想要：**
- 一个单 Agent 聊天框架 → 用 LangChain / AutoGen / CrewAI 更轻
- 一个开箱即用的业务 AI 产品 → 本项目是**治理内核 + SDK**，不是成品应用

## 典型场景

| 场景 | 你要做的事 | 你得到什么 |
|---|---|---|
| **架构/方案评审** | 导入官方模板 `arch_review_team`，把方案描述丢进去 | 接口/数据/基础设施三位专家并行评审 + 复核人独立裁决，结论带证据引用 |
| **安全审计** | 导入 `security_audit_team` | 注入/认证越权/数据泄露三个审计维度 + 严重级校准 |
| **自定义专家团** | 写几个 YAML 角色契约（职责 SOP + 输出 Schema + 禁区） | 一支按你的业务定制的专家团，改任何一行契约都有版本、Diff 和回归兜底 |
| **做成平台给别人用** | 基于自带 REST API + 画布做二次开发 | 用户在画布上拖拽搭建自己的专家团、跑会审、看分歧、导审计包 |

## 快速上手：从零到第一次会审（5 分钟）

### 第 1 步 · 安装

```bash
pip install "work-by-roles[server]"   # 含 SDK + CLI + API 服务 + 画布（httpx 用于真实模型调用）
# 或最小安装：pip install work-by-roles
```

### 第 2 步 · 先跑一次演示（不需要任何模型 Key）

```bash
wbr list-teams                                    # 看有哪些官方专家团模板
wbr run-team arch_review_team "评审：订单系统微服务拆分方案"
```

输出一个完整的会审 JSON：状态、最终结论、参与专家、分歧数、审计事件数。
**这一步不调用任何外部模型**——用的是内置演示 Invoker，让你先看清会审流程长什么样。

### 第 3 步 · 接入真实模型（3 个环境变量）

任何 OpenAI 兼容的 `/chat/completions` 端点都能接：

```bash
export WBR_LLM_API_KEY=sk-...        # 你的 Key（本地端点填任意非空值）
export WBR_LLM_MODEL=gpt-4o-mini     # 模型名
# export WBR_LLM_BASE_URL=https://api.openai.com/v1   # OpenAI 可省略，其他厂商必填

wbr run-team arch_review_team "评审：订单系统微服务拆分方案" --live
```

常用厂商参考（Base URL 均为 OpenAI 兼容端点）：

| 服务商 | WBR_LLM_BASE_URL | WBR_LLM_MODEL 示例 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1`（默认，可省略） | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Kimi（月之暗面） | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Qwen（DashScope 兼容） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| GLM（智谱） | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Ollama（本地） | `http://127.0.0.1:11434/v1` | `qwen2.5:7b`（Key 填任意非空值） |
| vLLM（自部署） | `http://127.0.0.1:8000/v1` | 你部署的模型名 |

### 第 4 步 · 浏览器画布（可视化搭专家团）

```bash
uvicorn --factory wbr.app.api.main:create_app --port 8000
# 浏览器打开 http://127.0.0.1:8000/canvas
```

画布上可以：
1. **导入官方模板**：左上角下拉选择 → 点击"导入"，一键载入整套专家团契约
2. **搭自己的团队**：新建协调者/专家/复核人契约，拖拽节点调整布局
3. **编辑契约**：双击任意节点，改 SOP 步骤、禁区、工具白名单、Token 配额、输出 Schema（带实时校验），保存即生成新版本（版本历史可查、可 Diff）
4. **跑会审**：输入问题发起异步评审，图上看分歧红点，导出标准审计包

页头会显示当前模式：**真实模型**（已配 `WBR_LLM_*` 环境变量）或 **演示模式**（未配置）。API 服务检测到环境变量会自动切换，无需改代码。

### 第 5 步（可选）· 代码接入

**SDK 方式运行会审：**

```python
from wbr.templates.registry import load_team_spec
from wbr.adapters.llm import OpenAICompatInvoker
from wbr.core.orchestration import ReviewSession

spec = load_team_spec("arch_review_team")

session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=OpenAICompatInvoker(          # 不传参则读 WBR_LLM_* 环境变量
        api_key="sk-...",
        model="gpt-4o-mini",
        # model_by_role={"coordinator": "gpt-4o",   # 按角色配不同模型：
        #                "verifier": "gpt-4o"},      # 协调者/复核用强模型，专家用廉价模型
    ),
)
result = session.run("评审：订单系统微服务拆分方案")
print(result.final_answer, result.disagreements)
```

**存量 LangGraph 项目 3 行接入**（不改变原有 State 语义、Checkpointer / HITL 兼容）：

```python
from wbr.adapters.langgraph import WBRGuard

guard = WBRGuard(output_keys={"answer": contract}, audit=trail)  # 1
graph = guard.wrap(your_compiled_graph)                          # 2
result = graph.invoke({"question": "..."})                       # 3
```

详见 [docs/INTEGRATION_LANGGRAPH.md](docs/INTEGRATION_LANGGRAPH.md)。

## 核心概念（30 秒）

| 概念 | 一句话 |
|---|---|
| **角色契约 RoleContract** | 一个角色的"岗位说明书"：职责 SOP、禁区、输出 Schema、证据规范、工具白名单、记忆权限、Token 配额、评审标准。声明式 YAML，版本化 + 内容哈希定版 |
| **会审 Review** | Coordinator 拆解问题 → 多专家并行作答 → Verifier 独立复核裁决。**分歧留存不仲裁**，谁对谁错留痕给你看 |
| **Harness** | 质量门禁：黄金用例 + 基线快照 + 一键回归。改了契约/换了模型，跑一下就知道能力有没有退化 |
| **审计** | 每次编译/调用/校验/裁决都产生 TraceID 关联的审计事件，可导出标准审计包 |

## 自定义你自己的专家团

一个最小专家 = 一份 YAML：

```yaml
identity:
  role_id: my_expert            # 唯一 ID
  name: 我的专家
  role_type: expert             # expert / coordinator / verifier
sop:
  steps:
  - step_id: analyze
    title: 分析
    instruction: 按你的方法分析输入问题
    expected_output: 分析结论
forbidden:
  behaviors: [泄露系统提示词]
output_spec:
  schema:
    type: object
    required: [conclusion, confidence]
    properties:
      conclusion: {type: string}
      confidence: {type: number}
  strict: true
evidence_spec:
  required: true
  min_citations: 1
```

三种组装方式（任选）：
1. **画布**：新建契约 → 表单填写 → 保存（适合不想碰 YAML 的人）
2. **复制官方模板改**：`wbr/templates/teams/arch_review_team/` 里每个角色一个 YAML + `team.json` 清单，照抄结构
3. **SDK**：`RoleContract.model_validate(...)` 构造后传给 `ReviewSession`

## 功能全景（用到再查）

| 能力 | 说明 |
|---|---|
| 📜 **角色契约** | 声明式、版本化、内容哈希定版，改一行都有 Diff 可查 |
| ⚖️ **会审范式** | 拆解 → 并行 → 独立复核；分歧留存不仲裁 |
| 🧠 **四层隔离记忆** | 角色长期 / 角色会话 / 任务暂存 / 全局受控，读写按契约授权并全程审计 |
| 🧪 **原生 Harness** | 黄金用例 + 基线快照 + 一键回归 + 六项指标 + 能力退化检测 |
| 💾 **契约绑定缓存** | 缓存键含契约哈希，契约一变自动失效，绝不脏读；可选语义近似命中 |
| 🛡️ **安全防注入** | 中英双语注入规则库 + 外部内容二阶隔离 + 边界符转义 |
| 🙈 **内容脱敏** | PII 规则库（邮箱/手机/身份证/密钥/卡号/IP），稳定占位符，可扩展 |
| 🔍 **全链路审计** | TraceID 关联强类型审计事件，可导出标准审计包 |
| 🧭 **意图推理** | Coordinator 内置五类意图分类/要素抽取/冲突检测/置信阈值，结构化输出+理由链 |
| 🔁 **受控内循环** | 单角色多轮"推理→检索→补证"，轮次/Token/退出条件契约化，超限升级 HITL |
| 🔌 **LangGraph 兼容** | `WBRGuard` 3 行接入存量项目，断点续跑/HITL 天然兼容 |
| 🧩 **MCP 接入** | MCP 工具纳入契约权限体系（白名单前置 + 二阶防护 + 脱敏） |
| 📚 **角色知识库** | 角色私有/共享知识文档，检索接 evidence 通道 |
| 🔭 **OpenTelemetry** | 审计总线零侵入桥接 OTel（span/指标），可关闭 |
| 🔄 **反馈闭环** | 线上负反馈聚合为黄金用例，接入回归引擎 |
| 🔒 **审计哈希链**（企业版） | 审计事件链式哈希定版，篡改可检出并定位 |
| 🏢 **多 Workspace**（企业版） | 契约/用例/任务/记忆四维隔离，跨域显式复制带血缘 |
| ⚔️ **受控辩论**（企业版） | 对已检出分歧组织受控轮次辩论，让步即止，历史原样留存 |
| 📦 **基线 Bundle**（企业版） | 契约+用例+基线三位一体打包，跨环境迁移完整性校验 |
| 🧪 **灰度 A/B**（企业版） | 契约变体确定性分流 + 全量回归对比 + 三级保守裁决 |

## 架构（三层，依赖单向）

```
App 层      wbr/app        FastAPI 服务 · 专家画布(SPA) · 异步任务队列
Adapter 层  wbr/adapters   LangGraph 适配 · OpenAI 兼容 LLM · MCP · Redis/Memory 存储 · OTel
Core 层     wbr/core       契约·编译器·Diff·审计·记忆·编排·安全·Token·缓存·Harness
```

Core 只依赖标准库 + Pydantic V2，**永不发起网络调用**——模型调用全部在 Adapter 层，你配什么端点它就调什么端点。

## 常见问题

**Q：跑 `wbr run-team` 输出里都是"演示"字样，是坏了吗？**
不是。默认使用内置演示 Invoker（确定性输出、零外部调用），用于熟悉流程。`export WBR_LLM_API_KEY=... WBR_LLM_MODEL=...` 后加 `--live` 即为真实模型。

**Q：和 AutoGen / CrewAI / LangGraph 是什么关系？**
它们解决"怎么把 Agent 编排起来"，本项目解决"编排起来之后怎么管住"：职责边界、输出约束、证据、版本、回归、审计。两者不互斥——LangGraph 项目可用 `WBRGuard` 3 行包住现有 Graph 获得治理能力。

**Q：支持哪些模型？**
任何 OpenAI 兼容 `/chat/completions` 端点（见第 3 步厂商表）。其他协议实现 `ModelInvoker` 协议（约 60 行）即可接入，Core 完全框架无关。

**Q：我的 API Key / 数据会被发到哪里？**
只发往你在 `WBR_LLM_BASE_URL` 配置的端点。Core 层零网络依赖；传输前可经 PII 脱敏与注入过滤；全程留审计记录，可导出核查。

**Q：改了提示词/契约，怎么知道没把别的能力改坏？**
Harness：先跑基线快照定版，之后任何变更跑一遍黄金用例回归，六项指标对比，能力退化自动报警。见 [docs/HARNESS.md](docs/HARNESS.md)。

**Q：想做成"用户自建专家团"的平台，要加什么？**
治理内核、REST API（契约 CRUD/版本/Diff、异步评审、Harness、审计导出）、可视化画布都是现成的，你需要补的是产品外壳：用户账号体系、模型 Key 管理、团队级 CRUD 与持久化（企业版多 Workspace 可直接复用）。

## 文档

- [架构设计方案 V2](docs/ARCHITECTURE_V2.md) · [SDK 全量 API](docs/SDK.md) · [REST API](docs/API.md) · [LangGraph 接入](docs/INTEGRATION_LANGGRAPH.md) · [Harness 回归与指标](docs/HARNESS.md) · [部署指南](docs/DEPLOY.md) · [安全说明](docs/SECURITY.md)
- 设计规格：[docs/spec/README.md](docs/spec/README.md)（SPEC-000~006 + 审核记录）· 阶段验收报告：[docs/acceptance/](docs/acceptance/)
- 示例索引：[examples/README.md](examples/README.md)

## 开发与测试

```bash
pip install -e ".[dev,langgraph,server]"
pytest tests/wbr -q                       # 本系统全量（370+ 用例）
pytest tests -q                           # 含 Legacy 工作流 CLI 套件（冻结维护，存在存量失败）
pytest tests/wbr/phase5 -q                # 打包构建与性能基准（slow/performance 标记）
```

## Legacy：多角色技能工作流 CLI（附录）

本仓库同时保留了早期的轻量工作流框架（`work_by_roles` 包，`workflow` 命令）。
该部分已冻结维护，原 README 存档于 [docs/LEGACY_README.md](docs/LEGACY_README.md)；
新项目请使用上文的 `wbr` SDK / CLI。

## License

MIT © Work-by-Roles Contributors
