"""Real child-process fixture mirroring ``fetch_fixture`` for grid fetches.

Invocation: ``python grid_fixture.py SCENARIO MARKER --fetch-grid GROUP
REGION DAY OUTPUT`` — the trailing args come from ``GridFetchProcess``
exactly like a real fetch child.
"""

import os
import sys
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from nemlab_core.prices import Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric, Slot
from nemlab_infrastructure.grid.source import GridFetch
from nemlab_infrastructure.prices.batch import Kind
from nemlab_infrastructure.prices.batch import hash as batch_hash
from nemlab_worker.grid import GridOutcome

scenario = sys.argv[1]
marker = Path(sys.argv[2])
mode_args = sys.argv[3:]
output = Path(mode_args[-1])
group = mode_args[1]
region = Region[mode_args[2]]
day = date.fromisoformat(mode_args[3])

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
if scenario == "unauthorised":
    result = GridOutcome.failed("HTTP_401", False)
elif scenario == "power-down" and group == "power":
    result = GridOutcome.failed("HTTP_503", True)
elif scenario == "throttle" and group == "market":
    result = GridOutcome.failed("HTTP_429", True)
else:
    slots = tuple(Slot(Kind.VALUE, Decimal("123.4")) for _ in range(288))
    if group == "market":
        batches = tuple(
            GridBatch(region, metric, "", day, slots)
            for metric in (
                Metric.DEMAND,
                Metric.FLOW_IMPORTS,
                Metric.FLOW_EXPORTS,
            )
        )
    else:
        batches = (
            GridBatch(region, Metric.POWER, "wind", day, slots),
            GridBatch(region, Metric.POWER, "solar_utility", day, slots),
        )
    result = GridOutcome.success(
        GridFetch(batches, datetime.now(UTC), batch_hash(f"grid-{group}"), "fix-1")
    )
output.write_text(result.to_json())
