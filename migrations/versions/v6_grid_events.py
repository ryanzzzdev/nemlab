"""V6: versioned GridReplay events, replay manifests, catalogue publications.

Revision ID: nemlab_v6_grid_events
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v6_grid_events"
down_revision = "nemlab_v5_grid_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V6__grid_events.sql")))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TABLE grid_detection_run, grid_catalogue_current, "
            "grid_publication_event, grid_publication, grid_replay, grid_event"
        )
    )
