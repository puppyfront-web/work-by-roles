import uuid

from wbr_studio.ratelimit import get_limiter, reset_limiter
from wbr_studio.settings import reset_settings


def mail_token(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("token: "):
            return line.removeprefix("token: ").strip()
    raise AssertionError(text)


def test_password_policy(client):
    short = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short-pass", "workspace_name": "S"},
    )
    assert short.status_code == 422
    digits = client.post(
        "/api/auth/register",
        json={"email": "digits@example.com", "password": "12345678901", "workspace_name": "S"},
    )
    assert digits.status_code == 422
    copied = client.post(
        "/api/auth/register",
        json={"email": "alpha@example.com", "password": "alpha12345", "workspace_name": "S"},
    )
    assert copied.status_code == 422
    ok = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "short"},
    )
    assert ok.status_code == 401


def test_email_verification_and_required_flag(client, mailbox, monkeypatch):
    created = client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "password": "password123", "workspace_name": "Ada"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["user"]["email_verified"] is False
    token = mail_token(mailbox.messages[-1]["text"])
    headers = {"Authorization": f"Bearer {created.json()['access_token']}"}

    monkeypatch.setenv("STUDIO_REQUIRE_EMAIL_VERIFICATION", "1")
    reset_settings()
    try:
        blocked = client.post(
            f"/api/workspaces/{created.json()['workspace']['id']}/teams",
            headers=headers,
            json={"name": "架构组", "template": "arch_review_team"},
        )
        assert blocked.status_code == 403
        verified = client.post("/api/auth/verify-email", json={"token": token})
        assert verified.status_code == 200, verified.text
        assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400
        me = client.get("/api/auth/me", headers=headers)
        assert me.json()["email_verified"] is True
        allowed = client.post(
            f"/api/workspaces/{created.json()['workspace']['id']}/teams",
            headers=headers,
            json={"name": "架构组", "template": "arch_review_team"},
        )
        assert allowed.status_code == 201, allowed.text
        assert client.post("/api/auth/resend-verification", headers=headers).status_code == 204
    finally:
        monkeypatch.setenv("STUDIO_REQUIRE_EMAIL_VERIFICATION", "0")
        reset_settings()


def test_refresh_rotation_and_logout_revocation(client, account):
    logged = client.post(
        "/api/auth/login",
        json={"email": account["email"], "password": account["password"]},
    )
    assert logged.status_code == 200, logged.text
    refresh = logged.json()["refresh_token"]
    access = logged.json()["access_token"]
    rotated = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["access_token"] != access
    reused = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401
    chained = client.post("/api/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]})
    assert chained.status_code == 401

    fresh = client.post(
        "/api/auth/login",
        json={"email": account["email"], "password": account["password"]},
    )
    headers = {"Authorization": f"Bearer {fresh.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.post(
        "/api/auth/refresh",
        json={"refresh_token": fresh.json()["refresh_token"]},
    ).status_code == 401


def test_auth_rate_limit(client, monkeypatch):
    monkeypatch.setenv("STUDIO_AUTH_RATE_LIMIT", "2")
    monkeypatch.setenv("STUDIO_AUTH_RATE_WINDOW_SECONDS", "60")
    reset_settings()
    reset_limiter()
    email = f"limit-{uuid.uuid4().hex[:8]}@example.com"
    try:
        for _ in range(2):
            response = client.post("/api/auth/login", json={"email": email, "password": "password123"})
            assert response.status_code == 401
        blocked = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        assert blocked.status_code == 429
    finally:
        monkeypatch.setenv("STUDIO_AUTH_RATE_LIMIT", "10000")
        reset_settings()
        reset_limiter()


def test_redis_rate_limiter(monkeypatch):
    import redis

    try:
        redis.Redis.from_url("redis://127.0.0.1:6379/0").ping()
    except Exception as exc:
        import pytest

        pytest.skip(f"Redis 不可用: {exc}")
    monkeypatch.setenv("STUDIO_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("STUDIO_AUTH_RATE_LIMIT", "2")
    monkeypatch.setenv("STUDIO_AUTH_RATE_WINDOW_SECONDS", "60")
    reset_settings()
    reset_limiter()
    try:
        limiter = get_limiter()
        key = f"unit-{uuid.uuid4().hex}"
        assert limiter.allow(key) is True
        assert limiter.allow(key) is True
        assert limiter.allow(key) is False
    finally:
        monkeypatch.setenv("STUDIO_RATE_LIMIT_BACKEND", "memory")
        monkeypatch.setenv("STUDIO_AUTH_RATE_LIMIT", "10000")
        reset_settings()
        reset_limiter()
