import uuid


def mail_token(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("token: "):
            return line.removeprefix("token: ").strip()
    raise AssertionError(text)


def _register(client, email: str, name: str = "Workspace"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "workspace_name": name},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "email": email,
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "workspace_id": body["workspace"]["id"],
        "user_id": body["user"]["id"],
    }


def test_owner_membership_and_invite_flow(client, account, mailbox):
    listed = client.get("/api/workspaces", headers=account["headers"])
    assert listed.status_code == 200
    assert listed.json()[0]["role"] == "owner"

    invited = client.post(
        f"/api/workspaces/{account['workspace_id']}/invites",
        headers=account["headers"],
        json={"email": "member@example.com", "role": "member"},
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["token"]
    assert mailbox.messages[-1]["to"] == "member@example.com"
    assert mail_token(mailbox.messages[-1]["text"]) == invited.json()["token"]

    hidden = client.get(
        f"/api/workspaces/{account['workspace_id']}/invites",
        headers=account["headers"],
    )
    assert "token" not in hidden.text

    guest = _register(client, "member@example.com", "Guest")
    accepted = client.post(f"/api/invites/{invited.json()['token']}/accept", headers=guest["headers"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "member"
    again = client.post(f"/api/invites/{invited.json()['token']}/accept", headers=guest["headers"])
    assert again.status_code == 200

    visible = client.get("/api/workspaces", headers=guest["headers"])
    ids = {item["id"]: item["role"] for item in visible.json()}
    assert ids[account["workspace_id"]] == "member"


def test_role_permissions(client, account, mailbox):
    workspace_id = account["workspace_id"]
    viewer_email = f"view-{uuid.uuid4().hex[:8]}@example.com"
    member_email = f"mem-{uuid.uuid4().hex[:8]}@example.com"
    member_only = f"only-{uuid.uuid4().hex[:8]}@example.com"
    for email, role in ((viewer_email, "viewer"), (member_email, "admin"), (member_only, "member")):
        created = client.post(
            f"/api/workspaces/{workspace_id}/invites",
            headers=account["headers"],
            json={"email": email, "role": role},
        )
        assert created.status_code == 201, created.text
        person = _register(client, email)
        accepted = client.post(
            f"/api/invites/{created.json()['token']}/accept",
            headers=person["headers"],
        )
        assert accepted.status_code == 200, accepted.text
        if role == "viewer":
            viewer = person
        elif role == "member":
            member = person
        else:
            admin = person

    outsider = _register(client, f"out-{uuid.uuid4().hex[:8]}@example.com")
    missing = client.get(f"/api/workspaces/{workspace_id}/teams", headers=outsider["headers"])
    assert missing.status_code == 404
    usage = client.get(f"/api/workspaces/{workspace_id}/usage", headers=outsider["headers"])
    assert usage.status_code == 404

    read = client.get(f"/api/workspaces/{workspace_id}/teams", headers=viewer["headers"])
    assert read.status_code == 200
    denied = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=viewer["headers"],
        json={"name": "nope", "template": "arch_review_team"},
    )
    assert denied.status_code == 403
    key_denied = client.post(
        f"/api/workspaces/{workspace_id}/provider-keys",
        headers=viewer["headers"],
        json={
            "name": "k",
            "base_url": "https://api.example.invalid/v1",
            "model": "m",
            "api_key": "secret",
        },
    )
    assert key_denied.status_code == 403

    team = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=admin["headers"],
        json={"name": "可编辑", "template": "arch_review_team"},
    )
    assert team.status_code == 201, team.text
    key_by_member = client.post(
        f"/api/workspaces/{workspace_id}/provider-keys",
        headers=admin["headers"],
        json={
            "name": "k",
            "base_url": "https://api.example.invalid/v1",
            "model": "m",
            "api_key": "secret",
        },
    )
    assert key_by_member.status_code == 201, key_by_member.text
    member_key = client.post(
        f"/api/workspaces/{workspace_id}/provider-keys",
        headers=member["headers"],
        json={
            "name": "k",
            "base_url": "https://api.example.invalid/v1",
            "model": "m",
            "api_key": "secret",
        },
    )
    assert member_key.status_code == 403
    member_team = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=member["headers"],
        json={"name": "成员可建", "template": "arch_review_team"},
    )
    assert member_team.status_code == 201, member_team.text

    invite_denied = client.post(
        f"/api/workspaces/{workspace_id}/invites",
        headers=viewer["headers"],
        json={"email": "x@example.com", "role": "member"},
    )
    assert invite_denied.status_code == 403


def test_change_role_transfer_and_remove(client, account, mailbox):
    workspace_id = account["workspace_id"]
    email = f"peer-{uuid.uuid4().hex[:8]}@example.com"
    created = client.post(
        f"/api/workspaces/{workspace_id}/invites",
        headers=account["headers"],
        json={"email": email, "role": "admin"},
    )
    peer = _register(client, email)
    client.post(f"/api/invites/{created.json()['token']}/accept", headers=peer["headers"])
    members = client.get(f"/api/workspaces/{workspace_id}/members", headers=account["headers"]).json()
    peer_id = next(item["user_id"] for item in members if item["email"] == email)
    owner_id = next(item["user_id"] for item in members if item["role"] == "owner")

    demote_owner = client.patch(
        f"/api/workspaces/{workspace_id}/members/{owner_id}",
        headers=peer["headers"],
        json={"role": "member"},
    )
    assert demote_owner.status_code == 403

    transferred = client.patch(
        f"/api/workspaces/{workspace_id}/members/{peer_id}",
        headers=account["headers"],
        json={"role": "owner"},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["role"] == "owner"
    owners = client.get("/api/workspaces", headers=account["headers"]).json()
    assert owners[0]["role"] == "admin"

    removed = client.delete(
        f"/api/workspaces/{workspace_id}/members/{owner_id}",
        headers=peer["headers"],
    )
    assert removed.status_code == 204
    gone = client.get(f"/api/workspaces/{workspace_id}/teams", headers=account["headers"])
    assert gone.status_code == 404


def test_invite_rejects_wrong_email_expired_and_revoked(client, account, mailbox):
    workspace_id = account["workspace_id"]
    created = client.post(
        f"/api/workspaces/{workspace_id}/invites",
        headers=account["headers"],
        json={"email": "right@example.com", "role": "viewer"},
    )
    token = created.json()["token"]
    other = _register(client, "wrong@example.com")
    mismatch = client.post(f"/api/invites/{token}/accept", headers=other["headers"])
    assert mismatch.status_code == 403

    preview = client.get(f"/api/invites/{token}")
    assert preview.status_code == 200
    assert preview.json()["email"] == "right@example.com"
    assert client.get(f"/api/invites/{uuid.uuid4().hex}").status_code == 404

    revoked = client.delete(
        f"/api/workspaces/{workspace_id}/invites/{created.json()['id']}",
        headers=account["headers"],
    )
    assert revoked.status_code == 204
    right = _register(client, "right@example.com")
    assert client.post(f"/api/invites/{token}/accept", headers=right["headers"]).status_code == 410
