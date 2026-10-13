# SPEC 自审核记录（SPEC-REVIEW）

> 审核对象：SPEC-000 ~ SPEC-006。审核方法：①方案要求 ↔ SPEC 覆盖矩阵核对；②八条全局规则逐条合规检查；③矛盾/歧义/可测试性专项审查。结论：**全部问题已闭环，SPEC 批准进入 Plan 阶段**。

## 1. 方案要求覆盖矩阵

| 方案要求 | SPEC 覆盖 | 状态 |
|---|---|---|
| 三层架构 + 依赖方向 | SPEC-000 §2 | ✅ |
| RoleContract 全字段（10 组） | SPEC-002 §1 | ✅ |
| 契约编译器（护栏头/隔离用户输入/防劫持） | SPEC-002 §2 | ✅ |
| 契约版本 Diff（字段/规则/Schema/禁区） | SPEC-002 §3（category 四类全覆盖） | ✅ |
| 基础审计模型 + 行为记录 + Trace 链路 | SPEC-002 §4 | ✅ |
| 四层记忆抽象 + 内存实现 | SPEC-002 §5 | ✅ |
| 最简会审 Coordinator→专家并行→Verifier | SPEC-002 §6 | ✅ |
| LangGraph 适配（Message/State/双拦截器/权限/HITL/Checkpointer） | SPEC-003 §1 | ✅ |
| 记忆持久化 Redis 隔离 | SPEC-003 §2 | ✅ |
| 安全 V1（一阶/二阶防注入 + 边界隔离符） | SPEC-003 §3 | ✅ |
| Token 计量（角色/步骤/任务 + 超限降级） | SPEC-003 §4 | ✅ |
| 两种接入示例（嵌入/原生） | SPEC-003 §5 | ✅ |
| 3 行代码接入存量项目 | SPEC-003 §1.5（WBRGuard.wrap）+ 验收测试 | ✅ |
| Harness（用例库/基线快照/回归引擎/六项指标） | SPEC-004 §1 | ✅ |
| AI Judge 钩子 + 基础实现 | SPEC-004 §1.5 | ✅ |
| 缓存 Key 三要素 + 契约变更失效 + 命中率 | SPEC-004 §2 | ✅ |
| 审计包导出 JSON | SPEC-004 §3 | ✅ |
| FastAPI（契约 CRUD/会审调度/回归/审计导出） | SPEC-005 §1 | ✅ |
| 画布（拖拽/编辑/流程可视化/分歧高亮） | SPEC-005 §2 | ✅ |
| 异步任务队列 | SPEC-005 §3 | ✅ |
| 两套官方模板（架构评审/安全审计） | SPEC-006 §1 | ✅ |
| 文档/示例/PyPI 打包/性能加固 | SPEC-006 §2-§5 | ✅ |
| V1.x/V2.0 内容不开发 | SPEC-000 §2.1 明示禁做清单 | ✅ |

## 2. 八条全局规则合规检查

| 规则 | 合规性说明 |
|---|---|
| 1 阶段顺序、不超前 | 每 SPEC 设"非目标"小节；V1.x/V2.0 禁做清单（SPEC-000 §2.1） |
| 2 只做当前阶段 | Plan 以阶段为闸口，验收报告未过不开下一阶段 |
| 3 阶段五件套 | 各 SPEC"验收标准→测试映射"含代码/测试/示例/文档/自测报告（docs/acceptance/） |
| 4 契约优先等五原则 | 契约模型为一切行为源头；审计/回归/插拔（StorageBackend、ModelInvoker、JudgeHook、TaskQueue、CacheBackend 五大可插拔点） |
| 5 Core 框架无关 | D-01 依赖白名单；SPEC-000 §2 import 方向禁令 + 阶段0 结构测试静态检查 |
| 6 声明式契约、禁硬编码 | 全部策略入 RoleContract；拦截器行为由 contract.strict/whitelist 驱动 |
| 7 强类型 Pydantic V2 | 所有模型 Pydantic V2；可序列化/可 Diff/可持久化为各 SPEC 验收项 |
| 8 SDK 优先、画布不耦合内核 | D-10：画布仅消费 API；内核全部能力无 API 可独立使用（阶段1/3 示例证明） |

