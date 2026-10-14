"""内容脱敏与安全风控（V1.x F1 / SPEC-007 §1）。

占位符稳定（同值同占位符）、规则可扩展、全链路可关闭；Core 零依赖。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from wbr.core.canonical import sha256_hex
from wbr.core.security.guard import InjectionDetector, InjectionReport, RiskLevel


@dataclass(frozen=True)
class RedactionRule:
    name: str
    pattern: str          # 正则；分组1 命中主体（无分组则整体）
    placeholder: str
    description: str = ""


def _default_rules() -> list[RedactionRule]:
    return [
        RedactionRule("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", "EMAIL"),
        RedactionRule("phone_cn", r"(?<!\d)1[3-9]\d{9}(?!\d)", "PHONE"),
        RedactionRule("id_card_cn", r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:[0-2]\d|3[01])\d{3}[\dXx](?!\d)", "IDCARD"),
        RedactionRule("api_key", r"(?:sk|pk|api[_-]?key|token)[-_=\s:]{0,3}[A-Za-z0-9\-_]{12,}", "APIKEY"),
        RedactionRule("credit_card", r"(?<!\d)(?:\d[ -]?){13,16}\d(?!\d)", "CREDITCARD"),
        RedactionRule("ipv4", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", "IPV4"),
    ]


def _card_ok(digits: str) -> bool:
    """Luhn 校验，降低普通数字串误报。"""
    total, alt = 0, False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


class RedactionReport(BaseModel):
    findings: list[dict[str, Any]] = Field(default_factory=list)  # [{rule, count, placeholder}]
    redacted_text: str = ""
    original_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"findings": self.findings, "redacted_text": self.redacted_text}


class Redactor:
    """脱敏器：正则规则 → 稳定占位符（[RULE_n]，同值同占位符）。"""

    def __init__(self, rules: list[RedactionRule] | None = None, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.rules = rules if rules is not None else _default_rules()

    def redact(self, text: str) -> RedactionReport:
        if not self.enabled:
            return RedactionReport(redacted_text=text, original_digest=sha256_hex(text))
        import re

        placeholders: dict[str, str] = {}   # 原值 -> 占位符
        counters: dict[str, int] = {}       # 规则 -> 已用序号
        rule_counts: dict[str, int] = {}    # 规则名 -> 命中数
        out = text
        for rule in self.rules:
            try:
                pattern = re.compile(rule.pattern)
            except re.error:  # 用户自定义规则容错
                continue

            def _sub(m: re.Match, _rule=rule) -> str:
                value = m.group(1) if m.groups() else m.group(0)
                if _rule.name == "credit_card" and not _card_ok(value.replace(" ", "").replace("-", "")):
                    return value  # 非 Luhn 合法卡号不脱敏（降误报）
                if value not in placeholders:
                    counters[_rule.name] = counters.get(_rule.name, 0) + 1
                    placeholders[value] = f"[{_rule.placeholder}_{counters[_rule.name]}]"
                    rule_counts[_rule.name] = rule_counts.get(_rule.name, 0) + 1
                return placeholders[value]

            out = pattern.sub(_sub, out)
        findings = [{"rule": name, "count": count} for name, count in sorted(rule_counts.items())]
        return RedactionReport(findings=findings, redacted_text=out, original_digest=sha256_hex(text))

    def redact_obj(self, obj: Any) -> tuple[Any, RedactionReport]:
        """递归清洗 dict/list 中的字符串值（返回新结构，不改原对象）。"""
        merged = RedactionReport(original_digest=sha256_hex(obj if isinstance(obj, str) else repr(obj)))
        merged.redacted_text = ""  # 对象模式不输出整篇文本

        def _walk(node: Any) -> Any:
            if isinstance(node, str):
                rep = self.redact(node)
                merged.findings.extend(rep.findings)
                return rep.redacted_text
            if isinstance(node, dict):
                return {k: _walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_walk(v) for v in node]
            return node

        return _walk(obj), merged


class RiskAction(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


class RiskControlPolicy(BaseModel):
    max_injection_risk: RiskLevel = RiskLevel.HIGH   # 达到该级别即阻断
    pii_action: str = "redact"                        # redact | block | off


class RiskDecision(BaseModel):
    allowed: bool
    action: str                                       # allow | redact | block
    injection: InjectionReport
    redaction: RedactionReport | None = None
    reason: str = ""


_RISK_ORDER = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]


def assess_and_redact(
    text: str,
    *,
    detector: InjectionDetector | None = None,
    redactor: Redactor | None = None,
    policy: RiskControlPolicy | None = None,
) -> RiskDecision:
    """风控评估 + 脱敏：注入超阈值阻断 → PII 按策略脱敏/阻断/忽略。"""
    detector = detector or InjectionDetector()
    redactor = redactor or Redactor()
    policy = policy or RiskControlPolicy()
    report = detector.detect(text)
    if (
        report.is_suspicious
        and _RISK_ORDER.index(report.risk_level) >= _RISK_ORDER.index(policy.max_injection_risk)
    ):
        return RiskDecision(
            allowed=False, action="block", injection=report,
            reason=f"注入风险 {report.risk_level.value} 达到阻断阈值",
        )
    if policy.pii_action == "off":
        return RiskDecision(allowed=True, action="allow", injection=report)
    redaction = redactor.redact(text)
    if policy.pii_action == "block" and redaction.findings:
        return RiskDecision(
            allowed=False, action="block", injection=report, redaction=redaction,
            reason=f"检出敏感信息 {len(redaction.findings)} 类，策略为阻断",
        )
    if not redaction.findings:
        return RiskDecision(allowed=True, action="allow", injection=report)
    return RiskDecision(allowed=True, action="redact", injection=report, redaction=redaction)


#: 默认脱敏规则库（可扩展替换）
DEFAULT_REDACTION_RULES = _default_rules
