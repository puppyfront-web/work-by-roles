"""团队：从内核模板创建，或提交已通过 RoleContract 校验的契约。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wbr_studio.contracts import TeamContractError, contracts_from_template, normalize_contract_payload
from wbr_studio.deps import get_db, get_workspace
from wbr_studio.models import Team, Workspace
from wbr_studio.present import team_out
from wbr_studio.schemas import TeamCreate, TeamUpdate

router = APIRouter()


def _team_or_404(db: Session, workspace: Workspace, team_id: uuid.UUID) -> Team:
    team = db.get(Team, team_id)
    if team is None or team.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="团队不存在")
    return team


@router.get("/{workspace_id}/teams")
def list_teams(workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Team).where(Team.workspace_id == workspace.id).order_by(Team.created_at.desc())
    ).all()
    return [team_out(row, with_contracts=False) for row in rows]


@router.post("/{workspace_id}/teams", status_code=201)
def create_team(
    body: TeamCreate,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> dict:
    try:
        if body.template is not None:
            contracts = contracts_from_template(body.template)
            template_name = body.template
        else:
            contracts = normalize_contract_payload(body.contracts or [])
            template_name = None
    except TeamContractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    team = Team(
        workspace_id=workspace.id,
        name=body.name,
        template_name=template_name,
        contracts=contracts,
    )
    db.add(team)
    db.commit()
    return team_out(team, with_contracts=True)


@router.get("/{workspace_id}/teams/{team_id}")
def get_team(
    team_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> dict:
    return team_out(_team_or_404(db, workspace, team_id), with_contracts=True)


@router.patch("/{workspace_id}/teams/{team_id}")
def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> dict:
    team = _team_or_404(db, workspace, team_id)
    if body.name is not None:
        team.name = body.name
    if body.contracts is not None:
        try:
            team.contracts = normalize_contract_payload(body.contracts)
        except TeamContractError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return team_out(team, with_contracts=True)


@router.delete("/{workspace_id}/teams/{team_id}", status_code=204)
def delete_team(
    team_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> None:
    team = _team_or_404(db, workspace, team_id)
    db.delete(team)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="团队已有运行记录，不能删除") from exc
