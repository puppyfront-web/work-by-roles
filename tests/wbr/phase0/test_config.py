"""TC-0-CFG-1/2：全局配置系统（YAML + 代码可配置）。"""
from __future__ import annotations

import logging

import pytest

from wbr.core.config import WBRConfig
from wbr.core.exceptions import ConfigError


def test_defaults():
    c = WBRConfig()
    assert c.project_name == "work-by-roles"
    assert c.log_level == "INFO"
    assert c.audit_enabled is True
    assert c.default_token_quota == 8000
    assert c.cache_enabled is True
    assert c.security_enabled is True


def test_yaml_and_overrides_merge(tmp_path):
    yml = tmp_path / "wbr.yaml"
    yml.write_text("log_level: DEBUG\naudit_enabled: false\nunknown_key: 1\n", encoding="utf-8")
    cfg = load_and_check(str(yml))
    assert cfg.log_level == "DEBUG"
    assert cfg.audit_enabled is False


def load_and_check(path):
    from wbr.config_loader import load_config

    cfg = load_config(path, overrides={"default_token_quota": 123})
    assert cfg.default_token_quota == 123  # 代码覆盖优先于文件
    return cfg


def test_overlay_immutable():
    base = WBRConfig()
    overlay = base.overlay(log_level="DEBUG")
    assert base.log_level == "INFO"
    assert overlay.log_level == "DEBUG"
    assert overlay.audit_enabled == base.audit_enabled


def test_unknown_yaml_key_ignored_with_warning(tmp_path, caplog):
    yml = tmp_path / "c.yaml"
    yml.write_text("no_such_key: 1\nlog_level: WARNING\n", encoding="utf-8")
    from wbr.config_loader import load_config

    with caplog.at_level(logging.WARNING):
        cfg = load_config(str(yml))
    assert cfg.log_level == "WARNING"
    assert any("no_such_key" in r.message for r in caplog.records)


def test_missing_file_raises_config_error():
    from wbr.config_loader import load_config

    with pytest.raises(ConfigError):
        load_config("/nonexistent/wbr.yaml")


def test_invalid_yaml_raises(tmp_path):
    yml = tmp_path / "bad.yaml"
    yml.write_text("a: [unclosed\n", encoding="utf-8")
    from wbr.config_loader import load_config

    with pytest.raises(ConfigError):
        load_config(str(yml))
