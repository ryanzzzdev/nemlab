"""Schema migration entry point: ``python -m nemlab_infrastructure.migrate ...``.

Wraps Alembic so the operator command mirrors the Java ``prices migrate`` CLI.
The Alembic configuration lives in ``migrations/`` at the repository root;
this command locates it by walking up from the working directory.
"""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config


def _find_config(start: Path) -> Path:
    for directory in (start, *start.parents):
        candidate = directory / "alembic.ini"
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"nemlab-migrate: no alembic.ini found at or above {start}; "
        "run from the repository checkout"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nemlab-migrate")
    parser.add_argument(
        "action",
        choices=["migrate", "check", "stamp"],
        help=(
            "migrate = upgrade head; check = report pending revisions; "
            "stamp = mark head without DDL"
        ),
    )
    args = parser.parse_args(argv)

    config = Config(str(_find_config(Path.cwd())))
    if args.action == "migrate":
        command.upgrade(config, "head")
    elif args.action == "stamp":
        command.stamp(config, "head")
    else:
        command.current(config)


if __name__ == "__main__":
    main()
