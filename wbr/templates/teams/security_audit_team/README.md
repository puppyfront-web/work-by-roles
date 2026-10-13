# 代码安全审计专家团（security_audit_team）

开箱即用的代码安全审计团队模板：按注入 / 认证越权 / 数据泄露三个审计面并行审计，Verifier 独立复核与严重级校准。

## 角色构成

| role_id | 类型 | 职责 |
|---|---|---|
| `coordinator` | coordinator | 审计范围界定、审计面拆解、分派汇总 |
| `injection_auditor` | expert | SQL/命令/模板/Prompt 注入（污点路径追踪） |
| `authz_auditor` | expert | 认证、会话、水平/垂直越权 |
| `data_leak_auditor` | expert | 敏感数据暴露、日志泄露、传输风险 |
| `verifier` | verifier | 发现复核（准确性/严重级校准/覆盖度三维裁决） |

安全约束：专家禁止输出可直接利用的攻击载荷；报告不含完整敏感数据样本；critical 发现不得未经复核降级。

## 使用

```python
from wbr.templates.registry import load_team_spec
from wbr.core.orchestration import ReviewSession, <你的 ModelInvoker 实现>

spec = load_team_spec("security_audit_team")
session = ReviewSession(
    coordinator_contract=spec.coordinator,
    expert_contracts=spec.experts,
    verifier_contract=spec.verifier,
    invoker=your_invoker,
)
result = session.run("审计：payment-service 仓库的 v2.3.1 版本")
```

CLI 快速体验（内置演示输出）：

```bash
wbr run-team security_audit_team "审计：payment-service 的登录与支付接口"
```
