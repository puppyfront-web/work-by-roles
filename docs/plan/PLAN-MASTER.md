# 开发主计划（PLAN-MASTER）

> 输入：docs/spec/SPEC-000~006（已审核）。方法论：SDD + TDD。
> 执行闸口：每阶段完成 = 代码 + 测试全绿 + 示例可运行 + 文档 + `docs/acceptance/PHASE<N>.md` 验收报告，五项齐备方可进入下一阶段。

## 0. 环境基线（已就绪）
- Python 3.13 venv（`.venv/`）：pydantic 2.14 / pytest 9 / pytest-cov / fastapi / httpx / uvicorn / langgraph 1.2 / redis 8.1 / pyyaml
- 测试命令：`.venv/bin/python -m pytest tests/wbr/<phase> -q`；覆盖率：`--cov=wbr --cov-report=term-missing`
- 存量回归保护：`.venv/bin/python -m pytest tests -q`（含 legacy，基准 156 passed / 1 known-fail：test_learning_module_config，不新增失败即为绿）

## 1. 阶段闸口与任务分解

### 阶段0（对应 SPEC-001）—— 基础架构
| # | 任务 | TDD 顺序 |
|---|---|---|
| 0.1 | pyproject 更新 + 目录骨架 + `wbr/__init__` | 先写 test_structure/test_packaging（RED）→ 建骨架（GREEN） |
| 0.2 | exceptions / constants | test_exceptions |
| 0.3 | context(TraceID) | test_context |
| 0.4 | config + config_loader | test_config |
| 0.5 | logging | test_logging |
| 0.6 | audit_bus | test_audit_bus |
| 0.7 | 验收报告 PHASE0.md | 结构+import 冒烟+存量回归证据 |

### 阶段1（SPEC-002）—— 核心契约内核（0.1.0）
0.1 schema/validator（被契约与编排依赖，先做）→ 0.2 contract/models → 0.3 contract/compiler → 0.4 contract/diff → 0.5 audit/models+trail → 0.6 memory → 0.7 orchestration(invoker/hitl 状态机/session) → 0.8 examples/phase1_core_demo.py → 验收报告。
覆盖率门禁：contract/memory/schema/orchestration ≥90%。

### 阶段2（SPEC-003）—— LangGraph 适配层（0.2.0）
1 security/guard+boundaries → 2 token（counter/meter/budget）→ 3 adapters/storage（base/memory/redis）→ 4 adapters/langgraph（mapping/state/interceptors/toolgate/hitl/guard.wrap/builder）→ 5 双示例 → 验收报告（3 行接入证明）。

### 阶段3（SPEC-004）—— Harness + 缓存（0.3.0）
1 harness/cases → 2 baseline → 3 harness/engine+metrics → 4 judge → 5 cache（backends/contract_cache + RedisCacheBackend）→ 6 audit/pack → 验收报告（改契约一键回归 + 退化检测演示）。

### 阶段4（SPEC-005）—— API + 画布（0.4.0）
1 app/store(JsonFileStore+ContractRegistry) → 2 tasks(queue/store/worker) → 3 api(main/routes×5) → 4 canvas 静态三件套 → 5 demo 文档 → 验收报告。

### 阶段5（SPEC-006）—— V1.0（1.0.0）
1 arch_review_team 模板 → 2 security_audit_team 模板 → 3 templates/registry → 4 wbr.cli → 5 文档全面更新（README 中英/SDK/INTEGRATION/HARNESS/DEPLOY/spec 索引）→ 6 打包构建（build+twine check）→ 7 基准测试 → 8 FINAL 验收报告。

## 2. TDD 工作约定
- 每个模块：先建测试文件（断言公开 API 与行为）→ 实现 → 绿；重构不改行为。
- 测试金字塔：单元为主（≈85%），集成（会审全链路、wrap 后图、回归流程）为辅，端到端以示例脚本代替。
- 测试数据：契约用 `tests/wbr/factories.py` 统一构造器（builder 模式），保证用例间零耦合。
- 假件：`ScriptedInvoker`（按角色脚本回放输出）、`FakeRedis`（dict 语义）、`InlineTaskQueue`。全部置于 `tests/wbr/fakes.py`。

## 3. 风险与对策
| 风险 | 对策 |
|---|---|
| LangGraph API 版本变动（1.2） | 适配层集中隔离在 mapping/state/hitl 三文件；集成测试锁定行为 |
| Python 3.13 与 StrEnum 等新特性 | 仅用 3.10+ 稳定特性；ci 本地 3.13 实测 |
| 存量测试误伤 | 存量包禁止改动；每阶段跑全量回归比对基准 |
| 范围蔓延 | 每 SPEC"非目标"清单为硬边界；新想法记入 BACKLOG 不实现 |
| 单轮上下文长度 | 分阶段提交 git；每阶段独立可验收，支持中断续作 |

## 4. 里程碑验收命令（固化）
```bash
VENV=.venv/bin/python
$VENV -m pytest tests/wbr -q --cov=wbr --cov-report=term   # 新系统全量
$VENV -m pytest tests -q                                   # 存量回归
$VENV examples/phase1_core_demo.py && ...                  # 示例冒烟
$VENV -m build && $VENV -m twine check dist/*              # 阶段5
```


## 5. V1.x 迭代计划（SPEC-007，版本 1.1.0）

| 顺序 | 任务 | TDD 载体 |
|---|---|---|
| 6.1 | 内容脱敏与安全风控 core/security/redactor | tests/wbr/phase6/test_redactor.py |
| 6.2 | 角色知识库 core/knowledge | test_knowledge.py |
| 6.3 | 语义缓存 core/cache/semantic | test_semantic_cache.py |
| 6.4 | 反馈闭环 core/harness/feedback | test_feedback.py |
| 6.5 | MCP 接入层 adapters/mcp | test_mcp_bridge.py |
| 6.6 | OTel 可观测 adapters/observability | test_otel_bridge.py |
| 6.7 | 版本 1.1.0 + 文档 + 验收报告 PHASE6.md | 全量回归 |


## 6. V2.0 企业版计划（SPEC-008，版本 2.0.0）

| 顺序 | 任务 | TDD 载体 |
|---|---|---|
| 7.1 | 审计哈希链 core/audit/chain | tests/wbr/phase7/test_hash_chain.py |
| 7.2 | 多 Workspace core/workspace | test_workspace.py |
| 7.3 | 受控辩论 core/orchestration/debate | test_debate.py |
| 7.4 | 基线 Bundle core/bundle | test_bundle.py |
| 7.5 | 灰度 A/B core/experiment | test_experiment.py |
| 7.6 | 版本 2.0.0 + 文档 + 验收报告 PHASE7.md | 全量回归 |
