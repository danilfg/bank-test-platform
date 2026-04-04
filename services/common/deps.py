from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.auth import decode_token
from common.errors import DomainError

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_claims(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise DomainError(status_code=401, code="AUTH_REQUIRED", message="Bearer token required")
    token = credentials.credentials
    try:
        return decode_token(token)
    except ValueError as exc:
        raise DomainError(status_code=401, code="INVALID_TOKEN", message="Invalid or expired token") from exc


def require_system_role(role: str):
    async def checker(claims: dict = Depends(get_current_claims)) -> dict:
        if claims.get("system_role") != role:
            raise DomainError(status_code=403, code="FORBIDDEN", message="Insufficient system role")
        return claims

    return checker


def require_business_role(role: str):
    async def checker(claims: dict = Depends(get_current_claims)) -> dict:
        if claims.get("business_role") != role:
            raise DomainError(status_code=403, code="FORBIDDEN", message="Insufficient business role")
        return claims

    return checker
