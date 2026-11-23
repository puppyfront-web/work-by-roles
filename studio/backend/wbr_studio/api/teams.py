"""团队：从内核模板创建，或提交已通过 RoleContract 校验的契约。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wbr_studio.contracts import TeamContractError, contracts_from_template, normalize_contract_payload
from wbr_studio.deps import WorkspaceContext, get_db, manage_workspace, read_workspace, write_workspace
from wbr_studio.models import ContractVersion, Team, User
from wbr_studio.present import iso, team_out
from wbr_studio.schemas import TeamCreate, TeamUpdate

router = APIRouter()


def _team_or_404(db: Session, ctx: WorkspaceContext, team_id: uuid.UUID) -> Team:
    team = db.get(Team, team_id)
    if team is None or team.workspace_id != ctx.workspace.id:
        raise HTTPException(status_code=404, detail="团队不存在")
    return team


def _store_version(db: Session, team: Team, contracts: list, user: User, version: int) -> None:
    team.contracts = contracts
    team.current_version = version
    db.add(
        ContractVersion(
            team_id=team.id,
            version=version,
            contracts=contracts,
            created_by=user.id,
        )
    )


@router.get("/{workspace_id}/teams")
def list_teams(ctx: WorkspaceContext = Depends(read_workspace), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Team).where(Team.workspace_id == ctx.workspace.id).order_by(Team.created_at.desc())
    ).all()
    return [team_out(row, with_contracts=False) for row in rows]


@router.post("/{workspace_id}/teams", status_code=201)
def create_team(
    body: TeamCreate,
    ctx: WorkspaceContext = Depends(write_workspace),
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
        workspace_id=ctx.workspace.id,
        name=body.name,
        template_name=template_name,
        contracts=contracts,
        current_version=1,
    )
    db.add(team)
    db.flush()
    _store_version(db, team, contracts, ctx.user, 1)
    db.commit()
    return team_out(team, with_contracts=True)


@router.get("/{workspace_id}/teams/{team_id}")
def get_team(
    team_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> dict:
    return team_out(_team_or_404(db, ctx, team_id), with_contracts=True)


@router.get("/{workspace_id}/teams/{team_id}/versions")
def list_versions(
    team_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> list[dict]:
    team = _team_or_404(db, ctx, team_id)
    rows = db.execute(
        select(ContractVersion, User.email)
        .outerjoin(User, User.id == ContractVersion.created_by)
        .where(ContractVersion.team_id == team.id)
        .order_by(ContractVersion.version.desc())
    ).all()
    return [
        {
            "version": row.version,
            "created_at": iso(row.created_at),
            "created_by": str(row.created_by) if row.created_by else None,
            "created_by_email": email,
        }
        for row, email in rows
    ]


@router.get("/{workspace_id}/teams/{team_id}/versions/{version}")
def get_version(
    team_id: uuid.UUID,
    version: int,
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> dict:
    team = _team_or_404(db, ctx, team_id)
    row = db.scalar(
        select(ContractVersion).where(
            ContractVersion.team_id == team.id,
            ContractVersion.version == version,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="契约版本不存在")
    return {
        "version": row.version,
        "contracts": row.contracts,
        "created_at": iso(row.created_at),
        "created_by": str(row.created_by) if row.created_by else None,
    }


@router.patch("/{workspace_id}/teams/{team_id}")
def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    ctx: WorkspaceContext = Depends(write_workspace),
    db: Session = Depends(get_db),
) -> dict:
    team = _team_or_404(db, ctx, team_id)
    if body.name is not None:
        team.name = body.name
    if body.contracts is not None:
        try:
            contracts = normalize_contract_payload(body.contracts)
        except TeamContractError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if contracts != team.contracts:
            _store_version(db, team, contracts, ctx.user, team.current_version + 1)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="契约版本冲突，请重试") from exc
    return team_out(team, with_contracts=True)


@router.delete("/{workspace_id}/teams/{team_id}", status_code=204)
def delete_team(
    team_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(manage_workspace),
    db: Session = Depends(get_db),
) -> None:
    team = _team_or_404(db, ctx, team_id)
    db.delete(team)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="团队已有运行记录，不能删除") from exc
