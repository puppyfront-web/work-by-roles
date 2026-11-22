"""工作室测试。会清空 STUDIO_TEST_DATABASE_URL 指向的库，默认本机 studio 库。"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BACKEND))

TEST_DATABASE_URL = os.environ.get("STUDIO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://studio:studio@127.0.0.1:5432/studio"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["STUDIO_SECRET_KEY"] = "test-secret-key-at-least-32-bytes"
os.environ["STUDIO_FERNET_KEY"] = "d2JyLXN0dWRpby10ZXN0LWtleS0zMi1ieXRlcyEhISE="
os.environ["STUDIO_RUN_INLINE"] = "1"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"

_TABLES = "audit_events, audit_chains, runs, teams, provider_keys, workspaces, users"


def _truncate(engine) -> None:
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))


def _upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine():
    from sqlalchemy import text

    from wbr_studio.db import get_engine, reset_engine
    from wbr_studio.settings import reset_settings

    reset_settings()
    reset_engine()
    opened = get_engine()
    try:
        with opened.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Postgres 不可用: {exc}")
    _upgrade()
    return opened


@pytest.fixture
def db(engine):
    _truncate(engine)
    yield engine
    _truncate(engine)


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from wbr_studio.main import create_app
    from wbr_studio.runner import set_invoker_builder

    set_invoker_builder(None)
    with TestClient(create_app()) as test_client:
        yield test_client
    set_invoker_builder(None)


@pytest.fixture
def account(client):
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "workspace_name": "Acme"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "email": email,
        "password": "password123",
        "token": body["access_token"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "workspace_id": body["workspace"]["id"],
    }
