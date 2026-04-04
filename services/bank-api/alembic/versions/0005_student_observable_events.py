"""student observable events feed

Revision ID: 0005_student_observable_events
Revises: 0004_iam_grafana_access
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0005_student_observable_events"
down_revision = "0004_iam_grafana_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_observable_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("ws_event", sa.String(length=128), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_user_id"], ["student_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_observable_events_student_occurred",
        "student_observable_events",
        ["student_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_student_observable_events_event_type",
        "student_observable_events",
        ["event_type"],
    )

    op.execute("ALTER TABLE student_observable_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE student_observable_events FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_student_observable_events_event_type", table_name="student_observable_events")
    op.drop_index("ix_student_observable_events_student_occurred", table_name="student_observable_events")
    op.drop_table("student_observable_events")
