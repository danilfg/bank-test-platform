from __future__ import annotations

import asyncio
import os

import psycopg
from psycopg import sql
from sqlalchemy import delete, select

from common.db import SessionLocal
from common.enums import IdentityAccessStatus, IdentityStatus, SystemRole
from common.models import (
    Account,
    Bank,
    Card,
    Client,
    RefreshToken,
    StudentIdentity,
    StudentIdentityAccess,
    StudentObservableEvent,
    StudentResourceUsage,
    StudentSession,
    StudentUser,
    SupportTicket,
    SupportTicketMessage,
    Transfer,
)
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


async def seed() -> None:
    async with SessionLocal() as session:
        bank = (await session.execute(select(Bank).limit(1))).scalar_one_or_none()
        if not bank:
            bank = _build_bank()
            session.add(bank)
            await session.flush()

        for model in (
            SupportTicketMessage,
            SupportTicket,
            Transfer,
            Card,
            Account,
            Client,
            StudentIdentityAccess,
            StudentIdentity,
            StudentSession,
            RefreshToken,
            StudentObservableEvent,
            StudentResourceUsage,
        ):
            await session.execute(delete(model))

        await session.execute(delete(StudentUser))
        await session.flush()

        student = StudentUser(
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
        session.add(student)
        await session.flush()

        identity = StudentIdentity(
            user_id=student.id,
            username=student.username,
            system_role=SystemRole.STUDENT,
            status=IdentityStatus.ACTIVE,
            requested_by_admin_id=None,
            last_error=None,
        )
        session.add(identity)
        await session.flush()

        for service_name in ("JENKINS", "ALLURE", "POSTGRES", "REST_API", "REDIS", "KAFKA"):
            session.add(
                StudentIdentityAccess(
                    identity_id=identity.id,
                    service_name=service_name,
                    principal=student.username,
                    status=IdentityAccessStatus.ACTIVE,
                    details_json={},
                    last_error=None,
                )
            )

        await session.commit()
        await asyncio.to_thread(_ensure_postgres_role, STUDENT_EMAIL, STUDENT_PASSWORD)

    print(
        "Minimal student-only seed completed:\n"
        f"  email={STUDENT_EMAIL}\n"
        f"  password={STUDENT_PASSWORD}\n"
        "  tool_accesses=JENKINS,ALLURE,POSTGRES,REST_API,REDIS,KAFKA"
    )


if __name__ == "__main__":
    asyncio.run(seed())
