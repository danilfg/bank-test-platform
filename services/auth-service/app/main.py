from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth import create_access_token, create_refresh_token, decode_token
from common.bootstrap import ensure_minimal_student_bootstrap
from common.db import SessionLocal, engine, get_db
from common.deps import get_current_claims
from common.enums import BusinessRole, IdentityAccessStatus, SystemRole
from common.errors import DomainError, domain_error_handler
from common.kafka import produce_event
from common.models import Client, RefreshToken, StudentIdentity, StudentIdentityAccess, StudentSession, StudentUser
from common.observability import setup_app
from common.security import hash_password, verify_password

app = FastAPI(title="EasyBank Auth Service", version="1.0.0")
app.add_exception_handler(DomainError, domain_error_handler)
setup_app(app, "auth-service", engine)
IAM_TOPIC = os.getenv("IAM_EVENTS_TOPIC", "iam-events")


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "student@easyitlab.tech",
                "password": "student123",
            }
        }
    )

    email: str = Field(validation_alias=AliasChoices("email", "username"))
    password: str
    business_role: BusinessRole | None = None

    @model_validator(mode="after")
    def normalize(self):
        self.email = self.email.strip().lower()
        self.password = self.password.strip()
        return self


class RefreshRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )

    refresh_token: str


class SwitchRoleRequest(BaseModel):
    business_role: BusinessRole


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    business_role: BusinessRole | None = None


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    previous_business_role: BusinessRole | None = None


class SwitchRoleResponse(BaseModel):
    access_token: str
    business_role: BusinessRole


class LogoutResponse(BaseModel):
    ok: bool


class AuthMeResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    first_name: str
    last_name: str
    system_role: SystemRole
    business_role: BusinessRole | None = None
    permissions: list[str]


class PasswordChangeResponse(BaseModel):
    ok: bool
    message: str


def permissions_for(system_role: SystemRole, business_role: BusinessRole | None) -> list[str]:
    if business_role == BusinessRole.CLIENT:
        return [
            "client:accounts:read",
            "client:transfers:create",
            "client:tickets:create",
        ]
    return [
        "employee:clients:create",
        "employee:accounts:block",
        "employee:tickets:update",
    ]


def resolve_business_role(system_role: SystemRole, requested: BusinessRole | None) -> BusinessRole | None:
    return requested or BusinessRole.CLIENT


async def create_session(db: AsyncSession, user_id: uuid.UUID, request: Request) -> str:
    session_id = uuid.uuid4().hex
    sess = StudentSession(
        user_id=user_id,
        session_id=session_id,
        ip=(request.client.host if request.client else None),
        user_agent=request.headers.get("user-agent"),
        is_active=True,
        last_seen_at=datetime.now(UTC),
    )
    db.add(sess)
    await db.flush()
    return session_id


async def store_refresh(db: AsyncSession, user_id: uuid.UUID, session_id: str, jti: str, expires_at: datetime):
    db.add(
        RefreshToken(
            token_jti=jti,
            user_id=user_id,
            session_id=session_id,
            expires_at=expires_at,
            revoked=False,
        )
    )


async def ensure_student_owner_login_allowed(db: AsyncSession, user: StudentUser) -> None:
    if user.system_role != SystemRole.STUDENT:
        return

    if user.created_by_admin_id:
        creator = await db.get(StudentUser, user.created_by_admin_id)
        if creator and creator.system_role == SystemRole.STUDENT:
            raise DomainError(403, "STUDENT_OWNER_REQUIRED", "Student owner access required")

    manages_clients = (
        await db.execute(select(Client.id).where(Client.created_by_employee_id == user.id).limit(1))
    ).scalar_one_or_none()
    if manages_clients:
        raise DomainError(403, "STUDENT_OWNER_REQUIRED", "Student owner access required")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def ensure_minimal_student_on_startup():
    async with SessionLocal() as session:
        await ensure_minimal_student_bootstrap(session)


@app.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return {"status": "ok"}


