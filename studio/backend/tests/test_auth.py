def test_register_login_and_me(client):
    created = client.post(
        "/api/auth/register",
        json={"email": "Ada@Example.com", "password": "password123", "workspace_name": "Ada"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["workspace"]["name"] == "Ada"
    assert body["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"

    logged = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "password123"})
    assert logged.status_code == 200
    assert logged.json()["access_token"]


def test_duplicate_email_and_bad_password(client, account):
    again = client.post(
        "/api/auth/register",
        json={"email": account["email"], "password": "password123", "workspace_name": "Other"},
    )
    assert again.status_code == 409

    wrong = client.post(
        "/api/auth/login",
        json={"email": account["email"], "password": "not-the-password"},
    )
    assert wrong.status_code == 401
    unknown = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "password123"},
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_missing_token_is_rejected(client, account):
    listed = client.get(f"/api/workspaces/{account['workspace_id']}/teams")
    assert listed.status_code == 401
    assert client.get("/api/health").json()["status"] == "ok"
