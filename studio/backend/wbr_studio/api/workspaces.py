"""工作区。列表包含当前用户在其中的角色。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from wbr_studio.contracts import public_templates
from wbr_studio.deps import get_current_user, get_db
from wbr_studio.membership import add_owner
from wbr_studio.models import User, Workspace, WorkspaceMember
from wbr_studio.present import workspace_out
from wbr_studio.schemas import WorkspaceIn

router = APIRouter()
template_router = APIRouter()


@template_router.get("")
def templates(_user: User = Depends(get_current_user)) -> list[dict]:
    return public_templates()


@router.get("")
def list_workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at.asc())
    ).all()
    return [workspace_out(workspace, role=role) for workspace, role in rows]


@router.post("", status_code=201)
def create_workspace(
    body: WorkspaceIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    workspace = Workspace(name=body.name, owner_id=user.id)
    db.add(workspace)
    db.flush()
    add_owner(db, workspace, user)
    db.commit()
    return workspace_out(workspace, role="owner")
