"""Baseline: the Java Flyway V1-V3 schema, byte-identical.

Revision ID: nemlab_baseline_v1_v3

The packaged ``nemlab_infrastructure/db/migration/*.sql`` files are verbatim
copies of the Java Flyway scripts (their Flyway CRC32 checksums are pinned by
tests), so a fresh ``migrate`` produces exactly the V1-V3 schema and an
``adopt`` of a Java-managed database stamps this revision without replaying
DDL.
"""

import sqlalchemy as sa
from alembic import op

from nemlab_infrastructure.schema import EXPECTED_HISTORY, migration_text

revision = "nemlab_baseline_v1_v3"
down_revision = None
branch_labels = None
depends_on = None

_DROP_ORDER = (
    "simulation_result",
    "simulation_job",
    "simulation_input",
    "refresh_job_event",
    "refresh_request",
    "refresh_job",
    "price_snapshot",
    "price_import_attempt",
    "price_current",
    "price_backfill",
    "price_revision",
)


def upgrade() -> None:
    for _version, _description, script in EXPECTED_HISTORY:
        # Each script is executed verbatim; psycopg3 handles multi-statement SQL.
        op.execute(sa.text(migration_text(script)))


def downgrade() -> None:
    for table in _DROP_ORDER:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    for function in (
        "reject_immutable_simulation_change",
        "require_complete_price_snapshot",
        "reject_immutable_price_change",
    ):
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {function}()"))
