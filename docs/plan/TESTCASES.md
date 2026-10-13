# 测试用例设计（TESTCASES）

> 用例编号规则：`TC-<阶段>-<模块>-<序号>`。执行载体：pytest。本表为 TDD 的"测试先行"依据；实现与测试同仓演进，测试断言以代码为准持续细化，但**验收必测项（标 ★）不得删减**。

## 阶段0（tests/wbr/phase0/）

| 编号 | 用例 | 断言要点 |
|---|---|---|
| TC-0-STRUCT-1 ★ | 目录结构对齐 | `wbr/core`、`wbr/adapters`、`wbr/app` 及 SPEC-000 §5 关键文件存在 |
| TC-0-STRUCT-2 ★ | 全 core 模块 import 冒烟 | phase0 允许 import 的模块全部可导入，且 core 未引入禁用三方依赖（静态扫描 import） |
| TC-0-EXC-1 ★ | 异常体系 | 每个异常可构造、`code` 符合 Exxxx、str 含 `[code]` 与 trace_id、`to_dict()` 可 JSON 序列化；WBRError 可捕获子类 |
| TC-0-CTX-1 | trace_id 生成唯一性 | 1000 次生成无重复、`wbr-` 前缀+32hex |
| TC-0-CTX-2 | 上下文传播 | set 后同协程/同线程可见；跨线程默认不可见（需显式传递） |
| TC-0-CFG-1 ★ | YAML+代码配置 | YAML 文件加载、代码 overrides 覆盖、默认值兜底 |
| TC-0-CFG-2 | overlay 不可变 | overlay 不改原实例；未知键忽略+告警；非法 YAML 报 ConfigError(E1001)；PyYAML 缺失路径报错可诊断（mock） |
| TC-0-LOG-1 | JSON 日志 | 输出单行 JSON，含 ts/level/trace_id/message |
| TC-0-LOG-2 | setup 幂等 | 两次 setup handler 数量不翻倍 |
| TC-0-BUS-1 ★ | 审计总线不阻塞 | 订阅者抛异常不影响 publish 调用方；error 计数增加 |
| TC-0-BUS-2 | 溢出丢弃计数 | 队列打满后 dropped_count 递增、published 继续成功 |
| TC-0-BUS-3 | 多订阅者广播 | 事件按序到达全部订阅者 |
| TC-0-PKG-1 ★ | 可安装 | `pip install -e .` 后 `import wbr; wbr.__version__=="0.1.0"` |
| TC-0-LEGACY-1 ★ | 存量回归 | 全量 legacy pytest 无新增失败 |

## 阶段1（tests/wbr/phase1/）

