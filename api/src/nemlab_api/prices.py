"""Public price read endpoints — Java ``PriceReadController`` + ``PriceReadErrors``.

Routes exist only when ``nemlab.data.enabled``; unauthenticated. Bodies are
built as plain dicts in the Java record field order so the JSON contract —
camelCase keys, decimal-string prices, ``Z`` instants — is reproduced
byte-for-byte.
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from nemlab_api.errors import ApiError, instant
from nemlab_api.validation import IsoDate
from nemlab_core import decimal_text
from nemlab_core.prices import INTERVAL_SECONDS, INTERVALS, NEM_OFFSET, Region
from nemlab_infrastructure.prices.store import Coverage, PriceStore

EARLIEST_DAY = date(2021, 10, 1)
NO_STORE = {"Cache-Control": "no-store"}


def _day_coverage(day: date, stored: Coverage | None) -> dict[str, Any]:
    if stored is None:
        return {
            "day": str(day),
            "availability": "NOT_IMPORTED",
            "revision": None,
            "retrievedAt": None,
            "valid": None,
            "missing": None,
            "sourceNull": None,
        }
    return {
        "day": str(day),
        "availability": "COMPLETE" if stored.valid == INTERVALS else "INCOMPLETE",
        "revision": str(stored.revision),
        "retrievedAt": instant(stored.retrieved_at),
        "valid": stored.valid,
        "missing": stored.missing,
        "sourceNull": stored.source_null,
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


def prices_router(prices: PriceStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/prices/{region}/coverage")
    def coverage(region: Region, start: IsoDate, endExclusive: IsoDate) -> Response:
        _validate_range(start, endExclusive)
        stored = prices.coverage_range(region, start, endExclusive)
        days = [
            _day_coverage(day, stored.get(day))
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

    @router.get("/api/v1/prices/{region}/{day}")
    def series(region: Region, day: IsoDate) -> Response:
        _validate_range(day, day + timedelta(days=1))
        stored = prices.coverage(region, day)
        if stored is None:
            raise ApiError(
                404, "PRICE_DAY_NOT_IMPORTED", "No stored prices for this day"
            )
        # Resolve the captured immutable revision, even if a refresh advances
        # the current pointer meanwhile.
        batch = prices.revision(stored.revision)
        midnight = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
        intervals = [
            {
                "start": instant(
                    midnight + timedelta(seconds=index * INTERVAL_SECONDS)
                ),
                "end": instant(
                    midnight + timedelta(seconds=(index + 1) * INTERVAL_SECONDS)
                ),
                "state": slot.kind.name,
                "price": (
                    None
                    if slot.price is None
                    else decimal_text.to_plain_string(slot.price)
                ),
            }
            for index, slot in enumerate(batch.slots)
        ]
        return JSONResponse(
            {
                "region": region.name,
                "day": str(day),
                "source": "Open Electricity",
                "unit": "AUD/MWh",
                "intervalSeconds": INTERVAL_SECONDS,
                "intervalLabel": "END",
                "marketOffset": "+10:00",
                "coverage": _day_coverage(day, stored),
                "intervals": intervals,
            },
            headers=NO_STORE,
        )

    return router
