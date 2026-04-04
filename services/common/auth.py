from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from common.config import get_settings

settings = get_settings()


def _base_claims(user_id: str, system_role: str, business_role: str | None, permissions: list[str], session_id: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "sub": user_id,
        "user_id": user_id,
        "system_role": system_role,
        "business_role": business_role,
        "permissions": permissions,
        "session_id": session_id,
        "iat": int(now.timestamp()),
    }


def create_access_token(
    user_id: str,
    system_role: str,
    business_role: str | None,
    permissions: list[str],
    session_id: str,
) -> str:
    payload = _base_claims(user_id, system_role, business_role, permissions, session_id)
    exp = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_expires_minutes)
    payload["exp"] = int(exp.timestamp())
    payload["type"] = "access"
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, session_id: str) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    exp = now + timedelta(days=settings.jwt_refresh_expires_days)
    jti = uuid.uuid4().hex
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "session_id": session_id,
        "jti": jti,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, exp


def create_docs_token(
    user_id: str,
    system_role: str,
    business_role: str | None,
    permissions: list[str],
    session_id: str,
    expires_seconds: int = 60,
) -> str:
    payload = _base_claims(user_id, system_role, business_role, permissions, session_id)
    exp = datetime.now(UTC) + timedelta(seconds=expires_seconds)
    payload["exp"] = int(exp.timestamp())
    payload["type"] = "student_docs"
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