| 编号 | 用例 | 断言要点 |
|---|---|---|
| TC-1-SCHEMA-1 ★ | 子集校验器：通过 | type(object/array/string/number/integer/boolean)、required、properties、items、enum、min/maxLength、min/max、additionalProperties:false 全支持 |
| TC-1-SCHEMA-2 ★ | 子集校验器：拒绝 | 每种约束的违规样例被拒；错误信息含路径 |
| TC-1-CONTRACT-1 ★ | 契约构建与 hash | build 生成 64hex hash；等价契约 hash 相同；任一业务字段改动 hash 变化 |
| TC-1-CONTRACT-2 ★ | 序列化往返 | to_json→from_json 深度相等；save/load 文件往返 |
| TC-1-CONTRACT-3 | 跨字段校验 | Verifier 无 criteria 拒绝；Coordinator 带 criteria 拒绝；空白名单+deny_by_default=禁用全部工具 |
| TC-1-CONTRACT-4 | with_changes 版本派生 | 新实例、旧实例不变、版本号 bump、hash 重算 |
| TC-1-CONTRACT-5 | 字段约束 | role_id 正则、token_quota>0、weight∈(0,1]、step_id 唯一 |
| TC-1-DIFF-1 ★ | 四类变更分类 | 改 sop→RULE；改 schema required→SCHEMA；放宽 forbidden→FORBIDDEN/HIGH；扩 whitelist→POLICY/HIGH；改 description→FIELD/LOW |
| TC-1-DIFF-2 | 列表对齐 | steps 按 step_id 对齐产生 ADDED/REMOVED/MODIFIED 而非全量替换 |
| TC-1-DIFF-3 | has_breaking | 存在 HIGH 时 True；DiffReport to_json |
| TC-1-COMPILE-1 ★ | 段序完整 | 输出按 护栏头→契约主体→输出约束→禁区→证据 规则拼接；缺省段跳过 |
| TC-1-COMPILE-2 ★ | 用户输入隔离 | 用户输入被 USER_INPUT 边界符包裹且位于 system 之外的用户块 |
| TC-1-COMPILE-3 ★ | 边界符转义 | 用户输入内含边界标记时被转义，无法伪造闭合 |
| TC-1-COMPILE-4 | 确定性 | 同输入两次编译除 trace_id 外逐字节相同 |
| TC-1-AUDIT-1 ★ | 强类型事件 | 各 event_type 事件创建、append、events_for(trace) 过滤正确 |
| TC-1-AUDIT-2 | 行为记录摘要 | RoleBehaviorRecord 只含 digest 不含全文 |
| TC-1-MEM-1 ★ | 四层作用域隔离 | 同 key 不同层/不同 role/不同 session 取值互不串扰（12+ 参数化） |
| TC-1-MEM-2 ★ | 权限校验 | 无 read 权限读→E3001；无 write 权限写→E3001；越权均产生 MEMORY_ACCESS 审计 |
| TC-1-MEM-3 | 全局写双保险 | write_layers 含 GLOBAL_SHARED 但未显式 allow_global_write 仍拒绝 |
| TC-1-FLOW-1 ★ | 会审全链路 | 3 专家（ScriptedInvoker）并行→全部 COMPLETED→Verifier 裁决 pass→final_answer 非空→审计链含 STARTED/COMPLETED/VERDICT/REVIEW_COMPLETED |
| TC-1-FLOW-2 ★ | 分歧留存 | 两专家对同一子问题 conclusion 不同→disagreements 非空且不被仲裁合并 |
| TC-1-FLOW-3 | 专家失败降级 | 单专家 invoker 抛错→该专家 FAILED、其余正常、会审整体完成且 status 反映降级 |
| TC-1-FLOW-4 | strict schema 拦截 | 专家输出不符 schema→SCHEMA_VIOLATION、strict 下 FAILED、审计留痕 |
| TC-1-FLOW-5 | 禁区检测 | 输出命中 forbidden 关键词→FORBIDDEN_VIOLATION 记录 |
| TC-1-FLOW-6 | Verifier 裁决 | 分数低于 threshold→verdict.fail 且 final_answer 标注复核未通过 |
| TC-1-DEMO-1 ★ | 独立运行 Demo | examples/phase1_core_demo.py 以子进程跑通退出码 0（环境无 langgraph 依赖路径） |

## 阶段2（tests/wbr/phase2/）

