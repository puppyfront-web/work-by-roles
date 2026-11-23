"""刷新令牌和一次性邮箱令牌。库里只留 sha256。"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from wbr_studio.models import AuthToken, RefreshToken, User, utcnow
from wbr_studio.settings import get_settings


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=get_settings().studio_refresh_ttl_days),
        )
    )
    return raw


def revoke_all(db: Session, user: User) -> None:
    user.token_version += 1
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def rotate_refresh(db: Session, raw: str) -> tuple[User, str] | None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if row is None:
        return None
    user = db.get(User, row.user_id)
    if user is None:
        return None
    now = utcnow()
    if row.revoked_at is not None:
        revoke_all(db, user)
        db.commit()
        return None
    if row.expires_at <= now:
        return None
    row.revoked_at = now
    fresh = issue_refresh(db, user)
    db.commit()
    return user, fresh


def issue_email_token(db: Session, user: User, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(hours=get_settings().studio_email_token_ttl_hours),
        )
    )
    return raw


def consume_email_token(db: Session, raw: str, purpose: str) -> uuid.UUID | None:
    row = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == hash_token(raw),
            AuthToken.purpose == purpose,
        )
    )
    if row is None or row.used_at is not None or row.expires_at <= utcnow():
        return None
    row.used_at = utcnow()
    return row.user_id