@app.post("/auth/login", tags=["Auth"], response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(
            select(StudentUser).where((StudentUser.username == payload.email) | (StudentUser.email == payload.email))
        )
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise DomainError(401, "INVALID_CREDENTIALS", "Invalid username or password")
    if user.is_blocked:
        raise DomainError(403, "STUDENT_BLOCKED", "Student is blocked")

    await ensure_student_owner_login_allowed(db, user)

    business_role = resolve_business_role(user.system_role, payload.business_role)
    permissions = permissions_for(user.system_role, business_role)
    session_id = await create_session(db, user.id, request)
    access = create_access_token(str(user.id), user.system_role.value, business_role.value if business_role else None, permissions, session_id)
    refresh, refresh_jti, refresh_exp = create_refresh_token(str(user.id), session_id)
    await store_refresh(db, user.id, session_id, refresh_jti, refresh_exp)

    user.last_login_at = datetime.now(UTC)
    await db.commit()

    await produce_event(
        "auth-events",
        "student.login",
        {"user_id": str(user.id), "session_id": session_id, "system_role": user.system_role.value},
        key=str(user.id),
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 15 * 60,
        "business_role": business_role.value if business_role else None,
    }


@app.post("/auth/refresh", tags=["Auth"], response_model=RefreshResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise DomainError(401, "INVALID_TOKEN_TYPE", "Refresh token required")
    token_row = (await db.execute(select(RefreshToken).where(RefreshToken.token_jti == claims["jti"]))).scalar_one_or_none()
    if not token_row or token_row.revoked:
        raise DomainError(401, "REFRESH_REVOKED", "Refresh token revoked")
    if token_row.expires_at < datetime.now(UTC):
        raise DomainError(401, "REFRESH_EXPIRED", "Refresh token expired")

    user = await db.get(StudentUser, uuid.UUID(claims["user_id"]))
    if not user:
        raise DomainError(404, "USER_NOT_FOUND", "User not found")

    await ensure_student_owner_login_allowed(db, user)

    token_row.revoked = True
    session_id = claims["session_id"]

    old_business_role = None
    # Use last business role from prior access token flow; default CLIENT for students.
    business_role = resolve_business_role(user.system_role, BusinessRole.CLIENT if user.system_role == SystemRole.STUDENT else None)
    perms = permissions_for(user.system_role, business_role)
    access = create_access_token(str(user.id), user.system_role.value, business_role.value if business_role else None, perms, session_id)
    refresh_token, refresh_jti, refresh_exp = create_refresh_token(str(user.id), session_id)
    await store_refresh(db, user.id, session_id, refresh_jti, refresh_exp)
    await db.commit()

    return {
        "access_token": access,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "previous_business_role": old_business_role,
    }


@app.post("/auth/logout", tags=["Auth"], response_model=LogoutResponse)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    decoded = decode_token(payload.refresh_token)
    token_row = (await db.execute(select(RefreshToken).where(RefreshToken.token_jti == decoded.get("jti")))).scalar_one_or_none()
    if token_row:
        token_row.revoked = True

    session_row = (await db.execute(select(StudentSession).where(StudentSession.session_id == claims["session_id"]))).scalar_one_or_none()
    if session_row:
        session_row.is_active = False
        session_row.last_seen_at = datetime.now(UTC)

    await db.commit()
    return {"ok": True}


@app.post("/auth/switch-role", tags=["Auth"], response_model=SwitchRoleResponse)
async def switch_role(payload: SwitchRoleRequest, claims: dict = Depends(get_current_claims), db: AsyncSession = Depends(get_db)):
    user = await db.get(StudentUser, uuid.UUID(claims["user_id"]))
    if not user:
        raise DomainError(404, "USER_NOT_FOUND", "User not found")
    if user.system_role != SystemRole.STUDENT:
        raise DomainError(400, "ROLE_SWITCH_NOT_ALLOWED", "Only STUDENT can switch business role")

    permissions = permissions_for(user.system_role, payload.business_role)
    access = create_access_token(
        str(user.id),
        user.system_role.value,
        payload.business_role.value,
        permissions,
        claims["session_id"],
    )
    return {
        "access_token": access,
        "business_role": payload.business_role.value,
    }


@app.get("/auth/me", tags=["Auth"], response_model=AuthMeResponse)
async def me(claims: dict = Depends(get_current_claims), db: AsyncSession = Depends(get_db)):
    user = await db.get(StudentUser, uuid.UUID(claims["user_id"]))
    if not user:
        raise DomainError(404, "USER_NOT_FOUND", "User not found")
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "full_name": full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "system_role": user.system_role,
        "business_role": claims.get("business_role"),
        "permissions": claims.get("permissions", []),
    }


@app.patch("/auth/password", tags=["Auth"], response_model=PasswordChangeResponse)
async def change_password(
    payload: PasswordChangeRequest,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
):
    if len(payload.new_password) < 8:
        raise DomainError(400, "WEAK_PASSWORD", "New password must be at least 8 characters long")
    if payload.new_password == payload.current_password:
        raise DomainError(400, "PASSWORD_REUSE_FORBIDDEN", "New password must differ from current password")

    user = await db.get(StudentUser, uuid.UUID(claims["user_id"]))
    if not user:
        raise DomainError(404, "USER_NOT_FOUND", "User not found")
    if not verify_password(payload.current_password, user.hashed_password):
        raise DomainError(401, "INVALID_CREDENTIALS", "Current password is invalid")

    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    await produce_event("auth-events", "student.password.changed", {"user_id": str(user.id), "system_role": user.system_role.value}, key=str(user.id))

    identity = (await db.execute(select(StudentIdentity).where(StudentIdentity.user_id == user.id))).scalar_one_or_none()
    if identity:
        active_accesses = (
            await db.execute(
                select(StudentIdentityAccess).where(
                    StudentIdentityAccess.identity_id == identity.id,
                    StudentIdentityAccess.status == IdentityAccessStatus.ACTIVE,
                )
            )
        ).scalars().all()
        services = sorted({row.service_name for row in active_accesses})
        try:
            await produce_event(
                IAM_TOPIC,
                "student.created",
                {
                    "identity_id": str(identity.id),
                    "user_id": str(user.id),
                    "username": user.username,
                    "system_role": user.system_role.value,
                    "services": services,
                    "bootstrap_password": payload.new_password,
                },
                key=str(identity.id),
            )
        except Exception:
            # Password change in auth must not fail due IAM async bus issues.
            pass
    return {"ok": True, "message": "Password updated"}