| 编号 | 用例 | 断言要点 |
|---|---|---|
| TC-2-SEC-1 ★ | 注入规则库 | ≥15 条中英文注入样例全部检出（参数化）；正常文本零误报样例集 |
| TC-2-SEC-2 | 风险分级 | 高危规则 score 阈值分级正确 |
| TC-2-SEC-3 | sanitize | 边界符中和+防御注记；guard_user_input 策略门控（允许低危/阻断高危） |
| TC-2-SEC-4 ★ | 二阶注入 | wrap_external_content 包裹+声明；scan 检出工具返回中的注入；默认不阻断仅标记 |
| TC-2-TOK-1 ★ | 启发式计数 | 中文/英文/混合样例计数符合 D-07 规则且确定性 |
| TC-2-TOK-2 | 多维计量 | 按 role/step/task 聚合查询正确 |
| TC-2-TOK-3 ★ | 预算降级 | 超总预算→degrade：history 被截断、system 保留、审计 degraded=True；超硬限→reject(E5001) |
| TC-2-STO-1 ★ | 双后端协议一致 | Memory/FakeRedis 后端通过同一协议测试（get/set/delete/keys/append/ttl） |
| TC-2-STO-2 ★ | 记忆隔离 | 4 层 × 双后端：同 key 不同 role/session 互不可见 |
| TC-2-STO-3 | Redis 键编码 | 键格式 `wbr:{layer}:{scope}:{key}`；真连测试 env 门控 skip |
| TC-2-LG-MAP-1 ★ | 契约→Message | SystemMessage=system_prompt、HumanMessage=user_block、历史转换正确 |
| TC-2-LG-STATE-1 ★ | State 注入 | 注入 wbr__meta 不覆盖既有业务键；merge 深合并 |
| TC-2-LG-INT-1 ★ | Schema 拦截 | 违规输出被拦、审计事件产生、enabled=False 时放行 |
| TC-2-LG-INT-2 ★ | 禁区拦截 | 命中 forbidden 被拦；独立开关生效 |
| TC-2-LG-TOOL-1 ★ | 工具权限 | 白名单内放行、白名单外拒绝（E8002）、拒绝产生审计 |
| TC-2-LG-GUARD-1 ★ | 3 行接入存量图 | 存量图（含业务键+stub 节点）wrap 后：业务键不变、节点逻辑照常、违规输出被拦 |
| TC-2-LG-GUARD-2 | wrap 可关闭组件 | security=False/token 关闭时对应检查跳过 |
| TC-2-LG-HITL-1 ★ | 审批状态机 | PENDING→APPROVED/REJECTED 合法迁移；非法迁移抛错 |
| TC-2-LG-HITL-2 | interrupt 映射 | 有 langgraph 时经 interrupt 暂停、Command(resume) 恢复继续执行 |
| TC-2-LG-CKPT-1 ★ | 断点续跑 | wrap 后图 + MemorySaver：interrupt 暂停→恢复→最终结果正确 |
| TC-2-LG-E2E-1 ★ | 原生会审图 | build_review_graph 生成图 invoke 全流程出结果 |
| TC-2-DEMO-1 ★ | 双示例运行 | examples/phase2 两个脚本子进程运行退出码 0 |

## 阶段3（tests/wbr/phase3/）

| 编号 | 用例 | 断言要点 |
|---|---|---|
| TC-3-CASE-1 ★ | 用例库持久化 | Suite save/load 往返；case_id 重复拒绝 |
| TC-3-BASE-1 ★ | 基线快照 | 快照锁定 contract_hashes/suite_hash/model 指纹；is_current 检出契约变更 |
| TC-3-ENG-1 ★ | 批量回归 | 多用例跑完产出 Report；每 case 有 review_id/trace_id；passed 判定正确 |
| TC-3-MET-1 ★ | 六项指标 | 构造已知结果：compliance/schema/forbidden/evidence/stability/disagreement 六率逐项断言（参数化 ≥6 组） |
| TC-3-MET-2 ★ | 退化检测 | 人为构造指标下滑→detect_degradation 报出；阈值边界 |
| TC-3-MET-3 | 一键回归对比 ★ | 修改契约（放宽 schema）→重跑→Report 与旧报告对比、缓存联动失效 |
| TC-3-JUDGE-1 ★ | Judge 钩子 | HeuristicJudge 关键词命中率计分；注入 engine 后 CaseResult.judge_score 生效并参与 passed |
| TC-3-CACHE-1 ★ | Key 三要素 | 同契约同问题不同证据→不同 key；hash 冲突不可能（构造不同输入断言 key 互异） |
| TC-3-CACHE-2 ★ | 命中与统计 | put→get 命中；miss 计数；hit_rate 计算；enabled=False 全 miss |
| TC-3-CACHE-3 ★ | 契约变更失效 | 主动 invalidate 与被动 hash 校验双路径；旧条目绝不返回 |
| TC-3-CACHE-4 ★ | 不脏数据 | 相同契约+问题但证据不同→不命中；LRU 驱逐正确 |
| TC-3-CACHE-5 | Redis 后端 | FakeRedis 桥接后行为一致；真连 env 门控 |
| TC-3-PACK-1 ★ | 审计包结构 | 必备顶层键齐全；digest 对同输入稳定、对内容变化敏感 |
| TC-3-PACK-2 | 脱敏导出 | include_contents=False 时无专家全文、含摘要 |
| TC-3-REG-1 ★ | 修改契约一键回归全链路 | 保存契约→改 forbidden→回归→报告退化/指标/缓存失效联动完整 |

