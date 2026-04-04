"""currency exchange rates

Revision ID: 0008_currency_exchange_rates
Revises: 0007_iam_jenkins_access
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_currency_exchange_rates"
down_revision = "0007_iam_jenkins_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "currency_exchange_rates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quote_currency", sa.Enum("RUB", "EUR", "USD", name="currency_exchange_quote", native_enum=False), nullable=False),
        sa.Column("rub_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("set_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["set_by_user_id"], ["student_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_currency", name="uq_currency_exchange_quote"),
    )
    op.execute(
        """
        INSERT INTO currency_exchange_rates (id, quote_currency, rub_amount, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'USD', 100, now(), now()),
            (gen_random_uuid(), 'EUR', 120, now(), now())
        """
    )


def downgrade() -> None:
    op.drop_table("currency_exchange_rates")
    sa.Enum(name="currency_exchange_quote").drop(op.get_bind(), checkfirst=True)
