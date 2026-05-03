from __future__ import annotations

import asyncio
import json
import os
import secrets
import string
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

import httpx
from fastapi import Cookie, Depends, FastAPI, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from redis.asyncio import Redis
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.bootstrap import ensure_minimal_student_bootstrap
from common.db import SessionLocal, engine, get_db
from common.deps import get_current_claims, require_business_role, require_system_role
from common.auth import create_docs_token, decode_token
from common.enums import (
    AccountStatus,
    AccountType,
    CardNetwork,
    CardStatus,
    CardType,
    ClientStatus,
    Currency,
    IdentityAccessStatus,
    IdentityStatus,
    RiskLevel,
    SystemRole,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    TransferStatus,
    TransferType,
)
from common.errors import DomainError, domain_error_handler
from common.iam import IAM_SERVICES, ensure_student_identity, sanitize_identity_slug, service_principal
from common.kafka import produce_event
from common.models import (
    Account,
    AuditLog,
    Bank,
    Card,
    Client,
    CurrencyExchangeRate,
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
from common.observability import setup_app
from common.state_machines import ACCOUNT_TRANSITIONS, CLIENT_TRANSITIONS, TICKET_TRANSITIONS, TRANSFER_TRANSITIONS
from app.student_entities_generator import generate_student_entities

SWAGGER_TOP_DESCRIPTION = """
Developed by Daniil Nikolaev

Cloud version of the platform for QA, backend, and DevOps practice with all 10+ tools - [bank.easyitlab.tech](https://bank.easyitlab.tech)

Contact via email [easyitwithdaniil@gmail.com](mailto:easyitwithdaniil@gmail.com) or Telegram [@danilfg](https://t.me/danilfg)

Join the community: [chat.easyitlab.tech](https://chat.easyitlab.tech)

## Base Path

`http://127.0.0.1:8080`

## How To Get Access Token

1. Request token via login:

```bash
curl -sS -X POST "http://127.0.0.1:8080/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"student@easyitlab.tech","password":"student123"}'
```

2. Copy `access_token` from response.
""".strip()

app = FastAPI(title="EasyBank Bank API", version="1.0.0", description=SWAGGER_TOP_DESCRIPTION)
app.add_exception_handler(DomainError, domain_error_handler)
setup_app(app, "bank-api", engine)

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
IAM_TOPIC = os.getenv("IAM_EVENTS_TOPIC", "iam-events")
IAM_PROVISIONING_WAIT_SECONDS = float(os.getenv("IAM_PROVISIONING_WAIT_SECONDS", "8"))
STUDENT_OBSERVABLE_EVENT_PREFIXES = ("client.", "account.", "transfer.", "ticket.", "card.", "jenkins.")
STUDENT_PUBLIC_ID_PREFIX = "st-"
STUDENT_PUBLIC_ID_START = 100
DEFAULT_RUB_EXCHANGE_RATES: dict[Currency, Decimal] = {
    Currency.USD: Decimal("100"),
    Currency.EUR: Decimal("120"),
}
SUPPORTED_RATE_QUOTES = tuple(DEFAULT_RUB_EXCHANGE_RATES.keys())
STUDENT_TOOL_SERVICES = ("JENKINS", "ALLURE", "POSTGRES", "REST_API", "REDIS", "KAFKA")
STUDENT_DOCS_ALLOWED_PREFIXES = (
    "/students/dashboard",
    "/students/entities",
    "/students/employees",
    "/students/clients",
    "/students/accounts",
    "/employees/",
    "/clients/",
)


class ClientCreate(BaseModel):
    student_user_id: str
    bank_id: str
    first_name: str
    last_name: str
    middle_name: str | None = None
    birth_date: date
    phone: str
    email: str
    passport_series: str
    passport_number: str
    passport_issued_by: str
    passport_issued_date: date
    residency_country: str = "RU"
    risk_level: RiskLevel = RiskLevel.LOW


class AccountCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "currency": "RUB",
                "type": "CURRENT",
            }
        }
    )

    currency: Currency = Currency.RUB
    type: AccountType = AccountType.CURRENT


class CardCreate(BaseModel):
    account_id: str
    network: CardNetwork = CardNetwork.MIR
    type: CardType = CardType.DEBIT


class TransferCreate(BaseModel):
    source_account_id: str = Field(description="Account UUID or account number")
    target_account_id: str = Field(description="Account UUID or account number")
    amount: Decimal = Field(gt=0)
    currency: Currency | None = None
    description: str | None = None
    idempotency_key: str | None = None


class TransferTopUp(BaseModel):
    account_id: str = Field(description="Account UUID or account number")
    amount: Decimal = Field(gt=0)
    idempotency_key: str | None = None


class ExchangeRateUpdate(BaseModel):
    rub_amount: Decimal = Field(gt=0, description="How many RUB equal one unit of target currency")


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory = TicketCategory.OTHER

    @model_validator(mode="after")
    def ensure_non_blank_text(self):
        self.subject = self.subject.strip()
        self.description = self.description.strip()
        if not self.subject:
            raise ValueError("subject is required")
        if not self.description:
            raise ValueError("description is required")
        return self


class TicketMessageCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Verification completed. You can contact the client and close the ticket."
            }
        }
    )

    message: str | None = Field(default=None, validation_alias=AliasChoices("message", "body"))

    @model_validator(mode="after")
    def ensure_message(self):
        if not self.message or not self.message.strip():
            raise ValueError("message is required")
        self.message = self.message.strip()
        return self


class StatusUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "IN_PROGRESS",
            }
        }
    )

    status: TicketStatus


class StudentEntitiesGenerateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confirm_cleanup": True,
            }
        }
    )

    confirm_cleanup: bool


class StudentEntitiesGenerateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": "demo-seed-42",
                "cleaned_employees": 2,
                "cleaned_clients": 4,
                "cleaned_accounts": 6,
                "cleaned_tickets": 3,
                "cleaned_messages": 7,
                "cleaned_users": 6,
                "cleaned_identities": 6,
                "cleaned_identity_accesses": 12,
                "created_employees": 2,
                "created_clients": 4,
                "created_accounts": 6,
                "created_tickets": 3,
                "created_messages": 7,
                "employee_ids": ["st-0101", "st-0102"],
                "client_ids": ["1b6d2f36-1d7f-4fd6-8d8c-11f1db7f2abc"],
            }
        }
    )

    run_id: str
    cleaned_employees: int
    cleaned_clients: int
    cleaned_accounts: int
    cleaned_tickets: int
    cleaned_messages: int
    cleaned_users: int
    cleaned_identities: int
    cleaned_identity_accesses: int
    created_employees: int
    created_clients: int
    created_accounts: int
    created_tickets: int
    created_messages: int
    employee_ids: list[str]
    client_ids: list[str]


class EmployeeClientQuickCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_username": "client-owner@demobank.local",
                "first_name": "Daniil",
                "last_name": "Nikolaev",
                "phone": "+79990001122",
                "email": "client-owner@demobank.local",
            }
        }
    )

    student_username: str
    first_name: str
    last_name: str
    phone: str
    email: str


class StudentEmployeeCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "employee.demo@demobank.local",
                "full_name": "Daniil Nikolaev",
                "password": "employee123",
            }
        }
    )

    email: str
    full_name: str
    password: str | None = None

    @model_validator(mode="after")
    def normalize(self):
        self.email = self.email.strip().lower()
        self.full_name = self.full_name.strip()
        self.password = self.password.strip() if self.password else None
        if "@" not in self.email:
            raise ValueError("email must contain '@'")
        if not self.full_name:
            raise ValueError("full_name is required")
        if self.password and len(self.password) < 8:
            raise ValueError("password must be at least 8 characters long")
        return self


class StudentEmployeeUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "employee.demo@demobank.local",
                "full_name": "Daniil Nikolaev",
            }
        }
    )

    email: str
    full_name: str

    @model_validator(mode="after")
    def normalize(self):
        self.email = self.email.strip().lower()
        self.full_name = self.full_name.strip()
        if "@" not in self.email:
            raise ValueError("email must contain '@'")
        if not self.full_name:
            raise ValueError("full_name is required")
        return self


class StudentEventResponse(BaseModel):
    id: str
    student_user_id: str
    topic: str
    event_type: str
    ws_event: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict
    occurred_at: datetime


class StudentToolResponse(BaseModel):
    service_name: str
    title: str
    url: str | None = None
    hint: str
    principal: str
    status: str


class JenkinsRunResponse(BaseModel):
    build_number: int
    status: str
    mode: str
    started_at: str
    finished_at: str
    job_url: str | None = None
    console_url: str | None = None
    allure_url: str | None = None
    log_excerpt: str
    checks_passed: int
    checks_total: int


class JenkinsRunsPayload(BaseModel):
    service_name: str
    folder_path: str
    job_name: str
    runs: list[JenkinsRunResponse]


class AllureOpenUrlResponse(BaseModel):
    url: str
    mode: str


class StudentDashboardPoint(BaseModel):
    day: str
    employees: int
    clients: int
    accounts: int
    tickets: int


class StudentDashboardResponse(BaseModel):
    employees_total: int
    employees_active: int
    employees_blocked: int
    clients_total: int
    accounts_total: int
    tickets_total: int
    transfers_total: int
    series: list[StudentDashboardPoint]


class StudentIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    identity: dict
    accesses: list[dict]


class StudentEmployeeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    uuid: str
    email: str
    username: str
    full_name: str
    status: str
    clients_count: int = 0
    tickets_count: int = 0


class StudentClientResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    status: ClientStatus


class StudentAccountResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID
    account_number: str
    currency: Currency
    type: AccountType
    status: AccountStatus


def to_dict(model) -> dict:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def build_full_name(first_name: str | None, last_name: str | None) -> str:
    parts = [part for part in [(first_name or "").strip(), (last_name or "").strip()] if part]
    return " ".join(parts).strip()


def split_full_name(full_name: str | None, *, fallback_email: str) -> tuple[str, str]:
    clean = (full_name or "").strip()
    if clean:
        chunks = [chunk for chunk in clean.split(" ") if chunk]
        if len(chunks) >= 2:
            return chunks[0], " ".join(chunks[1:])
        return chunks[0], "User"
    local = fallback_email.split("@", 1)[0].strip() or "Student"
    return local, "User"


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(ch.islower() for ch in value) and any(ch.isupper() for ch in value) and any(ch.isdigit() for ch in value):
            return value


def format_student_public_id(seq: int) -> str:
    if seq <= 9999:
        return f"{STUDENT_PUBLIC_ID_PREFIX}{seq:04d}"
    return f"{STUDENT_PUBLIC_ID_PREFIX}{seq}"


def parse_student_public_sequence(value: str | None) -> int | None:
    if not value:
        return None
    if not value.startswith(STUDENT_PUBLIC_ID_PREFIX):
        return None
    suffix = value[len(STUDENT_PUBLIC_ID_PREFIX) :]
    if not suffix.isdigit():
        return None
    return int(suffix)


def student_payload(student: StudentUser) -> dict:
    data = to_dict(student)
    data.pop("hashed_password", None)
    data["uuid"] = str(student.id)
    data["id"] = student.public_id or str(student.id)
    data["full_name"] = build_full_name(student.first_name, student.last_name)
    if "created_by_admin_id" in data:
        data["created_by_admin_id"] = str(student.created_by_admin_id) if student.created_by_admin_id else None
    return data


def student_event_to_dict(event: StudentObservableEvent) -> dict:
    return {
        "id": str(event.id),
        "student_user_id": str(event.student_user_id),
        "topic": event.topic,
        "event_type": event.event_type,
        "ws_event": event.ws_event,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "payload": event.payload_json,
        "occurred_at": event.occurred_at,
    }


def ensure_transition(current, target, transitions, entity: str):
    if target not in transitions.get(current, set()):
        raise DomainError(400, "INVALID_STATUS_TRANSITION", f"{entity} transition is not allowed", {"from": current, "to": target})


def fake_account_number() -> str:
    return "40702" + uuid.uuid4().hex[:15]


def fake_external_code() -> str:
    return "CL" + uuid.uuid4().hex[:8].upper()


def assert_client_can_operate(client: Client):
    if client.status == ClientStatus.BLOCKED:
        raise DomainError(409, "CLIENT_BLOCKED", "Client is blocked")


def assert_account_outgoing_allowed(account: Account):
    if account.status == AccountStatus.BLOCKED:
        raise DomainError(409, "ACCOUNT_BLOCKED", "Account is blocked")
    if account.status == AccountStatus.PARTIALLY_RESTRICTED:
        raise DomainError(409, "ACCOUNT_PARTIALLY_RESTRICTED", "Outgoing operations are restricted")


def assert_account_incoming_allowed(account: Account):
    if account.status == AccountStatus.BLOCKED:
        raise DomainError(409, "ACCOUNT_BLOCKED", "Account is blocked")
    if account.status == AccountStatus.CLOSED:
        raise DomainError(409, "ACCOUNT_CLOSED", "Account is closed")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def list_exchange_rates(db: AsyncSession) -> list[CurrencyExchangeRate]:
    return (
        await db.execute(
            select(CurrencyExchangeRate).order_by(CurrencyExchangeRate.quote_currency.asc())
        )
    ).scalars().all()


