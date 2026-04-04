from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base
from common.enums import (
    AccountStatus,
    AccountType,
    BusinessRole,
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


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Bank(Base, TimestampMixin):
    __tablename__ = "banks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    bik: Mapped[str] = mapped_column(String(16), nullable=False)
    inn: Mapped[str] = mapped_column(String(32), nullable=False)
    kpp: Mapped[str] = mapped_column(String(32), nullable=False)
    ogrn: Mapped[str] = mapped_column(String(32), nullable=False)
    correspondent_account: Mapped[str] = mapped_column(String(32), nullable=False)
    legal_address: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_address: Mapped[str] = mapped_column(String(255), nullable=False)
    support_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    support_email: Mapped[str] = mapped_column(String(128), nullable=False)
    swift_code: Mapped[str] = mapped_column(String(16), nullable=False)


class CurrencyExchangeRate(Base, TimestampMixin):
    __tablename__ = "currency_exchange_rates"

    __table_args__ = (UniqueConstraint("quote_currency", name="uq_currency_exchange_quote"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_currency: Mapped[Currency] = mapped_column(
        Enum(Currency, name="currency_exchange_quote", native_enum=False),
        nullable=False,
    )
    rub_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_users.id", ondelete="SET NULL"),
        nullable=True,
    )


class StudentUser(Base, TimestampMixin):
    __tablename__ = "student_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    system_role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="system_role", native_enum=False), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id"))
    is_primary_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_create_admins: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    client: Mapped[Client | None] = relationship(
        back_populates="student_user",
        uselist=False,
        foreign_keys="Client.student_user_id",
    )
    identity: Mapped[StudentIdentity | None] = relationship(
        back_populates="user",
        uselist=False,
        foreign_keys="StudentIdentity.user_id",
    )


class StudentIdentity(Base, TimestampMixin):
    __tablename__ = "student_identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    system_role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="identity_system_role", native_enum=False),
        nullable=False,
    )
    status: Mapped[IdentityStatus] = mapped_column(
        Enum(IdentityStatus, name="identity_status", native_enum=False),
        nullable=False,
        default=IdentityStatus.PENDING,
        index=True,
    )
    requested_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    deprovisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[StudentUser | None] = relationship(
        back_populates="identity",
        foreign_keys=[user_id],
    )
    accesses: Mapped[list[StudentIdentityAccess]] = relationship(
        back_populates="identity",
        cascade="all, delete-orphan",
    )


