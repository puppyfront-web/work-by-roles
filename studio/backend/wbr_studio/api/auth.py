"""邮箱注册与登录。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wbr_studio.deps import get_current_user, get_db
from wbr_studio.models import User, Workspace
from wbr_studio.present import user_out, workspace_out
from wbr_studio.schemas import LoginIn, RegisterIn
from wbr_studio.security import AuthError, encode_token, hash_password, verify_password

router = APIRouter()
_DUMMY = hash_password("not-a-real-password")


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> dict:
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="邮箱已注册") from exc
    name = body.workspace_name or body.email.split("@", 1)[0]
    workspace = Workspace(name=name[:128] or "workspace", owner_id=user.id)
    db.add(workspace)
    db.commit()
    try:
        token = encode_token(user.id)
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_out(user),
        "workspace": workspace_out(workspace),
    }


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict:
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if user is None:
        verify_password(body.password, _DUMMY)
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    try:
        token = encode_token(user.id)
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"access_token": token, "token_type": "bearer", "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return user_out(user)
