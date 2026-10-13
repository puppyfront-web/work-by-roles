# 阶段3 验收报告（PHASE3 · V0.3 Harness 评估体系与缓存）

> 日期：2026-10-14 · 依据：SPEC-004 · 版本：0.3.0 · 结论：**通过，进入阶段4**

## 1. 验收标准核对

| SPEC-004 验收标准 | 证据 | 结果 |
|---|---|---|
| 修改契约后可一键回归全量用例 | `test_rerun_after_contract_change_one_click_regression` + `examples/phase3_harness_demo.py`（基线漂移检出→回归→对比） | ✅ |
| 可自动检测专家能力退化 | `test_detect_degradation` + Demo 输出：compliance/schema/evidence/pass 四项 Δ-1.0 被报告 | ✅ |
| 指标计算正确（六项） | `test_six_metrics_known_values` 构造已知结果逐项断言 + 稳定性/分歧率参数化 | ✅ |
| 缓存 Key 三要素 | `test_key_three_factors`（契约/问题/证据任一变化 → key 变化；问题归一化 NFKC+strip） | ✅ |
| 缓存命中/未命中/命中率统计 | `test_hit_miss_and_stats`（hit_rate=0.5 精确断言） | ✅ |
| 契约变更自动失效 | 主动 `invalidate_contract`（含 Redis 后端）+ 被动防线（Key 隔离 + 篡改哈希被动校验）双层 | ✅ |
| 缓存精准、安全、不脏数据 | `test_no_cross_pollination` + LRU 驱逐 + enabled=False 直通 + FakeRedis 桥接 | ✅ |
| 审计包导出结构完整、脱敏、digest | `test_audit_pack.py`（format_version/generator/integrity；脱敏模式无全文含 digest；digest 稳定且敏感） | ✅ |
| 用例库/基线快照持久化 | `test_cases_baseline.py`（往返 + 一致性报告：契约漂移/角色缺失/套件变更） | ✅ |
| AI Judge 钩子 + 基础实现 | `test_judge.py`（HeuristicJudge 三因子加权 + 引擎挂接影响 passed 判定） | ✅ |
| harness/cache 模块覆盖率 ≥90% | harness: 100/100/100/94/91；cache: 90/98；pack 97 | ✅ |

**阶段3 测试统计：201 passed / 0 failed / 1 skipped（累计 phase0-3）**
**覆盖率：wbr.core 95%**

## 2. 关键实现记录
- 六项指标全部由 `from_case_results` 自动统计；`forbidden_violation_rate` 语义为"越低越好"，退化检测中按取反方向判定。
- 缓存键为最终 sha256，契约失效的主动路径对最终哈希键采用全扫比对（`delete_by_prefix` 不可用时自动降级）；被动路径由 Key 三要素构造保证 + 条目哈希被动校验双保险。
- JudgeScore 以 Protocol 注入 RegressionEngine，低分可判用例失败（`judge_pass_threshold`）。
- 回归引擎支持 `stability_runs` 重复执行以计算专家结论稳定性。

## 3. 交付物清单
- Core：`wbr/core/harness/{cases,baseline,engine,metrics,judge}`、`wbr/core/cache/{backends,contract_cache}`、`wbr/core/audit/pack`
- Adapter：`RedisCacheBackend`（adapters/storage/redis_backend.py）
- 测试：`tests/wbr/phase3/`（7 文件 36 用例）
- 示例：`examples/phase3_harness_demo.py` + `examples/tests_helpers.py`（实际运行通过，含真实退化检出输出）
- 文档：SPEC-004、本报告

## 4. 遗留事项
- AI Judge 的 LLM 实现留待 V1.x（钩子与启发式基实现已就位，符合 SPEC 非目标约束）。
- 高级语义缓存（向量匹配）按方案规划置于 V1.x。
