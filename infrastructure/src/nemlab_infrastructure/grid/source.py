"""``OeGridSource`` — bounded demand/flow/power retrieval.

Reuses the proven ``OePriceSource`` transport (3 attempts, exponential
backoff, ``Retry-After`` cap, 2 MiB body cap, credential only in the
``Authorization`` header). Grid metrics sit on the provider *source-label*
grid ``[00:00, 24:00)`` — position 0 is 00:00 — unlike interval-end price.
"""

import json
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.grid.batch import GridBatch, Metric, Slot
from nemlab_infrastructure.prices.batch import Kind, hash
from nemlab_infrastructure.prices.source import (
    _TIMESTAMP,
    Clock,
    OePriceSource,
    Sleeper,
    _reject_constant,
    _sub_micro_nonzero,
    _utc_now,
    time_sleep_ms,
)

MARKET_ENDPOINT = "https://api.openelectricity.org.au/v4/market/network/NEM"
DATA_ENDPOINT = "https://api.openelectricity.org.au/v4/data/network/NEM"
MARKET_METRICS = (Metric.DEMAND, Metric.FLOW_IMPORTS, Metric.FLOW_EXPORTS)
MAX_BODY_BYTES = 2_000_000


@dataclass(frozen=True)
class GridFetch:
    """One provider request covering one or more series of a day."""

    series: tuple[GridBatch, ...]
    retrieved_at: datetime
    response_hash: str
    source_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "series", tuple(self.series))
        if not self.series:
            raise ValueError("fetch produced no series")
        keys = [(b.metric, b.series) for b in self.series]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate series in fetch")
        region, day = self.series[0].region, self.series[0].day
        if any((b.region, b.day) != (region, day) for b in self.series):
            raise ValueError("mixed region/day fetch")


class OeGridSource(OePriceSource):
    """Same client/backoff policy as prices; different endpoints and metrics."""

    def __init__(
        self,
        key: str,
        *,
        endpoint: str = MARKET_ENDPOINT,
        data_endpoint: str = DATA_ENDPOINT,
        client: httpx.Client | None = None,
        clock: Clock = _utc_now,
        sleeper: Sleeper = time_sleep_ms,
    ) -> None:
        super().__init__(
            key, endpoint=endpoint, client=client, clock=clock, sleeper=sleeper
        )
        self._data_endpoint = data_endpoint

    def fetch_market(self, region: Region, day: date) -> GridFetch:
        """Demand plus both flow directions in one bounded request."""
        self.check_day(day)
        uri = self._day_uri(
            self._endpoint,
            [m.value for m in MARKET_METRICS],
            region,
            day,
            "primary_grouping=network_region",
        )
        return parse_market(region, day, self._request(uri), self._clock())

    def fetch_power(self, region: Region, day: date) -> GridFetch:
        """All fueltech power series for one market day."""
        self.check_day(day)
        uri = self._day_uri(
            self._data_endpoint,
            ["power"],
            region,
            day,
            "primary_grouping=network_region&secondary_grouping=fueltech",
        )
        return parse_power(region, day, self._request(uri), self._clock())

    @staticmethod
    def _day_uri(
        endpoint: str,
        metrics: list[str],
        region: Region,
        day: date,
        grouping: str,
    ) -> str:
        params = urllib.parse.urlencode(
            [("metrics", m) for m in metrics]
            + [
                ("interval", "5m"),
                ("network_region", region.name),
                ("date_start", f"{day}T00:00:00"),
                ("date_end", f"{day + timedelta(days=1)}T01:00:00"),
            ]
        )
        return f"{endpoint}?{params}&{grouping}"


def parse_market(
    region: Region, day: date, body: str, retrieved: datetime
) -> GridFetch:
    """Strict demand/flow validation; an expected metric absent from a
    200 response is an all-MISSING series, not a transport failure."""
    version, series = _series_slots(
        region, day, body, expected=MARKET_METRICS, power=False
    )
    return GridFetch(series, retrieved, hash(body), version)


