"""请求依赖：会话、当前用户、名下工作区。"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from wbr_studio.db import get_sessionmaker
from wbr_studio.models import User, Workspace
from wbr_studio.security import AuthError, decode_token

_bearer = HTTPBearer(auto_error=False)


def get_db():
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="未登录", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = decode_token(creds.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


def get_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.owner_id != user.id:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return workspace
