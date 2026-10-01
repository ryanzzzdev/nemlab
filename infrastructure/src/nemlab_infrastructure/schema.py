"""V1-V3 schema contract and Java-database adoption - NEM-070.

The Flyway migration scripts are packaged byte-identically in
``nemlab_infrastructure/db/migration/`` so the Alembic baseline replays the
exact DDL and adoption validation re-checks the recorded Flyway checksums
against the same bytes.

``flyway_checksum`` reproduces Flyway 12.x ``ChecksumCalculator``: CRC32 over
each ``BufferedReader.readLine()`` line (terminators excluded, UTF-8 BOM
stripped per line, UTF-8 bytes), truncated to signed int32. Verified against
a real ``flyway_schema_history`` produced by Flyway 12.4.0.
"""

import re
import zlib
from collections.abc import Sequence
from enum import Enum
from importlib import resources
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy import text

MIGRATION_PACKAGE = "nemlab_infrastructure.db.migration"

# (version, description, script) — the three applied Flyway migrations.
EXPECTED_HISTORY: tuple[tuple[str, str, str], ...] = (
    ("1", "price foundation", "V1__price_foundation.sql"),
    ("2", "refresh jobs", "V2__refresh_jobs.sql"),
    ("3", "simulation jobs", "V3__simulation_jobs.sql"),
)

BASELINE_REVISION = "nemlab_baseline_v1_v3"

TABLES = (
    "price_revision",
    "price_current",
    "price_import_attempt",
    "price_snapshot",
    "price_backfill",
    "refresh_job",
    "refresh_request",
    "refresh_job_event",
    "simulation_input",
    "simulation_job",
    "simulation_result",
)

FUNCTIONS = (
    "reject_immutable_price_change",
    "require_complete_price_snapshot",
    "reject_immutable_simulation_change",
)

TRIGGERS = (
    ("immutable_revision", "price_revision"),
    ("immutable_snapshot", "price_snapshot"),
    ("complete_snapshot", "price_snapshot"),
    ("complete_simulation_input", "simulation_input"),
    ("immutable_simulation_input", "simulation_input"),
    ("immutable_simulation_result", "simulation_result"),
)

INDEXES = (
    "price_attempt_history",
    "refresh_job_active_day",
    "refresh_job_ready",
    "simulation_job_ready",
    "simulation_one_running",
)

# Column inventory: (name, udt_name, nullable). Drift detection compares the
# live information_schema against this manifest exactly — extra or missing
# columns both refuse adoption.
COLUMNS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    "price_revision": (
        ("id", "uuid", False),
        ("region", "text", False),
        ("market_day", "date", False),
        ("content_hash", "bpchar", False),
        ("slots", "jsonb", False),
        ("valid_count", "int4", False),
        ("missing_count", "int4", False),
        ("null_count", "int4", False),
        ("created_at", "timestamptz", False),
    ),
    "price_current": (
        ("region", "text", False),
        ("market_day", "date", False),
        ("revision_id", "uuid", False),
        ("retrieved_at", "timestamptz", False),
    ),
    "price_import_attempt": (
        ("id", "uuid", False),
        ("region", "text", False),
        ("market_day", "date", False),
        ("retrieved_at", "timestamptz", False),
        ("status", "text", False),
        ("revision_id", "uuid", True),
        ("response_hash", "bpchar", True),
        ("source_version", "text", True),
        ("diagnostic", "text", True),
    ),
    "price_snapshot": (
        ("id", "uuid", False),
        ("revision_id", "uuid", False),
        ("created_at", "timestamptz", False),
    ),
    "price_backfill": (
        ("id", "uuid", False),
        ("region", "text", False),
        ("start_day", "date", False),
        ("end_exclusive", "date", False),
        ("next_day", "date", False),
        ("status", "text", False),
        ("diagnostic", "text", True),
    ),
    "refresh_job": (
        ("id", "uuid", False),
        ("backfill_id", "uuid", False),
        ("region", "text", False),
        ("market_day", "date", False),
        ("status", "text", False),
        ("attempts", "int4", False),
        ("available_at", "timestamptz", False),
        ("claim_token", "uuid", True),
        ("lease_until", "timestamptz", True),
        ("diagnostic", "text", True),
        ("created_at", "timestamptz", False),
    ),
    "refresh_request": (
        ("request_key", "text", False),
        ("job_id", "uuid", False),
    ),
    "refresh_job_event": (
        ("id", "int8", False),
        ("job_id", "uuid", False),
        ("occurred_at", "timestamptz", False),
        ("actor", "text", False),
        ("action", "text", False),
        ("diagnostic", "text", True),
    ),
    "simulation_input": (
        ("id", "uuid", False),
        ("scenario_key", "bpchar", False),
        ("revision_id", "uuid", False),
        ("request", "jsonb", False),
        ("versions", "jsonb", False),
        ("created_at", "timestamptz", False),
    ),
    "simulation_job": (
        ("id", "uuid", False),
        ("status", "text", False),
        ("attempts", "int4", False),
        ("available_at", "timestamptz", False),
        ("claim_token", "uuid", True),
        ("lease_until", "timestamptz", True),
        ("diagnostic", "text", True),
        ("created_at", "timestamptz", False),
    ),
    "simulation_result": (
        ("id", "uuid", False),
        ("result", "jsonb", False),
        ("created_at", "timestamptz", False),
    ),
}

