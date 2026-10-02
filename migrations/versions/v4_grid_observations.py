"""V4: grid observations (revision/current/attempt) for GridReplay.

Revision ID: nemlab_v4_grid_observations
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v4_grid_observations"
down_revision = "nemlab_baseline_v1_v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V4__grid_observations.sql")))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TABLE grid_import_attempt, grid_current, grid_revision;"
            " DROP FUNCTION reject_immutable_grid_change()"
        )
    )
