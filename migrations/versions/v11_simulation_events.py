"""V11: Append-only simulation lifecycle events.

Revision ID: nemlab_v11_simulation_events
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v11_simulation_events"
down_revision = "nemlab_v10_load_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V11__simulation_events.sql")))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE simulation_event"))
