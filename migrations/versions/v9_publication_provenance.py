"""V9: Publication-attempt provenance — actor and request key on runs.

Revision ID: nemlab_v9_publication_provenance
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v9_publication_provenance"
down_revision = "nemlab_v8_admin_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V9__publication_provenance.sql")))


def downgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE grid_detection_run DROP COLUMN actor, DROP COLUMN request_key"
        )
    )
