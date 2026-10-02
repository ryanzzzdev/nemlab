"""V5: bounded grid import jobs (job/request/event) for GridReplay.

Revision ID: nemlab_v5_grid_import_jobs
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v5_grid_import_jobs"
down_revision = "nemlab_v4_grid_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V5__grid_import_jobs.sql")))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TABLE grid_import_job_event, grid_import_request, grid_import_job"
        )
    )
