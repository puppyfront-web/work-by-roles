"""Token 全链路治理（SPEC-003 §4）：计数 / 计量 / 预算降级。"""
from __future__ import annotations

import math
import threading
import time
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from wbr.core.exceptions import TokenBudgetExceededError


# ---- 计数 ----
@runtime_checkable
class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class HeuristicTokenCounter(BaseModel):
    """确定性启发式计数（D-07）：CJK≈1 token/字符，其他≈1 token/4 字符。"""

    def count(self, text: str) -> int:
        if not text:
            return 0
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff" or "\u3000" <= ch <= "\u303f")
        other = len(text) - cjk
        return cjk + math.ceil(other / 4) if other else cjk


# ---- 计量 ----
class UsageRecord(BaseModel):
    role_id: str
    step: str
    prompt_tokens: int
    completion_tokens: int
    trace_id: str = ""
    degraded: bool = False
    cached_prompt_tokens: int = 0
    cache_write_tokens: int = 0
    cache_miss_tokens: int = 0
    cache_scope: str = "unknown"
    ts: float = Field(default_factory=time.time)

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_usage(self):
        from wbr.core.orchestration.invoker import TokenUsage

        return TokenUsage(
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            cached_prompt_tokens=self.cached_prompt_tokens,
            cache_write_tokens=self.cache_write_tokens,
            cache_miss_tokens=self.cache_miss_tokens,
            cache_scope=self.cache_scope,
        )


class TokenMeter:
    """按角色 / 步骤 / 任务三维统计用量。"""

    def __init__(self, *, counter: TokenCounter | None = None, audit=None) -> None:
        self.counter = counter or HeuristicTokenCounter()
        self._records: list[UsageRecord] = []
        self._lock = threading.Lock()
        self._audit = audit

    def count_text(self, text: str) -> int:
        return self.counter.count(text)

    def record(
        self,
        role_id: str,
        step: str,
        usage,  # TokenUsage | 任意含 prompt_tokens/completion_tokens 对象
        trace_id: str = "",
        *,
        degraded: bool = False,
    ) -> UsageRecord:
        rec = UsageRecord(
            role_id=role_id,
            step=step,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            trace_id=trace_id,
            degraded=degraded,
            cached_prompt_tokens=int(getattr(usage, "cached_prompt_tokens", 0) or 0),
            cache_write_tokens=int(getattr(usage, "cache_write_tokens", 0) or 0),
            cache_miss_tokens=int(getattr(usage, "cache_miss_tokens", 0) or 0),
            cache_scope=str(getattr(usage, "cache_scope", "unknown") or "unknown"),
        )
        with self._lock:
            self._records.append(rec)
        if self._audit is not None:
            from wbr.core.audit.models import AuditEvent, AuditEventType

            self._audit.append(
                AuditEvent(
                    event_type=AuditEventType.TOKEN_RECORD,
                    trace_id=trace_id or "no-trace",
                    role_id=role_id,
                    payload={
                        "step": step,
                        "prompt_tokens": rec.prompt_tokens,
                        "completion_tokens": rec.completion_tokens,
                        "cached_prompt_tokens": rec.cached_prompt_tokens,
                        "cache_write_tokens": rec.cache_write_tokens,
                        "cache_miss_tokens": rec.cache_miss_tokens,
                        "cache_scope": rec.cache_scope,
                        "degraded": degraded,
                    },
                )
            )
        return rec

    # ---- 聚合查询 ----
    def _sum(self, key) -> int:
        with self._lock:
            return sum(r.total for r in self._records if key(r))

    def usage_by_role(self, role_id: str) -> int:
        return self._sum(lambda r: r.role_id == role_id)

    def usage_by_step(self, step: str) -> int:
        return self._sum(lambda r: r.step == step)

    @property
    def usage_total(self) -> int:
        return self._sum(lambda _r: True)

    @property
    def records(self) -> list[UsageRecord]:
        with self._lock:
            return list(self._records)

    @property
    def cached_prompt_tokens(self) -> int:
        with self._lock:
            return sum(r.cached_prompt_tokens for r in self._records)

    def estimate_cost(self, **prices: float) -> dict[str, float]:
        """把各条记录的 estimate_cost 相加。prices 同 TokenUsage.estimate_cost。"""
        totals = {"input": 0.0, "output": 0.0, "total": 0.0, "baseline_total": 0.0, "savings": 0.0}
        for rec in self.records:
            part = rec.as_usage().estimate_cost(**prices)
            for key in totals:
                totals[key] += part[key]
        return totals