# CHECK / PK / FK / UNIQUE constraint kind counts per table (c=check, p=pk,
# f=fk, u=unique). PG 18 also records NOT NULL as contype 'n' — excluded.
CONSTRAINTS: dict[str, dict[str, int]] = {
    "price_revision": {"c": 6, "p": 1, "u": 2},
    "price_current": {"p": 1, "f": 1},
    "price_import_attempt": {"c": 2, "p": 1, "f": 1},
    "price_snapshot": {"p": 1, "f": 1},
    "price_backfill": {"c": 4, "p": 1},
    "refresh_job": {"c": 4, "p": 1, "f": 1, "u": 1},
    "refresh_request": {"c": 1, "p": 1, "f": 1},
    "refresh_job_event": {"c": 1, "p": 1, "f": 1},
    "simulation_input": {"c": 2, "p": 1, "f": 1, "u": 1},
    "simulation_job": {"c": 4, "p": 1, "f": 1},
    "simulation_result": {"c": 1, "p": 1, "f": 1},
}


class AdoptionError(RuntimeError):
    pass


class State(Enum):
    EMPTY = "EMPTY"
    JAVA_MANAGED = "JAVA_MANAGED"
    ALEMBIC_MANAGED = "ALEMBIC_MANAGED"
    UNKNOWN = "UNKNOWN"


def migration_text(script: str) -> str:
    return (
        resources.files(MIGRATION_PACKAGE).joinpath(script).read_text(encoding="utf-8")
    )


def flyway_checksum(text: str) -> int:
    """CRC32 over ``readLine()`` semantics: lines split only on \\r\\n/\\r/\\n
    (no Unicode extras), terminators excluded, per-line BOM strip, UTF-8."""
    lines = re.split(r"\r\n|\r|\n", text)
    if lines and lines[-1] == "":
        lines.pop()
    crc = 0
    for line in lines:
        crc = zlib.crc32(line.removeprefix("\ufeff").encode("utf-8"), crc)
    crc &= 0xFFFFFFFF
    return crc - 2**32 if crc >= 2**31 else crc


def inspect_state(engine: sa.engine.Engine) -> State:
    with engine.connect() as conn:
        has_alembic = _exists(conn, "alembic_version")
        has_flyway = _exists(conn, "flyway_schema_history")
        has_tables = bool(
            conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables"
                    " WHERE table_schema = 'public'"
                    " AND table_name NOT IN"
                    " ('alembic_version', 'flyway_schema_history')"
                )
            ).scalar()
        )
    if has_alembic:
        return State.ALEMBIC_MANAGED
    if has_flyway:
        return State.JAVA_MANAGED
    if has_tables:
        return State.UNKNOWN
    return State.EMPTY


def _exists(conn: sa.Connection, table: str) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:n)"), {"n": table}).scalar())


def validate_java_database(engine: sa.engine.Engine) -> None:
    """Verify a Flyway-managed database carries exactly V1-V3 with matching
    checksums and the complete expected schema. Raises ``AdoptionError`` on
    any unknown, drifted or partial state."""
    state = inspect_state(engine)
    if state is State.EMPTY:
        raise AdoptionError(
            "database has no schema objects — run `migrate` instead of `adopt`"
        )
    if state is State.UNKNOWN:
        raise AdoptionError(
            "schema objects exist but flyway_schema_history is absent — "
            "refusing to stamp a database of unknown provenance"
        )
    if state is State.ALEMBIC_MANAGED:
        raise AdoptionError("alembic_version already present — already managed")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT installed_rank, version, description, type, script,"
                " checksum, success FROM flyway_schema_history"
                " ORDER BY installed_rank"
            )
        ).all()
        _check_history(rows)
        _check_schema(conn)


