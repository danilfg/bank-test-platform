"""student public id for admin ui

Revision ID: 0006_student_public_id
Revises: 0005_student_observable_events
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_student_public_id"
down_revision = "0005_student_observable_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_users", sa.Column("public_id", sa.String(length=32), nullable=True))
    op.create_index("ix_student_users_public_id", "student_users", ["public_id"], unique=True)
    op.execute(
        """
        WITH numbered AS (
            SELECT id, (99 + ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC))::int AS seq
            FROM student_users
            WHERE system_role = 'STUDENT'
        )
        UPDATE student_users su
        SET public_id = CASE
            WHEN numbered.seq <= 9999 THEN 'st-' || LPAD(numbered.seq::text, 4, '0')
            ELSE 'st-' || numbered.seq::text
        END
        FROM numbered
        WHERE su.id = numbered.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_student_users_public_id", table_name="student_users")
    op.drop_column("student_users", "public_id")
