"""请求依赖：会话、当前用户、工作区内的角色。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from wbr_studio.db import get_sessionmaker
from wbr_studio.membership import role_at_least
from wbr_studio.models import User, Workspace, WorkspaceMember
from wbr_studio.security import AuthError, decode_token
from wbr_studio.settings import get_settings

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
        user_id, token_version = decode_token(creds.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, user_id)
    if user is None or user.token_version != token_version:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


@dataclass
class WorkspaceContext:
    workspace: Workspace
    membership: WorkspaceMember
    user: User

    @property
    def role(self) -> str:
        return self.membership.role


def _load(workspace_id: uuid.UUID, user: User, db: Session, minimum: str) -> WorkspaceContext:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    member = db.get(WorkspaceMember, (workspace.id, user.id))
    if member is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    if not role_at_least(member.role, minimum):
        raise HTTPException(status_code=403, detail="权限不足")
    return WorkspaceContext(workspace=workspace, membership=member, user=user)


def ensure_verified(user: User) -> None:
    if get_settings().studio_require_email_verification and not user.email_verified:
        raise HTTPException(status_code=403, detail="请先验证邮箱")


def read_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceContext:
    return _load(workspace_id, user, db, "viewer")


def write_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceContext:
    ctx = _load(workspace_id, user, db, "member")
    ensure_verified(user)
    return ctx


def manage_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceContext:
    ctx = _load(workspace_id, user, db, "admin")
    ensure_verified(user)
    return ctx