# ---- 预算与降级 ----
class BudgetAction(str, Enum):
    OK = "ok"
    DEGRADE = "degrade"
    REJECT = "reject"


class BudgetPolicy(BaseModel):
    max_total_tokens: int = Field(default=100000, gt=0)
    per_role: dict[str, int] = Field(default_factory=dict)
    on_exceed: BudgetAction = BudgetAction.DEGRADE


class BudgetDecision(BaseModel):
    action: BudgetAction
    reason: str = ""
    role_id: str | None = None


class TokenBudget:
    """预算管控：超限按策略降级或拒绝。"""

    def __init__(self, policy: BudgetPolicy, meter: TokenMeter) -> None:
        self.policy = policy
        self.meter = meter

    def check(self, role_id: str | None = None, *, incoming: int = 0) -> BudgetDecision:
        """检查已用量。incoming 是即将发生的提示 token 估计，默认 0（与旧调用兼容）。"""
        incoming = max(0, incoming)
        used = self.meter.usage_total
        projected = used + incoming
        if projected >= self.policy.max_total_tokens:
            if self.policy.on_exceed == BudgetAction.REJECT:
                raise TokenBudgetExceededError(
                    f"任务 Token 预算耗尽: {projected}/{self.policy.max_total_tokens}",
                    details={"used": used, "incoming": incoming, "limit": self.policy.max_total_tokens},
                )
            return BudgetDecision(
                action=BudgetAction.DEGRADE,
                reason=f"任务总量超限 {projected}>={self.policy.max_total_tokens}",
            )
        if role_id and role_id in self.policy.per_role:
            limit = self.policy.per_role[role_id]
            used_role = self.meter.usage_by_role(role_id)
            projected_role = used_role + incoming
            if projected_role >= limit:
                if self.policy.on_exceed == BudgetAction.REJECT:
                    raise TokenBudgetExceededError(
                        f"角色 {role_id} Token 预算耗尽: {projected_role}/{limit}",
                        details={
                            "role_id": role_id,
                            "used": used_role,
                            "incoming": incoming,
                            "limit": limit,
                        },
                    )
                return BudgetDecision(
                    action=BudgetAction.DEGRADE,
                    reason=f"角色 {role_id} 超限 {projected_role}>={limit}",
                    role_id=role_id,
                )
        return BudgetDecision(action=BudgetAction.OK)

    def remaining(self, role_id: str | None = None) -> int:
        left = self.policy.max_total_tokens - self.meter.usage_total
        if role_id and role_id in self.policy.per_role:
            left = min(left, self.policy.per_role[role_id] - self.meter.usage_by_role(role_id))
        return max(0, left)


def degrade_history(
    history: list[dict],
    *,
    counter: TokenCounter,
    max_tokens: int,
    keep_system: bool = True,
) -> list[dict]:
    """预算降级：从最旧的非 system 消息开始丢弃，保留 system 与最近消息。

    history 元素形如 {"role": "...", "content": "..."}。
    """
    if not history:
        return []
    kept: list[dict] = []
    system_msgs = [m for m in history if m.get("role") == "system"] if keep_system else []
    rest = [m for m in history if not (keep_system and m.get("role") == "system")]
    budget = max_tokens - sum(counter.count(str(m.get("content", ""))) for m in system_msgs)
    # 从最新往回保留
    picked: list[dict] = []
    for msg in reversed(rest):
        cost = counter.count(str(msg.get("content", "")))
        if budget - cost < 0 and picked:
            break
        budget -= cost
        picked.append(msg)
    kept = system_msgs + list(reversed(picked))
    return kept
