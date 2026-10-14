# work-by-roles · 专家团治理系统

> 契约驱动、会审范式原生、带原生 Harness 质量门禁的开源专家团治理系统。
> 让每一个 LLM 角色都有一份可版本化、可审计、可回归的"角色契约"。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.1-green.svg)]()

中文 | [English](README_EN.md)

---

## 它解决什么问题

直接把多个 LLM Agent 拼在一起，会得到：职责漂移、输出不可控、结论无据可查、改一行提示词不知道会不会弄坏别的能力、审计无从下手。work-by-roles 用一套**治理内核**回答这些问题：

| 能力 | 说明 |
|---|---|
| 📜 **角色契约 RoleContract** | 职责 SOP、禁区、输出 Schema、证据规范、工具白名单、记忆权限、Token 配额、评审标准——全部声明式，版本化 + 内容哈希定版 |
| ⚖️ **会审范式** | Coordinator 拆解 → 多专家并行 → Verifier 独立复核；**分歧留存不仲裁** |
| 🧠 **多层隔离记忆** | 角色长期 / 角色会话 / 任务暂存 / 全局受控四层，读写按契约授权并全程审计 |
| 🧪 **原生 Harness** | 黄金用例库 + 基线快照（契约/模型版本锁定）+ 一键回归 + 六项指标 + 能力退化自动检测 |
| 💾 **契约绑定缓存** | 缓存键 = 契约哈希 ‖ 问题哈希 ‖ 证据快照；契约变更自动失效，绝不脏读 |
| 🛡️ **安全防注入** | 中英双语注入规则库 + 外部内容二阶隔离 + 边界符转义 |
| 🔍 **全链路审计** | 每次编译/调用/校验/裁决均产生 TraceID 关联的强类型审计事件，可导出标准审计包 |
| 🔌 **LangGraph 兼容** | 存量项目 **3 行代码** 接入；也可一键生成原生会审 Graph |
| 🧩 **MCP 接入层** | MCP 工具纳入契约权限体系（白名单前置 + 二阶防护 + 脱敏） |
| 📚 **角色知识库** | 角色私有/共享知识文档，权限锚定记忆层，检索接 evidence 通道 |
| 🙈 **内容脱敏** | PII 规则库（邮箱/手机/身份证/密钥/卡号/IP），稳定占位符，可扩展 |
| 🔭 **OpenTelemetry** | 审计总线零侵入桥接 OTel（span/指标），可关闭 |
| 🧠 **语义缓存** | 契约哈希严格一致前提下的语义近似命中（可配阈值） |
| 🔄 **反馈闭环** | 线上负反馈聚合为黄金用例，接入回归引擎 |
| 🔒 **审计哈希链**（企业版） | 审计事件链式哈希定版，任何篡改可检出并定位 |
| 🏢 **多 Workspace**（企业版） | 契约/用例/任务/记忆四维隔离，跨域显式复制带血缘 |
| ⚔️ **受控辩论**（企业版） | 对已检出分歧组织受控轮次辩论，让步即止，历史原样留存 |
| 📦 **基线 Bundle**（企业版） | 契约+用例+基线三位一体打包，跨环境迁移完整性校验 |
| 🧪 **灰度 A/B**（企业版） | 契约变体确定性分流 + 全量回归对比 + 三级保守裁决 |
| 🧭 **意图推理流水线** | Coordinator 内置：五类意图分类/要素抽取/冲突检测/置信阈值，结构化输出+理由链审计 |
| 🔁 **受控内循环** | 单角色多轮"推理→检索→补证"，轮次/Token/退出条件全部契约化，超限升级 HITL |

## 架构（三层，依赖单向）

```
App 层      wbr/app        FastAPI 服务 · 专家画布(SPA) · 异步任务队列
Adapter 层  wbr/adapters   LangGraph 适配 · Redis/Memory 存储 · HITL interrupt
Core 层     wbr/core       契约·编译器·Diff·审计·记忆·编排·安全·Token·缓存·Harness
```

Core 只依赖标准库 + Pydantic V2，框架无关、可独立使用（SDK 优先，Web 画布只是上层应用）。

## 快速开始

```bash
pip install "work-by-roles[langgraph]"        # 或 pip install -e ".[server]"
```

### 30 秒跑通一次会审（纯 SDK）

```python
from wbr.templates.registry import load_team_spec
from wbr.core.orchestration import ReviewSession

spec = load_team_spec("arch_review_team")     # 开箱即用专家团模板

session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=your_invoker,                     # 实现 ModelInvoker 协议即可接入任意模型
)
result = session.run("评审：订单系统微服务拆分方案")
print(result.final_answer, result.disagreements)
```

CLI 体验（内置确定性演示输出，不调用外部模型）：

```bash
wbr list-teams
wbr run-team arch_review_team "评审：订单系统微服务拆分方案"
```

### 存量 LangGraph 项目：3 行接入

```python
from wbr.adapters.langgraph import WBRGuard

guard = WBRGuard(output_keys={"answer": contract}, audit=trail)  # 1
graph = guard.wrap(your_compiled_graph)                          # 2
result = graph.invoke({"question": "..."})                       # 3
```

不改变原有 State 键语义、不改节点逻辑、Checkpointer / interrupt（断点续跑、HITL）天然兼容。
详见 [docs/INTEGRATION_LANGGRAPH.md](docs/INTEGRATION_LANGGRAPH.md)。

### 完整平台（API + 画布）

```bash
pip install "work-by-roles[server]"
uvicorn --factory wbr.app.api.main:create_app --port 8000
# 浏览器打开 http://127.0.0.1:8000/canvas —— 搭建专家团、运行会审、看分歧、导出审计包
```

## 两套官方专家团模板（开箱即用）

| 模板 | 构成 |
|---|---|
| `arch_review_team` | 协调者 + 接口设计 / 数据架构 / 基础设施三位专家 + 复核人（三维评审标准） |
| `security_audit_team` | 协调者 + 注入 / 认证越权 / 数据泄露三位审计员 + 复核人（严重级校准） |

## 文档

- [SDK 全量 API](docs/SDK.md) · [LangGraph 接入](docs/INTEGRATION_LANGGRAPH.md) · [Harness 回归与指标](docs/HARNESS.md) · [部署指南](docs/DEPLOY.md) · [安全说明](docs/SECURITY.md)
- 设计规格：[docs/spec/README.md](docs/spec/README.md)（SPEC-000~006 + 审核记录）· 阶段验收报告：[docs/acceptance/](docs/acceptance/)
- 示例索引：[examples/README.md](examples/README.md)

## 开发与测试

```bash
pip install -e ".[dev,langgraph,server]"
pytest tests/wbr -q                       # 本系统全量（240+ 用例）
pytest tests -q                           # 含 Legacy 工作流 CLI 套件
pytest tests/wbr/phase5 -q                # 含打包构建与性能基准（slow/performance 标记）
```

## Legacy：多角色技能工作流 CLI（附录）

本仓库同时保留了早期的轻量工作流框架（`work_by_roles` 包，`workflow` 命令：
workflow setup / init / wfauto / role-execute / import-sop 等，面向 IDE 内的多角色技能约束）。
该部分已冻结维护，原 README 存档于 [docs/LEGACY_README.md](docs/LEGACY_README.md)，
使用文档见 [QUICKSTART.md](QUICKSTART.md) 与 [ROLES_AND_SKILLS.md](ROLES_AND_SKILLS.md)；
新项目请使用上文的 `wbr` SDK / CLI。

## License

MIT © Work-by-Roles Contributors
