"""Real child-process fixture mirroring the Java ``FetchFixture``: scenarios
with no live OE traffic. Marker file carries ``pid`` then the output path.

Invocation: ``python fetch_fixture.py SCENARIO MARKER --fetch-price REGION
DAY OUTPUT`` — the extra args come from ``PriceFetchProcess`` exactly like a
real fetch child.
"""

import os
import sys
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from nemlab_core.prices import Region
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot
from nemlab_infrastructure.prices.batch import hash as batch_hash
from nemlab_infrastructure.prices.source import Fetch
from nemlab_worker.refresh import FetchOutcome

scenario = sys.argv[1]
marker = Path(sys.argv[2])
output = Path(sys.argv[-1])

marker.write_text(f"{os.getpid()}\n{output}")

if os.environ.get("NEMLAB_DB_PASSWORD"):
    raise RuntimeError("Database secret inherited by child")

if scenario == "hang":
    time.sleep(60)
    sys.exit(0)
if scenario == "crash":
    sys.exit(7)
if scenario == "malformed":
    output.write_text("not-json")
    sys.exit(0)
if scenario == "huge":
    output.write_text(" " * 300_000)
    sys.exit(0)

if scenario == "unauthorised":
    result = FetchOutcome.failed("HTTP_401", False)
else:
    slots = tuple(Slot(Kind.VALUE, Decimal("42.5")) for _ in range(288))
    batch = PriceBatch(Region[sys.argv[4]], date.fromisoformat(sys.argv[5]), slots)
    result = FetchOutcome.success(
        Fetch(batch, datetime.now(UTC), batch_hash("worker-fixture"), "fixture-1")
    )
output.write_text(result.to_json())
