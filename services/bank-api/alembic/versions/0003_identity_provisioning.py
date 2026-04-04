"""identity provisioning registry

Revision ID: 0003_identity_provisioning
Revises: 0002_admin_hierarchy
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0003_identity_provisioning"
down_revision = "0002_admin_hierarchy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("system_role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("requested_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("deprovisioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["student_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_admin_id"], ["student_users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_student_identities_user_id", "student_identities", ["user_id"])
    op.create_index("ix_student_identities_username", "student_identities", ["username"])
    op.create_index("ix_student_identities_status", "student_identities", ["status"])

    op.create_table(
        "student_identity_accesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("identity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_name", sa.String(32), nullable=False),
        sa.Column("principal", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("secret_ref", sa.String(255), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["student_identities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("identity_id", "service_name", name="uq_identity_service"),
    )
    op.create_index("ix_student_identity_accesses_identity_id", "student_identity_accesses", ["identity_id"])
    op.create_index(
        "ix_identity_access_service_status",
        "student_identity_accesses",
        ["service_name", "status"],
    )

    op.execute(
        """
        INSERT INTO student_identities (id, user_id, username, system_role, status, created_at, updated_at)
        SELECT gen_random_uuid(), su.id, su.username, su.system_role, 'ACTIVE', now(), now()
        FROM student_users su
        WHERE NOT EXISTS (
            SELECT 1
            FROM student_identities si
            WHERE si.user_id = su.id
        )
        """
    )
    op.execute(
        """
        INSERT INTO student_identity_accesses (
            id,
            identity_id,
            service_name,
            principal,
            status,
            details_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            si.id,
            svc.service_name,
            CASE
                WHEN svc.service_name = 'GRAFANA' THEN si.username
                ELSE lower(svc.prefix || '_' || regexp_replace(si.username, '[^a-zA-Z0-9_]+', '_', 'g'))
            END,
            CASE
                WHEN svc.service_name IN ('REST_API', 'GRAPHQL', 'GRPC', 'JAEGER') THEN 'ACTIVE'
                ELSE 'PENDING'
            END,
            jsonb_build_object('seeded', true),
            now(),
            now()
        FROM student_identities si
        CROSS JOIN (
            VALUES
                ('POSTGRES', 'dbu'),
                ('KAFKA', 'kafka'),
                ('REDIS', 'redis'),
                ('GRAFANA', 'grafana'),
                ('KIBANA', 'kibana'),
                ('REST_API', 'rest'),
                ('GRAPHQL', 'graphql'),
                ('GRPC', 'grpc'),
                ('JAEGER', 'jaeger')
        ) AS svc(service_name, prefix)
        WHERE NOT EXISTS (
            SELECT 1
            FROM student_identity_accesses sia
            WHERE sia.identity_id = si.id
              AND sia.service_name = svc.service_name
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_identity_access_service_status", table_name="student_identity_accesses")
    op.drop_index("ix_student_identity_accesses_identity_id", table_name="student_identity_accesses")
    op.drop_table("student_identity_accesses")
    op.drop_index("ix_student_identities_status", table_name="student_identities")
    op.drop_index("ix_student_identities_username", table_name="student_identities")
    op.drop_index("ix_student_identities_user_id", table_name="student_identities")
    op.drop_table("student_identities")
