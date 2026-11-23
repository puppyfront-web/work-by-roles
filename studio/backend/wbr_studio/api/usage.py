"""工作区用量：按天、模型和角色汇总 token 与估算费用。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from wbr_studio.deps import WorkspaceContext, get_db, read_workspace
from wbr_studio.usage_report import build_usage

router = APIRouter()


@router.get("/{workspace_id}/usage")
def usage(
    days: int = Query(default=30, ge=1, le=366),
    ctx: WorkspaceContext = Depends(read_workspace),
    db: Session = Depends(get_db),
) -> dict:
    return build_usage(db, ctx.workspace.id, days)
