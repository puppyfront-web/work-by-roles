def test_create_team_from_template_and_isolate_workspaces(client, account):
    headers = account["headers"]
    workspace_id = account["workspace_id"]
    templates = client.get("/api/templates", headers=headers)
    assert templates.status_code == 200
    names = {item["name"] for item in templates.json()}
    assert "arch_review_team" in names

    created = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=headers,
        json={"name": "架构组", "template": "arch_review_team"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    role_types = {role["role_type"] for role in body["roles"]}
    assert role_types == {"coordinator", "expert", "verifier"}
    assert body["template_name"] == "arch_review_team"
    assert "contracts" in body

    listed = client.get(f"/api/workspaces/{workspace_id}/teams", headers=headers)
    assert [item["id"] for item in listed.json()] == [body["id"]]
    assert "contracts" not in listed.json()[0]

    renamed = client.patch(
        f"/api/workspaces/{workspace_id}/teams/{body['id']}",
        headers=headers,
        json={"name": "架构组 v2"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "架构组 v2"

    other = client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "password123", "workspace_name": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    stolen = client.get(
        f"/api/workspaces/{workspace_id}/teams/{body['id']}",
        headers=other_headers,
    )
    assert stolen.status_code == 404

    removed = client.delete(f"/api/workspaces/{workspace_id}/teams/{body['id']}", headers=headers)
    assert removed.status_code == 204
    missing = client.get(f"/api/workspaces/{workspace_id}/teams/{body['id']}", headers=headers)
    assert missing.status_code == 404


def test_reject_unknown_template_and_invalid_contract(client, account):
    headers = account["headers"]
    workspace_id = account["workspace_id"]
    unknown = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=headers,
        json={"name": "x", "template": "../secrets"},
    )
    assert unknown.status_code == 422

    invalid = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=headers,
        json={"name": "x", "contracts": [{"identity": {"role_id": "no"}}]},
    )
    assert invalid.status_code == 422
    both = client.post(
        f"/api/workspaces/{workspace_id}/teams",
        headers=headers,
        json={"name": "x", "template": "arch_review_team", "contracts": [{"identity": {}}]},
    )
    assert both.status_code == 422
