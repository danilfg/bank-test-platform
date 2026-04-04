"""iam jenkins access bootstrap

Revision ID: 0007_iam_jenkins_access
Revises: 0006_student_public_id
Create Date: 2026-03-31
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0007_iam_jenkins_access"
down_revision = "0006_student_public_id"
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
            'JENKINS',
            si.username,
            'PENDING',
            jsonb_build_object('migration', '0007'),
            now(),
            now()
        FROM student_identities si
        WHERE NOT EXISTS (
            SELECT 1
            FROM student_identity_accesses sia
            WHERE sia.identity_id = si.id
              AND sia.service_name = 'JENKINS'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM student_identity_accesses WHERE service_name = 'JENKINS'")
