# work-by-roles · LLM 专家团治理系统

> 像管理代码一样管理你的 AI 角色：**角色有契约、运行有强制、结论有证据、过程有审计、变更有回归。**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.1-green.svg)]()
[![CI](https://github.com/puppyfront-web/work-by-roles/actions/workflows/ci.yml/badge.svg)](https://github.com/puppyfront-web/work-by-roles/actions/workflows/ci.yml)

[中文](README.md) | [English](README_EN.md)

---

## 为什么需要它

把多个 LLM Agent 拼在一起上生产，通常会撞上三堵墙：

1. **输出不可控** — 职责漂移、格式乱飘、一本正经地编造
2. **结论不可查** — 模型说得自信，但证据在哪、谁复核过、哪一版提示词，答不上来
3. **变更不敢做** — 改一行提示词像拆盲盒，不知道会不会弄坏别的能力

work-by-roles 的回答：为每个 LLM 角色建立一份**可版本化的角色契约**（职责 SOP、禁区、输出 Schema、证据规范、工具白名单、Token 配额），用**会审范式**组织协作，在**运行时强制执行**边界，并为每一次变更提供**回归门禁**。

```text
                        ┌─────────────┐
         问题 / 方案 ──▶ │ Coordinator │  拆解子问题、分派专家
                        └──────┬──────┘
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
         ┌──────────┐    ┌──────────┐    ┌──────────┐
         │  专家 A   │    │  专家 B   │    │  专家 C   │  并行作答
         └─────┬────┘    └─────┬────┘    └─────┬────┘   （Schema 校验 + 证据引用强约束）
               └───────────────┼───────────────┘
                               ▼
                        ┌─────────────┐
                        │  Verifier   │  独立复核 · 裁决 · 分歧留存不仲裁
                        └──────┬──────┘
                               ▼
                     结构化结论 + 证据链 + 全程审计事件
```

## 定位：与主流方案的关系

| 你在用 | 它解决 | 本项目补充 |
|---|---|---|
| LangGraph / AutoGen / CrewAI | Agent 怎么编排、怎么通信 | 角色边界、输出约束、证据链、版本、回归、审计（`WBRGuard` 3 行接入存量 Graph） |
| promptfoo / DeepEval | Prompt 的离线评测 | 评测之外还有**运行时强制**（Schema 校验 / 工具白名单 / 配额）与契约版本闭环 |
| LangSmith（SaaS） | 观测与追踪 | 开源可私有化部署，审计 + 证据链面向合规审计场景 |
| 手写多角色 system prompt | — | 从第一天起就有边界定义与回归兜底 |

**一句话：编排框架负责"跑起来"，评测工具负责"测效果"，本项目负责"管得住"。**

团队既能让它**干活**，也能让它**把关**：会审范式不仅是评审——`content_creation_team` 模板演示了生产型用法（故事 / 干货 / 案例数据三种角度并行竞稿，主编合成终稿），复核人在生产团队中承担主编 / 质量门禁角色。

## 快速上手：从零到第一次会审（5 分钟）

### 第 1 步 · 安装

```bash
pip install "work-by-roles[server]"   # SDK + CLI + API 服务 + 画布（httpx 用于真实模型调用）
# 或最小安装：pip install work-by-roles
```

### 第 2 步 · 跑一次演示（无需任何模型 Key）

```bash
wbr list-teams                                    # 查看官方专家团模板
wbr run-team arch_review_team "评审：订单系统微服务拆分方案"
```

输出完整的会审 JSON：状态、最终结论、参与专家、分歧数、审计事件数。此步骤使用内置演示 Invoker（确定性输出），**不调用任何外部模型**。

### 第 3 步 · 接入真实模型（3 个环境变量）

兼容任何 OpenAI 风格的 `/chat/completions` 端点：

```bash
export WBR_LLM_API_KEY=sk-...        # API Key（本地端点填任意非空值）
export WBR_LLM_MODEL=gpt-4o-mini     # 模型名
# export WBR_LLM_BASE_URL=https://api.openai.com/v1   # OpenAI 可省略，其他厂商必填

wbr run-team arch_review_team "评审：订单系统微服务拆分方案" --live
```

常用服务商参考：

| 服务商 | WBR_LLM_BASE_URL | WBR_LLM_MODEL 示例 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1`（默认，可省略） | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Kimi（月之暗面） | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Qwen（DashScope 兼容） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| GLM（智谱） | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| Ollama（本地） | `http://127.0.0.1:11434/v1` | `qwen2.5:7b`（Key 填任意非空值） |
| vLLM（自部署） | `http://127.0.0.1:8000/v1` | 所部署的模型名 |

### 第 4 步 · 可视化画布

```bash
uvicorn --factory wbr.app.api.main:create_app --port 8000
# 浏览器打开 http://127.0.0.1:8000/canvas
```

- **导入官方模板**：左上角下拉选择 → 导入，一键载入整套专家团契约
- **搭建团队**：创建协调者 / 专家 / 复核人契约，拖拽节点调整布局
- **编辑契约**：双击节点修改 SOP、禁区、工具白名单、Token 配额、输出 Schema（实时校验），保存即产生新版本（历史可查、可 Diff）
- **运行会审**：发起异步评审，分歧节点红色高亮，支持导出标准审计包

页头显示当前模式（真实模型 / 演示模式）。API 服务检测到 `WBR_LLM_*` 环境变量后自动切换，无需改代码。

### 第 5 步（可选）· 代码接入

**SDK 运行会审：**

```python
from wbr.templates.registry import load_team_spec
from wbr.adapters.llm import OpenAICompatInvoker
from wbr.core.orchestration import ReviewSession

spec = load_team_spec("arch_review_team")

session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=OpenAICompatInvoker(          # 未传参时读取 WBR_LLM_* 环境变量
        api_key="sk-...",
        model="gpt-4o-mini",
        # model_by_role={"coordinator": "gpt-4o",   # 按角色配置模型：
        #                "verifier": "gpt-4o"},      # 协调者/复核人用强模型，专家用高性价比模型
    ),
)
result = session.run("评审：订单系统微服务拆分方案")
print(result.final_answer, result.disagreements)
```

**存量 LangGraph 项目 3 行接入**（不改变 State 语义，Checkpointer / HITL 天然兼容）：

```python
from wbr.adapters.langgraph import WBRGuard

guard = WBRGuard(output_keys={"answer": contract}, audit=trail)  # 1
graph = guard.wrap(your_compiled_graph)                          # 2
result = graph.invoke({"question": "..."})                       # 3
```

详见 [docs/INTEGRATION_LANGGRAPH.md](docs/INTEGRATION_LANGGRAPH.md)。

## 核心概念（30 秒）

| 概念 | 说明 |
|---|---|
| **角色契约 RoleContract** | 角色的"岗位说明书"：职责 SOP、禁区、输出 Schema、证据规范、工具白名单、记忆权限、Token 配额、评审标准。声明式 YAML，版本化 + 内容哈希定版 |
| **会审 Review** | Coordinator 拆解 → 专家并行 → Verifier 独立复核。**分歧留存不仲裁**，最终判断权留给使用方 |
| **Harness 质量门禁** | 黄金用例 + 基线快照 + 一键回归。契约或模型变更后，能力退化自动检出 |
| **全链路审计** | 编译、调用、校验、裁决均产生 TraceID 关联的审计事件，可导出标准审计包 |

## 设计原则

1. **契约先行** — 边界在运行前声明并强制执行，而非事后评测补救
2. **分歧留存** — 复核独立裁决但不仲裁，结论与分歧一并交付使用方
3. **变更可回归** — 任何契约与模型变更都可对照基线验证影响面
4. **全程可审计** — 每个结论可追溯至证据、契约版本与操作序列

## 适用场景

| 场景 | 做法 | 产出 |
|---|---|---|
| **架构 / 方案评审** | 导入 `arch_review_team` 模板，提交方案描述 | 接口 / 数据 / 基础设施三位专家并行评审 + 复核裁决，结论带证据引用 |
| **安全审计** | 导入 `security_audit_team` 模板 | 注入 / 认证越权 / 数据泄露三个审计维度 + 严重级校准 |
| **内容发布前评审** | 导入 `content_review_team` 模板，粘贴待发布文案与目标平台 | 事实核查 + 平台合规 + 转化力三专家并行评审，终审给出"可发布 / 需修改 / 不可发布"与必改清单 |
| **内容创作** | 导入 `content_creation_team` 模板，给出选题、平台与创作目标 | 故事型 / 干货型 / 案例数据型三种角度并行竞稿，主编独立评审并合成终稿 |
| **自定义专家团** | 编写 YAML 角色契约 | 按业务定制的专家团，每次契约变更具备版本、Diff 与回归保障 |
| **面向用户的专家团平台** | 基于自带 REST API + 画布二次开发 | 治理内核、契约 CRUD、异步评审、审计导出开箱即用，只需补充用户体系与模型 Key 管理 |

## 自定义你的专家团

一个最小专家只需一份 YAML：

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

三种组装方式任选：**画布表单**（无需接触 YAML）· **复制官方模板修改**（`wbr/templates/teams/arch_review_team/`）· **SDK 构造**（`RoleContract.model_validate(...)`）。

<details>
<summary><b>功能全景（点击展开）</b></summary>

| 能力 | 说明 |
|---|---|
| 📜 **角色契约** | 声明式、版本化、内容哈希定版，每次变更具备 Diff |
| ⚖️ **会审范式** | 拆解 → 并行 → 独立复核；分歧留存不仲裁 |
| 🧠 **四层隔离记忆** | 角色长期 / 角色会话 / 任务暂存 / 全局受控，读写按契约授权并全程审计 |
| 🧪 **原生 Harness** | 黄金用例 + 基线快照 + 一键回归 + 六项指标 + 能力退化检测 |
| 💾 **契约绑定缓存** | 缓存键含契约哈希，契约变更自动失效；支持可选语义近似命中 |
| 🛡️ **安全防注入** | 中英双语注入规则库 + 外部内容二阶隔离 + 边界符转义 |
| 🙈 **内容脱敏** | PII 规则库（邮箱 / 手机 / 身份证 / 密钥 / 卡号 / IP），稳定占位符，可扩展 |
| 🔍 **全链路审计** | TraceID 关联强类型审计事件，可导出标准审计包 |
| 🧭 **意图推理** | Coordinator 内置意图分类 / 要素抽取 / 冲突检测 / 置信阈值，结构化输出 + 理由链 |
| 🔁 **受控内循环** | 单角色多轮"推理 → 检索 → 补证"，轮次 / Token / 退出条件契约化，超限升级 HITL |
| 🔌 **LangGraph 兼容** | `WBRGuard` 3 行接入；断点续跑 / HITL 天然兼容 |
| 🧩 **MCP 接入** | MCP 工具纳入契约权限体系（白名单前置 + 二阶防护 + 脱敏） |
| 📚 **角色知识库** | 角色私有 / 共享知识文档，检索接入 evidence 通道 |
| 🔭 **OpenTelemetry** | 审计总线零侵入桥接 OTel（span / 指标），可关闭 |
| 🔄 **反馈闭环** | 线上负反馈聚合为黄金用例，接入回归引擎 |
| 🔒 **审计哈希链**（企业版） | 审计事件链式哈希定版，篡改可检出并定位 |
| 🏢 **多 Workspace**（企业版） | 契约 / 用例 / 任务 / 记忆四维隔离，跨域显式复制带血缘 |
| ⚔️ **受控辩论**（企业版） | 对已检出分歧组织受控轮次辩论，让步即止，历史原样留存 |
| 📦 **基线 Bundle**（企业版） | 契约 + 用例 + 基线三位一体打包，跨环境迁移完整性校验 |
| 🧪 **灰度 A/B**（企业版） | 契约变体确定性分流 + 全量回归对比 + 三级保守裁决 |

</details>

## 架构（三层，依赖单向）

```text
App 层      wbr/app        FastAPI 服务 · 专家画布(SPA) · 异步任务队列
Adapter 层  wbr/adapters   LangGraph 适配 · OpenAI 兼容 LLM · MCP · Redis/Memory 存储 · OTel
Core 层     wbr/core       契约 · 编译器 · Diff · 审计 · 记忆 · 编排 · 安全 · Token · 缓存 · Harness
```

Core 仅依赖标准库 + Pydantic V2，**不发起任何网络调用**——模型调用全部位于 Adapter 层，指向你配置的端点。治理在四个时刻生效：**定义时**（契约）、**运行时**（Schema / 白名单 / 配额强制）、**裁决时**（复核 + 审计）、**演进时**（Harness 回归）。

## 常见问题

**Q：`wbr run-team` 输出都是"演示"字样，是故障吗？**
不是。默认使用内置演示 Invoker（确定性输出、零外部调用）。配置 `WBR_LLM_API_KEY` / `WBR_LLM_MODEL` 后加 `--live` 即切换为真实模型。

**Q：与 AutoGen / CrewAI / LangGraph 是竞争关系吗？**
不是。它们解决编排问题，本项目解决编排之后的治理问题，可组合使用——`WBRGuard` 可为存量 LangGraph 提供治理能力。

**Q：支持哪些模型？**
任何 OpenAI 兼容 `/chat/completions` 端点（见上表）。其他协议实现 `ModelInvoker` 协议（约 60 行）即可接入，Core 完全框架无关。

**Q：API Key 与数据会被发送到哪里？**
仅发送至 `WBR_LLM_BASE_URL` 配置的端点。Core 层零网络依赖；传输前可经 PII 脱敏与注入过滤；全程留有审计记录，可导出核查。

**Q：如何确认契约 / 提示词变更没有破坏其他能力？**
使用 Harness：先固化基线快照，变更后运行黄金用例回归，六项指标对比，能力退化自动告警。见 [docs/HARNESS.md](docs/HARNESS.md)。

**Q：想搭建"用户自建专家团"平台，需要补充什么？**
治理内核、REST API（契约 CRUD / 版本 / Diff、异步评审、Harness、审计导出）、可视化画布均已内置；需自行补充产品外壳：用户账号体系、模型 Key 管理、团队级 CRUD 与持久化（企业版多 Workspace 可直接复用）。

## 文档

- [架构设计方案 V2](docs/ARCHITECTURE_V2.md) · [SDK 全量 API](docs/SDK.md) · [LangGraph 接入](docs/INTEGRATION_LANGGRAPH.md) · [Harness 回归与指标](docs/HARNESS.md) · [部署指南](docs/DEPLOY.md)
- 设计规格：[docs/spec/README.md](docs/spec/README.md)（SPEC-000~006 + 审核记录）· 阶段验收报告：[docs/acceptance/](docs/acceptance/)
- 示例索引：[examples/README.md](examples/README.md) · 更新日志：[CHANGELOG.md](CHANGELOG.md)

## 参与贡献

欢迎 Issue 与 PR，贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。一个好起点：为 `wbr/templates/teams/` 贡献新的官方专家团模板（法律合同评审、财务报告审阅、面试评估等场景均有真实需求）。

## 开发与测试

```bash
pip install -e ".[dev,langgraph,server]"
pytest tests -q                           # 全量测试（370+ 用例）
pytest tests/wbr/phase5 -q                # 打包构建与性能基准（slow/performance 标记）
```

## License

MIT © Work-by-Roles Contributors
