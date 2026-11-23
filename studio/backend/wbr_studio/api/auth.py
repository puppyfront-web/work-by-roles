"""邮箱注册、登录、刷新与邮箱验证。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wbr_studio.deps import get_current_user, get_db
from wbr_studio.mailer import get_mailer
from wbr_studio.membership import add_owner
from wbr_studio.models import User, Workspace
from wbr_studio.present import user_out, workspace_out
from wbr_studio.ratelimit import allow_auth
from wbr_studio.schemas import LoginIn, RefreshIn, RegisterIn, TokenIn
from wbr_studio.security import AuthError, encode_token, hash_password, verify_password
from wbr_studio.sessions import consume_email_token, issue_email_token, issue_refresh, revoke_all, rotate_refresh

router = APIRouter()
_log = logging.getLogger("wbr_studio.auth")
_DUMMY = hash_password("not-a-real-password")


def _limit(request: Request, email: str | None = None) -> None:
    if not allow_auth(request, email):
        raise HTTPException(status_code=429, detail="请求过于频繁", headers={"Retry-After": "60"})


def _session(user: User, db: Session) -> dict:
    try:
        access = encode_token(user.id, user.token_version)
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    refresh = issue_refresh(db, user)
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user_out(user),
    }


def _send_verification(db: Session, user: User) -> None:
    raw = issue_email_token(db, user, "verify_email")
    db.commit()
    text = f"打开 /verify-email?token={raw} 验证邮箱。\ntoken: {raw}\n"
    try:
        get_mailer().send(to=user.email, subject="验证邮箱", text=text)
    except Exception as exc:
        _log.warning("verification mail failed (%s)", type(exc).__name__)


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> dict:
    _limit(request, body.email)
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
    db.flush()
    add_owner(db, workspace, user)
    db.commit()
    _send_verification(db, user)
    payload = _session(user, db)
    payload["workspace"] = workspace_out(workspace, role="owner")
    return payload


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    _limit(request, body.email)
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if user is None:
        verify_password(body.password, _DUMMY)
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return _session(user, db)


@router.post("/refresh")
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)) -> dict:
    _limit(request)
    rotated = rotate_refresh(db, body.refresh_token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    user, refresh_token = rotated
    try:
        access = encode_token(user.id, user.token_version)
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "access_token": access,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_out(user),
    }


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    revoke_all(db, user)
    db.commit()


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return user_out(user)


@router.post("/verify-email")
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db)) -> dict:
    _limit(request)
    user_id = consume_email_token(db, body.token, "verify_email")
    if user_id is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="链接无效或已过期")
    user = db.get(User, user_id)
    if user is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="链接无效或已过期")
    user.email_verified = True
    db.commit()
    return {"email_verified": True}


@router.post("/resend-verification", status_code=204)
def resend_verification(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _limit(request, user.email)
    if user.email_verified:
        return
    _send_verification(db, user)
