"""OpenAI 兼容 Invoker（Adapter 层）：一次接入所有 /chat/completions 风格端点。

覆盖 OpenAI / DeepSeek / Kimi / Qwen(DashScope 兼容模式) / GLM / Ollama / vLLM 等。
契约编译产物天然映射为两条消息：system_prompt → system，user_block → user。
httpx 惰性导入：Core 保持零网络依赖，未安装 server 附加依赖时给出安装指引。

环境变量（构造参数优先）：
    WBR_LLM_BASE_URL   默认 https://api.openai.com/v1
    WBR_LLM_API_KEY    必填（Ollama/vLLM 等本地端点填任意非空值）
    WBR_LLM_MODEL      默认模型名
"""
from __future__ import annotations

import os
import time
from typing import Any

from wbr.core.exceptions import AdapterError
from wbr.core.orchestration.invoker import ModelRequest, ModelResponse, TokenUsage

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_RETRY_STATUS = {429, 500, 502, 503, 504}


class OpenAICompatInvoker:
    """把 ModelRequest 发送到 OpenAI 兼容 /chat/completions 端点。

    model_by_role 可按 role_id 覆盖模型（如协调者/复核人用更强模型，专家用廉价模型）。
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        model_by_role: dict[str, str] | None = None,
        temperature: float | None = None,
        timeout: float = 120.0,
        max_retries: int = 2,
        extra_headers: dict[str, str] | None = None,
        client: Any | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("WBR_LLM_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("WBR_LLM_API_KEY") or ""
        self.model = model or os.environ.get("WBR_LLM_MODEL") or ""
        if not self.api_key:
            raise AdapterError(
                "缺少 API Key：请设置环境变量 WBR_LLM_API_KEY（或在构造函数传入 api_key）。"
                "本地端点（Ollama/vLLM）可填任意非空值。"
            )
        if not self.model:
            raise AdapterError(
                "缺少模型名：请设置环境变量 WBR_LLM_MODEL（或在构造函数传入 model），"
                "例如 gpt-4o-mini / deepseek-chat / qwen-plus / glm-4-flash。"
            )
        self.model_by_role = dict(model_by_role or {})
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_headers = dict(extra_headers or {})
        self._client = client  # 测试注入点；None 时惰性创建

    @classmethod
    def from_env(cls) -> OpenAICompatInvoker | None:
        """环境变量齐全则返回实例，否则 None（供 create_app / CLI 探测）。"""
        if not (os.environ.get("WBR_LLM_API_KEY") and os.environ.get("WBR_LLM_MODEL")):
            return None
        return cls()

    def _default_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", **self.extra_headers}

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import httpx
            except ImportError as e:  # pragma: no cover
                raise AdapterError(
                    "OpenAICompatInvoker 需要 httpx：pip install 'work-by-roles[server]'"
                ) from e
            self._client = httpx.Client(
                base_url=self.base_url, headers=self._default_headers(), timeout=self.timeout
            )
        return self._client

    def invoke(self, request: ModelRequest) -> ModelResponse:
        contract = request.role_contract
        model = self.model_by_role.get(contract.role_id, self.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.compiled_prompt.system_prompt},
                {"role": "user", "content": request.compiled_prompt.user_block},
            ],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        client = self._ensure_client()
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                resp = client.post("/chat/completions", json=payload)
            except Exception as e:  # httpx 传输层异常（超时/连接失败）
                last_error = f"网络错误: {type(e).__name__}: {e}"
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise AdapterError(f"模型端点不可达（{self.base_url}）：{last_error}") from e
            if resp.status_code == 200:
                return self._parse_response(resp, contract.role_id)
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in _RETRY_STATUS and attempt < self.max_retries:
                time.sleep(0.5 * (2**attempt))
                continue
            raise AdapterError(f"模型调用失败（model={model}）: {last_error}")
        raise AdapterError(f"模型调用失败（重试耗尽）: {last_error}")  # pragma: no cover

    def _parse_response(self, resp: Any, role_id: str) -> ModelResponse:
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise AdapterError(f"响应结构异常（{role_id}）: {str(data)[:200]}") from e
        usage_data = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
            completion_tokens=int(usage_data.get("completion_tokens") or 0),
        )
        return ModelResponse(text=text, usage=usage, raw=data)
