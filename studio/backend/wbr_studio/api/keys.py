"""供应商密钥。响应里只有末四位提示，没有明文，也没有密文。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from wbr_studio.deps import get_db, get_workspace
from wbr_studio.models import ProviderKey, Workspace
from wbr_studio.present import key_out
from wbr_studio.schemas import ProviderKeyIn
from wbr_studio.security import SecretError, encrypt_secret, key_hint

router = APIRouter()


@router.get("/{workspace_id}/provider-keys")
def list_keys(
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(
        select(ProviderKey)
        .where(ProviderKey.workspace_id == workspace.id)
        .order_by(ProviderKey.created_at.desc())
    ).all()
    return [key_out(row) for row in rows]


@router.post("/{workspace_id}/provider-keys", status_code=201)
def create_key(
    body: ProviderKeyIn,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> dict:
    try:
        ciphertext = encrypt_secret(body.api_key)
    except SecretError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    row = ProviderKey(
        workspace_id=workspace.id,
        name=body.name,
        base_url=body.base_url,
        model=body.model,
        ciphertext=ciphertext,
        key_hint=key_hint(body.api_key),
    )
    db.add(row)
    db.commit()
    return key_out(row)


@router.delete("/{workspace_id}/provider-keys/{key_id}", status_code=204)
def delete_key(
    key_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> None:
    row = db.get(ProviderKey, key_id)
    if row is None or row.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="密钥不存在")
    db.delete(row)
    db.commit()
