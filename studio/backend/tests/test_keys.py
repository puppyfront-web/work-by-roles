from sqlalchemy import select

from wbr_studio.db import get_sessionmaker
from wbr_studio.models import ProviderKey
from wbr_studio.security import decrypt_secret

SECRET = "sk-live-DO-NOT-LEAK-8f3a2c91"


def test_provider_key_is_encrypted_and_never_returned(client, account):
    headers = account["headers"]
    workspace_id = account["workspace_id"]
    created = client.post(
        f"/api/workspaces/{workspace_id}/provider-keys",
        headers=headers,
        json={
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "api_key": SECRET,
        },
    )
    assert created.status_code == 201, created.text
    assert SECRET not in created.text
    assert "ciphertext" not in created.text
    assert created.json()["key_hint"] == SECRET[-4:]
    assert created.json()["model"] == "gpt-4o-mini"

    listed = client.get(f"/api/workspaces/{workspace_id}/provider-keys", headers=headers)
    assert listed.status_code == 200
    assert SECRET not in listed.text
    assert listed.json()[0]["key_hint"] == SECRET[-4:]

    with get_sessionmaker()() as db:
        row = db.scalars(select(ProviderKey)).one()
        assert SECRET not in row.ciphertext
        assert decrypt_secret(row.ciphertext) == SECRET


def test_validation_error_does_not_echo_the_key(client, account):
    response = client.post(
        f"/api/workspaces/{account['workspace_id']}/provider-keys",
        headers=account["headers"],
        json={
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": 1,
            "api_key": SECRET,
        },
    )
    assert response.status_code == 422
    assert SECRET not in response.text
