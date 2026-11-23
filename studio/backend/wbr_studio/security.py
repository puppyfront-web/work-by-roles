"""本地口令与供应商密钥。口令只存 PBKDF2，API Key 只存 Fernet 密文。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from wbr_studio.settings import get_settings

_ROUNDS = 120_000
_ALGO = "pbkdf2_sha256"


class AuthError(Exception):
    pass


class SecretError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ROUNDS)
    return f"{_ALGO}${_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds_text, salt_hex, digest_hex = stored.split("$")
        rounds = int(rounds_text)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, TypeError):
        return False
    if algo != _ALGO:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds).hex()
    return hmac.compare_digest(check, digest_hex)


def _fernet():
    from cryptography.fernet import Fernet

    settings = get_settings()
    raw = settings.studio_fernet_key.strip()
    if raw:
        try:
            return Fernet(raw.encode())
        except (ValueError, TypeError) as exc:
            raise SecretError(
                "STUDIO_FERNET_KEY 无效。生成命令："
                'python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
            ) from exc
    if not settings.studio_secret_key:
        raise SecretError("未配置 STUDIO_FERNET_KEY 或 STUDIO_SECRET_KEY，无法加密供应商密钥")
    material = hashlib.sha256(b"wbr-studio-fernet-v1\n" + settings.studio_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        raise SecretError("密钥为空")
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, SecretError, ValueError, TypeError) as exc:
        if isinstance(exc, SecretError):
            raise
        raise SecretError("供应商密钥无法解密，请核对 STUDIO_FERNET_KEY") from exc


def key_hint(plaintext: str) -> str:
    return plaintext[-4:]


def password_problem(password: str, email: str = "") -> str | None:
    """返回拒绝原因。登录不调用这里，已有口令不会被新策略锁在门外。"""
    if len(password) < 10:
        return "密码至少 10 位"
    if len(password) > 128:
        return "密码过长"
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        return "密码需要同时包含字母和数字"
    local = email.split("@", 1)[0]
    if len(local) >= 4 and local.lower() in password.lower():
        return "密码不能包含邮箱名"
    return None


def encode_token(user_id: uuid.UUID, token_version: int = 0) -> str:
    settings = get_settings()
    if not settings.studio_secret_key:
        raise AuthError("STUDIO_SECRET_KEY 未设置")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "typ": "access",
        "jti": secrets.token_hex(8),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.studio_jwt_ttl_minutes)).timestamp()),
    }
    token = jwt.encode(payload, settings.studio_secret_key, algorithm="HS256")
    return token if isinstance(token, str) else token.decode()


def decode_token(token: str) -> tuple[uuid.UUID, int]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.studio_secret_key, algorithms=["HS256"])
        if payload.get("typ") not in (None, "access"):
            raise AuthError("登录已失效")
        return uuid.UUID(str(payload["sub"])), int(payload.get("tv", 0))
    except AuthError:
        raise
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise AuthError("登录已失效") from exc
