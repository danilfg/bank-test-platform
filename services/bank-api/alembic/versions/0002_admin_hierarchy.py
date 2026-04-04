"""admin hierarchy and employee ownership

Revision ID: 0002_admin_hierarchy
Revises: 0001_initial
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0002_admin_hierarchy"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_users", sa.Column("created_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("student_users", sa.Column("is_primary_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("student_users", sa.Column("can_create_admins", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    op.add_column("clients", sa.Column("created_by_employee_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key(
        "fk_student_users_created_by_admin_id",
        "student_users",
        "student_users",
        ["created_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_clients_created_by_employee_id",
        "clients",
        "student_users",
        ["created_by_employee_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("ix_student_users_created_by_admin_id", "student_users", ["created_by_admin_id"])
    op.create_index("ix_clients_created_by_employee_id", "clients", ["created_by_employee_id"])

    op.execute(
        """
        WITH root_admin AS (
            SELECT id
            FROM student_users
            WHERE system_role = 'ADMIN'
            ORDER BY created_at ASC
            LIMIT 1
        )
        UPDATE student_users
        SET
            is_primary_admin = CASE WHEN id = (SELECT id FROM root_admin) THEN true ELSE false END,
            can_create_admins = CASE WHEN id = (SELECT id FROM root_admin) THEN true ELSE false END
        WHERE system_role = 'ADMIN'
        """
    )

    op.execute("UPDATE clients SET created_by_employee_id = student_user_id WHERE created_by_employee_id IS NULL")


def downgrade() -> None:
    op.drop_index("ix_clients_created_by_employee_id", table_name="clients")
    op.drop_index("ix_student_users_created_by_admin_id", table_name="student_users")

    op.drop_constraint("fk_clients_created_by_employee_id", "clients", type_="foreignkey")
    op.drop_constraint("fk_student_users_created_by_admin_id", "student_users", type_="foreignkey")

    op.drop_column("clients", "created_by_employee_id")
    op.drop_column("student_users", "can_create_admins")
    op.drop_column("student_users", "is_primary_admin")
    op.drop_column("student_users", "created_by_admin_id")
