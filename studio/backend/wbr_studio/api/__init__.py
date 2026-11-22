"""HTTP 路由集合。"""
from fastapi import APIRouter

from wbr_studio.api.auth import router as auth_router
from wbr_studio.api.keys import router as key_router
from wbr_studio.api.runs import router as run_router
from wbr_studio.api.teams import router as team_router
from wbr_studio.api.workspaces import router as workspace_router
from wbr_studio.api.workspaces import template_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(template_router, prefix="/templates", tags=["templates"])
router.include_router(workspace_router, prefix="/workspaces", tags=["workspaces"])
router.include_router(key_router, prefix="/workspaces", tags=["provider-keys"])
router.include_router(team_router, prefix="/workspaces", tags=["teams"])
router.include_router(run_router, prefix="/workspaces", tags=["runs"])
