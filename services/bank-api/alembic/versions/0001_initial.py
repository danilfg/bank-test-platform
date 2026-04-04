"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "banks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(64), nullable=False),
        sa.Column("bik", sa.String(16), nullable=False),
        sa.Column("inn", sa.String(32), nullable=False),
        sa.Column("kpp", sa.String(32), nullable=False),
        sa.Column("ogrn", sa.String(32), nullable=False),
        sa.Column("correspondent_account", sa.String(32), nullable=False),
        sa.Column("legal_address", sa.String(255), nullable=False),
        sa.Column("postal_address", sa.String(255), nullable=False),
        sa.Column("support_phone", sa.String(32), nullable=False),
        sa.Column("support_email", sa.String(128), nullable=False),
        sa.Column("swift_code", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "student_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(128), nullable=False, unique=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(64), nullable=False),
        sa.Column("last_name", sa.String(64), nullable=False),
        sa.Column("system_role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blocked_reason", sa.String(255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_student_users_email", "student_users", ["email"])

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("external_client_code", sa.String(32), nullable=False, unique=True),
        sa.Column("first_name", sa.String(64), nullable=False),
        sa.Column("last_name", sa.String(64), nullable=False),
        sa.Column("middle_name", sa.String(64), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("email", sa.String(128), nullable=False),
        sa.Column("passport_series", sa.String(8), nullable=False),
        sa.Column("passport_number", sa.String(16), nullable=False),
        sa.Column("passport_issued_by", sa.String(255), nullable=False),
        sa.Column("passport_issued_date", sa.Date(), nullable=False),
        sa.Column("tax_id_optional", sa.String(32), nullable=True),
        sa.Column("residency_country", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("is_pep_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("student_user_id", name="uq_client_student_user"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_number", sa.String(32), nullable=False, unique=True),
        sa.Column("iban_optional", sa.String(34), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("available_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("hold_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("overdraft_limit", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("available_balance + overdraft_limit >= 0", name="ck_available_balance_overdraft"),
    )
    op.create_index("ix_accounts_client_id", "accounts", ["client_id"])

    op.create_table(
        "cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pan_masked", sa.String(24), nullable=False),
        sa.Column("tokenized_pan", sa.String(128), nullable=False),
        sa.Column("cardholder_name", sa.String(128), nullable=False),
        sa.Column("expiry_month", sa.BigInteger(), nullable=False),
        sa.Column("expiry_year", sa.BigInteger(), nullable=False),
        sa.Column("network", sa.String(16), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("daily_limit", sa.Numeric(18, 2), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(18, 2), nullable=False),
        sa.Column("contactless_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("blocked_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cards_client_id", "cards", ["client_id"])

    op.create_table(
        "transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bank_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("source_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("target_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("fee_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("transfer_type", sa.String(32), nullable=False),
        sa.Column("initiated_by_role", sa.String(16), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_transfer_idempotency_key"),
    )
    op.create_index("ix_transfers_source_account_id", "transfers", ["source_account_id"])

    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id_nullable", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_users.id"), nullable=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "support_ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_type", sa.String(32), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_system_role", sa.String(16), nullable=True),
        sa.Column("actor_business_role", sa.String(16), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])

    op.create_table(
        "student_resource_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_bucket", sa.Date(), nullable=False),
        sa.Column("request_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("ws_messages_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("graphql_request_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("grpc_request_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("kafka_events_produced", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("kafka_events_consumed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_entities_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_entities_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("deleted_entities_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cpu_seconds_optional", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_memory_mb_optional", sa.Numeric(10, 2), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("student_user_id", "day_bucket", name="uq_usage_student_day"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_jti", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])

    op.create_table(
        "student_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False, unique=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("student_sessions")
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("student_resource_usage")
    op.drop_index("ix_audit_logs_trace_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("support_ticket_messages")
    op.drop_table("support_tickets")
    op.drop_index("ix_transfers_source_account_id", table_name="transfers")
    op.drop_table("transfers")
    op.drop_index("ix_cards_client_id", table_name="cards")
    op.drop_table("cards")
    op.drop_index("ix_accounts_client_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("clients")
    op.drop_index("ix_student_users_email", table_name="student_users")
    op.drop_table("student_users")
    op.drop_table("banks")
