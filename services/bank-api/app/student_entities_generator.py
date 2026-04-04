from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.enums import (
    AccountStatus,
    AccountType,
    ClientStatus,
    Currency,
    IdentityStatus,
    RiskLevel,
    SystemRole,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from common.errors import DomainError
from common.iam import ensure_student_identity
from common.models import (
    Account,
    Bank,
    Card,
    Client,
    StudentIdentity,
    StudentIdentityAccess,
    StudentUser,
    SupportTicket,
    SupportTicketMessage,
    Transfer,
)
from common.security import hash_password

STUDENT_PUBLIC_ID_PREFIX = "st-"
STUDENT_PUBLIC_ID_START = 100
EMPLOYEE_COUNT = 5
CLIENTS_PER_EMPLOYEE = 5
MIN_CLIENT_ACCOUNTS = 3
MAX_CLIENT_ACCOUNTS = 6
MIN_CLIENT_TICKETS = 1
MAX_CLIENT_TICKETS = 4
MIN_TICKET_MESSAGES = 3
MAX_TICKET_MESSAGES = 8

EMPLOYEE_NAME_PAIRS: tuple[tuple[str, str], ...] = (
    ("Alexey", "Voronov"),
    ("Marina", "Sokolova"),
    ("Dmitry", "Kozlov"),
    ("Olga", "Belova"),
    ("Pavel", "Kirillov"),
    ("Nikita", "Egorov"),
    ("Elena", "Smirnova"),
    ("Roman", "Karpov"),
)

CLIENT_NAME_PAIRS: tuple[tuple[str, str], ...] = (
    ("Ivan", "Pavlov"),
    ("Anna", "Semenova"),
    ("Maksim", "Lebedev"),
    ("Polina", "Morozova"),
    ("Artem", "Volkov"),
    ("Vera", "Kuznetsova"),
    ("Denis", "Belkin"),
    ("Svetlana", "Mironova"),
    ("Gleb", "Tarasov"),
    ("Irina", "Frolova"),
    ("Kirill", "Antonov"),
    ("Nina", "Tikhonova"),
)

TICKET_SUBJECTS: tuple[str, ...] = (
    "Card payment verification",
    "International transfer clarification",
    "Account statement mismatch",
    "Beneficiary details check",
    "Mobile app sign-in issue",
    "Card limits review request",
    "Transfer fee explanation",
    "Recurring transfer setup",
    "Transaction hold question",
    "Service package inquiry",
)

CLIENT_MESSAGES: tuple[str, ...] = (
    "Hello, I need help with this request.",
    "Please check the operation details in my profile.",
    "I can share additional details if needed.",
    "Could you confirm the current processing status?",
    "I tried again and still see the same issue.",
    "Thanks, waiting for your update.",
)

EMPLOYEE_MESSAGES: tuple[str, ...] = (
    "Received, I am checking your request now.",
    "Please confirm the last operation date and amount.",
    "I have escalated this to the processing queue.",
    "Update: verification in progress, no action needed from your side.",
    "The issue has been fixed, please validate on your side.",
    "Request closed. Reopen if you still face the issue.",
)


@dataclass(slots=True)
class GenerationEvent:
    topic: str
    event_type: str
    payload: dict[str, Any]
    scope_student_ids: list[str] = field(default_factory=list)
    entity_type: str | None = None
    entity_id: str | None = None


@dataclass(slots=True)
class StudentEntitiesGenerationResult:
    run_id: str
    cleaned_employees: int = 0
    cleaned_clients: int = 0
    cleaned_accounts: int = 0
    cleaned_tickets: int = 0
    cleaned_messages: int = 0
    cleaned_users: int = 0
    cleaned_identities: int = 0
    cleaned_identity_accesses: int = 0
    created_employees: int = 0
    created_clients: int = 0
    created_accounts: int = 0
    created_tickets: int = 0
    created_messages: int = 0
    employee_ids: list[str] = field(default_factory=list)
    client_ids: list[str] = field(default_factory=list)
    events: list[GenerationEvent] = field(default_factory=list)


class _StudentPublicIdAllocator:
    def __init__(self, current_seq: int):
        self._current_seq = current_seq

    @classmethod
    async def create(cls, db: AsyncSession) -> "_StudentPublicIdAllocator":
        rows = (
            await db.execute(
                select(StudentUser.public_id).where(
                    StudentUser.system_role == SystemRole.STUDENT,
                    StudentUser.public_id.is_not(None),
                )
            )
        ).scalars().all()
        max_seq = STUDENT_PUBLIC_ID_START - 1
        for raw in rows:
            seq = _parse_student_public_sequence(raw)
            if seq is not None:
                max_seq = max(max_seq, seq)
        return cls(max_seq)

    def next(self) -> str:
        self._current_seq += 1
        if self._current_seq <= 9999:
            return f"{STUDENT_PUBLIC_ID_PREFIX}{self._current_seq:04d}"
        return f"{STUDENT_PUBLIC_ID_PREFIX}{self._current_seq}"


def _parse_student_public_sequence(value: str | None) -> int | None:
    if not value or not value.startswith(STUDENT_PUBLIC_ID_PREFIX):
        return None
    suffix = value[len(STUDENT_PUBLIC_ID_PREFIX) :]
    if not suffix.isdigit():
        return None
    return int(suffix)


def _build_password(rng: random.Random, length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        value = "".join(rng.choice(alphabet) for _ in range(length))
        if any(ch.islower() for ch in value) and any(ch.isupper() for ch in value) and any(ch.isdigit() for ch in value):
            return value


def _fake_account_number(run_id: str, counter: int) -> str:
    return f"40702{run_id[:8]}{counter:07d}"[:20]


def _fake_external_client_code(run_id: str, counter: int) -> str:
    return f"CL{run_id[:6].upper()}{counter:04d}"[:32]


def _client_scope_ids(actor_id: uuid.UUID, employee_id: uuid.UUID, client_user_id: uuid.UUID) -> list[str]:
    return sorted({str(actor_id), str(employee_id), str(client_user_id)})


async def _cleanup_identities(db: AsyncSession, user_ids: set[uuid.UUID]) -> tuple[int, int]:
    if not user_ids:
        return 0, 0
    identities = (
        await db.execute(select(StudentIdentity).where(StudentIdentity.user_id.in_(user_ids)))
    ).scalars().all()
    if not identities:
        return 0, 0
    identity_ids = [identity.id for identity in identities]
    accesses = (
        await db.execute(select(StudentIdentityAccess.id).where(StudentIdentityAccess.identity_id.in_(identity_ids)))
    ).scalars().all()
    if accesses:
        await db.execute(delete(StudentIdentityAccess).where(StudentIdentityAccess.id.in_(accesses)))
    await db.execute(delete(StudentIdentity).where(StudentIdentity.id.in_(identity_ids)))
    return len(identities), len(accesses)


async def _cleanup_student_scope(
    db: AsyncSession,
    actor: StudentUser,
    result: StudentEntitiesGenerationResult,
) -> None:
    employees = (
        await db.execute(
            select(StudentUser).where(
                StudentUser.system_role == SystemRole.STUDENT,
                StudentUser.created_by_admin_id == actor.id,
                StudentUser.id != actor.id,
            )
        )
    ).scalars().all()
    employee_ids = [employee.id for employee in employees]
    result.cleaned_employees = len(employee_ids)

    clients: list[Client] = []
    if employee_ids:
        clients = (
            await db.execute(select(Client).where(Client.created_by_employee_id.in_(employee_ids)))
        ).scalars().all()
    fallback_clients = (
        await db.execute(
            select(Client)
            .join(StudentUser, StudentUser.id == Client.student_user_id)
            .where(
                StudentUser.system_role == SystemRole.STUDENT,
                StudentUser.created_by_admin_id == actor.id,
                StudentUser.id != actor.id,
            )
        )
    ).scalars().all()
    by_id = {client.id: client for client in clients}
    for client in fallback_clients:
        by_id.setdefault(client.id, client)
    clients = list(by_id.values())

    result.cleaned_clients = len(clients)
    removable_user_ids: set[uuid.UUID] = set(employee_ids)

    for client in clients:
        removable_user_ids.add(client.student_user_id)
        account_ids = (
            await db.execute(select(Account.id).where(Account.client_id == client.id))
        ).scalars().all()
        result.cleaned_accounts += len(account_ids)
        if account_ids:
            await db.execute(
                delete(Transfer).where(
                    or_(
                        Transfer.source_account_id.in_(account_ids),
                        Transfer.target_account_id.in_(account_ids),
                    )
                )
            )
            await db.execute(delete(Card).where(Card.account_id.in_(account_ids)))
            await db.execute(delete(Account).where(Account.id.in_(account_ids)))

        ticket_ids = (
            await db.execute(select(SupportTicket.id).where(SupportTicket.client_id == client.id))
        ).scalars().all()
        result.cleaned_tickets += len(ticket_ids)
        if ticket_ids:
            message_ids = (
                await db.execute(
                    select(SupportTicketMessage.id).where(SupportTicketMessage.ticket_id.in_(ticket_ids))
                )
            ).scalars().all()
            result.cleaned_messages += len(message_ids)
            if message_ids:
                await db.execute(delete(SupportTicketMessage).where(SupportTicketMessage.id.in_(message_ids)))
            await db.execute(delete(SupportTicket).where(SupportTicket.id.in_(ticket_ids)))
        await db.execute(delete(Client).where(Client.id == client.id))

    removable_user_ids.discard(actor.id)
    identities_count, accesses_count = await _cleanup_identities(db, removable_user_ids)
    result.cleaned_identities = identities_count
    result.cleaned_identity_accesses = accesses_count

    if removable_user_ids:
        delete_result = await db.execute(delete(StudentUser).where(StudentUser.id.in_(removable_user_ids)))
        result.cleaned_users = int(delete_result.rowcount or 0)


async def _load_bank_or_fail(db: AsyncSession) -> Bank:
    bank = (await db.execute(select(Bank).limit(1))).scalar_one_or_none()
    if not bank:
        raise DomainError(503, "BANK_NOT_CONFIGURED", "Bank seed is missing")
    return bank


async def generate_student_entities(
    db: AsyncSession,
    actor: StudentUser,
    *,
    confirm_cleanup: bool,
) -> StudentEntitiesGenerationResult:
    if actor.system_role != SystemRole.STUDENT:
        raise DomainError(403, "FORBIDDEN", "Student access required")
    if not confirm_cleanup:
        raise DomainError(400, "CONFIRMATION_REQUIRED", "Cleanup confirmation is required")

    run_id = uuid.uuid4().hex[:12]
    rng = random.Random(run_id)
    result = StudentEntitiesGenerationResult(run_id=run_id)
    await _cleanup_student_scope(db, actor, result)

    bank = await _load_bank_or_fail(db)
    id_allocator = await _StudentPublicIdAllocator.create(db)
    employee_status_cycle = ("ACTIVE", "BLOCKED", "INACTIVE")
    client_statuses = list(ClientStatus)
    account_statuses = list(AccountStatus)
    ticket_statuses = list(TicketStatus)
    account_types = list(AccountType)
    currencies = list(Currency)
    risk_levels = list(RiskLevel)
    priorities = list(TicketPriority)
    categories = list(TicketCategory)

    account_counter = 0
    client_counter = 0
    now = datetime.now(UTC)

    for employee_index in range(EMPLOYEE_COUNT):
        first_name, last_name = EMPLOYEE_NAME_PAIRS[employee_index % len(EMPLOYEE_NAME_PAIRS)]
        email = f"stgen.{run_id}.emp{employee_index + 1}@demobank.local"
        employee_id = uuid.uuid4()
        employee_status = employee_status_cycle[employee_index % len(employee_status_cycle)]
        employee_created_at = now - timedelta(days=28 - employee_index * 3, hours=rng.randint(0, 20))
        employee = StudentUser(
            id=employee_id,
            public_id=id_allocator.next(),
            email=email,
            username=email,
            hashed_password=hash_password(_build_password(rng)),
            first_name=first_name,
            last_name=last_name,
            system_role=SystemRole.STUDENT,
            is_active=employee_status == "ACTIVE",
            is_blocked=employee_status == "BLOCKED",
            blocked_reason="Generated demo block" if employee_status == "BLOCKED" else None,
            created_by_admin_id=actor.id,
            is_primary_admin=False,
            can_create_admins=False,
            created_at=employee_created_at,
            updated_at=employee_created_at,
            last_login_at=employee_created_at + timedelta(hours=rng.randint(1, 48)),
        )
        db.add(employee)
        await db.flush()
        await ensure_student_identity(
            db,
            employee,
            requested_by_admin_id=actor.id,
            default_status=IdentityStatus.PENDING,
        )
        result.created_employees += 1
        result.employee_ids.append(str(employee_id))
        result.events.append(
            GenerationEvent(
                topic="auth-events",
                event_type="employee.generated.by_student",
                payload={"employee_id": str(employee_id), "student_owner_id": str(actor.id), "run_id": run_id},
                entity_type="employee",
                entity_id=str(employee_id),
            )
        )

        for _ in range(CLIENTS_PER_EMPLOYEE):
            client_counter += 1
            client_user_id = uuid.uuid4()
            client_id = uuid.uuid4()
            c_first_name, c_last_name = CLIENT_NAME_PAIRS[(client_counter - 1) % len(CLIENT_NAME_PAIRS)]
            client_email = f"stgen.{run_id}.cli{client_counter}@demobank.local"
            client_created_at = employee_created_at + timedelta(hours=rng.randint(2, 120))
            client_user = StudentUser(
                id=client_user_id,
                public_id=id_allocator.next(),
                email=client_email,
                username=client_email,
                hashed_password=hash_password(_build_password(rng)),
                first_name=c_first_name,
                last_name=c_last_name,
                system_role=SystemRole.STUDENT,
                is_active=True,
                is_blocked=False,
                created_by_admin_id=actor.id,
                is_primary_admin=False,
                can_create_admins=False,
                created_at=client_created_at,
                updated_at=client_created_at,
                last_login_at=client_created_at + timedelta(hours=rng.randint(1, 24)),
            )
            db.add(client_user)
            await db.flush()
            await ensure_student_identity(
                db,
                client_user,
                requested_by_admin_id=actor.id,
                default_status=IdentityStatus.PENDING,
            )
            client = Client(
                id=client_id,
                student_user_id=client_user_id,
                created_by_employee_id=employee_id,
                bank_id=bank.id,
                external_client_code=_fake_external_client_code(run_id, client_counter),
                first_name=c_first_name,
                last_name=c_last_name,
                middle_name=None,
                birth_date=date(1988 + (client_counter % 12), (client_counter % 12) + 1, (client_counter % 27) + 1),
                phone=f"+7999{rng.randint(1000000, 9999999)}",
                email=client_email,
                passport_series=str(rng.randint(1000, 9999)),
                passport_number=str(rng.randint(100000, 999999)),
                passport_issued_by="Demo migration office",
                passport_issued_date=date(2014 + (client_counter % 8), (client_counter % 12) + 1, (client_counter % 27) + 1),
                residency_country="RU",
                status=client_statuses[(client_counter - 1) % len(client_statuses)],
                risk_level=risk_levels[client_counter % len(risk_levels)],
                is_pep_flag=False,
                created_at=client_created_at,
                updated_at=client_created_at,
            )
            db.add(client)
            await db.flush()
            result.created_clients += 1
            result.client_ids.append(str(client_id))
            client_scope_ids = _client_scope_ids(actor.id, employee_id, client_user_id)
            result.events.append(
                GenerationEvent(
                    topic="client-events",
                    event_type="client.created.by_student",
                    payload={
                        "id": str(client_id),
                        "employee_id": str(employee_id),
                        "student_owner_id": str(actor.id),
                        "run_id": run_id,
                    },
                    scope_student_ids=client_scope_ids,
                    entity_type="client",
                    entity_id=str(client_id),
                )
            )

            account_count = rng.randint(MIN_CLIENT_ACCOUNTS, MAX_CLIENT_ACCOUNTS)
            for _ in range(account_count):
                account_counter += 1
                account_id = uuid.uuid4()
                status = account_statuses[account_counter % len(account_statuses)]
                account_created_at = client_created_at + timedelta(hours=rng.randint(1, 90))
                balance_value = Decimal(str(rng.randint(0, 250000)))
                account = Account(
                    id=account_id,
                    bank_id=bank.id,
                    client_id=client_id,
                    account_number=_fake_account_number(run_id, account_counter),
                    currency=currencies[account_counter % len(currencies)],
                    type=account_types[account_counter % len(account_types)],
                    status=status,
                    balance=balance_value,
                    available_balance=balance_value,
                    hold_amount=Decimal("0"),
                    overdraft_limit=Decimal("0"),
                    opened_at=account_created_at,
                    closed_at=account_created_at + timedelta(days=2) if status == AccountStatus.CLOSED else None,
                    blocked_reason="Generated restriction" if status == AccountStatus.BLOCKED else None,
                    created_at=account_created_at,
                    updated_at=account_created_at,
                )
                db.add(account)
                result.created_accounts += 1
                result.events.append(
                    GenerationEvent(
                        topic="account-events",
                        event_type="account.opened.by_student",
                        payload={
                            "id": str(account_id),
                            "client_id": str(client_id),
                            "student_owner_id": str(actor.id),
                            "run_id": run_id,
                        },
                        scope_student_ids=client_scope_ids,
                        entity_type="account",
                        entity_id=str(account_id),
                    )
                )

            ticket_count = rng.randint(MIN_CLIENT_TICKETS, MAX_CLIENT_TICKETS)
            for ticket_index in range(ticket_count):
                ticket_id = uuid.uuid4()
                ticket_status = ticket_statuses[(client_counter + ticket_index) % len(ticket_statuses)]
                ticket_created_at = client_created_at + timedelta(days=rng.randint(1, 20), minutes=rng.randint(0, 500))
                ticket = SupportTicket(
                    id=ticket_id,
                    client_id=client_id,
                    employee_id_nullable=employee_id,
                    subject=TICKET_SUBJECTS[(client_counter + ticket_index) % len(TICKET_SUBJECTS)],
                    description="Generated support request for training workflow.",
                    priority=priorities[(client_counter + ticket_index) % len(priorities)],
                    category=categories[(client_counter + ticket_index) % len(categories)],
                    status=ticket_status,
                    resolution=(
                        "Generated auto-resolution note."
                        if ticket_status in {TicketStatus.RESOLVED, TicketStatus.REJECTED, TicketStatus.CLOSED}
                        else None
                    ),
                    closed_at=(
                        ticket_created_at + timedelta(hours=rng.randint(2, 24))
                        if ticket_status in {TicketStatus.RESOLVED, TicketStatus.REJECTED, TicketStatus.CLOSED}
                        else None
                    ),
                    created_at=ticket_created_at,
                    updated_at=ticket_created_at,
                )
                db.add(ticket)
                await db.flush()
                result.created_tickets += 1
                result.events.append(
                    GenerationEvent(
                        topic="support-events",
                        event_type="ticket.created.by_student",
                        payload={
                            "ticket_id": str(ticket_id),
                            "client_id": str(client_id),
                            "student_owner_id": str(actor.id),
                            "run_id": run_id,
                        },
                        scope_student_ids=client_scope_ids,
                        entity_type="ticket",
                        entity_id=str(ticket_id),
                    )
                )

                message_count = rng.randint(MIN_TICKET_MESSAGES, MAX_TICKET_MESSAGES)
                started_by_client = bool((client_counter + ticket_index) % 2)
                for message_index in range(message_count):
                    from_client = (message_index % 2 == 0) == started_by_client
                    author_type = "CLIENT" if from_client else "EMPLOYEE"
                    message_text = (
                        CLIENT_MESSAGES[(client_counter + message_index) % len(CLIENT_MESSAGES)]
                        if from_client
                        else EMPLOYEE_MESSAGES[(client_counter + message_index) % len(EMPLOYEE_MESSAGES)]
                    )
                    message_id = uuid.uuid4()
                    message_created_at = ticket_created_at + timedelta(minutes=message_index * rng.randint(2, 12) + 1)
                    message = SupportTicketMessage(
                        id=message_id,
                        ticket_id=ticket_id,
                        author_type=author_type,
                        author_id=client_user_id if from_client else employee_id,
                        message=message_text,
                        created_at=message_created_at,
                    )
                    db.add(message)
                    result.created_messages += 1
                    result.events.append(
                        GenerationEvent(
                            topic="support-events",
                            event_type="ticket.message.created.by_student",
                            payload={
                                "ticket_id": str(ticket_id),
                                "message_id": str(message_id),
                                "author_type": author_type,
                                "student_owner_id": str(actor.id),
                                "run_id": run_id,
                            },
                            scope_student_ids=client_scope_ids,
                            entity_type="ticket",
                            entity_id=str(ticket_id),
                        )
                    )

    return result
