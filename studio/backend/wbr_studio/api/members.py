"""成员、邀请链接。邮件走可替换的 Mailer，默认只写日志。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from wbr_studio.deps import (
    WorkspaceContext,
    ensure_verified,
    get_current_user,
    get_db,
    manage_workspace,
    read_workspace,
)
from wbr_studio.membership import (
    accept_invite,
    assert_invite_open,
    change_role,
    create_invite,
    invite_from_token,
    remove_member,
    revoke_invite,
    role_at_least,
)
from wbr_studio.models import User, Workspace, WorkspaceInvite, WorkspaceMember
from wbr_studio.present import invite_out, member_out, workspace_out
from wbr_studio.schemas import InviteIn, RoleIn

router = APIRouter()
public_router = APIRouter()


def _member_or_404(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
    member = db.get(WorkspaceMember, (workspace_id, user_id))
    if member is None:
        raise HTTPException(status_code=404, detail="成员不存在")
    return member


@router.get("/{workspace_id}/members")
def list_members(ctx: WorkspaceContext = Depends(read_workspace), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(WorkspaceMember, User.email)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == ctx.workspace.id)
        .order_by(WorkspaceMember.created_at.asc())
    ).all()
    return [member_out(member, email) for member, email in rows]


@router.patch("/{workspace_id}/members/{user_id}")
def update_member(
    user_id: uuid.UUID,
    body: RoleIn,
    ctx: WorkspaceContext = Depends(manage_workspace),
    db: Session = Depends(get_db),
) -> dict:
    target = _member_or_404(db, ctx.workspace.id, user_id)
    changed = change_role(db, ctx.workspace, ctx.membership, target, body.role)
    email = db.get(User, changed.user_id)
    return member_out(changed, email.email if email else "")


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
def delete_member(
    user_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> None:
    target = _member_or_404(db, ctx.workspace.id, user_id)
    self_remove = target.user_id == ctx.user.id
    if not self_remove:
        if not role_at_least(ctx.role, "admin"):
            raise HTTPException(status_code=403, detail="权限不足")
        ensure_verified(ctx.user)
    remove_member(db, ctx.membership, target, self_remove=self_remove)


@router.get("/{workspace_id}/invites")
def list_invites(ctx: WorkspaceContext = Depends(manage_workspace), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == ctx.workspace.id)
        .order_by(WorkspaceInvite.created_at.desc())
    ).all()
    return [invite_out(row) for row in rows]


@router.post("/{workspace_id}/invites", status_code=201)
def invite(
    body: InviteIn,
    ctx: WorkspaceContext = Depends(manage_workspace),
    db: Session = Depends(get_db),
) -> dict:
    row, token = create_invite(db, ctx.workspace, ctx.user, body.email, body.role)
    return invite_out(row, token)


@router.delete("/{workspace_id}/invites/{invite_id}", status_code=204)
def revoke(
    invite_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(manage_workspace),
    db: Session = Depends(get_db),
) -> None:
    row = db.get(WorkspaceInvite, invite_id)
    if row is None or row.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="邀请不存在")
    revoke_invite(db, row)


@public_router.get("/{token}")
def preview_invite(token: str, db: Session = Depends(get_db)) -> dict:
    invite = invite_from_token(db, token)
    assert_invite_open(invite)
    workspace = db.get(Workspace, invite.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="邀请不存在")
    return {
        "email": invite.email,
        "role": invite.role,
        "workspace_name": workspace.name,
        "expires_at": invite.expires_at.isoformat(),
    }


@public_router.post("/{token}/accept")
def accept(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    member = accept_invite(db, token, user)
    workspace = db.get(Workspace, member.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return {"workspace": workspace_out(workspace, role=member.role), "role": member.role}
