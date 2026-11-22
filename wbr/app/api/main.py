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
from wbr.adapters.demo import SchemaDemoInvoker
from wbr.app.api.auth import ApiKeyMiddleware, install_security_scheme, resolve_api_key
from wbr.app.store import ContractRegistry
from wbr.app.tasks.queue import (
    InlineTaskQueue,
    InProcessTaskQueue,
    JsonTaskStore,
    TaskKind,
    TaskQueue,
    TaskRecord,
)
from wbr.app.workspace import WorkspaceRegistry
from wbr.core.audit.pack import AuditPackBuilder
from wbr.core.audit.trail import AuditTrail
from wbr.core.contract.models import RoleContract
from wbr.core.exceptions import AppError, WBRError
from wbr.core.harness import BaselineSnapshot, CaseSuite, RegressionEngine
from wbr.core.orchestration import ReviewSession

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
    "E9008": 401,  # 缺少或无效的 API Key
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


class WorkspaceCreate(BaseModel):
    name: str


class ContractCopy(BaseModel):
    source: str


class _DemoInvoker(SchemaDemoInvoker):
    """默认演示 Invoker：Schema 驱动确定性输出，任意契约形状零违例（无外部 LLM 依赖）。"""


def _resolve_contracts(registry: ContractRegistry, cids: list[str]) -> dict[str, RoleContract]:
    out: dict[str, RoleContract] = {}
    for cid in cids:
        c = registry.get(cid)
        if c is None:
            raise AppError(f"契约不存在: {cid}", code="E9003")
        out[cid] = c
    return out


