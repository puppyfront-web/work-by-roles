# SPEC-008 · V2.0 企业版 · 治理增强

> 前置：V1.1 已交付。目标版本：**2.0.0**。全部为 Core 模块（零新依赖），延续既有扩展点。

## 0. 范围（锁定）

| # | 模块 | 代码位置 |
|---|---|---|
| E1 | 防篡改审计哈希链 | `wbr/core/audit/chain.py` |
| E2 | 多 Workspace 隔离 | `wbr/core/workspace.py` |
| E3 | 受控专家辩论 | `wbr/core/orchestration/debate.py` |
| E4 | 基线 Bundle 版本打包 | `wbr/core/bundle.py` |
| E5 | 灰度 A/B 实验 | `wbr/core/experiment.py` |

## 1. E1 审计哈希链 `HashChainAuditor`

```python
ChainedEvent(原有 AuditEvent 字段 + seq: int, prev_hash: str, event_hash: str)
HashChainAuditor(*, scope: str = "global"):
    append(event: AuditEvent) -> ChainedEvent     # event_hash = sha256(canonical(prev_hash|seq|event全文))
    chain() -> list[ChainedEvent]
    verify() -> ChainVerification(ok, broken_at: int|None, checked: int)
    export_json() / from_json(...)                # 链随包持久化
```
- 创世节点 `prev_hash = "0"*64`；任何历史篡改（改 payload/顺序/删除）→ `verify().ok = False` 且定位断点。
- `HashChainTrail`：AuditTrail 门面，`append` 同时写 trail 与链，`verify()` 透出。

## 2. E2 多 Workspace `WorkspaceRegistry`

```python
Workspace(name, root, created_at)
WorkspaceRegistry(root: Path):
    create(name) / get(name) / list() / delete(name)      # 目录隔离：<root>/workspaces/<name>/
    registry(name) -> ContractRegistry                     # 各 workspace 独立契约库
    suite_path(name) / task_store(name)                    # 用例库与任务落盘隔离
    memory_hub(name) -> MemoryHub                          # 记忆命名空间前缀 ws:<name>:
    copy_contract(src_ws, dst_ws, role_id) -> 新契约副本   # 显式跨域复制（保留 hash 血缘记录）
```
- 隔离不变量：workspace A 的任何读写不可见 B（契约/用例/任务/记忆四维参数化测试）。
- 名称约束 `[a-z][a-z0-9_]{0,31}`；重复创建抛 E9002；不存在抛 E9003。

## 3. E3 受控专家辩论 `DebateRound`

```python
DebateConfig(max_rounds: int=2, referee: RoleContract(VERIFIER), require_rebuttal: bool=True)
DebateTurn(round_no, role_id, statement, agrees_with: list[str], concedes: bool)
DebateResult(rounds: list[list[DebateTurn]], concessions, unresolved_disagreements, trace)
DebateModerator(*, contracts, invoker, config, audit=None):
    run(question, disputed: list[Disagreement]) -> DebateResult
```
- 受控语义：仅对已检出的 disagreement 组织辩论；每轮专家须声明 `agrees_with`/`concedes`；
  全员让步或达 max_rounds 即止；**辩论历史原样留存**（不仲裁抹平），unresolved 仍进 ReviewResult.disagreements。
- 每轮发言经契约 Schema/禁区校验（复用 `_check_contract_output` 语义，违规者该轮禁言并审计）。

## 4. E4 基线 Bundle `BaselineBundle`

```python
BaselineBundle.pack(*, contracts, suite, baseline, note) -> BaselineBundle
    format: {format_version, bundle_id, contracts:[契约JSON], suite:{...}, baseline:{...},
             manifest: {file_digests, bundle_digest}}
    save(path) / BaselineBundle.load(path)
    verify() -> bool                    # manifest 逐文件校验
    to_registry(target: ContractRegistry) / suite() / baseline()
```
- 打包即快照（契约+用例+基线三位一体），跨环境迁移 = save/load + verify。
- 任何成员被篡改 → verify False 且定位文件。

## 5. E5 灰度 A/B 实验 `ABExperiment`

```python
ABVariant(name, contracts: dict[role_id, RoleContract])
ABExperiment(*, experiment_id, suite, invoker, traffic_fn=None, audit=None):
    add_variant(v)          # ≥2 个；契约集角色必须同构（role_id 集合一致，否则 E7001）
    split(key: str) -> str  # 确定性分流：sha256(experiment_id|key) % n
    run(*, runs_per_case=1) -> ABReport
ABReport: per_variant: {name, RegressionReport}, winner: str|None, decision_reason
```
- winner 判定：overall_pass_rate 高者（并列时 forbidden_violation_rate 低者；再并列 None=保守不切换）。
- 变体契约集自动建 BaselineSnapshot（版本锁定语义复用）。

## 6. 非目标
跨进程 workspace 锁、A/B 在线流量接入（仅分流函数+回归对比）、辩论 LLM 裁判。

## 7. 验收标准 → 测试映射（tests/wbr/phase7/）

| 验收标准 | 测试 |
|---|---|
| 链式追加/创世/verify 通过；篡改 payload/删除/乱序均检出并定位 | `test_hash_chain.py` |
| Workspace 四维隔离参数化 + 跨域显式复制 + 名称约束 | `test_workspace.py` |
| 辩论：受限启动（仅 disagreement）/max_rounds/让步提前终止/违规禁言/历史留存 | `test_debate.py` |
| Bundle：打包→load→verify→落注册表；篡改检出定位 | `test_bundle.py` |
| A/B：同构校验/确定性分流/双变体回归/winner 判定三规则 | `test_experiment.py` |
| 全量回归 + 覆盖率 ≥90%（新模块） | PHASE7 验收报告 |
