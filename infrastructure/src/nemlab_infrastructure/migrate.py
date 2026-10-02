"""Schema migration entry point: ``python -m nemlab_infrastructure.migrate ...``.

Wraps Alembic so the operator command mirrors the Java ``prices migrate`` CLI.
The Alembic configuration lives in ``migrations/`` at the repository root;
this command locates it by walking up from the working directory.

Actions:

- ``migrate`` — apply pending revisions (creates the schema on an empty
  database; no-ops once Alembic-managed). Refuses a Java-managed or
  unknown-provenance database — run ``adopt`` on a valid V1-V3 Java
  database first rather than replaying DDL over existing tables.
- ``check`` — report database state: empty / java-managed (adoption status)
  / alembic-managed at revision / unknown.
- ``adopt`` — verify a Java-managed database (Flyway history, checksums and
  schema objects), stamp the baseline revision, then apply later
  migrations. Refuses drifted, partial or unknown databases; Flyway
  history is preserved, never replayed.
- ``stamp`` — force-stamp head without validation (explicit operator repair
  escape hatch; prefer ``adopt``).
"""

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from nemlab_infrastructure.schema import (
    BASELINE_REVISION,
    AdoptionError,
    State,
    inspect_state,
    validate_java_database,
)
from nemlab_infrastructure.settings import DatabaseSettings


def _find_config(start: Path) -> Path:
    for directory in (start, *start.parents):
        candidate = directory / "alembic.ini"
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"nemlab-migrate: no alembic.ini found at or above {start}; "
        "run from the repository checkout"
    )


def _check(settings: DatabaseSettings) -> int:
    engine = create_engine(settings.sqlalchemy_url())
    try:
        state = inspect_state(engine)
        if state is State.ALEMBIC_MANAGED:
            with engine.connect() as conn:
                rev = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
            print(f"alembic-managed at {rev}")
            return 0
        if state is State.JAVA_MANAGED:
            try:
                validate_java_database(engine)
            except AdoptionError as ex:
                print(f"java-managed, adoption refused: {ex}")
                return 1
            print("java-managed, valid V1-V3 flyway schema — run `adopt` to stamp")
            return 0
        print(state.name.lower())
        return 0 if state is not State.UNKNOWN else 1
    finally:
        engine.dispose()


def _migrate(config: Config, settings: DatabaseSettings) -> int:
    engine = create_engine(settings.sqlalchemy_url())
    try:
        state = inspect_state(engine)
    finally:
        engine.dispose()
    if state is State.JAVA_MANAGED:
        print(
            "nemlab-migrate: database is Java-managed — run `adopt` to stamp "
            "the baseline; `migrate` would replay DDL over existing tables",
            file=sys.stderr,
        )
        return 1
    if state is State.UNKNOWN:
        print(
            "nemlab-migrate: schema objects exist with neither "
            "flyway_schema_history nor alembic_version — refusing to migrate "
            "a database of unknown provenance; inspect it manually",
            file=sys.stderr,
        )
        return 1
    command.upgrade(config, "head")
    return 0


def _adopt(config: Config, settings: DatabaseSettings) -> int:
    engine = create_engine(settings.sqlalchemy_url())
    try:
        try:
            validate_java_database(engine)
        except AdoptionError as ex:
            print(f"adoption refused: {ex}", file=sys.stderr)
            return 1
    finally:
        engine.dispose()
    # Stamp only the baseline so the V1-V3 DDL is never replayed over the
    # existing tables, then apply any later revisions for real.
    command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")
    print("stamped baseline; flyway_schema_history preserved")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nemlab-migrate")
    parser.add_argument(
        "action",
        choices=["migrate", "check", "adopt", "stamp"],
        help="migrate=upgrade head; check=report state; "
        "adopt=validate Java DB then stamp; stamp=force mark head without DDL",
    )
    args = parser.parse_args(argv)

    config = Config(str(_find_config(Path.cwd())))
    settings = DatabaseSettings()
    if args.action == "migrate":
        return _migrate(config, settings)
    if args.action == "stamp":
        command.stamp(config, "head")
        return 0
    if args.action == "adopt":
        return _adopt(config, settings)
    return _check(settings)


if __name__ == "__main__":
    raise SystemExit(main())
