"""wbr-studio HTTP 入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wbr_studio.api import router
from wbr_studio.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    if not settings.studio_secret_key:
        raise RuntimeError("STUDIO_SECRET_KEY 未设置")
    app = FastAPI(title="wbr-studio", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins() or ["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.exception_handler(RequestValidationError)
    async def hide_rejected_input(_request, exc: RequestValidationError) -> JSONResponse:
        detail = [
            {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