def parse_power(region: Region, day: date, body: str, retrieved: datetime) -> GridFetch:
    """All returned fueltech series are kept — optional categories stay
    explicit in storage rather than being silently dropped."""
    version, series = _series_slots(
        region, day, body, expected=(Metric.POWER,), power=True
    )
    return GridFetch(series, retrieved, hash(body), version)


def _series_slots(
    region: Region,
    day: date,
    body: str,
    *,
    expected: tuple[Metric, ...],
    power: bool,
) -> tuple[str, tuple[GridBatch, ...]]:
    try:
        if len(body) > MAX_BODY_BYTES:
            raise ValueError
        root = json.loads(body, parse_float=Decimal, parse_constant=_reject_constant)
        if root.get("success") is not True or not isinstance(root.get("version"), str):
            raise ValueError
        by_metric: dict[str, Any] = {}
        for entry in root["data"]:
            metric = entry.get("metric") if isinstance(entry, dict) else None
            if not isinstance(metric, str) or metric in by_metric:
                raise ValueError
            by_metric[metric] = entry
        batches: list[GridBatch] = []
        for metric in expected:
            entry = by_metric.pop(metric.value, None)
            if entry is None:
                if power:
                    raise ValueError
                batches.append(_absent(region, metric, day))
                continue
            batches.extend(_entry_batches(region, day, metric, entry, power))
        if by_metric:
            raise ValueError  # unrequested metric in the response
        return root["version"], tuple(batches)
    except Exception as ex:
        raise ValueError(
            "Invalid OE grid response (metadata, duplicate, timestamp or value)"
        ) from ex


def _absent(region: Region, metric: Metric, day: date) -> GridBatch:
    return GridBatch(
        region, metric, "", day, tuple(Slot(Kind.MISSING, None) for _ in range(288))
    )


def _entry_batches(
    region: Region, day: date, metric: Metric, entry: dict[str, Any], power: bool
) -> list[GridBatch]:
    if (
        entry.get("network_code") != "NEM"
        or entry.get("interval") != "5m"
        or entry.get("unit") != "MW"
    ):
        raise ValueError
    results = entry["results"]
    if not isinstance(results, list) or not results:
        raise ValueError
    if not power and len(results) != 1:
        raise ValueError
    batches = []
    for result in results:
        columns = result.get("columns")
        if not isinstance(columns, dict) or columns.get("region") != region.name:
            raise ValueError
        key = ""
        if power:
            fueltech = columns.get("fueltech")
            if not isinstance(fueltech, str) or not fueltech or len(fueltech) > 80:
                raise ValueError
            key = fueltech
        rows = result["data"]
        if not isinstance(rows, list):
            raise ValueError
        batches.append(GridBatch(region, metric, key, day, _slots(rows, day)))
    return batches


def _slots(rows: list[Any], day: date) -> tuple[Slot, ...]:
    """Source-label grid ``[00:00, 24:00)`` — position ``seconds/300``.

    Rows at or after next-day 00:00 (the bounded request overshoots to
    01:00) are boundary observations and skipped once validated.
    """
    slots = [Slot(Kind.MISSING, None)] * 288
    seen: set[datetime] = set()
    start = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError
        timestamp_text, raw = row
        if not isinstance(timestamp_text, str) or not _TIMESTAMP.fullmatch(
            timestamp_text
        ):
            raise ValueError
        timestamp = datetime.fromisoformat(timestamp_text)
        if timestamp in seen:
            raise ValueError
        seen.add(timestamp)
        seconds = int((timestamp - start).total_seconds())
        if (
            timestamp.microsecond != 0
            or _sub_micro_nonzero(timestamp_text)
            or seconds % 300 != 0
            or seconds < 0
        ):
            raise ValueError
        if seconds >= 86400:
            continue  # next-day boundary observation
        if raw is not None and (
            not isinstance(raw, (int, float, Decimal)) or isinstance(raw, bool)
        ):
            raise ValueError
        slots[seconds // 300] = (
            Slot(Kind.SOURCE_NULL, None)
            if raw is None
            else Slot(Kind.VALUE, Decimal(str(raw)))
        )
    return tuple(slots)
