"""全局配置模型（SPEC-001 §2.5）。YAML 解析位于 wbr.config_loader（D-15）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WBRConfig(BaseModel):
    """全局配置。所有字段带默认值，能力均可开关（规则6）。"""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    project_name: str = "work-by-roles"
    log_level: str = "INFO"
    audit_enabled: bool = True
    audit_bus_max_queue: int = Field(default=10000, ge=1)
    default_token_quota: int = Field(default=8000, ge=1)
    security_enabled: bool = True
    cache_enabled: bool = True
    cache_max_entries: int = Field(default=4096, ge=1)
    extra: dict[str, Any] = Field(default_factory=dict)

    def overlay(self, **kw: Any) -> WBRConfig:
        """返回应用了覆盖项的新配置实例（不可变更新）。"""
        data = self.model_dump()
        data.update(kw)
        return WBRConfig.model_validate(data)
