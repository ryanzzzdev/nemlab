"""``PriceImportCommand`` — explicit local operator tool.

``python -m nemlab_infrastructure.prices ...``. Never loads ``.env``
implicitly and never prints credentials. Direct production ingestion
(``start``/``resume``) stays retired: refreshes go through the protected
operator API like the Java backend. Schema migration moved to
``python -m nemlab_infrastructure.migrate``.
"""

import sys
from datetime import date
from uuid import UUID

from nemlab_core.prices import Region
from nemlab_infrastructure.database import create_bounded_engine
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.settings import DatabaseSettings

RETIRED = (
    "Direct ingestion is retired. Submit refreshes through the protected operator API."
)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("start", "resume"):
        print(RETIRED, file=sys.stderr)
        return 2
    try:
        _run(args)
    except Exception as ex:
        print(
            f"Price command failed: {type(ex).__name__}"
            " (details omitted; check inputs, database and OE access)",
            file=sys.stderr,
        )
        return 1
    return 0


def _run(args: list[str]) -> None:
    if not args:
        raise ValueError("no action")
    store = PriceStore(create_bounded_engine(DatabaseSettings()))
    match args[0]:
        case "status":
            print(store.backfill(UUID(args[1])))
        case "history":
            for attempt in store.history(Region[args[1]], date.fromisoformat(args[2])):
                print(attempt)
        case "coverage":
            print(store.coverage(Region[args[1]], date.fromisoformat(args[2])))
        case _:
            raise ValueError(f"unknown action {args[0]!r}")


if __name__ == "__main__":
    raise SystemExit(main())
