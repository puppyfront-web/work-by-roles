# 节省回执（savings-receipt-v1）

每次 `ReviewSession.run()` 都附带一份 `result.savings`。它比较的是**同一次会审**：实际计费，以及这些优化如果没生效时的反事实基线。基线不发起第二次模型调用，也不编造节省比例。

单价由调用方传入（每 token）。没传单价时费用为 0，token 仍可核对。`receipt.priced(...)` 用同一批数量重算费用。

## 恒等式

```text
saved_tokens = baseline_tokens - actual_tokens = Σ lever.tokens
saved_cost   = baseline_cost   - actual_cost   = Σ lever.cost
```

三条杠杆固定为 `shared_prefix`、`skipped_unassigned`、`cache_hit`。优化都没生效时（或效果等价于没生效），三条杠杆和 `saved_*` 都是 0。

`actual_tokens` 是各次调用的 `prompt_tokens + completion_tokens`。本地响应缓存命中这两项为 0。

## 基线

同一份会审，假如下面三件事没有省下费用：

1. **没有共享前缀缓存。** 每个专家仍收到完整独立提示（安全护栏 + 团队共享上下文 + 角色契约 + 该角色的任务）。供应商若把其中一段按缓存价计费，基线改按未缓存的输入单价计。
2. **未分配的专家仍计一次空调用。** 与 `skip_unassigned_experts=False` 相同：用户输入是原始问题，不带「你的子任务」。提示 token 用本次计数器计算（默认启发式：CJK≈1，其余≈1/4）。
3. **缓存命中按未缓存提示 token 计费。** 本地响应缓存把省下的提示 token 加回基线，实际费用按 0。供应商缓存在 `included` 范围里已经含在 `prompt_tokens` 中，所以 token 差为 0，费用差仍在；`additional` 范围把缓存读和缓存写加进基线 token。

## 杠杆怎么归属

| 杠杆 | 计入什么 | 不计入什么 |
|---|---|---|
| `skipped_unassigned` | 实际被跳过、且原因是未分配的专家的反事实提示 token，费用 = 该 token × 输入单价 | 补全 token。调用没发生，不估计补全 |
| `shared_prefix` | 专家调用上，供应商回报的 `cached_prompt_tokens` / `cache_write_tokens`（`included` 或 `additional`） | 供应商回报 0 时为 0。对齐了前缀但没有命中，就不记节省 |
| `cache_hit` | 本地响应缓存（`cache_scope=local`）；协调者和复核人的供应商缓存 | 专家的供应商缓存（那部分在 `shared_prefix`） |

供应商只回报整段缓存 token，不按「安全护栏 + 团队共享上下文」和角色契约切开。前缀缓存从提示词开头命中，而编译器把这两段放在开头，所以专家调用上的供应商缓存**整笔**记入 `shared_prefix`。这是可核对的上界，里面可能含紧随共享段之后、同样被前缀缓存吃进的角色契约 token。内核不再按字符比例切一刀。

## 明确不算节省的部分

- **Token 预算跳过**（`token_budget_exceeded` / `skip_reason=budget`）写在 `budget_skipped` 里，不进入任何杠杆。少做了工作不是节省。
- **协调者没跑完**时，不估计还没分派的专家。
- **输出被 `max_tokens` 截断**省下多少，看不到被截掉的补全，不算。
- **只打开了响应缓存或语义缓存的开关、但这次没有命中**，`cache_hit` 为 0。
- 工作室不单独保存缓存写入单价；未传时按输入单价。

## 工作室与离线脚本

工作室把回执存在运行的 `savings_receipt`。用量报表把各次运行的 `saved_tokens` 和 `saved_cost` 加总，不另算一套比例。

`python scripts/token_savings_report.py` 套的是同一份公式，但数据来自启发式计数和演示 Invoker。输出里 `kind=offline_heuristic_demo`、`live_run_receipt=false`，每份回执的 `live_run=false`。它不是某次线上会审的回执。其中 `prompt_tokens_before/after` 只是提示词离线对比，不是回执。

## English

`SavingsReceipt` (`savings-receipt-v1`) is attached to every `ReviewSession` result. Baseline is the same review with three counterfactuals and no second model call: experts billed for a full independent prompt instead of a shared cached prefix, unassigned experts billed as one empty call (`skip_unassigned_experts=False`), and cache hits billed as uncached prompt tokens. `saved_* = baseline_* - actual_*`, and both equal the sum of `shared_prefix`, `skipped_unassigned`, and `cache_hit`. When those optimizations did nothing, `saved_*` is 0. Provider cached tokens on expert calls are attributed entirely to `shared_prefix` because the provider does not split them by section; a zero provider cache is a zero lever. Budget skips are listed and are not savings. Costs stay 0 until the caller supplies per-token prices. `scripts/token_savings_report.py` uses this schema as an offline heuristic demo (`live_run_receipt: false`), not as a live-run receipt.
