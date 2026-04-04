from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.enums import IdentityAccessStatus, IdentityStatus, SystemRole
from common.models import StudentIdentity, StudentIdentityAccess, StudentUser

IAM_SERVICES: tuple[str, ...] = (
    "POSTGRES",
    "JENKINS",
    "ALLURE",
    "REST_API",
    "REDIS",
    "KAFKA",
)

_NON_ALNUM = re.compile(r"[^a-z0-9_]+")


def sanitize_identity_slug(value: str) -> str:
    clean = _NON_ALNUM.sub("_", value.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "user"


def service_principal(service_name: str, username: str) -> str:
    # All IAM services must use the same student/admin account identity (email + password).
    return username.strip()[:64]


async def ensure_student_identity(
    session: AsyncSession,
    user: StudentUser,
    *,
    requested_by_admin_id: uuid.UUID | None = None,
    default_status: IdentityStatus = IdentityStatus.PENDING,
) -> StudentIdentity:
    identity = (
        await session.execute(
            select(StudentIdentity).where(StudentIdentity.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not identity:
        identity = StudentIdentity(
            user_id=user.id,
            username=user.username,
            system_role=SystemRole(user.system_role),
            status=default_status,
            requested_by_admin_id=requested_by_admin_id,
        )
        session.add(identity)
        await session.flush()
    else:
        identity.username = user.username
        identity.system_role = SystemRole(user.system_role)
        if requested_by_admin_id:
            identity.requested_by_admin_id = requested_by_admin_id

    existing = (
        await session.execute(
            select(StudentIdentityAccess).where(StudentIdentityAccess.identity_id == identity.id)
        )
    ).scalars().all()
    by_service = {row.service_name: row for row in existing}
    for service_name in IAM_SERVICES:
        if service_name in by_service:
            principal = service_principal(service_name, user.username)
            if by_service[service_name].principal != principal:
                by_service[service_name].principal = principal
            continue
        session.add(
            StudentIdentityAccess(
                identity_id=identity.id,
                service_name=service_name,
                principal=service_principal(service_name, user.username),
                status=IdentityAccessStatus.PENDING,
            )
        )
    await session.flush()
    return identity
