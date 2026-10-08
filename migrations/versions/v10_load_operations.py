"""V10: Load operations — resumable bounded owner import dispatch.

Revision ID: nemlab_v10_load_operations
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import migration_text

revision = "nemlab_v10_load_operations"
down_revision = "nemlab_v9_publication_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(migration_text("V10__load_operations.sql")))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE load_operation_child, load_operation"))
