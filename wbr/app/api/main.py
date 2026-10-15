"""WBR API 服务（SPEC-005 §1）：契约 CRUD / 会审调度 / Harness 回归 / 审计导出。

- fastapi 惰性导入，缺失时给出安装指引（R15）
- 统一错误体：{"error": {"code", "message"}}（全部经 WBRError 子类 + 映射表）
- 画布 SPA 由 /canvas 静态托管（D-10）
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

import wbr
from wbr.app.store import ContractRegistry
from wbr.app.tasks.queue import (
    InlineTaskQueue,
    InProcessTaskQueue,
    JsonTaskStore,
    TaskKind,
    TaskQueue,
    TaskRecord,
)
from wbr.core.audit.pack import AuditPackBuilder
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import AppError, WBRError
from wbr.core.harness import BaselineSnapshot, CaseSuite, RegressionEngine
from wbr.core.orchestration import ReviewSession, ScriptedInvoker

_STATIC_DIR = Path(__file__).resolve().parent.parent / "canvas" / "static"

# WBRError code → HTTP 状态码
_ERROR_STATUS = {
    "E1001": 400,
    "E2001": 422,
    "E3001": 403,
    "E7001": 422,
    "E8001": 400,
    "E9001": 500,
    "E9002": 409,  # 契约已存在
    "E9003": 404,  # 契约不存在
    "E9004": 409,  # role_id 不可变更
    "E9005": 409,  # 无变化
    "E9006": 404,  # 任务不存在
    "E9007": 404,  # 用例库不存在
    "E9022": 422,  # 请求体校验失败
}


class ContractPayload(BaseModel):
    contract: dict[str, Any]


class ReviewSubmit(BaseModel):
    question: str = Field(min_length=1)
    coordinator: str
    experts: list[str] = Field(min_length=1)
    verifier: str


class RegressionSubmit(BaseModel):
    contract_ids: list[str] = Field(min_length=1)
    suite: dict[str, Any]
    baseline: dict[str, Any] | None = None
    stability_runs: int = Field(default=1, ge=1, le=5)


class _DemoInvoker(ScriptedInvoker):
    """默认演示 Invoker：按契约类型返回确定性结构化输出（无外部 LLM 依赖）。"""

    def __init__(self) -> None:
        super().__init__({})
        self.question = "（未提供问题）"
        self.expert_ids: list[str] = []

    def invoke(self, request):
        contract = request.role_contract
        rid = contract.role_id
        question = "（未提供问题）"
        if isinstance(request.memory_snapshot, dict):
            question = request.memory_snapshot.get("__question__", self.question)
        from wbr.core.contract.models import RoleType

        if contract.role_type == RoleType.COORDINATOR:
            payload = {"assignments": [
                {"expert_role_id": cid, "sub_question": f"分析: {question}"}
                for cid in sorted(self.expert_ids)
            ]}
        elif contract.role_type == RoleType.VERIFIER:
            payload = {"passed": True, "scores": {"completeness": 0.85, "accuracy": 0.85},
                       "comments": "复核通过（演示）", "final_answer": f"综合结论: {question}"}
        else:
            required = (contract.output_spec.schema_ or {}).get("required", [])
            base = {"conclusion": f"{rid} 的结构化结论: {question}",
                    "confidence": 0.9, "citations": ["[^1] 演示证据"]}
            if "findings" in required:
                payload = {"findings": [
                    {"severity": "low", "title": "演示发现", "detail": "演示环境的示例发现（非真实）",
                     "location": "demo://placeholder", "citations": ["[^1] 演示证据"]},
                ], **base}
            elif "claims" in required:
                payload = {"claims": [
                    {"claim": "演示主张", "verdict": "verified", "reason": "演示环境示例核查"},
                ], **base}
            elif "violations" in required:
                payload = {"violations": [
                    {"severity": "low", "rule": "演示规则", "excerpt": "演示片段", "suggestion": "演示整改建议"},
                ], **base}
            elif "scores" in required:
                payload = {"scores": {"钩子": 0.8, "结构": 0.8, "行动引导": 0.8},
                           "rewrite_suggestions": ["演示改写建议"], **base}
            else:
                payload = base
        from wbr.core.orchestration.invoker import ModelResponse, TokenUsage

        return ModelResponse(
            text=json.dumps(payload, ensure_ascii=False),
            usage=TokenUsage(prompt_tokens=100, completion_tokens=60),
            raw=payload,
        )


def _resolve_contracts(services: _Services, cids: list[str]) -> dict[str, RoleContract]:
    out: dict[str, RoleContract] = {}
    for cid in cids:
        c = services.registry.get(cid)
        if c is None:
            raise AppError(f"契约不存在: {cid}", code="E9003")
        out[cid] = c
    return out


def _handle_review(services: _Services, record: TaskRecord) -> dict:
    payload = record.payload
    contracts = _resolve_contracts(
        services, [payload["coordinator"], *payload["experts"], payload["verifier"]]
    )
    session = ReviewSession(
        coordinator_contract=contracts[payload["coordinator"]],
        expert_contracts=[contracts[c] for c in payload["experts"]],
        verifier_contract=contracts[payload["verifier"]],
        invoker=services.invoker,
        audit=services.audit,
    )
    result = session.run(payload["question"])
    return json.loads(result.to_json())


def _handle_regression(services: _Services, record: TaskRecord) -> dict:
    payload = record.payload
    contracts = _resolve_contracts(services, payload["contract_ids"])
    suite = CaseSuite.model_validate(payload["suite"])
    baseline = None
    if payload.get("baseline"):
        baseline = BaselineSnapshot.model_validate(payload["baseline"])
    engine = RegressionEngine(contracts=contracts, invoker=services.invoker, audit=services.audit)
    report = engine.run_suite(
        suite, baseline=baseline, stability_runs=payload.get("stability_runs", 1)
    )
    return json.loads(report.to_json())


class _Services:
    def __init__(self, *, registry, queue, audit, invoker, data_root, task_store) -> None:
        self.registry = registry
        self.queue = queue
        self.audit = audit
        self.invoker = invoker
        self.data_root = data_root
        self.task_store = task_store


def create_app(
    *,
    invoker: Any | None = None,
    data_root: str | Path | None = None,
    queue: TaskQueue | None = None,
) -> Any:
    """构建 FastAPI 应用。fastapi 缺失时抛带指引的 AppError。"""
    try:
        from fastapi import FastAPI, Query, Request
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import ValidationError
    except ImportError as e:  # pragma: no cover
        raise AppError(
            "API 服务需要安装可选依赖: pip install 'work-by-roles[server]' (fastapi/uvicorn/httpx)"
        ) from e

    root = Path(data_root) if data_root else Path("./wbr-data")
    if invoker is None:
        # 环境变量配置了真实模型（WBR_LLM_API_KEY + WBR_LLM_MODEL）则自动启用，否则回落演示 Invoker
        from wbr.adapters.llm import OpenAICompatInvoker

        invoker = OpenAICompatInvoker.from_env() or _DemoInvoker()
    services = _Services(
        registry=ContractRegistry(root),
        queue=queue or InlineTaskQueue(lambda r: None),
        audit=AuditTrail(),
        invoker=invoker,
        data_root=root,
        task_store=JsonTaskStore(root / "tasks"),
    )

    def _dispatch(record: TaskRecord) -> Any:
        if record.kind == TaskKind.REVIEW:
            return _handle_review(services, record)
        return _handle_regression(services, record)

    if queue is None:
        services.queue = InProcessTaskQueue(_dispatch)
    elif isinstance(services.queue, InlineTaskQueue):
        services.queue.handler = _dispatch

    @asynccontextmanager
    async def lifespan(_app):
        if isinstance(services.queue, InProcessTaskQueue):
            await services.queue.start()
        yield
        if isinstance(services.queue, InProcessTaskQueue):
            await services.queue.stop()

    app = FastAPI(title="work-by-roles API", version=wbr.__version__, lifespan=lifespan)

    # ---- 统一错误体 ----
    @app.exception_handler(WBRError)
    async def wbr_error_handler(request: Request, exc: WBRError):
        status = _ERROR_STATUS.get(exc.code, 400)
        return JSONResponse(status_code=status, content={"error": exc.to_dict()})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "E9022",
            "message": json.dumps(exc.errors()[:3], ensure_ascii=False, default=str),
        }})

    def _parse_contract(body: ContractPayload) -> RoleContract:
        try:
            contract = RoleContract.model_validate(body.contract)
        except ValidationError as e:
            raise AppError(f"契约结构不合法: {e.errors()[:3]}", code="E9022") from e
        contract.meta.content_hash = RoleContract.compute_hash(contract)
        return contract

    # ---- 健康 ----
    @app.get("/api/v1/healthz")
    def healthz():
        return {
            "status": "ok",
            "version": wbr.__version__,
            "components": {
                "registry": True,
                "queue": type(services.queue).__name__,
                "audit": True,
                "invoker": type(services.invoker).__name__,
            },
        }

    # ---- 契约 CRUD + 版本 ----
    @app.post("/api/v1/contracts", status_code=201)
    def create_contract(body: ContractPayload):
        saved = services.registry.create(_parse_contract(body))
        return json.loads(saved.to_json())

    @app.get("/api/v1/contracts")
    def list_contracts():
        return [json.loads(c.to_json()) for c in services.registry.list()]

    @app.get("/api/v1/contracts/{cid}")
    def get_contract(cid: str):
        c = services.registry.get(cid)
        if c is None:
            raise AppError(f"契约不存在: {cid}", code="E9003")
        return json.loads(c.to_json())

    @app.put("/api/v1/contracts/{cid}")
    def update_contract(cid: str, body: ContractPayload):
        updated, diff = services.registry.update(cid, _parse_contract(body))
        return {"contract": json.loads(updated.to_json()),
                "diff": diff.to_dict() if diff else None}

    @app.delete("/api/v1/contracts/{cid}", status_code=204)
    def delete_contract(cid: str):
        if not services.registry.delete(cid):
            raise AppError(f"契约不存在: {cid}", code="E9003")

    @app.get("/api/v1/contracts/{cid}/versions")
    def list_versions(cid: str):
        if services.registry.get(cid) is None:
            raise AppError(f"契约不存在: {cid}", code="E9003")
        return services.registry.versions(cid)

    @app.get("/api/v1/contracts/{cid}/versions/{version}")
    def get_version(cid: str, version: str):
        v = services.registry.get_version(cid, version)
        if v is None:
            raise AppError(f"版本不存在: {cid}@{version}", code="E9003")
        return json.loads(v.to_json())

    @app.get("/api/v1/contracts/{cid}/diff")
    def diff_versions(
        cid: str,
        from_version: str | None = Query(default=None, alias="from"),
        to_version: str | None = Query(default=None, alias="to"),
    ):
        v1, v2 = from_version, to_version
        if not v1 or not v2:
            raise AppError("需要 from/to 查询参数", code="E9022")
        report = services.registry.diff_versions(cid, v1, v2)
        if report is None:
            raise AppError(f"版本不存在: {cid} {v1}/{v2}", code="E9003")
        return report.to_dict()

    # ---- 会审调度 ----
    @app.post("/api/v1/reviews", status_code=202)
    def submit_review(body: ReviewSubmit):
        _resolve_contracts(services, [body.coordinator, *body.experts, body.verifier])
        record = services.queue.submit(TaskRecord(kind=TaskKind.REVIEW, payload=body.model_dump()))
        services.task_store.save(record)
        if isinstance(services.invoker, _DemoInvoker):
            services.invoker.expert_ids = list(body.experts)
            services.invoker.question = body.question
        return {"task_id": record.task_id, "status": record.status.value}

    @app.get("/api/v1/reviews")
    def list_reviews():
        return [{"task_id": r.task_id, "status": r.status.value, "created_at": r.created_at}
                for r in services.queue.list() if r.kind == TaskKind.REVIEW]

    @app.get("/api/v1/reviews/{task_id}")
    def get_review(task_id: str):
        record = services.queue.get(task_id) or services.task_store.load(task_id)
        if record is None:
            raise AppError(f"任务不存在: {task_id}", code="E9006")
        return {"task_id": record.task_id, "status": record.status.value,
                "error": record.error, "result": record.result}

    # ---- Harness 回归 ----
    @app.post("/api/v1/harness/suites", status_code=201)
    def create_suite(suite: dict[str, Any]):
        try:
            validated = CaseSuite.model_validate(suite)
        except ValidationError as e:
            raise AppError(f"用例库不合法: {e.errors()[:3]}", code="E9022") from e
        suite_dir = services.data_root / "suites"
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / f"{validated.suite_id}.json").write_text(
            validated.model_dump_json(indent=2), encoding="utf-8"
        )
        return json.loads(validated.model_dump_json())

    @app.get("/api/v1/harness/suites/{suite_id}")
    def get_suite(suite_id: str):
        p = services.data_root / "suites" / f"{suite_id}.json"
        if not p.is_file():
            raise AppError(f"用例库不存在: {suite_id}", code="E9007")
        return json.loads(p.read_text(encoding="utf-8"))

    @app.post("/api/v1/harness/regressions", status_code=202)
    def submit_regression(body: RegressionSubmit):
        _resolve_contracts(services, body.contract_ids)
        record = services.queue.submit(TaskRecord(kind=TaskKind.REGRESSION, payload=body.model_dump()))
        services.task_store.save(record)
        return {"task_id": record.task_id, "status": record.status.value}

    @app.get("/api/v1/harness/regressions/{task_id}")
    def get_regression(task_id: str):
        record = services.queue.get(task_id) or services.task_store.load(task_id)
        if record is None:
            raise AppError(f"任务不存在: {task_id}", code="E9006")
        return {"task_id": record.task_id, "status": record.status.value,
                "error": record.error, "report": record.result}

    # ---- 官方模板导入 ----
    @app.get("/api/v1/templates")
    def list_templates():
        from wbr.templates.registry import list_teams

        return list_teams()

    @app.post("/api/v1/templates/{team}/import", status_code=201)
    def import_template(team: str):
        from wbr.templates.registry import load_team

        contracts = load_team(team)  # 未知名抛 E9003
        imported, skipped = [], []
        for rid in sorted(contracts):
            if services.registry.get(rid) is not None:
                skipped.append(rid)
                continue
            services.registry.create(contracts[rid])
            imported.append(rid)
        return {"team": team, "imported": imported, "skipped": skipped}

    # ---- 审计导出 ----
    @app.get("/api/v1/audits/export")
    def export_audit(
        contents: str = Query(default="false"),
        trace_id: str | None = Query(default=None),
    ):
        contents = contents.lower() in ("true", "1", "yes")
        builder = AuditPackBuilder(services.audit, include_contents=contents)
        pack = builder.build(trace_ids=[trace_id] if trace_id else None)
        return json.loads(pack.to_json())

    # ---- 画布静态托管 ----
    @app.get("/canvas")
    def canvas():
        return FileResponse(_STATIC_DIR / "index.html")

    app.mount("/canvas/static", StaticFiles(directory=str(_STATIC_DIR)), name="canvas-static")

    @app.get("/canvas/api-bootstrap")
    def canvas_bootstrap():
        return {
            "contracts": [
                {"role_id": c.role_id, "role_type": c.role_type.value,
                 "version": c.meta.version, "content_hash": c.content_hash[:8],
                 "name": c.identity.name}
                for c in services.registry.list()
            ],
            "version": wbr.__version__,
            "invoker": type(services.invoker).__name__,
            "live": not isinstance(services.invoker, _DemoInvoker),
        }

    return app
