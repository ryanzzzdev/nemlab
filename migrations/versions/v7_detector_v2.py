"""V7: detector v2 event types and per-event evidence detail.

Revision ID: nemlab_v7_detector_v2
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v7_detector_v2"
down_revision = "nemlab_v6_grid_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V7__detector_v2.sql")))


def downgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE grid_event DROP COLUMN detail; "
            "ALTER TABLE grid_event DROP CONSTRAINT grid_event_type_check; "
            "ALTER TABLE grid_event ADD CONSTRAINT grid_event_type_check "
            "CHECK (type IN ('negative_price_run','price_spike','demand_ramp'))"
        )
    )
