from __future__ import annotations

import asyncio
import os

import psycopg
from psycopg import sql
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.enums import IdentityAccessStatus, IdentityStatus, SystemRole
from common.iam import IAM_SERVICES, ensure_student_identity, service_principal
from common.models import Bank, StudentIdentityAccess, StudentUser
from common.security import hash_password

STUDENT_EMAIL = "student@easyitlab.tech"
STUDENT_PASSWORD = "student123"


def _build_bank() -> Bank:
    return Bank(
        full_name="Easy IT Bank Educational Sandbox",
        short_name="Easy IT Bank",
        bik="044525225",
        inn="7701234567",
        kpp="770101001",
        ogrn="1027700132195",
        correspondent_account="30101810400000000225",
        legal_address="Moscow, Demo st. 1",
        postal_address="Moscow, PO Box 10",
        support_phone="+7-800-555-35-35",
        support_email="support@easyitlab.tech",
        swift_code="EASYRUMM",
    )


def _postgres_sync_dsn() -> str:
    from_env = os.getenv("IAM_POSTGRES_DSN")
    if from_env:
        return from_env
    return os.getenv("DATABASE_URL", "postgresql+asyncpg://demobank:demobank@postgres:5432/demobank").replace("+asyncpg", "")


def _ensure_postgres_role(username: str, password: str) -> None:
    dsn = _postgres_sync_dsn()
    database = os.getenv("POSTGRES_DB", "demobank")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
            exists = cur.fetchone() is not None
            if exists:
                cur.execute(
                    sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(username),
                        sql.Literal(password),
                    )
                )
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(username),
                        sql.Literal(password),
                    )
                )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database),
                    sql.Identifier(username),
                )
            )
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(username)))
            cur.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
                    sql.Identifier(username)
                )
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(sql.Identifier(username))
            )


async def ensure_minimal_student_bootstrap(session: AsyncSession) -> None:
    bank = (await session.execute(select(Bank).limit(1))).scalar_one_or_none()
    if not bank:
        session.add(_build_bank())
        await session.flush()

    user = (
        await session.execute(
            select(StudentUser).where(
                (StudentUser.email == STUDENT_EMAIL) | (StudentUser.username == STUDENT_EMAIL)
            )
        )
    ).scalar_one_or_none()
    if not user:
        user = StudentUser(
            email=STUDENT_EMAIL,
            username=STUDENT_EMAIL,
            hashed_password=hash_password(STUDENT_PASSWORD),
            first_name="Student",
            last_name="User",
            system_role=SystemRole.STUDENT,
            is_active=True,
            is_blocked=False,
            blocked_reason=None,
            created_by_admin_id=None,
            is_primary_admin=False,
            can_create_admins=False,
        )
        session.add(user)
        await session.flush()
    else:
        user.email = STUDENT_EMAIL
        user.username = STUDENT_EMAIL
        user.hashed_password = hash_password(STUDENT_PASSWORD)
        user.first_name = user.first_name or "Student"
        user.last_name = user.last_name or "User"
        user.system_role = SystemRole.STUDENT
        user.is_active = True
        user.is_blocked = False
        user.blocked_reason = None
        user.created_by_admin_id = None
        user.is_primary_admin = False
        user.can_create_admins = False
        await session.flush()

    identity = await ensure_student_identity(session, user, default_status=IdentityStatus.ACTIVE)
    identity.username = user.username
    identity.system_role = SystemRole.STUDENT
    identity.status = IdentityStatus.ACTIVE
    identity.last_error = None
    identity.deprovisioned_at = None
    await session.flush()

    accesses = (
        await session.execute(
            select(StudentIdentityAccess).where(StudentIdentityAccess.identity_id == identity.id)
        )
    ).scalars().all()
    by_service = {row.service_name: row for row in accesses}
    for service_name in IAM_SERVICES:
        principal = service_principal(service_name, user.username)
        access = by_service.get(service_name)
        if access:
            access.principal = principal
            access.status = IdentityAccessStatus.ACTIVE
            access.last_error = None
            access.details_json = access.details_json or {}
            continue
        session.add(
            StudentIdentityAccess(
                identity_id=identity.id,
                service_name=service_name,
                principal=principal,
                status=IdentityAccessStatus.ACTIVE,
                details_json={},
                last_error=None,
            )
        )

    await session.commit()
    await asyncio.to_thread(_ensure_postgres_role, STUDENT_EMAIL, STUDENT_PASSWORD)
