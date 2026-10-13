"""配置加载器：YAML 文件 + 代码覆盖（SPEC-000 D-15）。

PyYAML 属于基础设施依赖，位于内核之外；缺失时给出可诊断错误。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from wbr.core.config import WBRConfig
from wbr.core.exceptions import ConfigError

logger = logging.getLogger("wbr.config")

_YAML_INSTALL_HINT = (
    "PyYAML 未安装，无法解析 YAML 配置文件。请安装: pip install pyyaml，"
    "或改用 WBRConfig(代码) 配置方式。"
)


def _known_fields() -> set[str]:
    return set(WBRConfig.model_fields.keys())


def load_config(
    path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> WBRConfig:
    """加载配置：默认值 ← YAML 文件 ← 代码 overrides。未知键忽略并告警。"""
    data: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"配置文件不存在: {p}", details={"path": str(p)})
        try:
            import yaml
        except ImportError as e:  # pragma: no cover - 环境相关
            raise ConfigError(_YAML_INSTALL_HINT) from e
        try:
            loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ConfigError(f"YAML 解析失败: {e}", details={"path": str(p)}) from e
        if loaded is None:
            loaded = {}
        if not isinstance(loaded, dict):
            raise ConfigError(
                "YAML 顶层必须是键值映射",
                details={"path": str(p), "got": type(loaded).__name__},
            )
        known = _known_fields()
        for key, value in loaded.items():
            if key in known:
                data[key] = value
            else:
                logger.warning("配置文件包含未知键，已忽略: %s (path=%s)", key, p)
    if overrides:
        known = _known_fields()
        for key, value in overrides.items():
            if key in known:
                data[key] = value
            else:
                logger.warning("代码覆盖包含未知键，已忽略: %s", key)
    return WBRConfig.model_validate(data)
