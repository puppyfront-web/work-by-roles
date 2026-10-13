"""WBRGuard：存量 LangGraph 项目的 3 行接入守卫（SPEC-003 §1.5 / R8）。

包装语义（可关闭、可配置，规则6）：
- 前置：Trace 建立、输入防注入扫描（record / block 可选）、wbr__meta 注入
- 后置：绑定输出键的 Schema 校验 + 禁区检测（record / block 可选）、审计
- 不改变用户 State 键语义、不改节点内部逻辑、checkpointer config 原样透传
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wbr.core.audit.models import AuditEvent, AuditEventType
from wbr.core.audit.trail import AuditTrail
from wbr.core.constants import USER_INPUT_CLOSE, USER_INPUT_OPEN
from wbr.core.context import new_trace_id, set_trace_id
from wbr.core.contract.models import RoleContract
from wbr.core.schema.validator import validate as schema_validate
from wbr.core.security.guard import InjectionDetector
from wbr.adapters.langgraph.interceptors import ForbiddenDetectorInterceptor, SchemaValidationInterceptor
from wbr.adapters.langgraph.state import WBR_META_KEY, inject_meta, read_meta


class _GuardConfig(BaseModel):
    security: str = "record"       # record | block | off
    schema_validation: str = "record"  # record | block | off
    forbidden_check: str = "record"    # record | block | off
    strict_security: bool = False      # True 时高危注入直接抛 SecurityViolationError


class WBRGuard:
    """用法（3 行接入）::

        guard = WBRGuard(contracts={"agent": contract})
        graph = guard.wrap(graph)
        result = graph.invoke({"question": "..."})
    """

    def __init__(
        self,
        contracts: dict[str, RoleContract] | RoleContract | None = None,
        *,
        output_keys: dict[str, RoleContract] | None = None,
        security: str = "record",
        schema_validation: str = "record",
        forbidden_check: str = "record",
        audit: AuditTrail | None = None,
        detector: InjectionDetector | None = None,
        token_meter: Any | None = None,
    ) -> None:
        if isinstance(contracts, RoleContract):
            contracts = {contracts.role_id: contracts}
        self.contracts: dict[str, RoleContract] = dict(contracts or {})
        self.output_keys: dict[str, RoleContract] = dict(output_keys or {})
        self.audit = audit
        self.detector = detector or InjectionDetector()
        self.token_meter = token_meter
        self.cfg = _GuardConfig(
            security=security, schema_validation=schema_validation, forbidden_check=forbidden_check
        )
        self._schema_ic = SchemaValidationInterceptor(enabled=schema_validation != "off", audit=audit)
        self._forbidden_ic = ForbiddenDetectorInterceptor(enabled=forbidden_check != "off", audit=audit)
        self.last_input_report = None
        self.last_violations: list[dict] = []

    # ---- 3 行接入入口 ----
    def wrap(self, graph: Any) -> "WBRGuardedGraph":
        return WBRGuardedGraph(graph, self)

    # ---- 节点级加固（可选） ----
    def guard_node(self, contract: RoleContract):
        """装饰器：包一层节点函数——meta 注入 + 输出校验（strict 违规抛错）。"""

        def decorator(fn):
            def wrapper(state: dict[str, Any], *args, **kw):
                ctx = read_meta(state)
                set_trace_id(ctx.get("trace_id") or new_trace_id())
                result = fn(state, *args, **kw)
                update = result if isinstance(result, dict) else {}
                for key, value in update.items():
                    if isinstance(value, (dict,)) and key != WBR_META_KEY:
                        ic = self._schema_ic.check(contract, value)
                        if not ic.allowed and contract.output_spec.strict:
                            raise ValueError(f"[wbr] 节点输出 Schema 校验失败({contract.role_id}): {ic.detail}")
                        fi = self._forbidden_ic.check(contract, str(value))
                        if not fi.allowed and contract.output_spec.strict:
                            raise ValueError(f"[wbr] 节点输出命中禁区({contract.role_id}): {fi.detail}")
                return result

            wrapper.__name__ = getattr(fn, "__name__", "wbr_guarded_node")
            return wrapper

        return decorator

    # ---- 内部：输入扫描 ----
    def scan_input(self, state: dict[str, Any]) -> dict:
        """扫描输入 State 中的字符串值（跳过 wbr__ 命名空间与边界块内部）。"""
        texts = []
        for k, v in state.items():
            if k.startswith("wbr__"):
                continue
            if isinstance(v, str):
                texts.append(v)
            elif isinstance(v, list):
                texts.extend(x for x in v if isinstance(x, str))
        merged_text = "\n".join(texts)
        report = self.detector.detect(merged_text)
        self.last_input_report = report
        return report.to_dict()

    def _emit(self, event_type: AuditEventType, payload: dict) -> None:
        if self.audit is not None:
            self.audit.append(AuditEvent(event_type=event_type, trace_id="no-trace", payload=payload))


class WBRGuardedGraph:
    """图包装器：invoke/stream 前后插入守卫逻辑。"""

    def __init__(self, graph: Any, guard: WBRGuard) -> None:
        self._graph = graph
        self._guard = guard

    @property
    def inner(self) -> Any:
        return self._graph

    def invoke(self, input_state: dict[str, Any] | None = None, config: dict | None = None, **kw) -> Any:
        guard = self._guard
        # 非 dict 输入（如 langgraph Command(resume=...)）原样透传前置，仅做后置
        if input_state is not None and not isinstance(input_state, dict):
            result = self._graph.invoke(input_state, config, **kw)
            return self._post_process(result, new_trace_id(), {"skipped": True, "reason": "resume"})
        state = dict(input_state or {})
        trace_id = read_meta(state).get("trace_id") or new_trace_id()
        set_trace_id(trace_id)

        # 前置：输入防注入
        report = guard.scan_input(state)
        if (
            guard.cfg.security != "off"
            and report["is_suspicious"]
            and (guard.cfg.security == "block" or (guard.cfg.strict_security and report["risk_level"] == "high"))
        ):
            from wbr.core.exceptions import SecurityViolationError

            raise SecurityViolationError(
                f"输入疑似注入攻击被阻断: {report['matches'][:3]}",
                details={"report": report},
            )
        state = inject_meta(state, {"trace_id": trace_id, "input_scan": report})
        guard._emit(AuditEventType.SESSION_STARTED, {"trace_id": trace_id})

        result = self._graph.invoke(state, config, **kw)
        return self._post_process(result, trace_id, report)

    def _post_process(self, result: Any, trace_id: str, report: dict) -> Any:
        """后置：输出键 Schema/禁区校验 + meta 回写。"""
        guard = self._guard
        violations: list[dict] = []
        if isinstance(result, dict):
            for key, contract in guard.output_keys.items():
                value = result.get(key)
                if not isinstance(value, dict):
                    continue
                ic = guard._schema_ic.check(contract, value)
                if not ic.allowed:
                    violations.append({"key": key, "kind": "schema", "detail": ic.detail})
                fi = guard._forbidden_ic.check(contract, str(value))
                if not fi.allowed:
                    violations.append({"key": key, "kind": "forbidden", "detail": fi.detail})
                blocked = any(v["key"] == key for v in violations) and (
                    (guard.cfg.schema_validation == "block" and any(v["kind"] == "schema" for v in violations if v["key"] == key))
                    or (guard.cfg.forbidden_check == "block" and any(v["kind"] == "forbidden" for v in violations if v["key"] == key))
                )
                if blocked:
                    result[key] = None
            meta = read_meta(result)
            meta["violations"] = violations
            meta["trace_id"] = trace_id
            meta["input_scan"] = report
            result[WBR_META_KEY] = meta
        guard.last_violations = violations
        guard._emit(
            AuditEventType.REVIEW_COMPLETED,
            {"trace_id": trace_id, "violations": len(violations)},
        )
        return result

    def stream(self, input_state: dict[str, Any] | None = None, config: dict | None = None, **kw):
        guard = self._guard
        if input_state is not None and not isinstance(input_state, dict):
            yield from self._graph.stream(input_state, config, **kw)
            return
        state = dict(input_state or {})
        trace_id = read_meta(state).get("trace_id") or new_trace_id()
        set_trace_id(trace_id)
        report = guard.scan_input(state)
        state = inject_meta(state, {"trace_id": trace_id, "input_scan": report})
        yield from self._graph.stream(state, config, **kw)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - 透传其余属性
        return getattr(self._graph, name)
