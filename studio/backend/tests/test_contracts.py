def test_contract_edits_are_versioned_and_rejected_when_invalid(client, account):
    created = client.post(
        f"/api/workspaces/{account['workspace_id']}/teams",
        headers=account["headers"],
        json={"name": "架构组", "template": "arch_review_team"},
    )
    assert created.status_code == 201, created.text
    team_id = created.json()["id"]
    assert created.json()["current_version"] == 1

    renamed = client.patch(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}",
        headers=account["headers"],
        json={"name": "架构组二"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["current_version"] == 1

    contracts = renamed.json()["contracts"]
    contracts[1]["identity"]["name"] = "新的专家名"
    saved = client.patch(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}",
        headers=account["headers"],
        json={"contracts": contracts},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["current_version"] == 2
    assert saved.json()["contracts"][1]["identity"]["name"] == "新的专家名"

    same = client.patch(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}",
        headers=account["headers"],
        json={"contracts": saved.json()["contracts"]},
    )
    assert same.status_code == 200, same.text
    assert same.json()["current_version"] == 2

    invalid = client.patch(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}",
        headers=account["headers"],
        json={"contracts": [{"identity": {"role_id": "no"}}]},
    )
    assert invalid.status_code == 422
    current = client.get(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}",
        headers=account["headers"],
    )
    assert current.json()["current_version"] == 2

    history = client.get(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}/versions",
        headers=account["headers"],
    )
    assert [item["version"] for item in history.json()] == [2, 1]
    first = client.get(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}/versions/1",
        headers=account["headers"],
    )
    assert first.status_code == 200
    assert first.json()["contracts"][1]["identity"]["name"] != "新的专家名"
    missing = client.get(
        f"/api/workspaces/{account['workspace_id']}/teams/{team_id}/versions/9",
        headers=account["headers"],
    )
    assert missing.status_code == 404