## 阶段4（tests/wbr/phase4/）

| 编号 | 用例 | 断言要点 |
|---|---|---|
| TC-4-STORE-1 ★ | 契约注册表 | create/get/update(版本+1)/delete/list_versions/get_version/diff_versions |
| TC-4-TASK-1 ★ | InlineQueue | submit→立即执行→DONE 含结果；失败→FAILED 含 error |
| TC-4-TASK-2 ★ | 异步 worker | asyncio 队列消费；PENDING→RUNNING→DONE 状态流转 |
| TC-4-TASK-3 | 落盘恢复 | JsonTaskStore 重启后 DONE 可查、PENDING 重投递 |
| TC-4-API-C-1 ★ | 契约 CRUD | POST/GET/PUT/DELETE 全路径 200/201；PUT 自动新版本+diff 可查 |
| TC-4-API-C-2 | 错误规范 ★ | 未知 cid→404 E2xxx；重复版本→409；非法 body→422；错误体统一结构 |
| TC-4-API-R-1 ★ | 会审 API | POST /reviews→task_id→轮询 DONE→结果含 disagreements；GET 列表 |
| TC-4-API-H-1 ★ | 回归 API | 建套件→提交回归→报告含 metrics 六项 |
| TC-4-API-A-1 ★ | 审计导出 | /audits/export 返回合法 AuditPack JSON；contents 开关生效 |
| TC-4-API-X-1 | 健康检查 | /healthz 含版本与组件开关 |
| TC-4-CANVAS-1 ★ | 静态资源 | /canvas 200 且 HTML 引用的 js/css 均可访问；页面含挂载点与分歧高亮关键标识 |
| TC-4-DEMO-1 | 可演示形态 | examples/phase4_demo.md 记录启动→搭建→运行→导出全路径 |

## 阶段5（tests/wbr/phase5/）

| 编号 | 用例 | 断言要点 |
|---|---|---|
| TC-5-TPL-1 ★ | 双模板加载 | list_teams 含两套；load_team 全角色通过 RoleContract 模型校验 |
| TC-5-TPL-2 | 模板完整性 | 每契约 SOP≥3、verifier criteria≥3 维、禁区非空、schema 非空 |
| TC-5-TPL-3 ★ | 模板端到端 | arch_review_team 直接驱动 ReviewSession+RegressionEngine 全流程通过 |
| TC-5-CLI-1 | wbr CLI | version/list-teams 子进程冒烟 |
| TC-5-PKG-1 ★ | 打包 | 版本==1.0.0；`python -m build` 产出 sdist+wheel；wheel 含 templates 资源 |
| TC-5-PERF-1 | 基准 | 5 专家会审<2s、缓存命中<1ms、10k 事件导出<2s（宽松阈值防抖动） |
| TC-5-QUAL-1 | 异常统一 | 静态扫描 core 无裸 except:pass；异常均 WBRError 子类 |
| TC-5-REG-1 ★ | 最终全量回归 | legacy + phase0-5 全绿，记录 FINAL.md |

★ = 验收必测项，共 62 项。
