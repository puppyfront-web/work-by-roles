"""工作区成员与邀请。一个工作区始终只有一个 owner。"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from wbr_studio.mailer import get_mailer
from wbr_studio.models import User, Workspace, WorkspaceInvite, WorkspaceMember, utcnow
from wbr_studio.sessions import hash_token
from wbr_studio.settings import get_settings

_log = logging.getLogger("wbr_studio.membership")

ROLES = ("viewer", "member", "admin", "owner")
INVITE_ROLES = ("viewer", "member", "admin")
_RANK = {role: index for index, role in enumerate(ROLES)}


def role_at_least(role: str, minimum: str) -> bool:
    return _RANK[role] >= _RANK[minimum]


def add_owner(db: Session, workspace: Workspace, user: User) -> WorkspaceMember:
    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(member)
    return member


def create_invite(
    db: Session,
    workspace: Workspace,
    actor: User,
    email: str,
    role: str,
) -> tuple[WorkspaceInvite, str]:
    if role not in INVITE_ROLES:
        raise HTTPException(status_code=422, detail="角色只能是 admin、member 或 viewer")
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        member = db.get(WorkspaceMember, (workspace.id, existing.id))
        if member is not None:
            raise HTTPException(status_code=409, detail="该用户已在工作区中")
    now = utcnow()
    db.execute(
        update(WorkspaceInvite)
        .where(
            WorkspaceInvite.workspace_id == workspace.id,
            WorkspaceInvite.email == email,
            WorkspaceInvite.accepted_at.is_(None),
            WorkspaceInvite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    raw = secrets.token_urlsafe(32)
    invite = WorkspaceInvite(
        workspace_id=workspace.id,
        email=email,
        role=role,
        token_hash=hash_token(raw),
        invited_by=actor.id,
        expires_at=now + timedelta(hours=get_settings().studio_invite_ttl_hours),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    _send_invite(workspace, invite, raw)
    return invite, raw


def _send_invite(workspace: Workspace, invite: WorkspaceInvite, raw: str) -> None:
    path = f"/invite/{raw}"
    text = (
        f"你被邀请加入工作区「{workspace.name}」，角色为 {invite.role}。\n"
        f"打开 {path} 接受邀请。\n"
        f"token: {raw}\n"
    )
    try:
        get_mailer().send(to=invite.email, subject=f"加入工作区 {workspace.name}", text=text)
    except Exception as exc:
        _log.warning("invite mail failed (%s)", type(exc).__name__)


def invite_from_token(db: Session, raw: str) -> WorkspaceInvite:
    invite = db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.token_hash == hash_token(raw)))
    if invite is None:
        raise HTTPException(status_code=404, detail="邀请不存在")
    return invite


def assert_invite_open(invite: WorkspaceInvite) -> None:
    if invite.revoked_at is not None:
        raise HTTPException(status_code=410, detail="邀请已撤销")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=410, detail="邀请已使用")
    if invite.expires_at <= utcnow():
        raise HTTPException(status_code=410, detail="邀请已过期")


def accept_invite(db: Session, raw: str, user: User) -> WorkspaceMember:
    invite = invite_from_token(db, raw)
    if user.email != invite.email:
        raise HTTPException(status_code=403, detail="请使用受邀邮箱的账号接受邀请")
    current = db.get(WorkspaceMember, (invite.workspace_id, user.id))
    if invite.accepted_at is not None:
        if current is not None:
            return current
        raise HTTPException(status_code=410, detail="邀请已使用")
    assert_invite_open(invite)
    if current is None:
        current = WorkspaceMember(
            workspace_id=invite.workspace_id,
            user_id=user.id,
            role=invite.role,
        )
        db.add(current)
    now = utcnow()
    invite.accepted_at = now
    db.execute(
        update(WorkspaceInvite)
        .where(
            WorkspaceInvite.workspace_id == invite.workspace_id,
            WorkspaceInvite.email == invite.email,
            WorkspaceInvite.id != invite.id,
            WorkspaceInvite.accepted_at.is_(None),
            WorkspaceInvite.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
    db.refresh(current)
    return current


def change_role(
    db: Session,
    workspace: Workspace,
    actor: WorkspaceMember,
    target: WorkspaceMember,
    new_role: str,
) -> WorkspaceMember:
    if new_role not in ROLES:
        raise HTTPException(status_code=422, detail="角色无效")
    if not role_at_least(actor.role, "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    if target.role == new_role:
        return target
    if target.role == "owner" or (new_role == "owner" and actor.role != "owner"):
        raise HTTPException(status_code=403, detail="不能更改所有者")
    if new_role == "owner":
        if target.user_id == actor.user_id:
            return target
        actor.role = "admin"
        db.flush()
        target.role = "owner"
        workspace.owner_id = target.user_id
        db.commit()
        db.refresh(target)
        return target
    if actor.role != "owner" and target.user_id == actor.user_id and new_role != "owner":
        raise HTTPException(status_code=403, detail="不能更改自己的角色")
    target.role = new_role
    db.commit()
    db.refresh(target)
    return target


def remove_member(
    db: Session,
    actor: WorkspaceMember,
    target: WorkspaceMember,
    *,
    self_remove: bool,
) -> None:
    if target.role == "owner":
        raise HTTPException(status_code=403, detail="不能移除所有者")
    if not self_remove and not role_at_least(actor.role, "admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    db.delete(target)
    db.commit()


def revoke_invite(db: Session, invite: WorkspaceInvite) -> None:
    if invite.revoked_at is None and invite.accepted_at is None:
        invite.revoked_at = utcnow()
        db.commit()
