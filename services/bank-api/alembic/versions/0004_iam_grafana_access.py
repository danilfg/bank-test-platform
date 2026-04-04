"""iam grafana access and postgres principal normalization

Revision ID: 0004_iam_grafana_access
Revises: 0003_identity_provisioning
Create Date: 2026-03-13
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0004_iam_grafana_access"
down_revision = "0003_identity_provisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
            'GRAFANA',
            si.username,
            'PENDING',
            jsonb_build_object('migration', '0004'),
            now(),
            now()
        FROM student_identities si
        WHERE NOT EXISTS (
            SELECT 1
            FROM student_identity_accesses sia
            WHERE sia.identity_id = si.id
              AND sia.service_name = 'GRAFANA'
        )
        """
    )

    op.execute(
        """
        UPDATE student_identity_accesses sia
        SET principal = lower('dbu_' || regexp_replace(si.username, '[^a-zA-Z0-9_]+', '_', 'g')),
            updated_at = now()
        FROM student_identities si
        WHERE sia.identity_id = si.id
          AND sia.service_name = 'POSTGRES'
          AND sia.principal LIKE 'pg_%'
        """
    )

    op.execute(
        """
        UPDATE student_identity_accesses sia
        SET principal = si.username,
            updated_at = now()
        FROM student_identities si
        WHERE sia.identity_id = si.id
          AND sia.service_name = 'GRAFANA'
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM student_identity_accesses WHERE service_name = 'GRAFANA'")
