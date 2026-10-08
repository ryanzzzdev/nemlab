"""Operator grid-coverage endpoint — pre-import inspection (NEM-082).

Mounted only when ``nemlab.admin.enabled``; ``OperatorBearer`` authenticates
every ``/api/admin/**`` request before these routes run. Reports which
market days and series have stored current revisions; import attempts and
job state stay with the grid-import endpoints.
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from nemlab_api.errors import instant
from nemlab_api.validation import IsoDate
from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.batch import Metric
from nemlab_infrastructure.grid.store import Coverage, GridStore, SeriesKey
from nemlab_infrastructure.prices.store import EARLIEST_DAY

BASE = "/api/admin/v1/grid-coverage"
NO_STORE = {"Cache-Control": "no-store"}

# Market metrics an import always attempts; power fueltech series are
# optional and appear only when stored.
REQUIRED = (Metric.DEMAND, Metric.FLOW_IMPORTS, Metric.FLOW_EXPORTS)


def _series(metric: Metric, series: str, stored: Coverage | None) -> dict[str, Any]:
    if stored is None:
        return {
            "metric": metric.value,
            "series": series,
            "availability": "NOT_IMPORTED",
            "revision": None,
            "retrievedAt": None,
            "valid": None,
            "missing": None,
            "sourceNull": None,
        }
    return {
        "metric": metric.value,
        "series": series,
        "availability": "COMPLETE" if stored.complete else "INCOMPLETE",
        "revision": str(stored.revision),
        "retrievedAt": instant(stored.retrieved_at),
        "valid": stored.valid,
        "missing": stored.missing,
        "sourceNull": stored.source_null,
    }


def _day(day: date, stored: dict[SeriesKey, Coverage]) -> dict[str, Any]:
    have = [stored.get((metric, "")) for metric in REQUIRED]
    if all(c is not None and c.complete for c in have):
        availability = "COMPLETE"
    elif all(c is None for c in have):
        availability = "NOT_IMPORTED"
    else:
        availability = "PARTIAL"
    return {
        "day": str(day),
        "availability": availability,
        "series": [
            _series(metric, "", coverage)
            for metric, coverage in zip(REQUIRED, have, strict=True)
        ]
        + [
            _series(metric, series, coverage)
            for (metric, series), coverage in stored.items()
            if metric is Metric.POWER
        ],
    }


def _validate_range(start: date, end: date) -> None:
    today = datetime.now(NEM_OFFSET).date()
    if (
        start < EARLIEST_DAY
        or not start < end
        or start + timedelta(days=31) < end
        or end > today
    ):
        raise ValueError("Require 1-31 completed NEM market days since 2021-10-01")


def grid_coverage_router(grid: GridStore) -> APIRouter:
    router = APIRouter()

    @router.get(BASE + "/{region}")
    def coverage(region: Region, start: IsoDate, endExclusive: IsoDate) -> Response:
        _validate_range(start, endExclusive)
        stored = grid.coverage_days(region, start, endExclusive)
        days = [
            _day(day, stored.get(day, {}))
            for day in (
                start + timedelta(days=offset)
                for offset in range((endExclusive - start).days)
            )
        ]
        return JSONResponse(
            {
                "region": region.name,
                "start": str(start),
                "endExclusive": str(endExclusive),
                "marketOffset": "+10:00",
                "days": days,
            },
            headers=NO_STORE,
        )

    return router