## 3. 发现问题与裁定（审核实录）

| # | 问题 | 裁定 |
|---|---|---|
| R1 | 方案自相矛盾：要求"Core 无第三方依赖"又要求"全程 Pydantic V2" | **D-01**：Pydantic V2 为 Core 唯一许可依赖；JSON Schema 校验自研子集（D-08），PyYAML 外置（D-15） |
| R2 | 存量 `work_by_roles/core` 与新三层架构目录冲突，存量 157 项测试不可破坏 | **D-02**：新系统独立包 `wbr`，存量包冻结只读，作为回归基线 |
| R3 | 存量 `requires-python>=3.8` 与 LangGraph/现代 Pydantic 冲突 | **D-03**：新包要求 ≥3.10；存量代码在 3.13 验证可运行，无兼容损失 |
| R4 | 测试环境无 Redis 服务，"Redis 记忆持久化"不可直接集成测试 | **D-04**：客户端注入 + 进程内 Fake 同协议测试；真连测 env 门控跳过 |
| R5 | "多专家并行"未定义并发模型与结果确定性 | **D-05**：ThreadPoolExecutor + 按契约 ID 排序；专家失败不阻断全场 |
| R6 | Core 发起真实 LLM 调用将违反"框架无关+可测试" | **D-06**：ModelInvoker 协议；Core 永无网络调用；示例脚本化 |
| R7 | Token 精确计数依赖 tiktoken（第三方） | **D-07**：确定性启发式计数器 + 可替换协议；精确计量留 V1.x |
| R8 | "断点续跑兼容 Checkpointer"可能被包装破坏 State 结构 | SPEC-003 §1.5：仅追加命名空间键 `wbr__meta`；MemorySaver 中断恢复纳入验收测试 |
| R9 | "分歧留存"未定义检出语义，易被实现为仲裁 | SPEC-002 §6：同子问题结论冲突即记录 Disagreement，禁止仲裁抹平 |
| R10 | "专家结论稳定性"指标需重复运行语义 | SPEC-004 §1.4：stability_runs 参数显式化 |
| R11 | 画布若引入 Node 构建链将违反"极简 MVP"与交付环境约束 | **D-10**：原生 JS+SVG SPA，FastAPI 静态托管 |
| R12 | 异步队列若引 Celery/Redis broker 则超阶段范围且环境不可用 | **D-11**：进程内 asyncio 队列 + JSON 落盘恢复，Protocol 预留替换 |
| R13 | 无证据时缓存 Key 的证据快照 ID 未定义 | SPEC-004 §2.1：取字面量 `"none"` |
| R14 | 审计包导出含专家全文存在泄露风险 | SPEC-004 §3：默认脱敏（摘要+digest），`include_contents` 显式开关 |
| R15 | langgraph/fastapi 缺失时 import 即崩，违背"可关闭可配置" | SPEC-003/005：可选依赖惰性 import，缺失抛带安装指引的错误 |
| R16 | Verifier 评审标准可被误配到 Coordinator/Expert | SPEC-002 §1：模型级跨字段校验（Verifier 必有、Coordinator 必无） |
| R17 | legacy 测试基线存在 1 项失败（test_learning_module_config） | 记录为存量已知问题，不属于本方案范围；最终回归标准=不新增失败 |

## 4. 可测试性审查

- 全部验收标准均映射到具名测试文件与具名用例（各 SPEC 末节），无"不可验证验收项"。
- 量化门禁：核心六模块行覆盖率 ≥90%（pytest-cov 实测）；存量回归零新增失败。
- 全部测试不依赖外部服务（Redis 真连测除外，env 门控跳过）与外部 LLM API。

## 5. 批准结论

SPEC-000~006 通过审核，进入 Plan/TESTCASES 设计（docs/plan/）。此后 SPEC 变更须在本文件追加变更记录。
