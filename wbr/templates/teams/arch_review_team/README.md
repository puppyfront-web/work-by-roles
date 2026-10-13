# 软件架构评审专家团（arch_review_team）

开箱即用的架构评审团队模板：Coordinator 拆解分派 → 三位专家独立评审 → Verifier 复核裁决，分歧留存。

## 角色构成

| role_id | 类型 | 职责 |
|---|---|---|
| `coordinator` | coordinator | 解析请求、任务拆解、分派与汇总 |
| `api_design_expert` | expert | API 契约、一致性、演进兼容（需证据引用） |
| `data_architect` | expert | 数据模型、存储选型、一致性扩展性（需证据引用） |
| `infra_expert` | expert | 可用性、扩展性、部署成本（需证据引用） |
| `verifier` | verifier | 按三维标准（证据质量/技术正确性/风险覆盖）独立裁决 |

## 使用

```python
from wbr.templates.registry import load_team_spec
from wbr.core.orchestration import ReviewSession, <你的 ModelInvoker 实现>

spec = load_team_spec("arch_review_team")
session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=your_invoker,
)
result = session.run("评审：订单系统从单体拆分为微服务的方案")
```

CLI 快速体验（内置演示输出，不调用外部模型）：

```bash
wbr run-team arch_review_team "评审：订单系统从单体拆分为微服务的方案"
```

## 回归基准

把本团队与黄金用例库绑定即可获得可回归的评审基线（契约哈希锁定，见 docs/HARNESS.md）。
