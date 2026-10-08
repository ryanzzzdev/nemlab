"""V8: Admin identity — users, requests, grants, tokens, sessions, outbox.

Revision ID: nemlab_v8_admin_identity
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v8_admin_identity"
down_revision = "nemlab_v7_detector_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V8__admin_identity.sql")))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TABLE admin_rate_limit, admin_access_audit,"
            " admin_email_outbox, admin_session, admin_token,"
            " admin_viewer_grant, admin_access_request, admin_user"
        )
    )
