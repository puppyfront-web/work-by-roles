"""HTTP 入参。响应模型只包含可以公开的字段。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _stripped(value: str) -> str:
    return value.strip()


def normalize_email(value: str) -> str:
    text = value.strip().lower()
    if "@" not in text or text.startswith("@") or text.endswith("@") or " " in text:
        raise ValueError("邮箱格式不正确")
    return text


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    workspace_name: str = Field(default="", max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)

    @model_validator(mode="after")
    def _password_policy(self) -> RegisterIn:
        from wbr_studio.security import password_problem

        message = password_problem(self.password, self.email)
        if message:
            raise ValueError(message)
        return self

    @field_validator("workspace_name")
    @classmethod
    def _workspace(cls, value: str) -> str:
        return value.strip()


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("名称不能为空")
        return text


class ProviderKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=8, max_length=512)
    model: str = Field(min_length=1, max_length=128)
    api_key: str = Field(min_length=1, max_length=4096)

    @field_validator("name", "base_url", "model", "api_key")
    @classmethod
    def _strip(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("base_url")
    @classmethod
    def _url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url 需要以 http:// 或 https:// 开头")
        return value.rstrip("/")


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    template: str | None = Field(default=None, max_length=128)
    contracts: list[dict[str, Any]] | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("名称不能为空")
        return text

    @field_validator("template")
    @classmethod
    def _template(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @model_validator(mode="after")
    def _one_source(self) -> TeamCreate:
        has_template = self.template is not None
        has_contracts = bool(self.contracts)
        if has_template == has_contracts:
            raise ValueError("请指定 template 或 contracts 之一")
        return self


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    contracts: list[dict[str, Any]] | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("名称不能为空")
        return text

    @model_validator(mode="after")
    def _something(self) -> TeamUpdate:
        if self.name is None and self.contracts is None:
            raise ValueError("没有可更新的字段")
        return self


class RunCreate(BaseModel):
    team_id: str
    question: str = Field(min_length=1, max_length=20000)
    token_budget: int | None = Field(default=None, ge=1, le=5_000_000)
    provider_key_id: str | None = None
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)
    cached_input_price: float | None = Field(default=None, ge=0)

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("问题不能为空")
        return text

    @model_validator(mode="after")
    def _prices(self) -> RunCreate:
        if (self.input_price is None) != (self.output_price is None):
            raise ValueError("input_price 与 output_price 需要同时提供")
        if self.cached_input_price is not None and self.input_price is None:
            raise ValueError("设置 cached_input_price 时需要同时提供输入和输出单价")
        return self


class InviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = "member"

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        if value not in {"admin", "member", "viewer"}:
            raise ValueError("角色只能是 admin、member 或 viewer")
        return value


class RoleIn(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        if value not in {"owner", "admin", "member", "viewer"}:
            raise ValueError("角色无效")
        return value


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=512)

    @field_validator("token")
    @classmethod
    def _token(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("令牌不能为空")
        return text


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=512)

    @field_validator("refresh_token")
    @classmethod
    def _token(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("令牌不能为空")
        return text