async def get_exchange_rate_or_404(db: AsyncSession, quote_currency: Currency) -> CurrencyExchangeRate:
    if quote_currency not in SUPPORTED_RATE_QUOTES:
        raise DomainError(400, "UNSUPPORTED_CURRENCY_PAIR", "Only RUB-based rates are configurable")
    row = (
        await db.execute(
            select(CurrencyExchangeRate).where(CurrencyExchangeRate.quote_currency == quote_currency)
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = CurrencyExchangeRate(quote_currency=quote_currency, rub_amount=DEFAULT_RUB_EXCHANGE_RATES[quote_currency])
    db.add(row)
    await db.flush()
    return row


def exchange_rate_payload(row: CurrencyExchangeRate) -> dict:
    rub_amount = Decimal(row.rub_amount)
    return {
        "base_currency": "RUB",
        "quote_currency": row.quote_currency.value,
        "rub_amount": float(rub_amount),
        "direct_rate": float(quantize_rate(Decimal("1") / rub_amount)),
        "inverse_rate": float(quantize_rate(rub_amount)),
        "set_by_user_id": str(row.set_by_user_id) if row.set_by_user_id else None,
        "updated_at": row.updated_at,
        "created_at": row.created_at,
    }


async def resolve_conversion_rate(db: AsyncSession, source_currency: Currency, target_currency: Currency) -> Decimal:
    if source_currency == target_currency:
        return Decimal("1")

    usd_rate = Decimal((await get_exchange_rate_or_404(db, Currency.USD)).rub_amount)
    eur_rate = Decimal((await get_exchange_rate_or_404(db, Currency.EUR)).rub_amount)
    rub_rates = {
        Currency.USD: usd_rate,
        Currency.EUR: eur_rate,
    }

    if source_currency == Currency.RUB and target_currency in rub_rates:
        return Decimal("1") / rub_rates[target_currency]
    if target_currency == Currency.RUB and source_currency in rub_rates:
        return rub_rates[source_currency]
    if source_currency in rub_rates and target_currency in rub_rates:
        return rub_rates[source_currency] / rub_rates[target_currency]

    raise DomainError(400, "UNSUPPORTED_CURRENCY_PAIR", "Transfer conversion is not configured for this pair")


async def compute_transfer_amounts(
    db: AsyncSession,
    *,
    source_currency: Currency,
    target_currency: Currency,
    source_amount: Decimal,
) -> tuple[Decimal, Decimal]:
    rate = await resolve_conversion_rate(db, source_currency, target_currency)
    target_amount = quantize_money(source_amount * rate)
    if target_amount <= 0:
        raise DomainError(409, "AMOUNT_TOO_SMALL", "Amount is too small for the selected currency pair")
    return target_amount, quantize_rate(rate)


def transfer_target_amount(transfer: Transfer) -> Decimal:
    return quantize_money(Decimal(transfer.amount) * Decimal(transfer.exchange_rate))


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}


def is_student_observable_event_type(event_type: str) -> bool:
    return event_type.startswith(STUDENT_OBSERVABLE_EVENT_PREFIXES)


def normalize_scope_student_ids(scope_student_ids: list[str] | set[str] | None) -> list[str]:
    if not scope_student_ids:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in scope_student_ids:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return sorted(result)


def client_scope_student_ids(client: Client | None) -> list[str]:
    if not client:
        return []
    scope: set[str] = {str(client.student_user_id)}
    if client.created_by_employee_id:
        scope.add(str(client.created_by_employee_id))
    return sorted(scope)


def client_scope_student_ids_for_actor(client: Client | None, actor_id: uuid.UUID | str | None) -> list[str]:
    scope = set(client_scope_student_ids(client))
    if actor_id:
        scope.add(str(actor_id))
    return sorted(scope)


async def load_account_scope_student_ids(db: AsyncSession, account: Account | None) -> list[str]:
    if not account:
        return []
    client = await db.get(Client, account.client_id)
    return client_scope_student_ids(client)


async def load_transfer_scope_student_ids(db: AsyncSession, source: Account | None, target: Account | None) -> list[str]:
    scope = set(await load_account_scope_student_ids(db, source))
    scope.update(await load_account_scope_student_ids(db, target))
    return sorted(scope)


async def load_ticket_scope_student_ids(db: AsyncSession, ticket: SupportTicket | None) -> list[str]:
    if not ticket:
        return []
    client = await db.get(Client, ticket.client_id)
    return client_scope_student_ids(client)


async def persist_student_observable_event(
    *,
    topic: str,
    event_type: str,
    payload: dict,
    scope_student_ids: list[str],
    ws_event: str | None,
    entity_type: str | None,
    entity_id: str | None,
) -> None:
    if not scope_student_ids:
        return
    occurred_at = datetime.now(UTC)
    async with SessionLocal() as event_db:
        for student_id in scope_student_ids:
            try:
                student_uuid = uuid.UUID(student_id)
            except ValueError:
                continue
            event_db.add(
                StudentObservableEvent(
                    student_user_id=student_uuid,
                    topic=topic,
                    event_type=event_type,
                    ws_event=ws_event,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    payload_json=payload,
                    occurred_at=occurred_at,
                )
            )
        try:
            await event_db.commit()
        except Exception:
            await event_db.rollback()


async def emit(
    topic: str,
    event_type: str,
    payload: dict,
    ws_event: str | None = None,
    *,
    scope_student_ids: list[str] | set[str] | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
):
    encoded_payload = jsonable_encoder(payload)
    scope = normalize_scope_student_ids(scope_student_ids)
    if scope and is_student_observable_event_type(event_type):
        encoded_payload["scope_student_ids"] = scope
    key = str(encoded_payload.get("id", entity_id or event_type))

    try:
        await produce_event(topic, event_type, encoded_payload, key=key)
        await produce_event("audit-events", f"audit.{event_type}", encoded_payload, key=key)
        if scope and is_student_observable_event_type(event_type):
            for student_id in scope:
                scoped_payload = {**encoded_payload, "student_user_id": student_id}
                await produce_event("student-events", event_type, scoped_payload, key=student_id)
    except Exception:
        pass

    if ws_event:
        message = {"event": ws_event, "payload": encoded_payload}
        if scope:
            message["scope_student_ids"] = scope
        await redis.publish("notifications", json.dumps(message, ensure_ascii=False, default=str))

    if scope and is_student_observable_event_type(event_type):
        await persist_student_observable_event(
            topic=topic,
            event_type=event_type,
            payload=encoded_payload,
            scope_student_ids=scope,
            ws_event=ws_event,
            entity_type=entity_type,
            entity_id=entity_id,
        )


async def get_bank(session: AsyncSession) -> Bank:
    bank = (await session.execute(select(Bank).limit(1))).scalar_one_or_none()
    if not bank:
        raise DomainError(503, "BANK_NOT_CONFIGURED", "Bank seed is missing")
    return bank


async def get_my_client_or_404(session: AsyncSession, user_id: str) -> Client:
    client = (await session.execute(select(Client).where(Client.student_user_id == user_id))).scalar_one_or_none()
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client profile not found")
    return client


async def get_account_by_ref(session: AsyncSession, account_ref: str) -> Account | None:
    ref = (account_ref or "").strip()
    if not ref:
        return None
    try:
        return await session.get(Account, uuid.UUID(ref))
    except ValueError:
        return (await session.execute(select(Account).where(Account.account_number == ref))).scalar_one_or_none()


async def upsert_usage(session: AsyncSession, user_id: str, field: str):
    usage = (
        await session.execute(
            select(StudentResourceUsage).where(
                StudentResourceUsage.student_user_id == user_id,
                StudentResourceUsage.day_bucket == date.today(),
            )
        )
    ).scalar_one_or_none()
    if not usage:
        usage = StudentResourceUsage(student_user_id=user_id, day_bucket=date.today())
        session.add(usage)
        await session.flush()
    setattr(usage, field, getattr(usage, field) + 1)
    try:
        await produce_event(
            "usage-events",
            "usage.updated",
            {
                "student_user_id": user_id,
                "day_bucket": usage.day_bucket.isoformat(),
                "field": field,
                "value": getattr(usage, field),
            },
            key=user_id,
        )
    except Exception:
        # Usage metrics should not break business operations.
        pass


async def get_student_actor(db: AsyncSession, claims: dict) -> StudentUser:
    actor = await db.get(StudentUser, uuid.UUID(claims["user_id"]))
    if not actor or actor.system_role != SystemRole.STUDENT:
        raise DomainError(403, "FORBIDDEN", "Student access required")
    if actor.created_by_admin_id:
        creator = await db.get(StudentUser, actor.created_by_admin_id)
        if creator and creator.system_role == SystemRole.STUDENT:
            raise DomainError(403, "STUDENT_OWNER_REQUIRED", "Student owner access required")
    manages_clients = (
        await db.execute(
            select(Client.id).where(Client.created_by_employee_id == actor.id).limit(1)
        )
    ).scalar_one_or_none()
    if manages_clients:
        raise DomainError(403, "STUDENT_OWNER_REQUIRED", "Student owner access required")
    return actor


def user_activity_status(user: StudentUser) -> str:
    if user.is_blocked:
        return "BLOCKED"
    if user.is_active:
        return "ACTIVE"
    return "INACTIVE"


def employee_payload(
    employee: StudentUser,
    *,
    clients_count: int = 0,
    tickets_count: int = 0,
) -> dict:
    data = student_payload(employee)
    data["status"] = user_activity_status(employee)
    data["clients_count"] = clients_count
    data["tickets_count"] = tickets_count
    return data


async def allocate_next_student_public_id(db: AsyncSession) -> str:
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
        seq = parse_student_public_sequence(raw)
        if seq is not None:
            max_seq = max(max_seq, seq)
    return format_student_public_id(max_seq + 1)


async def resolve_student_by_ref(db: AsyncSession, student_ref: str) -> StudentUser | None:
    ref = (student_ref or "").strip()
    if not ref:
        return None
    student = (
        await db.execute(
            select(StudentUser).where(
                StudentUser.public_id == ref,
                StudentUser.system_role == SystemRole.STUDENT,
            )
        )
    ).scalar_one_or_none()
    if student:
        return student
    try:
        ref_uuid = uuid.UUID(ref)
    except ValueError:
        return None
    student = await db.get(StudentUser, ref_uuid)
    if not student or student.system_role != SystemRole.STUDENT:
        return None
    return student


def ensure_student_owns_employee(actor: StudentUser, employee: StudentUser):
    if employee.system_role != SystemRole.STUDENT:
        raise DomainError(404, "EMPLOYEE_NOT_FOUND", "Employee not found")
    if employee.id == actor.id:
        raise DomainError(400, "SELF_OPERATION_FORBIDDEN", "You cannot perform this operation on yourself")
    if employee.created_by_admin_id != actor.id:
        raise DomainError(403, "FORBIDDEN", "Employee is outside student scope")


async def get_student_employee_or_404(db: AsyncSession, actor: StudentUser, employee_id: str) -> StudentUser:
    employee = await resolve_student_by_ref(db, employee_id)
    if not employee:
        raise DomainError(404, "EMPLOYEE_NOT_FOUND", "Employee not found")
    ensure_student_owns_employee(actor, employee)
    # Student users linked to client profiles are not employees in student cabinet.
    linked_client = (
        await db.execute(select(Client.id).where(Client.student_user_id == employee.id))
    ).scalar_one_or_none()
    if linked_client is not None:
        raise DomainError(404, "EMPLOYEE_NOT_FOUND", "Employee not found")
    return employee


async def get_student_employee_ids(db: AsyncSession, actor: StudentUser) -> list[uuid.UUID]:
    rows = (
        await db.execute(
            select(StudentUser.id)
            .outerjoin(Client, Client.student_user_id == StudentUser.id)
            .where(
                StudentUser.system_role == SystemRole.STUDENT,
                StudentUser.created_by_admin_id == actor.id,
                Client.id.is_(None),
            )
        )
    ).scalars().all()
    return list(rows)


async def get_student_scoped_client_or_404(db: AsyncSession, actor: StudentUser, client_id: str) -> tuple[Client, StudentUser]:
    client = await get_client_or_404(db, client_id)
    if client.created_by_employee_id is None:
        raise DomainError(403, "FORBIDDEN", "Client ownership is not assigned")
    employee = await db.get(StudentUser, client.created_by_employee_id)
    if not employee or employee.system_role != SystemRole.STUDENT:
        raise DomainError(404, "EMPLOYEE_NOT_FOUND", "Employee not found")
    ensure_student_owns_employee(actor, employee)
    return client, employee


async def get_student_scoped_employee_ticket_or_404(
    db: AsyncSession,
    actor: StudentUser,
    employee: StudentUser,
    ticket_id: str,
) -> tuple[SupportTicket, Client]:
    ensure_student_owns_employee(actor, employee)
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise DomainError(404, "TICKET_NOT_FOUND", "Ticket not found") from None
    ticket = await db.get(SupportTicket, ticket_uuid)
    if not ticket:
        raise DomainError(404, "TICKET_NOT_FOUND", "Ticket not found")
    client = await db.get(Client, ticket.client_id)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    if client.created_by_employee_id != employee.id:
        raise DomainError(403, "FORBIDDEN", "Ticket is outside employee scope")
    return ticket, client


async def get_student_scoped_account_or_404(
    db: AsyncSession,
    actor: StudentUser,
    account_id: str,
) -> tuple[Account, Client]:
    account = await get_account_or_404(db, account_id)
    client = await db.get(Client, account.client_id)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    if client.created_by_employee_id is None:
        raise DomainError(403, "FORBIDDEN", "Client ownership is not assigned")
    employee = await db.get(StudentUser, client.created_by_employee_id)
    if not employee:
        raise DomainError(404, "EMPLOYEE_NOT_FOUND", "Employee not found")
    ensure_student_owns_employee(actor, employee)
    return account, client


def identity_payload(identity: StudentIdentity, accesses: list[StudentIdentityAccess]) -> dict:
    return {
        "identity": to_dict(identity),
        "accesses": [to_dict(access) for access in sorted(accesses, key=lambda item: item.service_name)],
    }


async def get_identity_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> StudentIdentity | None:
    return (
        await db.execute(select(StudentIdentity).where(StudentIdentity.user_id == user_id))
    ).scalar_one_or_none()


async def get_identity_accesses(db: AsyncSession, identity_id: uuid.UUID) -> list[StudentIdentityAccess]:
    return (
        await db.execute(
            select(StudentIdentityAccess)
            .where(StudentIdentityAccess.identity_id == identity_id)
            .order_by(StudentIdentityAccess.service_name.asc())
            .execution_options(populate_existing=True)
        )
    ).scalars().all()


def student_tool_meta(service_name: str, host: str) -> dict:
    mapping: dict[str, dict[str, str | None]] = {
        "JENKINS": {
            "title": "Jenkins",
            "url": f"http://{host}:8086",
            "hint": "CI/CD and training jobs. Use the same credentials as the student cabinet.",
        },
        "ALLURE": {
            "title": "Allure",
            "url": f"http://{host}:8086",
            "hint": "Allure reports for automated test runs in Jenkins.",
        },
        "POSTGRES": {
            "title": "PostgreSQL",
            "url": None,
            "hint": f"Connection: postgresql://{host}:5432 (login = student email).",
        },
        "REST_API": {
            "title": "REST API / Swagger",
            "url": "/students/docs",
            "hint": "Student Swagger/OpenAPI. Use it for contracts and examples; run real requests via Postman or curl.",
        },
        "REDIS": {
            "title": "Redis",
            "url": None,
            "hint": f"Connection: redis://{host}:6379",
        },
        "KAFKA": {
            "title": "Kafka",
            "url": f"http://{host}:8090/",
            "hint": f"Kafka broker checks via CLI. Bootstrap: {host}:9092 (or kafka:9092 in docker network). AsyncAPI docs: http://{host}:8090/.",
        },
    }
    return mapping.get(service_name, {"title": service_name, "url": None, "hint": "Service is not documented"})


async def ensure_student_tool_access(
    db: AsyncSession,
    actor: StudentUser,
    service_name: str,
) -> StudentIdentityAccess:
    normalized_service = service_name.strip().upper()
    if normalized_service not in IAM_SERVICES:
        raise DomainError(400, "UNKNOWN_SERVICE", f"Unsupported service: {service_name}")
    if normalized_service not in STUDENT_TOOL_SERVICES:
        raise DomainError(403, "FORBIDDEN", "Tool is not available in student cabinet")

    identity = await get_identity_by_user_id(db, actor.id)
    if not identity:
        raise DomainError(403, "FORBIDDEN", "Identity is not provisioned")
    accesses = await get_identity_accesses(db, identity.id)
    by_service = {access.service_name: access for access in accesses}
    access = by_service.get(normalized_service)
    if not access or access.status != IdentityAccessStatus.ACTIVE:
        raise DomainError(403, "FORBIDDEN", f"{normalized_service} access is disabled")
    return access


def jenkins_external_url(host: str) -> str:
    return os.getenv("JENKINS_EXTERNAL_URL", f"http://{host}:8086").rstrip("/")


def jenkins_internal_url() -> str:
    return os.getenv("JENKINS_URL", "http://jenkins:8080").rstrip("/")


def _jenkins_public_to_internal(url: str, host: str) -> str:
    external = jenkins_external_url(host)
    fallback = f"http://{host}:8086"
    internal = jenkins_internal_url()
    if url.startswith(external):
        return f"{internal}{url[len(external):]}"
    if url.startswith(fallback):
        return f"{internal}{url[len(fallback):]}"
    return url


def _jenkins_internal_to_public(url: str, host: str) -> str:
    internal = jenkins_internal_url()
    external = jenkins_external_url(host)
    if url.startswith(internal):
        return f"{external}{url[len(internal):]}"
    return url


def ensure_jenkins_details(access: StudentIdentityAccess, host: str, actor: StudentUser) -> dict:
    details = access.details_json.copy() if isinstance(access.details_json, dict) else {}
    username = (actor.username or actor.email or "student").strip().lower()
    slug = sanitize_identity_slug(username)
    folder_path = str(details.get("folder_path") or f"students/{slug}")
    job_name = str(details.get("job_name") or os.getenv("JENKINS_STARTER_JOB_NAME", "starter-job"))
    job_url = str(details.get("job_url") or f"{jenkins_external_url(host)}/job/students/job/{slug}/job/{job_name}/")
    reports_url = str(details.get("reports_url") or f"{job_url.rstrip('/')}/allure/")
    reports = details.get("allure_reports")
    if not isinstance(reports, list):
        reports = []
    details.update(
        {
            "mode": str(details.get("mode") or "mock"),
            "jenkins_url": str(details.get("jenkins_url") or jenkins_external_url(host)),
            "folder_path": folder_path,
            "job_name": job_name,
            "job_path": str(details.get("job_path") or f"{folder_path}/{job_name}"),
            "job_url": job_url,
            "reports_url": reports_url,
            "allure_reports": reports[-10:],
            "last_build_number": int(details.get("last_build_number") or 0),
            "starter_pipeline": str(details.get("starter_pipeline") or "echo 'Training job started successfully'"),
            "scope_student_id": str(details.get("scope_student_id") or actor.id),
        }
    )
    return details


def build_mock_jenkins_run(build_number: int, details: dict) -> dict:
    started = datetime.now(UTC)
    finished = datetime.now(UTC)
    allure_url = f"{str(details.get('reports_url') or '').rstrip('/')}/{build_number}/"
    return {
        "build_number": build_number,
        "status": "SUCCESS",
        "mode": "mock",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "job_url": details.get("job_url"),
        "console_url": f"{str(details.get('job_url') or '').rstrip('/')}/{build_number}/console",
        "allure_url": allure_url,
        "log_excerpt": "Training job started successfully",
        "checks_passed": 3,
        "checks_total": 3,
    }


async def jenkins_request_crumb(client: httpx.AsyncClient, base_url: str) -> dict[str, str]:
    response = await client.get(f"{base_url}/crumbIssuer/api/json")
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    payload = response.json()
    field = payload.get("crumbRequestField")
    crumb = payload.get("crumb")
    if not field or not crumb:
        return {}
    return {str(field): str(crumb)}


async def run_real_jenkins_build(details: dict, host: str) -> dict | None:
    public_job_url = str(details.get("job_url") or "").strip()
    if not public_job_url:
        return None
    internal_job_url = _jenkins_public_to_internal(public_job_url, host).rstrip("/") + "/"
    base_url = jenkins_internal_url()
    admin_user = os.getenv("JENKINS_ADMIN_USER", "admin")
    admin_password = os.getenv("JENKINS_ADMIN_PASSWORD", "admin")
    started = datetime.now(UTC)
    try:
        async with httpx.AsyncClient(timeout=20, auth=(admin_user, admin_password)) as client:
            headers = await jenkins_request_crumb(client, base_url)
            trigger = await client.post(f"{internal_job_url}build", headers=headers)
            if trigger.status_code not in {200, 201, 202}:
                return None
            build_payload: dict = {}
            for _ in range(30):
                await asyncio.sleep(2)
                current = await client.get(f"{internal_job_url}lastBuild/api/json")
                if current.status_code == 404:
                    continue
                current.raise_for_status()
                build_payload = current.json()
                if not build_payload.get("building"):
                    break
            if not build_payload:
                return None
            build_number = int(build_payload.get("number") or 0)
            result = str(build_payload.get("result") or "UNKNOWN")
            status = "SUCCESS" if result == "SUCCESS" else "FAILED"
            internal_build_url = str(build_payload.get("url") or "").rstrip("/") + "/"
            public_build_url = _jenkins_internal_to_public(internal_build_url, host)
            log_excerpt = "Build completed"
            if internal_build_url:
                log_response = await client.get(f"{internal_build_url}consoleText")
                if log_response.status_code < 400:
                    log_excerpt = (log_response.text or "Build completed").strip()[:400]
            allure_url = f"{public_build_url}allure/"
            checks_total = 0
            checks_passed = 0
            if internal_build_url:
                allure_check = await client.get(f"{internal_build_url}allure/")
                if allure_check.status_code < 400:
                    checks_total = 1
                    checks_passed = 1 if status == "SUCCESS" else 0
                else:
                    allure_url = f"{str(details.get('reports_url') or '').rstrip('/')}/{build_number or 0}/"
            finished = datetime.now(UTC)
            return {
                "build_number": build_number or int(details.get("last_build_number") or 0) + 1,
                "status": status,
                "mode": "real",
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "job_url": details.get("job_url"),
                "console_url": f"{public_build_url}console",
                "allure_url": allure_url,
                "log_excerpt": log_excerpt,
                "checks_passed": checks_passed,
                "checks_total": checks_total if checks_total > 0 else 1,
            }
    except Exception:
        return None


async def _jenkins_url_exists(client: httpx.AsyncClient, host: str, public_url: str) -> bool:
    internal_url = _jenkins_public_to_internal(public_url, host).rstrip("/") + "/api/json"
    try:
        response = await client.get(internal_url)
    except Exception:
        return False
    return response.status_code < 400 and "/login" not in str(response.url).lower()


async def resolve_allure_open_url(host: str, preferred_job_url: str) -> dict[str, str]:
    admin_user = os.getenv("JENKINS_ADMIN_USER", "admin")
    admin_password = os.getenv("JENKINS_ADMIN_PASSWORD", "admin")
    jenkins_url = jenkins_external_url(host)
    job_candidates = [
        f"{preferred_job_url.rstrip('/')}/",
        f"{jenkins_url}/job/training-github-allure/",
        f"{jenkins_url}/",
    ]
    try:
        async with httpx.AsyncClient(timeout=8, auth=(admin_user, admin_password), follow_redirects=True) as client:
            selected_job_url = f"{jenkins_url}/"
            for candidate in job_candidates:
                if await _jenkins_url_exists(client, host, candidate):
                    selected_job_url = candidate
                    break

            report_candidates = [
                f"{selected_job_url}lastSuccessfulBuild/artifact/allure-report/index.html",
                f"{selected_job_url}lastCompletedBuild/artifact/allure-report/index.html",
                f"{selected_job_url}lastBuild/artifact/allure-report/index.html",
            ]
            for report_url in report_candidates:
                internal_url = _jenkins_public_to_internal(report_url, host)
                try:
                    response = await client.get(internal_url)
                except Exception:
                    continue
                body_head = ((response.text or "")[:2000]).lower()
                resolved_url = str(response.url).lower()
                not_found_markers = ("not found", "oops", "may not exist", "you may not have permission")
                if response.status_code < 400 and "/login" not in resolved_url and not any(marker in body_head for marker in not_found_markers):
                    return {"url": report_url, "mode": "report"}
            return {"url": selected_job_url, "mode": "job"}
    except Exception:
        pass
    fallback = f"{jenkins_url}/job/training-github-allure/"
    return {"url": fallback, "mode": "job"}


async def get_identity_fresh(db: AsyncSession, identity_id: uuid.UUID) -> StudentIdentity | None:
    return (
        await db.execute(
            select(StudentIdentity)
            .where(StudentIdentity.id == identity_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def wait_identity_final_status(db: AsyncSession, identity_id: uuid.UUID, timeout_seconds: float) -> StudentIdentity | None:
    if timeout_seconds <= 0:
        return await get_identity_fresh(db, identity_id)
    deadline = datetime.now(UTC).timestamp() + timeout_seconds
    async with SessionLocal() as poll_db:
        while datetime.now(UTC).timestamp() < deadline:
            identity = (
                await poll_db.execute(
                    select(StudentIdentity)
                    .where(StudentIdentity.id == identity_id)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if not identity:
                return None
            if identity.status not in {IdentityStatus.PENDING, IdentityStatus.PROVISIONING}:
                break
            await asyncio.sleep(0.25)
    return await get_identity_fresh(db, identity_id)


def ensure_employee_owns_client(client: Client, user_id: str):
    if client.created_by_employee_id is None:
        raise DomainError(403, "FORBIDDEN", "Client ownership is not assigned")
    if str(client.created_by_employee_id) != user_id:
        raise DomainError(403, "FORBIDDEN", "Client is outside employee scope")


async def get_employee_client_or_404(db: AsyncSession, client_id: str, employee_user_id: str) -> Client:
    client = await db.get(Client, uuid.UUID(client_id))
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    ensure_employee_owns_client(client, employee_user_id)
    return client


async def get_employee_ticket_or_404(db: AsyncSession, ticket_id: str, employee_user_id: str) -> SupportTicket:
    ticket = await db.get(SupportTicket, uuid.UUID(ticket_id))
    if not ticket:
        raise DomainError(404, "TICKET_NOT_FOUND", "Ticket not found")
    client = await db.get(Client, ticket.client_id)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    ensure_employee_owns_client(client, employee_user_id)
    return ticket


async def get_client_or_404(db: AsyncSession, client_id: str) -> Client:
    try:
        cid = uuid.UUID(client_id)
    except ValueError:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found") from None
    client = await db.get(Client, cid)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    return client


async def get_account_or_404(db: AsyncSession, account_id: str) -> Account:
    try:
        aid = uuid.UUID(account_id)
    except ValueError:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found") from None
    account = await db.get(Account, aid)
    if not account:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    return account


async def hard_delete_account(
    db: AsyncSession,
    account: Account,
    *,
    allow_non_zero_balance: bool,
):
    if not allow_non_zero_balance:
        if Decimal(account.balance) != Decimal("0") or Decimal(account.available_balance) != Decimal("0"):
            raise DomainError(409, "ACCOUNT_NON_ZERO_BALANCE", "Account balance must be zero for hard delete")

    await db.execute(
        delete(Transfer).where(
            or_(
                Transfer.source_account_id == account.id,
                Transfer.target_account_id == account.id,
            )
        )
    )
    await db.execute(delete(Card).where(Card.account_id == account.id))
    await db.execute(delete(Account).where(Account.id == account.id))


async def hard_delete_client(
    db: AsyncSession,
    client: Client,
    *,
    delete_student_user: bool,
    protected_user_id: uuid.UUID | None = None,
) -> dict:
    account_ids = (await db.execute(select(Account.id).where(Account.client_id == client.id))).scalars().all()
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

    await db.execute(delete(SupportTicket).where(SupportTicket.client_id == client.id))
    await db.execute(delete(Client).where(Client.id == client.id))

    deleted_student_user_id: str | None = None
    if delete_student_user and (protected_user_id is None or client.student_user_id != protected_user_id):
        owner = await db.get(StudentUser, client.student_user_id)
        if owner and owner.system_role == SystemRole.STUDENT:
            deleted_student_user_id = str(owner.id)
            await db.execute(delete(StudentUser).where(StudentUser.id == owner.id))

    return {
        "deleted_client_id": str(client.id),
        "deleted_account_count": len(account_ids),
        "deleted_student_user_id": deleted_student_user_id,
    }


def student_docs_path_allowed(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in STUDENT_DOCS_ALLOWED_PREFIXES)


def get_student_docs_claims(
    authorization: str = Header(default=""),
    student_docs_ticket: str | None = Cookie(default=None),
    docs_ticket: str | None = Query(default=None, alias="docs_ticket"),
    access_token: str | None = Query(default=None, alias="access_token"),
) -> dict:
    token = ""
    expected_type: str | None = None
    if authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        expected_type = "access"
    elif docs_ticket:
        token = docs_ticket.strip()
        expected_type = "student_docs"
    elif student_docs_ticket:
        token = student_docs_ticket.strip()
        expected_type = "student_docs"
    elif access_token:
        token = access_token.strip()
        expected_type = "access"
    if not token:
        raise DomainError(status_code=401, code="AUTH_REQUIRED", message="Bearer token required")
    try:
        claims = decode_token(token)
    except ValueError as exc:
        raise DomainError(status_code=401, code="INVALID_TOKEN", message="Invalid or expired token") from exc
    if expected_type and claims.get("type") != expected_type:
        raise DomainError(status_code=401, code="INVALID_TOKEN_TYPE", message="Invalid token type")
    if claims.get("system_role") != SystemRole.STUDENT.value:
        raise DomainError(status_code=403, code="FORBIDDEN", message="Insufficient system role")
    return claims


@app.get("/health", tags=["Observability / debug"])
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def ensure_minimal_student_on_startup():
    async with SessionLocal() as session:
        await ensure_minimal_student_bootstrap(session)


@app.get("/ready", tags=["Observability / debug"])
async def ready(db: AsyncSession = Depends(get_db)):
    await db.execute(select(1))
    return {"status": "ok"}


def build_student_openapi_schema() -> dict:
    schema = get_openapi(
        title="EasyBank API - Student API",
        version=app.version,
        description=SWAGGER_TOP_DESCRIPTION,
        routes=app.routes,
    )
    all_paths = schema.get("paths", {})
    filtered_paths = {path: spec for path, spec in all_paths.items() if student_docs_path_allowed(path)}
    schema["paths"] = filtered_paths
    return schema


@app.get("/students/openapi.json", include_in_schema=False)
async def students_openapi_json(db: AsyncSession = Depends(get_db), claims: dict = Depends(get_student_docs_claims)):
    actor = await get_student_actor(db, claims)
    await ensure_student_tool_access(db, actor, "REST_API")
    return build_student_openapi_schema()


@app.post("/students/docs-ticket", include_in_schema=False)
async def issue_students_docs_ticket(db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    actor = await get_student_actor(db, claims)
    await ensure_student_tool_access(db, actor, "REST_API")
    docs_ticket = create_docs_token(
        user_id=str(actor.id),
        system_role=actor.system_role.value,
        business_role=claims.get("business_role"),
        permissions=list(claims.get("permissions") or []),
        session_id=str(claims.get("session_id") or ""),
        expires_seconds=60,
    )
    return {"docs_url": f"/students/docs?docs_ticket={quote(docs_ticket, safe='')}"}


@app.get("/students/docs", include_in_schema=False)
async def students_swagger_ui(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_student_docs_claims),
    docs_ticket: str | None = Query(default=None, alias="docs_ticket"),
    access_token: str | None = Query(default=None, alias="access_token"),
):
    actor = await get_student_actor(db, claims)
    await ensure_student_tool_access(db, actor, "REST_API")
    openapi_url = "/students/openapi.json"
    if access_token:
        openapi_url = f"/students/openapi.json?access_token={quote(access_token, safe='')}"
    response = get_swagger_ui_html(
        openapi_url=openapi_url,
        title="EasyBank - Student API",
        swagger_ui_parameters={"persistAuthorization": True, "supportedSubmitMethods": []},
    )
    html = response.body.decode("utf-8").replace(
        "</body>",
        """
<script>
if (window.location.search.includes("docs_ticket=")) {
  const nextUrl = window.location.pathname + window.location.hash;
  window.history.replaceState({}, document.title, nextUrl);
}
</script>
</body>
""",
    )
    html_response = HTMLResponse(content=html, status_code=response.status_code)
    if docs_ticket:
        html_response.set_cookie(
            key="student_docs_ticket",
            value=docs_ticket,
            max_age=60,
            httponly=True,
            samesite="lax",
        )
    return html_response


@app.get("/debug/request-context", tags=["Observability / debug"])
async def request_context(request: Request):
    return {
        "request_id": getattr(request.state, "request_id", None),
        "trace_id": request.headers.get("x-trace-id"),
        "headers": dict(request.headers),
    }


@app.get("/debug/whoami", tags=["Observability / debug"])
async def whoami(claims: dict = Depends(get_current_claims)):
    return claims


@app.get("/students/me/events", tags=["Students / Events"], response_model=list[StudentEventResponse])
async def student_events_feed(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    event_prefix: str | None = Query(default=None),
    topic: str | None = Query(default=None),
):
    if claims.get("system_role") != SystemRole.STUDENT.value:
        raise DomainError(403, "FORBIDDEN", "Only STUDENT can view personal event feed")
    stmt = (
        select(StudentObservableEvent)
        .where(StudentObservableEvent.student_user_id == uuid.UUID(claims["user_id"]))
        .order_by(StudentObservableEvent.occurred_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if event_prefix:
        stmt = stmt.where(StudentObservableEvent.event_type.like(f"{event_prefix}%"))
    if topic:
        stmt = stmt.where(StudentObservableEvent.topic == topic)
    rows = (await db.execute(stmt)).scalars().all()
    return [student_event_to_dict(row) for row in rows]


@app.get("/students/me/identity", tags=["Students / Identity"], response_model=StudentIdentityResponse)
async def student_my_identity(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    if claims.get("system_role") != SystemRole.STUDENT.value:
        raise DomainError(403, "FORBIDDEN", "Only STUDENT can view own identity")
    user = await db.get(StudentUser, uuid.UUID(claims["user_id"]))
    if not user:
        raise DomainError(404, "USER_NOT_FOUND", "User not found")
    identity = await get_identity_by_user_id(db, user.id)
    if not identity:
        identity = await ensure_student_identity(
            db,
            user,
            requested_by_admin_id=user.created_by_admin_id,
            default_status=IdentityStatus.PENDING,
        )
        await db.commit()
    accesses = await get_identity_accesses(db, identity.id)
    return identity_payload(identity, accesses)


@app.get("/students/tools/{service_name}", tags=["Students / Identity"], response_model=StudentToolResponse)
async def student_tool_access_info(
    service_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    access = await ensure_student_tool_access(db, actor, service_name)
    host = request.url.hostname or "127.0.0.1"
    meta = student_tool_meta(access.service_name, host)
    return {
        "service_name": access.service_name,
        "title": meta["title"],
        "url": meta["url"],
        "hint": meta["hint"],
        "principal": access.principal,
        "status": access.status.value,
    }


@app.get("/students/allure/open-url", tags=["Students / Jenkins"], response_model=AllureOpenUrlResponse, include_in_schema=False)
async def student_allure_open_url(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    await ensure_student_tool_access(db, actor, "ALLURE")
    host = request.url.hostname or "127.0.0.1"
    jenkins_access = await ensure_student_tool_access(db, actor, "JENKINS")
    details = ensure_jenkins_details(jenkins_access, host, actor)
    job_url = str(details.get("job_url") or f"{jenkins_external_url(host)}/")
    return await resolve_allure_open_url(host, job_url)


@app.get("/students/jenkins/job/runs", tags=["Students / Jenkins"], response_model=JenkinsRunsPayload, include_in_schema=False)
async def student_jenkins_runs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    access = await ensure_student_tool_access(db, actor, "JENKINS")
    host = request.url.hostname or "127.0.0.1"
    details = ensure_jenkins_details(access, host, actor)
    access.details_json = details
    await db.commit()
    runs_raw = details.get("allure_reports") if isinstance(details.get("allure_reports"), list) else []
    runs = [JenkinsRunResponse.model_validate(item) for item in runs_raw if isinstance(item, dict)]
    return {
        "service_name": "JENKINS",
        "folder_path": str(details["folder_path"]),
        "job_name": str(details["job_name"]),
        "runs": sorted(runs, key=lambda item: item.build_number, reverse=True),
    }


@app.post("/students/jenkins/job/run", tags=["Students / Jenkins"], response_model=JenkinsRunResponse, include_in_schema=False)
async def student_jenkins_run_job(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    access = await ensure_student_tool_access(db, actor, "JENKINS")
    host = request.url.hostname or "127.0.0.1"
    details = ensure_jenkins_details(access, host, actor)
    next_build = int(details.get("last_build_number") or 0) + 1
    run_payload = None
    if env_flag("JENKINS_REAL_RUN_ENABLED", False):
        run_payload = await run_real_jenkins_build(details, host)
    if not run_payload:
        run_payload = build_mock_jenkins_run(next_build, details)
    last_build_number = int(run_payload.get("build_number") or next_build)
    details["last_build_number"] = max(last_build_number, int(details.get("last_build_number") or 0))
    history = details.get("allure_reports") if isinstance(details.get("allure_reports"), list) else []
    history.append(run_payload)
    details["allure_reports"] = history[-10:]
    access.details_json = details
    await db.commit()
    await emit(
        "bank-events",
        "jenkins.job.run",
        {
            "student_user_id": str(actor.id),
            "build_number": last_build_number,
            "status": run_payload.get("status"),
            "mode": run_payload.get("mode"),
        },
        scope_student_ids=[str(actor.id)],
        entity_type="jenkins_job",
        entity_id=f"{actor.id}:{last_build_number}",
    )
    return JenkinsRunResponse.model_validate(run_payload)


@app.get("/students/dashboard", tags=["Students / Dashboard"], response_model=StudentDashboardResponse)
async def student_dashboard(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee_ids = await get_student_employee_ids(db, actor)

    if not employee_ids:
        return {
            "employees_total": 0,
            "employees_active": 0,
            "employees_blocked": 0,
            "clients_total": 0,
            "accounts_total": 0,
            "tickets_total": 0,
            "transfers_total": 0,
            "series": [],
        }

    employees = (
        await db.execute(
            select(StudentUser).where(StudentUser.id.in_(employee_ids)).order_by(StudentUser.created_at.desc())
        )
    ).scalars().all()
    clients = (
        await db.execute(
            select(Client).where(Client.created_by_employee_id.in_(employee_ids)).order_by(Client.created_at.desc())
        )
    ).scalars().all()
    client_ids = [row.id for row in clients]

    accounts: list[Account] = []
    tickets: list[SupportTicket] = []
    transfers_count = 0
    if client_ids:
        accounts = (await db.execute(select(Account).where(Account.client_id.in_(client_ids)))).scalars().all()
        tickets = (await db.execute(select(SupportTicket).where(SupportTicket.client_id.in_(client_ids)))).scalars().all()
        account_ids = [row.id for row in accounts]
        if account_ids:
            transfers_count = int(
                (
                    await db.execute(
                        select(func.count(Transfer.id)).where(
                            or_(
                                Transfer.source_account_id.in_(account_ids),
                                Transfer.target_account_id.in_(account_ids),
                            )
                        )
                    )
                ).scalar_one()
            )

    now = datetime.now(UTC)
    day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    day_rows: list[datetime] = []
    for offset in range(6, -1, -1):
        day = day_start
        day = day.replace() - timedelta(days=offset)
        day_rows.append(day)
    day_keys = [
        f"{row.year:04d}-{row.month:02d}-{row.day:02d}"
        for row in day_rows
    ]
    series_map = {
        key: {"day": key, "employees": 0, "clients": 0, "accounts": 0, "tickets": 0}
        for key in day_keys
    }

    def inc_for_day(value: datetime | None, field: str):
        if not value:
            return
        dt = value.astimezone(UTC)
        key = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
        target = series_map.get(key)
        if target:
            target[field] += 1

    for row in employees:
        inc_for_day(row.created_at, "employees")
    for row in clients:
        inc_for_day(row.created_at, "clients")
    for row in accounts:
        inc_for_day(row.created_at, "accounts")
    for row in tickets:
        inc_for_day(row.created_at, "tickets")

    return {
        "employees_total": len(employees),
        "employees_active": len([row for row in employees if not row.is_blocked and row.is_active]),
        "employees_blocked": len([row for row in employees if row.is_blocked]),
        "clients_total": len(clients),
        "accounts_total": len(accounts),
        "tickets_total": len(tickets),
        "transfers_total": transfers_count,
        "series": [series_map[key] for key in day_keys],
    }


@app.post(
    "/students/entities/generate",
    tags=["Students / Entities"],
    response_model=StudentEntitiesGenerateResponse,
)
async def student_generate_entities(
    payload: StudentEntitiesGenerateRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    lock_key = f"demobank:student:{actor.id}:entities_generation_lock"
    lock_value = uuid.uuid4().hex
    try:
        lock_acquired = await redis.set(lock_key, lock_value, nx=True, ex=180)
    except Exception as exc:
        raise DomainError(503, "GENERATION_LOCK_UNAVAILABLE", "Generation lock storage is unavailable") from exc
    if not lock_acquired:
        raise DomainError(409, "GENERATION_IN_PROGRESS", "Entity generation is already in progress")

    try:
        result = await generate_student_entities(
            db,
            actor,
            confirm_cleanup=payload.confirm_cleanup,
        )
        await upsert_usage(db, claims["user_id"], "deleted_entities_count")
        await upsert_usage(db, claims["user_id"], "created_entities_count")
        await db.commit()
    except DomainError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise DomainError(500, "GENERATION_FAILED", "Failed to generate student entities") from exc
    finally:
        try:
            current_lock_value = await redis.get(lock_key)
            if current_lock_value == lock_value:
                await redis.delete(lock_key)
        except Exception:
            pass

    for event in result.events:
        await emit(
            event.topic,
            event.event_type,
            event.payload,
            scope_student_ids=event.scope_student_ids,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
        )

    await emit(
        "audit-events",
        "student.entities.generated",
        {
            "run_id": result.run_id,
            "student_owner_id": str(actor.id),
            "cleaned_employees": result.cleaned_employees,
            "cleaned_clients": result.cleaned_clients,
            "cleaned_accounts": result.cleaned_accounts,
            "cleaned_tickets": result.cleaned_tickets,
            "cleaned_messages": result.cleaned_messages,
            "cleaned_users": result.cleaned_users,
            "cleaned_identities": result.cleaned_identities,
            "cleaned_identity_accesses": result.cleaned_identity_accesses,
            "created_employees": result.created_employees,
            "created_clients": result.created_clients,
            "created_accounts": result.created_accounts,
            "created_tickets": result.created_tickets,
            "created_messages": result.created_messages,
        },
        scope_student_ids=[str(actor.id)],
    )

    return {
        "run_id": result.run_id,
        "cleaned_employees": result.cleaned_employees,
        "cleaned_clients": result.cleaned_clients,
        "cleaned_accounts": result.cleaned_accounts,
        "cleaned_tickets": result.cleaned_tickets,
        "cleaned_messages": result.cleaned_messages,
        "cleaned_users": result.cleaned_users,
        "cleaned_identities": result.cleaned_identities,
        "cleaned_identity_accesses": result.cleaned_identity_accesses,
        "created_employees": result.created_employees,
        "created_clients": result.created_clients,
        "created_accounts": result.created_accounts,
        "created_tickets": result.created_tickets,
        "created_messages": result.created_messages,
        "employee_ids": result.employee_ids,
        "client_ids": result.client_ids,
    }


@app.get("/students/employees", tags=["Students / Employees"], response_model=list[StudentEmployeeResponse])
async def student_list_employees(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee_ids = await get_student_employee_ids(db, actor)
    if not employee_ids:
        return []
    employees = (
        await db.execute(
            select(StudentUser)
            .where(StudentUser.id.in_(employee_ids))
            .order_by(StudentUser.created_at.desc())
        )
    ).scalars().all()
    clients = (
        await db.execute(select(Client).where(Client.created_by_employee_id.in_(employee_ids)))
    ).scalars().all()
    clients_count_map = {str(row.id): 0 for row in employees}
    client_owner_map: dict[uuid.UUID, uuid.UUID] = {}
    for row in clients:
        if row.created_by_employee_id:
            eid = str(row.created_by_employee_id)
            clients_count_map[eid] = clients_count_map.get(eid, 0) + 1
            client_owner_map[row.id] = row.created_by_employee_id

    tickets_count_map = {str(row.id): 0 for row in employees}
    client_ids = list(client_owner_map.keys())
    if client_ids:
        tickets = (
            await db.execute(select(SupportTicket.client_id).where(SupportTicket.client_id.in_(client_ids)))
        ).scalars().all()
        for client_id in tickets:
            owner_id = client_owner_map.get(client_id)
            if owner_id:
                key = str(owner_id)
                tickets_count_map[key] = tickets_count_map.get(key, 0) + 1

    return [
        employee_payload(
            row,
            clients_count=clients_count_map.get(str(row.id), 0),
            tickets_count=tickets_count_map.get(str(row.id), 0),
        )
        for row in employees
    ]


@app.post("/students/employees", tags=["Students / Employees"], response_model=StudentEmployeeResponse)
async def student_create_employee(
    payload: StudentEmployeeCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    from common.security import hash_password

    actor = await get_student_actor(db, claims)
    existing = (
        await db.execute(select(StudentUser).where((StudentUser.email == payload.email) | (StudentUser.username == payload.email)))
    ).scalar_one_or_none()
    if existing:
        raise DomainError(409, "USER_ALREADY_EXISTS", "Email already exists")

    first_name, last_name = split_full_name(payload.full_name, fallback_email=payload.email)
    raw_password = payload.password or generate_password()
    public_id = await allocate_next_student_public_id(db)
    employee = StudentUser(
        email=payload.email,
        username=payload.email,
        public_id=public_id,
        hashed_password=hash_password(raw_password),
        first_name=first_name,
        last_name=last_name,
        system_role=SystemRole.STUDENT,
        created_by_admin_id=actor.id,
        is_primary_admin=False,
        can_create_admins=False,
    )
    db.add(employee)
    await db.flush()
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    data = employee_payload(employee)
    return data


@app.get("/students/employees/{employee_id}", tags=["Students / Employees"], response_model=StudentEmployeeResponse)
async def student_get_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    clients_count = int(
        (
            await db.execute(
                select(func.count(Client.id)).where(Client.created_by_employee_id == employee.id)
            )
        ).scalar_one()
    )
    tickets_count = int(
        (
            await db.execute(
                select(func.count(SupportTicket.id))
                .select_from(SupportTicket)
                .join(Client, SupportTicket.client_id == Client.id)
                .where(Client.created_by_employee_id == employee.id)
            )
        ).scalar_one()
    )
    return employee_payload(employee, clients_count=clients_count, tickets_count=tickets_count)


@app.patch("/students/employees/{employee_id}", tags=["Students / Employees"], response_model=StudentEmployeeResponse)
async def student_update_employee(
    employee_id: str,
    payload: StudentEmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)

    duplicate = (
        await db.execute(
            select(StudentUser).where(
                StudentUser.id != employee.id,
                or_(StudentUser.email == payload.email, StudentUser.username == payload.email),
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise DomainError(409, "USER_ALREADY_EXISTS", "Email already exists")

    first_name, last_name = split_full_name(payload.full_name, fallback_email=payload.email)
    employee.email = payload.email
    employee.username = payload.email
    employee.first_name = first_name
    employee.last_name = last_name
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(employee)
    return employee_payload(employee)


@app.patch("/students/employees/{employee_id}/block", tags=["Students / Employees"], response_model=StudentEmployeeResponse)
async def student_block_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    employee.is_blocked = True
    employee.is_active = False
    employee.blocked_reason = "Blocked by student owner"
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(employee)
    await emit(
        "auth-events",
        "employee.blocked.by_student",
        {"student_owner_id": str(actor.id), "employee_id": str(employee.id)},
    )
    return employee_payload(employee)


@app.patch("/students/employees/{employee_id}/unblock", tags=["Students / Employees"], response_model=StudentEmployeeResponse)
async def student_unblock_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    employee.is_blocked = False
    employee.is_active = True
    employee.blocked_reason = None
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(employee)
    await emit(
        "auth-events",
        "employee.unblocked.by_student",
        {"student_owner_id": str(actor.id), "employee_id": str(employee.id)},
    )
    return employee_payload(employee)


@app.delete("/students/employees/{employee_id}", tags=["Students / Employees"])
async def student_delete_employee(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)

    managed_clients = (
        await db.execute(select(Client).where(Client.created_by_employee_id == employee.id))
    ).scalars().all()
    deleted_client_ids: list[str] = []
    deleted_client_users: list[str] = []
    for client in managed_clients:
        summary = await hard_delete_client(
            db,
            client,
            delete_student_user=True,
            protected_user_id=employee.id,
        )
        deleted_client_ids.append(summary["deleted_client_id"])
        if summary.get("deleted_student_user_id"):
            deleted_client_users.append(summary["deleted_student_user_id"])

    await db.execute(delete(StudentUser).where(StudentUser.id == employee.id))
    await upsert_usage(db, claims["user_id"], "deleted_entities_count")
    await db.commit()
    await emit(
        "auth-events",
        "employee.deleted.by_student",
        {
            "student_owner_id": str(actor.id),
            "employee_id": str(employee.id),
            "deleted_client_ids": deleted_client_ids,
            "deleted_client_users": deleted_client_users,
        },
    )
    return {
        "deleted_employee_id": str(employee.id),
        "deleted_client_ids": deleted_client_ids,
        "deleted_client_users": deleted_client_users,
    }


@app.get("/students/employees/{employee_id}/clients", tags=["Students / Employees"], response_model=list[StudentClientResponse])
async def student_employee_clients(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    clients = (
        await db.execute(
            select(Client).where(Client.created_by_employee_id == employee.id).order_by(Client.created_at.desc())
        )
    ).scalars().all()
    if not clients:
        return []

    client_ids = [row.id for row in clients]
    account_rows = (
        await db.execute(select(Account.client_id).where(Account.client_id.in_(client_ids)))
    ).scalars().all()
    ticket_rows = (
        await db.execute(select(SupportTicket.client_id).where(SupportTicket.client_id.in_(client_ids)))
    ).scalars().all()
    owner_ids = [row.student_user_id for row in clients]
    owners = (
        await db.execute(select(StudentUser).where(StudentUser.id.in_(owner_ids)))
    ).scalars().all()
    owner_map = {row.id: row for row in owners}

    accounts_count: dict[uuid.UUID, int] = {}
    tickets_count: dict[uuid.UUID, int] = {}
    for cid in account_rows:
        accounts_count[cid] = accounts_count.get(cid, 0) + 1
    for cid in ticket_rows:
        tickets_count[cid] = tickets_count.get(cid, 0) + 1

    response = []
    employee_name = build_full_name(employee.first_name, employee.last_name) or employee.email
    for row in clients:
        payload = to_dict(row)
        owner = owner_map.get(row.student_user_id)
        payload["student_full_name"] = build_full_name(owner.first_name, owner.last_name) if owner else None
        payload["student_email"] = owner.email if owner else None
        payload["employee_id"] = str(employee.id)
        payload["employee_name"] = employee_name
        payload["accounts_count"] = accounts_count.get(row.id, 0)
        payload["tickets_count"] = tickets_count.get(row.id, 0)
        response.append(payload)
    return response


@app.post("/students/employees/{employee_id}/clients", tags=["Students / Employees"], response_model=StudentClientResponse)
async def student_employee_create_client(
    employee_id: str,
    payload: EmployeeClientQuickCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    from common.security import hash_password

    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)

    student_username = (payload.student_username or payload.email or "").strip().lower()
    email = (payload.email or "").strip().lower()
    if not student_username:
        student_username = email
    if not email or "@" not in email:
        raise DomainError(400, "INVALID_EMAIL", "Email is invalid")

    student = (
        await db.execute(
            select(StudentUser).where(
                or_(StudentUser.username == student_username, StudentUser.email == email)
            )
        )
    ).scalar_one_or_none()
    generated_password: str | None = None
    if student:
        if student.system_role != SystemRole.STUDENT:
            raise DomainError(409, "USER_ALREADY_EXISTS", "User already exists with non-student role")
    else:
        generated_password = generate_password()
        student = StudentUser(
            email=email,
            username=student_username,
            hashed_password=hash_password(generated_password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            system_role=SystemRole.STUDENT,
            created_by_admin_id=actor.id,
            is_primary_admin=False,
            can_create_admins=False,
        )
        db.add(student)
        await db.flush()

    existing_client = (await db.execute(select(Client).where(Client.student_user_id == student.id))).scalar_one_or_none()
    if existing_client:
        raise DomainError(409, "CLIENT_ALREADY_EXISTS", "Client profile already exists for this user")

    bank = await get_bank(db)
    client = Client(
        student_user_id=student.id,
        created_by_employee_id=employee.id,
        bank_id=bank.id,
        external_client_code=fake_external_code(),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        middle_name=None,
        birth_date=date(1999, 1, 1),
        phone=payload.phone.strip(),
        email=email,
        passport_series="4500",
        passport_number=uuid.uuid4().hex[:6].upper(),
        passport_issued_by="UFMS Demo",
        passport_issued_date=date(2018, 1, 1),
        residency_country="RU",
        status=ClientStatus.PENDING_VERIFICATION,
        risk_level=RiskLevel.LOW,
    )
    db.add(client)
    await db.flush()
    default_account = build_default_client_account(bank_id=bank.id, client_id=client.id)
    db.add(default_account)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()

    await emit(
        "client-events",
        "client.created.by_student",
        {"id": str(client.id), "employee_id": str(employee.id), "student_owner_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="client",
        entity_id=str(client.id),
    )
    await emit(
        "account-events",
        "account.opened.by_student",
        {"id": str(default_account.id), "client_id": str(client.id), "student_owner_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="account",
        entity_id=str(default_account.id),
    )

    result = to_dict(client)
    result["employee_id"] = str(employee.id)
    result["employee_name"] = build_full_name(employee.first_name, employee.last_name) or employee.email
    return result


@app.get("/students/employees/{employee_id}/tickets", tags=["Students / Employees"])
async def student_employee_tickets(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    client_ids = (
        await db.execute(select(Client.id).where(Client.created_by_employee_id == employee.id))
    ).scalars().all()
    if not client_ids:
        return []
    rows = (
        await db.execute(select(SupportTicket).where(SupportTicket.client_id.in_(client_ids)).order_by(SupportTicket.created_at.desc()))
    ).scalars().all()
    return [to_dict(row) for row in rows]


@app.patch("/students/employees/{employee_id}/tickets/{ticket_id}/assign", tags=["Students / Employees"])
async def student_assign_employee_ticket(
    employee_id: str,
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    ticket, client = await get_student_scoped_employee_ticket_or_404(db, actor, employee, ticket_id)
    ticket.employee_id_nullable = employee.id
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(ticket)
    await emit(
        "support-events",
        "ticket.assigned.by_student",
        {"ticket_id": str(ticket.id), "employee_id": str(employee.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="ticket",
        entity_id=str(ticket.id),
    )
    return to_dict(ticket)


@app.patch("/students/employees/{employee_id}/tickets/{ticket_id}/status", tags=["Students / Employees"])
async def student_update_employee_ticket_status(
    employee_id: str,
    ticket_id: str,
    payload: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    ticket, client = await get_student_scoped_employee_ticket_or_404(db, actor, employee, ticket_id)
    ensure_transition(ticket.status, payload.status, TICKET_TRANSITIONS, "Ticket")
    ticket.status = payload.status
    if payload.status in {TicketStatus.CLOSED, TicketStatus.RESOLVED, TicketStatus.REJECTED}:
        ticket.closed_at = datetime.now(UTC)
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(ticket)
    await emit(
        "support-events",
        "ticket.status.updated.by_student",
        {"ticket_id": str(ticket.id), "status": payload.status.value, "employee_id": str(employee.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="ticket",
        entity_id=str(ticket.id),
    )
    return to_dict(ticket)


@app.post("/students/employees/{employee_id}/tickets/{ticket_id}/messages", tags=["Students / Employees"])
async def student_create_employee_ticket_message(
    employee_id: str,
    ticket_id: str,
    payload: TicketMessageCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    ticket, client = await get_student_scoped_employee_ticket_or_404(db, actor, employee, ticket_id)
    message = SupportTicketMessage(
        ticket_id=ticket.id,
        author_type="EMPLOYEE",
        author_id=employee.id,
        message=payload.message,
    )
    db.add(message)
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(message)
    await emit(
        "support-events",
        "ticket.message.created.by_student",
        {"ticket_id": str(ticket.id), "message_id": str(message.id), "employee_id": str(employee.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="ticket",
        entity_id=str(ticket.id),
    )
    return to_dict(message)


@app.get("/students/employees/{employee_id}/audit", tags=["Students / Employees"])
async def student_employee_audit(
    employee_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    rows = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.actor_user_id == employee.id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [to_dict(row) for row in rows]


@app.get("/students/employees/{employee_id}/exchange-rates", tags=["Students / Employees"])
async def student_employee_exchange_rates(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    await get_student_employee_or_404(db, actor, employee_id)
    return [exchange_rate_payload(row) for row in await list_exchange_rates(db)]


@app.put("/students/employees/{employee_id}/exchange-rates/{quote_currency}", tags=["Students / Employees"])
async def student_employee_set_exchange_rate(
    employee_id: str,
    quote_currency: Currency,
    payload: ExchangeRateUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee = await get_student_employee_or_404(db, actor, employee_id)
    row = await get_exchange_rate_or_404(db, quote_currency)
    row.rub_amount = payload.rub_amount
    row.set_by_user_id = employee.id
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(row)
    await emit(
        "transfer-events",
        "exchange-rate.updated.by_student",
        {
            "employee_id": str(employee.id),
            "quote_currency": quote_currency.value,
            "rub_amount": float(Decimal(row.rub_amount)),
        },
        scope_student_ids=[str(actor.id), str(employee.id)],
        entity_type="exchange-rate",
        entity_id=quote_currency.value,
    )
    return exchange_rate_payload(row)


@app.get("/students/clients", tags=["Students / Clients"], response_model=list[StudentClientResponse])
async def student_list_clients(
    status: ClientStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    employee_ids = await get_student_employee_ids(db, actor)
    if not employee_ids:
        return []

    stmt = select(Client).where(Client.created_by_employee_id.in_(employee_ids))
    if status:
        stmt = stmt.where(Client.status == status)
    clients = (await db.execute(stmt.order_by(Client.created_at.desc()))).scalars().all()
    if not clients:
        return []

    employee_rows = (await db.execute(select(StudentUser).where(StudentUser.id.in_(employee_ids)))).scalars().all()
    employee_name_map = {row.id: build_full_name(row.first_name, row.last_name) or row.email for row in employee_rows}
    client_ids = [row.id for row in clients]
    account_rows = (await db.execute(select(Account.client_id).where(Account.client_id.in_(client_ids)))).scalars().all()
    ticket_rows = (await db.execute(select(SupportTicket.client_id).where(SupportTicket.client_id.in_(client_ids)))).scalars().all()

    accounts_count: dict[uuid.UUID, int] = {}
    tickets_count: dict[uuid.UUID, int] = {}
    for cid in account_rows:
        accounts_count[cid] = accounts_count.get(cid, 0) + 1
    for cid in ticket_rows:
        tickets_count[cid] = tickets_count.get(cid, 0) + 1

    response = []
    for row in clients:
        payload = to_dict(row)
        if row.created_by_employee_id:
            payload["employee_id"] = str(row.created_by_employee_id)
            payload["employee_name"] = employee_name_map.get(row.created_by_employee_id)
        else:
            payload["employee_id"] = None
            payload["employee_name"] = None
        payload["accounts_count"] = accounts_count.get(row.id, 0)
        payload["tickets_count"] = tickets_count.get(row.id, 0)
        response.append(payload)
    return response


@app.get("/students/clients/{client_id}", tags=["Students / Clients"], response_model=StudentClientResponse)
async def student_get_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, employee = await get_student_scoped_client_or_404(db, actor, client_id)
    owner = await db.get(StudentUser, client.student_user_id)
    payload = to_dict(client)
    payload["employee_id"] = str(employee.id)
    payload["employee_name"] = build_full_name(employee.first_name, employee.last_name) or employee.email
    payload["student_full_name"] = build_full_name(owner.first_name, owner.last_name) if owner else None
    payload["student_email"] = owner.email if owner else None
    return payload


@app.get("/students/clients/{client_id}/accounts", tags=["Students / Clients"], response_model=list[StudentAccountResponse])
async def student_client_accounts(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    rows = (
        await db.execute(
            select(Account).where(
                Account.client_id == client.id,
                Account.type != AccountType.DEPOSIT_SIMULATED,
            )
        )
    ).scalars().all()
    return [to_dict(row) for row in rows]


@app.get("/students/clients/{client_id}/tickets", tags=["Students / Clients"])
async def student_client_tickets(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    rows = (
        await db.execute(select(SupportTicket).where(SupportTicket.client_id == client.id).order_by(SupportTicket.created_at.desc()))
    ).scalars().all()
    return [to_dict(row) for row in rows]


@app.get("/students/clients/{client_id}/transfers", tags=["Students / Clients"])
async def student_client_transfers(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    account_ids = (
        await db.execute(select(Account.id).where(Account.client_id == client.id))
    ).scalars().all()
    if not account_ids:
        return []
    rows = (
        await db.execute(
            select(Transfer)
            .where(or_(Transfer.source_account_id.in_(account_ids), Transfer.target_account_id.in_(account_ids)))
            .order_by(Transfer.created_at.desc())
        )
    ).scalars().all()
    return [to_dict(row) for row in rows]


@app.post("/students/clients/{client_id}/transfers/top-up", tags=["Students / Clients"])
async def student_client_top_up(
    client_id: str,
    payload: TransferTopUp,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    account = await get_account_by_ref(db, payload.account_id)
    if not account or account.client_id != client.id or account.type == AccountType.DEPOSIT_SIMULATED:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if account.status == AccountStatus.BLOCKED:
        raise DomainError(409, "ACCOUNT_BLOCKED", "Account is blocked")
    bank = await get_bank(db)
    transfer = await create_cash_top_up_transfer(
        db,
        bank=bank,
        client=client,
        account=account,
        amount=payload.amount,
        initiated_by_role="EMPLOYEE",
        description="Cash top up by student",
        idempotency_key=payload.idempotency_key,
    )
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    scope = await load_transfer_scope_student_ids(db, account, account)
    await emit(
        "transfer-events",
        "transfer.completed",
        {"id": str(transfer.id), "status": transfer.status.value},
        ws_event="transfer.completed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=str(transfer.id),
    )
    return to_dict(transfer)


@app.post("/students/clients/{client_id}/transfers/self", tags=["Students / Clients"])
async def student_client_self_transfer(
    client_id: str,
    payload: TransferCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    source = await get_account_by_ref(db, payload.source_account_id)
    target = await get_account_by_ref(db, payload.target_account_id)
    if not source or not target:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if source.client_id != client.id or target.client_id != client.id:
        raise DomainError(403, "FORBIDDEN", "Transfer is available only between client accounts")
    if source.type == AccountType.DEPOSIT_SIMULATED or target.type == AccountType.DEPOSIT_SIMULATED:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    assert_account_outgoing_allowed(source)
    assert_account_incoming_allowed(target)
    if Decimal(source.available_balance) < payload.amount:
        raise DomainError(409, "INSUFFICIENT_FUNDS", "Not enough available balance")
    bank = await get_bank(db)
    transfer = await create_transfer(
        db,
        bank.id,
        source,
        target,
        payload.amount,
        payload.currency or source.currency,
        TransferType.SELF,
        "EMPLOYEE",
        payload.description,
        payload.idempotency_key,
    )
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    scope = await load_transfer_scope_student_ids(db, source, target)
    await emit(
        "transfer-events",
        "transfer.completed",
        {"id": str(transfer.id), "status": transfer.status.value},
        ws_event="transfer.completed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=str(transfer.id),
    )
    return to_dict(transfer)


async def student_set_client_status(
    db: AsyncSession,
    actor: StudentUser,
    client_id: str,
    status: ClientStatus,
):
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    ensure_transition(client.status, status, CLIENT_TRANSITIONS, "Client")
    client.status = status
    await upsert_usage(db, str(actor.id), "updated_entities_count")
    await db.commit()
    await db.refresh(client)
    await emit(
        "client-events",
        f"client.{status.value.lower()}",
        {"id": str(client.id), "status": status.value, "changed_by_student_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="client",
        entity_id=str(client.id),
    )
    return to_dict(client)


@app.patch("/students/clients/{client_id}/block", tags=["Students / Clients"])
async def student_block_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    return await student_set_client_status(db, actor, client_id, ClientStatus.BLOCKED)


@app.patch("/students/clients/{client_id}/suspend", tags=["Students / Clients"])
async def student_suspend_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    return await student_set_client_status(db, actor, client_id, ClientStatus.SUSPENDED)


@app.patch("/students/clients/{client_id}/activate", tags=["Students / Clients"])
async def student_activate_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    return await student_set_client_status(db, actor, client_id, ClientStatus.ACTIVE)


@app.delete("/students/clients/{client_id}", tags=["Students / Clients"])
async def student_delete_client(
    client_id: str,
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    if force:
        summary = await hard_delete_client(db, client, delete_student_user=True, protected_user_id=actor.id)
        await upsert_usage(db, claims["user_id"], "deleted_entities_count")
        await db.commit()
        await emit(
            "client-events",
            "client.deleted.by_student",
            {"id": client_id, "hard_delete": True, "student_owner_id": str(actor.id)},
            scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
            entity_type="client",
            entity_id=client_id,
        )
        return summary
    await db.execute(delete(Client).where(Client.id == client.id))
    await upsert_usage(db, claims["user_id"], "deleted_entities_count")
    await db.commit()
    await emit(
        "client-events",
        "client.deleted.by_student",
        {"id": client_id, "hard_delete": False, "student_owner_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="client",
        entity_id=client_id,
    )
    return {"deleted": client_id}


@app.post("/students/clients/{client_id}/accounts", tags=["Students / Clients"], response_model=StudentAccountResponse)
async def student_open_client_account(
    client_id: str,
    payload: AccountCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    client, _ = await get_student_scoped_client_or_404(db, actor, client_id)
    bank = await get_bank(db)
    account = Account(
        bank_id=bank.id,
        client_id=client.id,
        account_number=fake_account_number(),
        currency=payload.currency,
        type=payload.type,
        status=AccountStatus.ACTIVE,
        balance=0,
        available_balance=0,
        hold_amount=0,
        overdraft_limit=0,
    )
    db.add(account)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    await emit(
        "account-events",
        "account.opened.by_student",
        {"id": str(account.id), "client_id": str(client.id), "student_owner_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="account",
        entity_id=str(account.id),
    )
    return to_dict(account)


async def student_account_status_change(
    db: AsyncSession,
    actor: StudentUser,
    account_id: str,
    status: AccountStatus,
):
    account, client = await get_student_scoped_account_or_404(db, actor, account_id)
    ensure_transition(account.status, status, ACCOUNT_TRANSITIONS, "Account")
    account.status = status
    if status == AccountStatus.CLOSED:
        account.closed_at = datetime.now(UTC)
    await upsert_usage(db, str(actor.id), "updated_entities_count")
    await db.commit()
    await db.refresh(account)
    await emit(
        "account-events",
        f"account.{status.value.lower()}.by_student",
        {"id": str(account.id), "status": status.value, "student_owner_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="account",
        entity_id=str(account.id),
    )
    return to_dict(account)


@app.patch("/students/accounts/{account_id}/block", tags=["Students / Clients"], response_model=StudentAccountResponse)
async def student_block_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    return await student_account_status_change(db, actor, account_id, AccountStatus.BLOCKED)


@app.patch("/students/accounts/{account_id}/unblock", tags=["Students / Clients"], response_model=StudentAccountResponse)
async def student_unblock_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    return await student_account_status_change(db, actor, account_id, AccountStatus.ACTIVE)


@app.patch("/students/accounts/{account_id}/close", tags=["Students / Clients"], response_model=StudentAccountResponse)
async def student_close_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    return await student_account_status_change(db, actor, account_id, AccountStatus.CLOSED)


@app.delete("/students/accounts/{account_id}", tags=["Students / Clients"])
async def student_delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_system_role(SystemRole.STUDENT.value)),
):
    actor = await get_student_actor(db, claims)
    account, client = await get_student_scoped_account_or_404(db, actor, account_id)
    await hard_delete_account(db, account, allow_non_zero_balance=True)
    await upsert_usage(db, claims["user_id"], "deleted_entities_count")
    await db.commit()
    await emit(
        "account-events",
        "account.deleted.by_student",
        {"id": account_id, "client_id": str(client.id), "student_owner_id": str(actor.id)},
        scope_student_ids=client_scope_student_ids_for_actor(client, actor.id),
        entity_type="account",
        entity_id=account_id,
    )
    return {"deleted_account_id": account_id, "hard_delete": True}


@app.post("/employees/clients", tags=["Employees / Clients"])
async def employee_create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    student = await db.get(StudentUser, uuid.UUID(payload.student_user_id))
    if not student or student.system_role != SystemRole.STUDENT:
        raise DomainError(404, "STUDENT_NOT_FOUND", "Student user not found")
    existing_client = (await db.execute(select(Client).where(Client.student_user_id == student.id))).scalar_one_or_none()
    if existing_client:
        raise DomainError(409, "CLIENT_ALREADY_EXISTS", "Client profile already exists for this student")

    client = Client(
        student_user_id=student.id,
        created_by_employee_id=uuid.UUID(claims["user_id"]),
        bank_id=uuid.UUID(payload.bank_id),
        external_client_code=fake_external_code(),
        first_name=payload.first_name,
        last_name=payload.last_name,
        middle_name=payload.middle_name,
        birth_date=payload.birth_date,
        phone=payload.phone,
        email=payload.email,
        passport_series=payload.passport_series,
        passport_number=payload.passport_number,
        passport_issued_by=payload.passport_issued_by,
        passport_issued_date=payload.passport_issued_date,
        residency_country=payload.residency_country,
        status=ClientStatus.PENDING_VERIFICATION,
        risk_level=payload.risk_level,
    )
    db.add(client)
    await db.flush()
    default_account = build_default_client_account(bank_id=uuid.UUID(payload.bank_id), client_id=client.id)
    db.add(default_account)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    await emit(
        "client-events",
        "client.created",
        {"id": str(client.id)},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="client",
        entity_id=str(client.id),
    )
    await emit(
        "account-events",
        "account.opened",
        {"id": str(default_account.id), "client_id": str(client.id)},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=str(default_account.id),
    )
    return to_dict(client)


@app.post("/employees/clients/quick-create", tags=["Employees / Clients"])
async def employee_quick_create_client(
    payload: EmployeeClientQuickCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_business_role("EMPLOYEE")),
):
    student = (await db.execute(select(StudentUser).where(StudentUser.username == payload.student_username))).scalar_one_or_none()
    if not student or student.system_role != SystemRole.STUDENT:
        raise DomainError(404, "STUDENT_NOT_FOUND", "Student user not found")
    existing_client = (await db.execute(select(Client).where(Client.student_user_id == student.id))).scalar_one_or_none()
    if existing_client:
        raise DomainError(409, "CLIENT_ALREADY_EXISTS", "Client profile already exists for this student")

    bank = await get_bank(db)
    client = Client(
        student_user_id=student.id,
        created_by_employee_id=uuid.UUID(claims["user_id"]),
        bank_id=bank.id,
        external_client_code=fake_external_code(),
        first_name=payload.first_name,
        last_name=payload.last_name,
        middle_name=None,
        birth_date=date(1999, 1, 1),
        phone=payload.phone,
        email=payload.email,
        passport_series="4500",
        passport_number=uuid.uuid4().hex[:6].upper(),
        passport_issued_by="UFMS Demo",
        passport_issued_date=date(2018, 1, 1),
        residency_country="RU",
        status=ClientStatus.PENDING_VERIFICATION,
        risk_level=RiskLevel.LOW,
    )
    db.add(client)
    await db.flush()
    default_account = build_default_client_account(bank_id=bank.id, client_id=client.id)
    db.add(default_account)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    await emit(
        "client-events",
        "client.created",
        {"id": str(client.id)},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="client",
        entity_id=str(client.id),
    )
    await emit(
        "account-events",
        "account.opened",
        {"id": str(default_account.id), "client_id": str(client.id)},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=str(default_account.id),
    )
    return to_dict(client)


@app.get("/employees/clients", tags=["Employees / Clients"])
async def employee_list_clients(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_business_role("EMPLOYEE")),
    status: ClientStatus | None = Query(default=None),
):
    stmt = select(Client).where(Client.created_by_employee_id == uuid.UUID(claims["user_id"]))
    if status:
        stmt = stmt.where(Client.status == status)
    rows = (await db.execute(stmt.order_by(Client.created_at.desc()))).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/employees/clients/{client_id}", tags=["Employees / Clients"])
async def employee_get_client(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    return to_dict(client)


class ClientPatch(BaseModel):
    phone: str | None = None
    email: str | None = None
    risk_level: RiskLevel | None = None


@app.patch("/employees/clients/{client_id}", tags=["Employees / Clients"])
async def employee_patch_client(client_id: str, payload: ClientPatch, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(client, key, value)
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DomainError(409, "CLIENT_CONTACT_ALREADY_EXISTS", "Phone or email already exists") from exc
    await db.refresh(client)
    return to_dict(client)


async def set_client_status(db: AsyncSession, client_id: str, status: ClientStatus, employee_user_id: str):
    client = await get_employee_client_or_404(db, client_id, employee_user_id)
    ensure_transition(client.status, status, CLIENT_TRANSITIONS, "Client")
    client.status = status
    await db.commit()
    await db.refresh(client)
    await emit(
        "client-events",
        f"client.{status.value.lower()}",
        {"id": client_id, "status": status.value},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="client",
        entity_id=client_id,
    )
    return to_dict(client)


@app.patch("/employees/clients/{client_id}/block", tags=["Employees / Clients"])
async def employee_block_client(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await set_client_status(db, client_id, ClientStatus.BLOCKED, claims["user_id"])


@app.patch("/employees/clients/{client_id}/suspend", tags=["Employees / Clients"])
async def employee_suspend_client(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await set_client_status(db, client_id, ClientStatus.SUSPENDED, claims["user_id"])


@app.patch("/employees/clients/{client_id}/activate", tags=["Employees / Clients"])
async def employee_activate_client(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await set_client_status(db, client_id, ClientStatus.ACTIVE, claims["user_id"])


@app.delete("/employees/clients/{client_id}", tags=["Employees / Clients"])
async def employee_delete_client(
    client_id: str,
    force: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_business_role("EMPLOYEE")),
):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    if force:
        summary = await hard_delete_client(db, client, delete_student_user=False)
        await upsert_usage(db, claims["user_id"], "deleted_entities_count")
        await db.commit()
        await emit(
            "client-events",
            "client.deleted",
            {"id": client_id, "hard_delete": True},
            scope_student_ids=client_scope_student_ids(client),
            entity_type="client",
            entity_id=client_id,
        )
        return summary

    active_accounts = (
        await db.execute(
            select(func.count(Account.id)).where(
                Account.client_id == uuid.UUID(client_id),
                Account.status != AccountStatus.CLOSED,
            )
        )
    ).scalar_one()
    active_cards = (
        await db.execute(
            select(func.count(Card.id)).where(
                Card.client_id == uuid.UUID(client_id),
                Card.status.notin_([CardStatus.CLOSED, CardStatus.EXPIRED]),
            )
        )
    ).scalar_one()
    if active_accounts > 0 or active_cards > 0:
        raise DomainError(409, "CLIENT_HAS_ACTIVE_PRODUCTS", "Cannot delete client with active accounts or cards")
    await db.execute(delete(Client).where(Client.id == uuid.UUID(client_id)))
    await upsert_usage(db, claims["user_id"], "deleted_entities_count")
    await db.commit()
    await emit(
        "client-events",
        "client.deleted",
        {"id": client_id, "hard_delete": False},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="client",
        entity_id=client_id,
    )
    return {"deleted": client_id}


@app.post("/clients/me/accounts", tags=["Accounts"])
async def client_open_account(payload: AccountCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    assert_client_can_operate(client)
    bank = await get_bank(db)
    account = build_account_record(bank_id=bank.id, client_id=client.id, currency=payload.currency, account_type=payload.type)
    db.add(account)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    await emit(
        "account-events",
        "account.opened",
        {"id": str(account.id), "client_id": str(client.id)},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=str(account.id),
    )
    return to_dict(account)


@app.get("/clients/me/accounts", tags=["Accounts"])
async def client_accounts(db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    rows = (
        await db.execute(
            select(Account).where(
                Account.client_id == client.id,
                Account.type != AccountType.DEPOSIT_SIMULATED,
            )
        )
    ).scalars().all()
    if await get_training_mode() and env_flag("TRAINING_INCONSISTENT_STATUS", False):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=201, content=jsonable_encoder([to_dict(r) for r in rows]))
    return [to_dict(r) for r in rows]


@app.get("/clients/me/accounts/{account_id}", tags=["Accounts"])
async def client_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    account = await db.get(Account, uuid.UUID(account_id))
    if not account or account.client_id != client.id:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    return to_dict(account)


@app.delete("/clients/me/accounts/{account_id}", tags=["Accounts"])
async def client_delete_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    account = await db.get(Account, uuid.UUID(account_id))
    if not account or account.client_id != client.id:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    count = (await db.execute(select(func.count(Account.id)).where(Account.client_id == client.id))).scalar_one()
    if count <= 1:
        raise DomainError(409, "LAST_ACCOUNT_DELETE_FORBIDDEN", "Cannot delete last account")
    if Decimal(account.balance) != Decimal("0"):
        raise DomainError(409, "ACCOUNT_NON_ZERO_BALANCE", "Account balance must be zero")
    ensure_transition(account.status, AccountStatus.CLOSED, ACCOUNT_TRANSITIONS, "Account")
    account.status = AccountStatus.CLOSED
    account.closed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(account)
    await emit(
        "account-events",
        "account.closed",
        {"id": account_id, "client_id": str(client.id), "status": account.status.value},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=account_id,
    )
    return to_dict(account)


@app.delete("/clients/me/accounts/{account_id}/hard-delete", tags=["Accounts"])
async def client_hard_delete_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    account = await get_account_or_404(db, account_id)
    if account.client_id != client.id:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    await hard_delete_account(db, account, allow_non_zero_balance=False)
    await upsert_usage(db, claims["user_id"], "deleted_entities_count")
    await db.commit()
    await emit(
        "account-events",
        "account.deleted",
        {"id": account_id, "client_id": str(client.id), "hard_delete": True},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=account_id,
    )
    return {"deleted_account_id": account_id, "hard_delete": True}


@app.post("/employees/clients/{client_id}/accounts", tags=["Accounts"])
async def employee_open_client_account(client_id: str, payload: AccountCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    bank = await get_bank(db)
    account = build_account_record(bank_id=bank.id, client_id=client.id, currency=payload.currency, account_type=payload.type)
    db.add(account)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    await emit(
        "account-events",
        "account.opened",
        {"id": str(account.id), "client_id": str(client.id)},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=str(account.id),
    )
    return to_dict(account)


@app.get("/employees/clients/{client_id}/accounts", tags=["Accounts"])
async def employee_client_accounts(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    rows = (
        await db.execute(
            select(Account).where(
                Account.client_id == client.id,
                Account.type != AccountType.DEPOSIT_SIMULATED,
            )
        )
    ).scalars().all()
    return [to_dict(r) for r in rows]


async def account_status_change(db: AsyncSession, account_id: str, status: AccountStatus, employee_user_id: str):
    account = await db.get(Account, uuid.UUID(account_id))
    if not account:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    client = await db.get(Client, account.client_id)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    ensure_employee_owns_client(client, employee_user_id)
    ensure_transition(account.status, status, ACCOUNT_TRANSITIONS, "Account")
    account.status = status
    if status == AccountStatus.CLOSED:
        account.closed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(account)
    await emit(
        "account-events",
        f"account.{status.value.lower()}",
        {"id": account_id, "status": status.value},
        ws_event="account.blocked" if status == AccountStatus.BLOCKED else None,
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=account_id,
    )
    return to_dict(account)


@app.patch("/employees/accounts/{account_id}/block", tags=["Accounts"])
async def employee_block_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await account_status_change(db, account_id, AccountStatus.BLOCKED, claims["user_id"])


@app.patch("/employees/accounts/{account_id}/unblock", tags=["Accounts"])
async def employee_unblock_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await account_status_change(db, account_id, AccountStatus.ACTIVE, claims["user_id"])


@app.patch("/employees/accounts/{account_id}/close", tags=["Accounts"])
async def employee_close_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await account_status_change(db, account_id, AccountStatus.CLOSED, claims["user_id"])


@app.delete("/employees/accounts/{account_id}", tags=["Accounts"])
async def employee_delete_account(account_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    account = await get_account_or_404(db, account_id)
    client = await db.get(Client, account.client_id)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    ensure_employee_owns_client(client, claims["user_id"])
    await hard_delete_account(db, account, allow_non_zero_balance=True)
    await upsert_usage(db, claims["user_id"], "deleted_entities_count")
    await db.commit()
    await emit(
        "account-events",
        "account.deleted",
        {"id": account_id, "client_id": str(client.id), "hard_delete": True},
        scope_student_ids=client_scope_student_ids(client),
        entity_type="account",
        entity_id=account_id,
    )
    return {"deleted_account_id": account_id, "client_id": str(client.id), "hard_delete": True}


@app.post("/employees/clients/{client_id}/cards", tags=["Cards"])
async def employee_issue_card(client_id: str, payload: CardCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    account = await db.get(Account, uuid.UUID(payload.account_id))
    if not account or str(account.client_id) != client_id:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if account.status == AccountStatus.CLOSED:
        raise DomainError(409, "ACCOUNT_CLOSED", "Cannot issue card for closed account")
    card = Card(
        client_id=uuid.UUID(client_id),
        account_id=uuid.UUID(payload.account_id),
        pan_masked=f"2200 **** **** {uuid.uuid4().hex[:4]}",
        tokenized_pan=uuid.uuid4().hex,
        cardholder_name="Demo User",
        expiry_month=12,
        expiry_year=datetime.now(UTC).year + 3,
        network=payload.network,
        type=payload.type,
        status=CardStatus.ISSUED,
    )
    db.add(card)
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    await emit(
        "card-events",
        "card.issued",
        {"id": str(card.id), "client_id": client_id},
        ws_event="card.issued",
        scope_student_ids=client_scope_student_ids(client),
        entity_type="card",
        entity_id=str(card.id),
    )
    return to_dict(card)


@app.get("/clients/me/cards", tags=["Cards"])
async def client_cards(db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    rows = (await db.execute(select(Card).where(Card.client_id == client.id))).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/employees/clients/{client_id}/cards", tags=["Cards"])
async def employee_cards(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    rows = (await db.execute(select(Card).where(Card.client_id == client.id))).scalars().all()
    return [to_dict(r) for r in rows]


async def update_card_status(db: AsyncSession, card_id: str, status: CardStatus, employee_user_id: str, reason: str | None = None):
    card = await db.get(Card, uuid.UUID(card_id))
    if not card:
        raise DomainError(404, "CARD_NOT_FOUND", "Card not found")
    client = await db.get(Client, card.client_id)
    if not client:
        raise DomainError(404, "CLIENT_NOT_FOUND", "Client not found")
    ensure_employee_owns_client(client, employee_user_id)
    from common.state_machines import CARD_TRANSITIONS

    ensure_transition(card.status, status, CARD_TRANSITIONS, "Card")
    card.status = status
    card.blocked_reason = reason
    await db.commit()
    await db.refresh(card)
    await emit(
        "card-events",
        f"card.{status.value.lower()}",
        {"id": card_id, "status": status.value},
        ws_event="card.blocked" if status in {CardStatus.BLOCKED, CardStatus.TEMP_BLOCKED} else None,
        scope_student_ids=client_scope_student_ids(client),
        entity_type="card",
        entity_id=card_id,
    )
    return to_dict(card)


@app.patch("/employees/cards/{card_id}/block", tags=["Cards"])
async def block_card(card_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await update_card_status(db, card_id, CardStatus.BLOCKED, claims["user_id"], "Manual block")


@app.patch("/employees/cards/{card_id}/temp-block", tags=["Cards"])
async def temp_block_card(card_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await update_card_status(db, card_id, CardStatus.TEMP_BLOCKED, claims["user_id"], "Temporary block")


@app.patch("/employees/cards/{card_id}/activate", tags=["Cards"])
async def activate_card(card_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await update_card_status(db, card_id, CardStatus.ACTIVE, claims["user_id"])


@app.patch("/employees/cards/{card_id}/close", tags=["Cards"])
async def close_card(card_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    return await update_card_status(db, card_id, CardStatus.CLOSED, claims["user_id"])


async def execute_transfer(
    session: AsyncSession,
    source: Account,
    target: Account,
    source_amount: Decimal,
    target_amount: Decimal,
) -> None:
    source.available_balance = Decimal(source.available_balance) - source_amount
    source.balance = Decimal(source.balance) - source_amount
    target.available_balance = Decimal(target.available_balance) + target_amount
    target.balance = Decimal(target.balance) + target_amount


def build_account_record(
    *,
    bank_id: uuid.UUID,
    client_id: uuid.UUID,
    currency: Currency,
    account_type: AccountType,
    account_number: str | None = None,
    balance: Decimal | int | str = 0,
    available_balance: Decimal | int | str = 0,
) -> Account:
    return Account(
        bank_id=bank_id,
        client_id=client_id,
        account_number=account_number or fake_account_number(),
        currency=currency,
        type=account_type,
        status=AccountStatus.ACTIVE,
        balance=balance,
        available_balance=available_balance,
        hold_amount=0,
        overdraft_limit=0,
    )


def build_default_client_account(*, bank_id: uuid.UUID, client_id: uuid.UUID) -> Account:
    return build_account_record(
        bank_id=bank_id,
        client_id=client_id,
        currency=Currency.RUB,
        account_type=AccountType.CURRENT,
    )


async def create_transfer(
    db: AsyncSession,
    bank_id: uuid.UUID,
    source: Account,
    target: Account,
    amount: Decimal,
    currency: Currency,
    transfer_type: TransferType,
    initiated_by_role: str,
    description: str | None,
    idempotency_key: str | None,
):
    if idempotency_key:
        existing = (await db.execute(select(Transfer).where(Transfer.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing:
            return existing

    target_amount, exchange_rate = await compute_transfer_amounts(
        db,
        source_currency=source.currency,
        target_currency=target.currency,
        source_amount=amount,
    )

    transfer = Transfer(
        bank_id=bank_id,
        source_account_id=source.id,
        target_account_id=target.id,
        amount=amount,
        currency=source.currency,
        exchange_rate=exchange_rate,
        fee_amount=0,
        description=description,
        transfer_type=transfer_type,
        initiated_by_role=initiated_by_role,
        status=TransferStatus.CREATED,
        idempotency_key=idempotency_key,
    )
    db.add(transfer)
    transfer.status = TransferStatus.PENDING_ANTI_FRAUD
    transfer.status = TransferStatus.PENDING_EXECUTION
    transfer.status = TransferStatus.PROCESSING

    if await get_training_mode() and env_flag("TRAINING_RACE_TRANSFER", False):
        # Optional training bug simulation switch.
        pass

    await execute_transfer(db, source, target, amount, target_amount)
    transfer.status = TransferStatus.COMPLETED
    transfer.executed_at = datetime.now(UTC)
    return transfer


async def create_cash_top_up_transfer(
    db: AsyncSession,
    *,
    bank: Bank,
    client: Client,
    account: Account,
    amount: Decimal,
    initiated_by_role: str,
    description: str,
    idempotency_key: str | None,
):
    synthetic = build_account_record(
        bank_id=bank.id,
        client_id=client.id,
        currency=account.currency,
        account_type=AccountType.DEPOSIT_SIMULATED,
        account_number=f"99999{uuid.uuid4().hex[:15]}",
        balance=amount,
        available_balance=amount,
    )
    db.add(synthetic)
    await db.flush()
    return await create_transfer(
        db,
        bank.id,
        synthetic,
        account,
        amount,
        account.currency,
        TransferType.TOP_UP,
        initiated_by_role,
        description,
        idempotency_key,
    )


@app.post("/clients/me/transfers/top-up", tags=["Transfers"])
async def top_up(payload: TransferTopUp, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    account = await get_account_by_ref(db, payload.account_id)
    if not account or account.client_id != client.id or account.type == AccountType.DEPOSIT_SIMULATED:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if account.status == AccountStatus.BLOCKED:
        raise DomainError(409, "ACCOUNT_BLOCKED", "Account is blocked")
    bank = await get_bank(db)
    transfer = await create_cash_top_up_transfer(
        db,
        bank=bank,
        client=client,
        account=account,
        amount=payload.amount,
        initiated_by_role=claims["business_role"],
        description="Top up",
        idempotency_key=payload.idempotency_key,
    )
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    scope = await load_transfer_scope_student_ids(db, account, account)
    await emit(
        "transfer-events",
        "transfer.completed",
        {"id": str(transfer.id), "status": transfer.status.value},
        ws_event="transfer.completed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=str(transfer.id),
    )
    return to_dict(transfer)


@app.post("/clients/me/transfers", tags=["Transfers"])
async def create_client_transfer(payload: TransferCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    source = await get_account_by_ref(db, payload.source_account_id)
    target = await get_account_by_ref(db, payload.target_account_id)
    if not source or not target or source.client_id != client.id:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if source.type == AccountType.DEPOSIT_SIMULATED or target.type == AccountType.DEPOSIT_SIMULATED:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    assert_client_can_operate(client)
    assert_account_outgoing_allowed(source)
    assert_account_incoming_allowed(target)
    if Decimal(source.available_balance) < payload.amount:
        raise DomainError(409, "INSUFFICIENT_FUNDS", "Not enough available balance")
    bank = await get_bank(db)
    transfer = await create_transfer(
        db,
        bank.id,
        source,
        target,
        payload.amount,
        payload.currency or source.currency,
        TransferType.INTERNAL,
        claims["business_role"],
        payload.description,
        payload.idempotency_key,
    )
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    scope = await load_transfer_scope_student_ids(db, source, target)
    await emit(
        "transfer-events",
        "transfer.completed",
        {"id": str(transfer.id), "status": transfer.status.value},
        ws_event="transfer.completed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=str(transfer.id),
    )
    return to_dict(transfer)


@app.post("/clients/me/transfers/self", tags=["Transfers"])
async def create_self_transfer(payload: TransferCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    source = await get_account_by_ref(db, payload.source_account_id)
    target = await get_account_by_ref(db, payload.target_account_id)
    if not source or not target:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if source.client_id != client.id or target.client_id != client.id:
        raise DomainError(403, "FORBIDDEN", "Self transfer only between own accounts")
    if source.type == AccountType.DEPOSIT_SIMULATED or target.type == AccountType.DEPOSIT_SIMULATED:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    assert_account_outgoing_allowed(source)
    assert_account_incoming_allowed(target)
    if Decimal(source.available_balance) < payload.amount:
        raise DomainError(409, "INSUFFICIENT_FUNDS", "Not enough available balance")
    bank = await get_bank(db)
    transfer = await create_transfer(
        db,
        bank.id,
        source,
        target,
        payload.amount,
        payload.currency or source.currency,
        TransferType.SELF,
        claims["business_role"],
        payload.description,
        payload.idempotency_key,
    )
    await db.commit()
    scope = await load_transfer_scope_student_ids(db, source, target)
    await emit(
        "transfer-events",
        "transfer.completed",
        {"id": str(transfer.id), "status": transfer.status.value},
        ws_event="transfer.completed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=str(transfer.id),
    )
    return to_dict(transfer)


@app.get("/clients/me/transfers", tags=["Transfers"])
async def my_transfers(db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    account_ids = (await db.execute(select(Account.id).where(Account.client_id == client.id))).scalars().all()
    rows = (
        await db.execute(
            select(Transfer).where(
                Transfer.source_account_id.in_(account_ids) | Transfer.target_account_id.in_(account_ids)
            )
        )
    ).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/clients/me/transfers/{transfer_id}", tags=["Transfers"])
async def my_transfer(transfer_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    account_ids = (await db.execute(select(Account.id).where(Account.client_id == client.id))).scalars().all()
    try:
        transfer_uuid = uuid.UUID(transfer_id)
    except ValueError:
        raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer not found") from None
    transfer = await db.get(Transfer, transfer_uuid)
    if not transfer or (transfer.source_account_id not in account_ids and transfer.target_account_id not in account_ids):
        raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer not found")
    return to_dict(transfer)


@app.get("/employees/exchange-rates", tags=["Transfers"])
async def employee_exchange_rates(db: AsyncSession = Depends(get_db), _: dict = Depends(require_business_role("EMPLOYEE"))):
    return [exchange_rate_payload(row) for row in await list_exchange_rates(db)]


@app.put("/employees/exchange-rates/{quote_currency}", tags=["Transfers"])
async def employee_set_exchange_rate(
    quote_currency: Currency,
    payload: ExchangeRateUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_business_role("EMPLOYEE")),
):
    row = await get_exchange_rate_or_404(db, quote_currency)
    row.rub_amount = payload.rub_amount
    row.set_by_user_id = uuid.UUID(claims["user_id"])
    await upsert_usage(db, claims["user_id"], "updated_entities_count")
    await db.commit()
    await db.refresh(row)
    return exchange_rate_payload(row)


@app.post("/employees/transfers", tags=["Transfers"])
async def employee_create_transfer(payload: TransferCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    source = await get_account_by_ref(db, payload.source_account_id)
    target = await get_account_by_ref(db, payload.target_account_id)
    if not source or not target:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    if source.type == AccountType.DEPOSIT_SIMULATED or target.type == AccountType.DEPOSIT_SIMULATED:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Account not found")
    assert_account_outgoing_allowed(source)
    assert_account_incoming_allowed(target)
    if Decimal(source.available_balance) < payload.amount:
        raise DomainError(409, "INSUFFICIENT_FUNDS", "Not enough balance")
    bank = await get_bank(db)
    transfer = await create_transfer(
        db,
        bank.id,
        source,
        target,
        payload.amount,
        payload.currency or source.currency,
        TransferType.EMPLOYEE_INITIATED,
        claims["business_role"],
        payload.description,
        payload.idempotency_key,
    )
    await upsert_usage(db, claims["user_id"], "created_entities_count")
    await db.commit()
    scope = await load_transfer_scope_student_ids(db, source, target)
    await emit(
        "transfer-events",
        "transfer.completed",
        {"id": str(transfer.id), "status": transfer.status.value},
        ws_event="transfer.completed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=str(transfer.id),
    )
    return to_dict(transfer)


@app.patch("/employees/transfers/{transfer_id}/cancel", tags=["Transfers"])
async def employee_cancel_transfer(transfer_id: str, db: AsyncSession = Depends(get_db), _: dict = Depends(require_business_role("EMPLOYEE"))):
    transfer = await db.get(Transfer, uuid.UUID(transfer_id))
    if not transfer:
        raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer not found")
    ensure_transition(transfer.status, TransferStatus.CANCELLED, TRANSFER_TRANSITIONS, "Transfer")
    transfer.status = TransferStatus.CANCELLED
    transfer.cancelled_at = datetime.now(UTC)
    await db.commit()
    source = await db.get(Account, transfer.source_account_id)
    target = await db.get(Account, transfer.target_account_id)
    scope = await load_transfer_scope_student_ids(db, source, target)
    await emit(
        "transfer-events",
        "transfer.cancelled",
        {"id": transfer_id, "status": transfer.status.value},
        ws_event="transfer.failed",
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=transfer_id,
    )
    return to_dict(transfer)


@app.patch("/employees/transfers/{transfer_id}/reverse", tags=["Transfers"])
async def employee_reverse_transfer(transfer_id: str, db: AsyncSession = Depends(get_db), _: dict = Depends(require_business_role("EMPLOYEE"))):
    transfer = await db.get(Transfer, uuid.UUID(transfer_id))
    if not transfer:
        raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer not found")
    ensure_transition(transfer.status, TransferStatus.REVERSED, TRANSFER_TRANSITIONS, "Transfer")
    source = await db.get(Account, transfer.source_account_id)
    target = await db.get(Account, transfer.target_account_id)
    if not source or not target:
        raise DomainError(404, "ACCOUNT_NOT_FOUND", "Accounts not found")
    amount = Decimal(transfer.amount)
    target_amount = transfer_target_amount(transfer)
    if Decimal(target.available_balance) < target_amount:
        raise DomainError(409, "REVERSAL_NOT_POSSIBLE", "Target account has insufficient balance for reversal")
    target.available_balance = Decimal(target.available_balance) - target_amount
    target.balance = Decimal(target.balance) - target_amount
    source.available_balance = Decimal(source.available_balance) + amount
    source.balance = Decimal(source.balance) + amount
    transfer.status = TransferStatus.REVERSED
    await db.commit()
    await db.refresh(transfer)
    scope = await load_transfer_scope_student_ids(db, source, target)
    await emit(
        "transfer-events",
        "transfer.reversed",
        {"id": transfer_id, "status": transfer.status.value},
        scope_student_ids=scope,
        entity_type="transfer",
        entity_id=transfer_id,
    )
    return to_dict(transfer)


@app.get("/employees/transfers", tags=["Transfers"])
async def employee_transfers(db: AsyncSession = Depends(get_db), _: dict = Depends(require_business_role("EMPLOYEE"))):
    rows = (await db.execute(select(Transfer).order_by(Transfer.created_at.desc()))).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/employees/transfers/{transfer_id}", tags=["Transfers"])
async def employee_transfer(transfer_id: str, db: AsyncSession = Depends(get_db), _: dict = Depends(require_business_role("EMPLOYEE"))):
    transfer = await db.get(Transfer, uuid.UUID(transfer_id))
    if not transfer:
        raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer not found")
    return to_dict(transfer)


@app.post("/clients/me/tickets", tags=["Support"])
async def create_ticket(payload: TicketCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    ticket = SupportTicket(
        client_id=client.id,
        subject=payload.subject,
        description=payload.description,
        priority=payload.priority,
        category=payload.category,
        status=TicketStatus.NEW,
    )
    db.add(ticket)
    await db.commit()
    await emit(
        "support-events",
        "ticket.created",
        {"id": str(ticket.id), "client_id": str(client.id)},
        ws_event="ticket.created",
        scope_student_ids=client_scope_student_ids(client),
        entity_type="ticket",
        entity_id=str(ticket.id),
    )
    return to_dict(ticket)


@app.get("/clients/me/tickets", tags=["Support"])
async def my_tickets(db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    rows = (await db.execute(select(SupportTicket).where(SupportTicket.client_id == client.id))).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/clients/me/tickets/{ticket_id}", tags=["Support"])
async def my_ticket(ticket_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    ticket = await db.get(SupportTicket, uuid.UUID(ticket_id))
    if not ticket or ticket.client_id != client.id:
        raise DomainError(404, "TICKET_NOT_FOUND", "Ticket not found")
    return to_dict(ticket)


@app.post("/clients/me/tickets/{ticket_id}/messages", tags=["Support"])
async def my_ticket_message(ticket_id: str, payload: TicketMessageCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("CLIENT"))):
    client = await get_my_client_or_404(db, claims["user_id"])
    ticket = await db.get(SupportTicket, uuid.UUID(ticket_id))
    if not ticket or ticket.client_id != client.id:
        raise DomainError(404, "TICKET_NOT_FOUND", "Ticket not found")
    message = SupportTicketMessage(ticket_id=ticket.id, author_type="CLIENT", author_id=uuid.UUID(claims["user_id"]), message=payload.message)
    db.add(message)
    await db.commit()
    await emit(
        "support-events",
        "ticket.message.created",
        {"ticket_id": ticket_id, "id": str(message.id)},
        ws_event="ticket.message.created",
        scope_student_ids=client_scope_student_ids(client),
        entity_type="ticket",
        entity_id=ticket_id,
    )
    return to_dict(message)


@app.get("/employees/tickets", tags=["Support"])
async def employee_tickets(db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    rows = (
        await db.execute(
            select(SupportTicket)
            .join(Client, SupportTicket.client_id == Client.id)
            .where(Client.created_by_employee_id == uuid.UUID(claims["user_id"]))
            .order_by(SupportTicket.created_at.desc())
        )
    ).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/employees/clients/{client_id}/tickets", tags=["Support"])
async def employee_client_tickets(client_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    client = await get_employee_client_or_404(db, client_id, claims["user_id"])
    rows = (
        await db.execute(
            select(SupportTicket).where(SupportTicket.client_id == client.id).order_by(SupportTicket.created_at.desc())
        )
    ).scalars().all()
    return [to_dict(r) for r in rows]


@app.get("/employees/tickets/{ticket_id}", tags=["Support"])
async def employee_ticket(ticket_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    ticket = await get_employee_ticket_or_404(db, ticket_id, claims["user_id"])
    return to_dict(ticket)


@app.patch("/employees/tickets/{ticket_id}/assign", tags=["Support"])
async def assign_ticket(ticket_id: str, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    ticket = await get_employee_ticket_or_404(db, ticket_id, claims["user_id"])
    ticket.employee_id_nullable = uuid.UUID(claims["user_id"])
    await db.commit()
    await db.refresh(ticket)
    scope = await load_ticket_scope_student_ids(db, ticket)
    await emit(
        "support-events",
        "ticket.updated",
        {"id": ticket_id, "status": ticket.status.value},
        ws_event="ticket.updated",
        scope_student_ids=scope,
        entity_type="ticket",
        entity_id=ticket_id,
    )
    return to_dict(ticket)


@app.patch("/employees/tickets/{ticket_id}/status", tags=["Support"])
async def update_ticket_status(ticket_id: str, payload: StatusUpdate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    ticket = await get_employee_ticket_or_404(db, ticket_id, claims["user_id"])
    ensure_transition(ticket.status, payload.status, TICKET_TRANSITIONS, "Ticket")
    ticket.status = payload.status
    if payload.status in (TicketStatus.CLOSED, TicketStatus.RESOLVED):
        ticket.closed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(ticket)
    scope = await load_ticket_scope_student_ids(db, ticket)
    await emit(
        "support-events",
        "ticket.updated",
        {"id": ticket_id, "status": ticket.status.value},
        ws_event="ticket.updated",
        scope_student_ids=scope,
        entity_type="ticket",
        entity_id=ticket_id,
    )
    return to_dict(ticket)


@app.post("/employees/tickets/{ticket_id}/messages", tags=["Support"])
async def employee_ticket_message(ticket_id: str, payload: TicketMessageCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(require_business_role("EMPLOYEE"))):
    ticket = await get_employee_ticket_or_404(db, ticket_id, claims["user_id"])
    message = SupportTicketMessage(ticket_id=ticket.id, author_type="EMPLOYEE", author_id=uuid.UUID(claims["user_id"]), message=payload.message)
    db.add(message)
    await db.commit()
    scope = await load_ticket_scope_student_ids(db, ticket)
    await emit(
        "support-events",
        "ticket.message.created",
        {"ticket_id": ticket_id, "id": str(message.id)},
        ws_event="ticket.message.created",
        scope_student_ids=scope,
        entity_type="ticket",
        entity_id=ticket_id,
    )
    return to_dict(message)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/health"):
        return response
    return response