def _handle_review(services: _Services, record: TaskRecord) -> dict:
    payload = record.payload
    contracts = _resolve_contracts(
        services.registry_for(record),
        [payload["coordinator"], *payload["experts"], payload["verifier"]],
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
    contracts = _resolve_contracts(services.registry_for(record), payload["contract_ids"])
    suite = CaseSuite.model_validate(payload["suite"])
    baseline = None
    if payload.get("baseline"):
        baseline = BaselineSnapshot.model_validate(payload["baseline"])
    engine = RegressionEngine(contracts=contracts, invoker=services.invoker, audit=services.audit)
    report = engine.run_suite(
        suite, baseline=baseline, stability_runs=payload.get("stability_runs", 1)
    )
    return json.loads(report.to_json())


class _Scope:
    def __init__(self, registry, task_store, suite_dir: Path, workspace: str | None) -> None:
        self.registry = registry
        self.task_store = task_store
        self.suite_dir = suite_dir
        self.workspace = workspace


class _Services:
    def __init__(
        self, *, registry, queue, audit, invoker, data_root, task_store, workspaces,
    ) -> None:
        self.registry = registry
        self.queue = queue
        self.audit = audit
        self.invoker = invoker
        self.data_root = data_root
        self.task_store = task_store
        self.workspaces = workspaces

    def registry_for(self, record: TaskRecord) -> ContractRegistry:
        if record.workspace:
            return self.workspaces.registry(record.workspace)
        return self.registry

    def scope(self, workspace_header: str | None) -> _Scope:
        name = (workspace_header or "").strip()
        if not name:
            return _Scope(self.registry, self.task_store, self.data_root / "suites", None)
        self.workspaces.get(name)
        return _Scope(
            self.workspaces.registry(name),
            self.workspaces.task_store(name),
            self.workspaces.suite_path(name),
            name,
        )


def create_app(
    *,
    invoker: Any | None = None,
    data_root: str | Path | None = None,
    queue: TaskQueue | None = None,
    api_key: str | None = None,
) -> Any:
    """构建 FastAPI 应用。fastapi 缺失时抛带指引的 AppError。

    api_key 为 None 时读取环境变量 WBR_API_KEY；传入空字符串则强制关闭鉴权。
    密钥非空时，除健康检查与画布静态资源外的接口都要带 X-API-Key 或 Bearer。
    """
    try:
        from fastapi import Depends, FastAPI, Header, Query, Request
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import ValidationError
    except ImportError as e:  # pragma: no cover
        raise AppError(
            "API 服务需要安装可选依赖: pip install 'work-by-roles[server]' (fastapi/uvicorn/httpx)"
        ) from e

    configured_key = resolve_api_key(api_key)
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
        workspaces=WorkspaceRegistry(root),
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
    app.add_middleware(ApiKeyMiddleware, api_key=configured_key)

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

    def _owned(scope: _Scope, record: TaskRecord | None) -> TaskRecord | None:
        if record is None or record.workspace != scope.workspace:
            return None
        return record

    def _load_task(scope: _Scope, task_id: str) -> TaskRecord:
        record = _owned(scope, services.queue.get(task_id))
        if record is None:
            record = _owned(scope, scope.task_store.load(task_id))
        if record is None:
            raise AppError(f"任务不存在: {task_id}", code="E9006")
        return record

    def _parse_contract(body: ContractPayload) -> RoleContract:
        try:
            contract = RoleContract.model_validate(body.contract)
        except ValidationError as e:
            raise AppError(f"契约结构不合法: {e.errors()[:3]}", code="E9022") from e
        contract.meta.content_hash = RoleContract.compute_hash(contract)
        return contract

    def _workspace_name(
        x_wbr_workspace: str | None = Header(default=None, alias="X-WBR-Workspace"),
    ) -> str | None:
        return x_wbr_workspace

    # ---- 健康 ----
    @app.get("/api/v1/healthz")
    def healthz():
        return {
            "status": "ok",
            "version": wbr.__version__,
            "auth_required": bool(configured_key),
            "components": {
                "registry": True,
                "queue": type(services.queue).__name__,
                "audit": True,
                "invoker": type(services.invoker).__name__,
            },
        }

    # ---- 契约 CRUD + 版本 ----
    @app.post("/api/v1/contracts", status_code=201)
    def create_contract(body: ContractPayload, workspace: str | None = Depends(_workspace_name)):
        saved = services.scope(workspace).registry.create(_parse_contract(body))
        return json.loads(saved.to_json())

    @app.get("/api/v1/contracts")
    def list_contracts(workspace: str | None = Depends(_workspace_name)):
        return [json.loads(c.to_json()) for c in services.scope(workspace).registry.list()]

    @app.get("/api/v1/contracts/{cid}")
    def get_contract(cid: str, workspace: str | None = Depends(_workspace_name)):
        c = services.scope(workspace).registry.get(cid)
        if c is None:
            raise AppError(f"契约不存在: {cid}", code="E9003")
        return json.loads(c.to_json())

    @app.put("/api/v1/contracts/{cid}")
    def update_contract(
        cid: str, body: ContractPayload, workspace: str | None = Depends(_workspace_name),
    ):
        updated, diff = services.scope(workspace).registry.update(cid, _parse_contract(body))
        return {"contract": json.loads(updated.to_json()),
                "diff": diff.to_dict() if diff else None}

    @app.delete("/api/v1/contracts/{cid}", status_code=204)
    def delete_contract(cid: str, workspace: str | None = Depends(_workspace_name)):
        if not services.scope(workspace).registry.delete(cid):
            raise AppError(f"契约不存在: {cid}", code="E9003")

    @app.get("/api/v1/contracts/{cid}/versions")
    def list_versions(cid: str, workspace: str | None = Depends(_workspace_name)):
        registry = services.scope(workspace).registry
        if registry.get(cid) is None:
            raise AppError(f"契约不存在: {cid}", code="E9003")
        return registry.versions(cid)

    @app.get("/api/v1/contracts/{cid}/versions/{version}")
    def get_version(cid: str, version: str, workspace: str | None = Depends(_workspace_name)):
        v = services.scope(workspace).registry.get_version(cid, version)
        if v is None:
            raise AppError(f"版本不存在: {cid}@{version}", code="E9003")
        return json.loads(v.to_json())

    @app.get("/api/v1/contracts/{cid}/diff")
    def diff_versions(
        cid: str,
        workspace: str | None = Depends(_workspace_name),
        from_version: str | None = Query(default=None, alias="from"),
        to_version: str | None = Query(default=None, alias="to"),
    ):
        v1, v2 = from_version, to_version
        if not v1 or not v2:
            raise AppError("需要 from/to 查询参数", code="E9022")
        report = services.scope(workspace).registry.diff_versions(cid, v1, v2)
        if report is None:
            raise AppError(f"版本不存在: {cid} {v1}/{v2}", code="E9003")
        return report.to_dict()

    # ---- 会审调度 ----
    @app.post("/api/v1/reviews", status_code=202)
    def submit_review(body: ReviewSubmit, workspace: str | None = Depends(_workspace_name)):
        scope = services.scope(workspace)
        _resolve_contracts(scope.registry, [body.coordinator, *body.experts, body.verifier])
        record = services.queue.submit(TaskRecord(
            kind=TaskKind.REVIEW, payload=body.model_dump(), workspace=scope.workspace,
        ))
        scope.task_store.save(record)
        if isinstance(services.invoker, _DemoInvoker):
            services.invoker.expert_ids = list(body.experts)
            services.invoker.question = body.question
        return {"task_id": record.task_id, "status": record.status.value}

    @app.get("/api/v1/reviews")
    def list_reviews(workspace: str | None = Depends(_workspace_name)):
        scope = services.scope(workspace)
        return [{"task_id": r.task_id, "status": r.status.value, "created_at": r.created_at}
                for r in services.queue.list()
                if r.kind == TaskKind.REVIEW and r.workspace == scope.workspace]

    @app.get("/api/v1/reviews/{task_id}")
    def get_review(task_id: str, workspace: str | None = Depends(_workspace_name)):
        record = _load_task(services.scope(workspace), task_id)
        return {"task_id": record.task_id, "status": record.status.value,
                "error": record.error, "result": record.result}

    # ---- Harness 回归 ----
    @app.post("/api/v1/harness/suites", status_code=201)
    def create_suite(suite: dict[str, Any], workspace: str | None = Depends(_workspace_name)):
        try:
            validated = CaseSuite.model_validate(suite)
        except ValidationError as e:
            raise AppError(f"用例库不合法: {e.errors()[:3]}", code="E9022") from e
        suite_dir = services.scope(workspace).suite_dir
        suite_dir.mkdir(parents=True, exist_ok=True)
        (suite_dir / f"{validated.suite_id}.json").write_text(
            validated.model_dump_json(indent=2), encoding="utf-8"
        )
        return json.loads(validated.model_dump_json())

    @app.get("/api/v1/harness/suites/{suite_id}")
    def get_suite(suite_id: str, workspace: str | None = Depends(_workspace_name)):
        p = services.scope(workspace).suite_dir / f"{suite_id}.json"
        if not p.is_file():
            raise AppError(f"用例库不存在: {suite_id}", code="E9007")
        return json.loads(p.read_text(encoding="utf-8"))

    @app.post("/api/v1/harness/regressions", status_code=202)
    def submit_regression(body: RegressionSubmit, workspace: str | None = Depends(_workspace_name)):
        scope = services.scope(workspace)
        _resolve_contracts(scope.registry, body.contract_ids)
        record = services.queue.submit(TaskRecord(
            kind=TaskKind.REGRESSION, payload=body.model_dump(), workspace=scope.workspace,
        ))
        scope.task_store.save(record)
        return {"task_id": record.task_id, "status": record.status.value}

    @app.get("/api/v1/harness/regressions/{task_id}")
    def get_regression(task_id: str, workspace: str | None = Depends(_workspace_name)):
        record = _load_task(services.scope(workspace), task_id)
        return {"task_id": record.task_id, "status": record.status.value,
                "error": record.error, "report": record.result}

    # ---- 官方模板导入 ----
    @app.get("/api/v1/templates")
    def list_templates():
        from wbr.templates.registry import list_teams

        return list_teams()

    @app.post("/api/v1/templates/{team}/import", status_code=201)
    def import_template(team: str, workspace: str | None = Depends(_workspace_name)):
        from wbr.templates.registry import load_team

        registry = services.scope(workspace).registry
        contracts = load_team(team)  # 未知名抛 E9003
        imported, skipped = [], []
        for rid in sorted(contracts):
            if registry.get(rid) is not None:
                skipped.append(rid)
                continue
            registry.create(contracts[rid])
            imported.append(rid)
        return {"team": team, "imported": imported, "skipped": skipped}

    # ---- Workspace ----
    @app.get("/api/v1/workspaces")
    def list_workspaces():
        return [{"name": ws.name} for ws in services.workspaces.list()]

    @app.post("/api/v1/workspaces", status_code=201)
    def create_workspace(body: WorkspaceCreate):
        ws = services.workspaces.create(body.name)
        return {"name": ws.name}

    @app.delete("/api/v1/workspaces/{name}", status_code=204)
    def delete_workspace(name: str):
        services.workspaces.delete(name)

    @app.post("/api/v1/workspaces/{name}/contracts/{role_id}/copy", status_code=201)
    def copy_contract(name: str, role_id: str, body: ContractCopy):
        copied = services.workspaces.copy_contract(body.source, name, role_id)
        return json.loads(copied.to_json())

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
    def canvas_bootstrap(workspace: str | None = Depends(_workspace_name)):
        scope = services.scope(workspace)
        return {
            "contracts": [
                {"role_id": c.role_id, "role_type": c.role_type.value,
                 "version": c.meta.version, "content_hash": c.content_hash[:8],
                 "name": c.identity.name}
                for c in scope.registry.list()
            ],
            "version": wbr.__version__,
            "workspace": scope.workspace,
            "invoker": type(services.invoker).__name__,
            "live": not isinstance(services.invoker, _DemoInvoker),
        }

    install_security_scheme(app, enabled=bool(configured_key))
    return app