class _HistoryRow(Protocol):
    installed_rank: int
    version: str | None
    description: str
    type: str
    script: str
    checksum: int | None
    success: bool


def _check_history(rows: Sequence[_HistoryRow]) -> None:
    if len(rows) != len(EXPECTED_HISTORY):
        raise AdoptionError(
            f"flyway_schema_history has {len(rows)} rows; expected exactly"
            f" {len(EXPECTED_HISTORY)} (V1-V3)"
        )
    for rank, (version, description, script) in enumerate(EXPECTED_HISTORY, 1):
        row = rows[rank - 1]
        checksum = flyway_checksum(migration_text(script))
        if (
            row.installed_rank != rank
            or row.version != version
            or row.description != description
            or row.type != "SQL"
            or row.script != script
            or row.checksum != checksum
            or not row.success
        ):
            raise AdoptionError(
                f"flyway_schema_history row {rank} drifted:"
                f" ({row.installed_rank}, {row.version}, {row.description},"
                f" {row.type}, {row.script}, {row.checksum}, {row.success})"
                f" != ({rank}, {version}, {description}, SQL, {script},"
                f" {checksum}, true)"
            )


def _check_schema(conn: sa.Connection) -> None:
    missing = [t for t in TABLES if not _exists(conn, t)]
    if missing:
        raise AdoptionError(f"missing tables: {', '.join(missing)}")
    objects = conn.execute(
        text(
            "SELECT table_name, column_name, udt_name, is_nullable"
            " FROM information_schema.columns WHERE table_schema = 'public'"
            " ORDER BY table_name, ordinal_position"
        )
    ).all()
    actual: dict[str, list[tuple[str, str, bool]]] = {}
    for table, name, udt, nullable in objects:
        if table in COLUMNS:
            actual.setdefault(table, []).append((name, udt, nullable == "YES"))
    for table, expected in COLUMNS.items():
        got = sorted(actual.get(table, []))
        want = sorted(expected)
        if got != want:
            diff = set(got).symmetric_difference(want)
            raise AdoptionError(f"table {table} columns drifted: {sorted(diff)}")
    kinds = conn.execute(
        text(
            "SELECT conrelid::regclass::text, contype, count(*)"
            " FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
            " AND contype IN ('c', 'p', 'f', 'u')"
            " GROUP BY conrelid::regclass::text, contype"
        )
    ).all()
    actual_kinds: dict[str, dict[str, int]] = {}
    for table, kind, count in kinds:
        actual_kinds.setdefault(table, {})[kind] = count
    for table, expected_kinds in CONSTRAINTS.items():
        got_kinds = actual_kinds.get(table, {})
        if any(
            got_kinds.get(kind, 0) != count for kind, count in expected_kinds.items()
        ):
            raise AdoptionError(
                f"table {table} constraint drift: expected"
                f" {expected_kinds}, found {got_kinds}"
            )
    present_functions = {
        r[0]
        for r in conn.execute(
            text(
                "SELECT proname FROM pg_proc"
                " WHERE pronamespace = 'public'::regnamespace"
            )
        )
    }
    missing = [f for f in FUNCTIONS if f not in present_functions]
    if missing:
        raise AdoptionError(f"missing functions: {', '.join(missing)}")
    present_triggers = {
        (r[0], r[1])
        for r in conn.execute(
            text(
                "SELECT tgname, tgrelid::regclass::text FROM pg_trigger"
                " WHERE NOT tgisinternal"
            )
        )
    }
    missing = [f"{t} on {r}" for t, r in TRIGGERS if (t, r) not in present_triggers]
    if missing:
        raise AdoptionError(f"missing triggers: {', '.join(missing)}")
    present_indexes = {
        r[0]
        for r in conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
        )
    }
    missing = [i for i in INDEXES if i not in present_indexes]
    if missing:
        raise AdoptionError(f"missing indexes: {', '.join(missing)}")