class StudentIdentityAccess(Base, TimestampMixin):
    __tablename__ = "student_identity_accesses"

    __table_args__ = (
        UniqueConstraint("identity_id", "service_name", name="uq_identity_service"),
        Index("ix_identity_access_service_status", "service_name", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_identities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_name: Mapped[str] = mapped_column(String(32), nullable=False)
    principal: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[IdentityAccessStatus] = mapped_column(
        Enum(IdentityAccessStatus, name="identity_access_status", native_enum=False),
        nullable=False,
        default=IdentityAccessStatus.PENDING,
    )
    secret_ref: Mapped[str | None] = mapped_column(String(255))
    details_json: Mapped[dict | None] = mapped_column(JSON)
    last_error: Mapped[str | None] = mapped_column(Text)
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    identity: Mapped[StudentIdentity] = relationship(back_populates="accesses")


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    __table_args__ = (UniqueConstraint("student_user_id", name="uq_client_student_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False)
    created_by_employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id"))
    bank_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("banks.id"), nullable=False)
    external_client_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(64))
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False)
    passport_series: Mapped[str] = mapped_column(String(8), nullable=False)
    passport_number: Mapped[str] = mapped_column(String(16), nullable=False)
    passport_issued_by: Mapped[str] = mapped_column(String(255), nullable=False)
    passport_issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    tax_id_optional: Mapped[str | None] = mapped_column(String(32))
    residency_country: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status", native_enum=False), nullable=False, default=ClientStatus.NEW
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", native_enum=False), nullable=False, default=RiskLevel.LOW
    )
    is_pep_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    student_user: Mapped[StudentUser] = relationship(
        back_populates="client",
        foreign_keys=[student_user_id],
    )


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    __table_args__ = (
        CheckConstraint("available_balance + overdraft_limit >= 0", name="ck_available_balance_overdraft"),
        Index("ix_accounts_client_id", "client_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("banks.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    account_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    iban_optional: Mapped[str | None] = mapped_column(String(34))
    currency: Mapped[Currency] = mapped_column(Enum(Currency, name="currency", native_enum=False), nullable=False)
    type: Mapped[AccountType] = mapped_column(Enum(AccountType, name="account_type", native_enum=False), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    available_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    hold_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    overdraft_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status", native_enum=False), nullable=False, default=AccountStatus.DRAFT
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(String(255))


class Card(Base, TimestampMixin):
    __tablename__ = "cards"

    __table_args__ = (Index("ix_cards_client_id", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    pan_masked: Mapped[str] = mapped_column(String(24), nullable=False)
    tokenized_pan: Mapped[str] = mapped_column(String(128), nullable=False)
    cardholder_name: Mapped[str] = mapped_column(String(128), nullable=False)
    expiry_month: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expiry_year: Mapped[int] = mapped_column(BigInteger, nullable=False)
    network: Mapped[CardNetwork] = mapped_column(
        Enum(CardNetwork, name="card_network", native_enum=False), nullable=False
    )
    type: Mapped[CardType] = mapped_column(Enum(CardType, name="card_type", native_enum=False), nullable=False)
    status: Mapped[CardStatus] = mapped_column(
        Enum(CardStatus, name="card_status", native_enum=False), nullable=False, default=CardStatus.ORDERED
    )
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=50000)
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=500000)
    contactless_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255))


class Transfer(Base, TimestampMixin):
    __tablename__ = "transfers"

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transfer_idempotency_key"),
        Index("ix_transfers_source_account_id", "source_account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("banks.id"), nullable=False)
    source_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    target_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        Enum(Currency, name="transfer_currency", native_enum=False), nullable=False
    )
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=1)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(255))
    transfer_type: Mapped[TransferType] = mapped_column(
        Enum(TransferType, name="transfer_type", native_enum=False), nullable=False
    )
    initiated_by_role: Mapped[BusinessRole | None] = mapped_column(
        Enum(BusinessRole, name="business_role", native_enum=False), nullable=True
    )
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus, name="transfer_status", native_enum=False), nullable=False, default=TransferStatus.CREATED
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    employee_id_nullable: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id"))
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticket_priority", native_enum=False), nullable=False
    )
    category: Mapped[TicketCategory] = mapped_column(
        Enum(TicketCategory, name="ticket_category", native_enum=False), nullable=False
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status", native_enum=False), nullable=False, default=TicketStatus.NEW
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportTicketMessage(Base):
    __tablename__ = "support_ticket_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_system_role: Mapped[SystemRole | None] = mapped_column(
        Enum(SystemRole, name="audit_system_role", native_enum=False)
    )
    actor_business_role: Mapped[BusinessRole | None] = mapped_column(
        Enum(BusinessRole, name="audit_business_role", native_enum=False)
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StudentResourceUsage(Base):
    __tablename__ = "student_resource_usage"

    __table_args__ = (UniqueConstraint("student_user_id", "day_bucket", name="uq_usage_student_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False)
    day_bucket: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    ws_messages_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    graphql_request_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    grpc_request_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    kafka_events_produced: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    kafka_events_consumed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_entities_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_entities_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    deleted_entities_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_cpu_seconds_optional: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_memory_mb_optional: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StudentObservableEvent(Base):
    __tablename__ = "student_observable_events"

    __table_args__ = (
        Index("ix_student_observable_events_student_occurred", "student_user_id", "occurred_at"),
        Index("ix_student_observable_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    ws_event: Mapped[str | None] = mapped_column(String(128))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StudentSession(Base):
    __tablename__ = "student_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
