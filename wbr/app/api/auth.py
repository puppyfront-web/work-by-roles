"""可选 API Key 鉴权。

未配置密钥时接口保持开放，方便本机使用。
配置 WBR_API_KEY 后，除健康检查与画布静态资源外都必须带密钥。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

logger = logging.getLogger("wbr.app.api.auth")

_PUBLIC_PATHS = frozenset({
    "/api/v1/healthz",
    "/canvas",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
})

# ASGI 测试客户端的占位主机，不是进程真实监听地址。
_LOCAL_OR_TEST_HOSTS = frozenset({
    "127.0.0.1",
    "::1",
    "localhost",
    "testclient",
    "testserver",
})

_UNAUTHORIZED = {
    "error": {
        "code": "E9008",
        "message": "缺少或无效的 API Key",
        "trace_id": None,
        "details": {},
    }
}


def resolve_api_key(explicit: str | None) -> str:
    """显式参数优先；空字符串表示关闭。未传时读取环境变量 WBR_API_KEY。"""
    if explicit is not None:
        return explicit.strip()
    return os.environ.get("WBR_API_KEY", "").strip()


def normalize_path(path: str) -> str:
    parts: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def is_public_path(path: str) -> bool:
    normalized = normalize_path(path)
    if normalized in _PUBLIC_PATHS:
        return True
    return normalized == "/canvas/static" or normalized.startswith("/canvas/static/")


def is_non_local_bind(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().lower()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    normalized = normalized.split("%", 1)[0]
    return normalized not in _LOCAL_OR_TEST_HOSTS


def api_key_matches(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    given = hashlib.sha256(provided.encode("utf-8")).digest()
    wanted = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(given, wanted)


def provided_api_key(headers: list[tuple[bytes, bytes]]) -> str:
    api_key = ""
    authorization = ""
    for name, value in headers:
        lowered = name.lower()
        if lowered == b"x-api-key" and not api_key:
            api_key = value.decode("latin-1").strip()
        elif lowered == b"authorization" and not authorization:
            authorization = value.decode("latin-1").strip()
    if api_key:
        return api_key
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix):].strip()
    return ""


def warn_if_public_bind(host: str | None, *, api_key_configured: bool) -> bool:
    """非本机监听且未配置密钥时写一条告警。返回是否已告警。"""
    if api_key_configured or not is_non_local_bind(host):
        return False
    logger.warning(
        "API 监听在非本机地址 %s，且未配置 WBR_API_KEY。"
        "任何能访问该端口的客户端都可以修改契约并消耗模型额度。"
        "请设置 WBR_API_KEY，或只绑定 127.0.0.1，或放到已鉴权的反向代理之后。",
        host,
    )
    return True


class ApiKeyMiddleware:
    """配置了密钥时拦截非公开接口；未配置时仅在非本机监听上告警。"""

    def __init__(self, app: Any, api_key: str) -> None:
        self.app = app
        self.api_key = api_key
        self._bind_warned = False

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        if not self.api_key:
            self._note_bind(scope)
            await self.app(scope, receive, send)
            return
        if is_public_path(scope.get("path") or "/"):
            await self.app(scope, receive, send)
            return
        provided = provided_api_key(list(scope.get("headers") or []))
        if api_key_matches(provided, self.api_key):
            await self.app(scope, receive, send)
            return
        await _send_unauthorized(send)

    def _note_bind(self, scope: dict) -> None:
        if self._bind_warned:
            return
        server = scope.get("server") or (None, None)
        host = server[0] if server else None
        if warn_if_public_bind(host, api_key_configured=False):
            self._bind_warned = True


async def _send_unauthorized(send: Any) -> None:
    body = json.dumps(_UNAUTHORIZED, ensure_ascii=False).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"www-authenticate", b"Bearer"),
        ],
    })
    await send({"type": "http.response.body", "body": body})


def install_security_scheme(app: Any, *, enabled: bool) -> None:
    """把密钥写进 OpenAPI，/docs 调试时可以附带 X-API-Key 或 Bearer。"""
    if not enabled:
        return

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        components["securitySchemes"] = {
            "ApiKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            "BearerAuth": {"type": "http", "scheme": "bearer"},
        }
        for path, item in schema.get("paths", {}).items():
            if is_public_path(path):
                continue
            for operation in item.values():
                if isinstance(operation, dict) and "responses" in operation:
                    operation["security"] = [{"ApiKeyHeader": []}, {"BearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
