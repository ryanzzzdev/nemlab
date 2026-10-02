"""``PriceSource`` / ``OePriceSource`` — bounded OpenElectricity retrieval.

Ports the Java adapter: 3 attempts, exponential backoff (1000 << attempt ms)
with ``Retry-After`` honoured up to a 60 s ceiling, 2 MiB response cap, and
credentials carried only in the ``Authorization`` header — never logged.
"""

import email.utils
import json
import logging
import re
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import httpx

from nemlab_core.prices import NEM_OFFSET, Region
from nemlab_infrastructure.prices.batch import Kind, PriceBatch, Slot, hash

DEFAULT_ENDPOINT = "https://api.openelectricity.org.au/v4/market/network/NEM"
EARLIEST_DAY = date(2021, 10, 1)
MAX_BODY_BYTES = 2_000_000
ATTEMPTS = 3

_RESPONSE_HASH = re.compile(r"[0-9a-f]{64}")
_SOURCE_VERSION = re.compile(r"[A-Za-z0-9._+-]{1,80}")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?[+-]\d{2}:\d{2}(:\d{2})?$"
)


class Failure(OSError):
    """Retriable/diagnostic fetch failure; ``code`` is safe to persist."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Fetch:
    batch: PriceBatch
    retrieved_at: datetime
    response_hash: str
    source_version: str

    def __post_init__(self) -> None:
        if not _RESPONSE_HASH.fullmatch(self.response_hash):
            raise ValueError("response hash required")
        if not _SOURCE_VERSION.fullmatch(self.source_version):
            raise ValueError("invalid source version")


class PriceSource(Protocol):
    def fetch(self, region: Region, day: date) -> Fetch: ...


Clock = Callable[[], datetime]
Sleeper = Callable[[int], None]

LOG = logging.getLogger(__name__)


def time_sleep_ms(milliseconds: int) -> None:
    time.sleep(milliseconds / 1000)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class OePriceSource:
    def __init__(
        self,
        key: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        client: httpx.Client | None = None,
        clock: Clock = _utc_now,
        sleeper: Sleeper = time_sleep_ms,
    ) -> None:
        if not key or not key.strip() or "\n" in key or "\r" in key:
            raise ValueError("OE key required")
        self._key = key
        self._endpoint = endpoint
        # connect timeout 10 s, request timeout 30 s (as the Java HttpClient)
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=False
        )
        self._clock = clock
        self._sleeper = sleeper

    def fetch(self, region: Region, day: date) -> Fetch:
        self.check_day(day)
        start = f"{day}T00:00:00"
        end = f"{day + timedelta(days=1)}T00:05:00"
        uri = (
            f"{self._endpoint}?metrics=price&interval=5m&network_region={region.name}"
            "&primary_grouping=network_region"
            f"&date_start={urllib.parse.quote(start, safe='')}"
            f"&date_end={urllib.parse.quote(end, safe='')}"
        )
        return parse(region, day, self._request(uri), self._clock())

    def check_day(self, day: date) -> None:
        today = self._clock().astimezone(NEM_OFFSET).date()
        if day < EARLIEST_DAY or not day < today:
            raise ValueError(
                "require a completed post-five-minute-settlement market day"
            )

    def _request(self, uri: str) -> str:
        """GET with the shared retry policy; returns the response body."""
        headers = {
            "Authorization": f"Bearer {self._key}",
            "User-Agent": "NEMLab-data-ingestion/0.1",
        }
        for attempt in range(ATTEMPTS):
            # The credential travels in the Authorization header and is never
            # logged.
            LOG.info("OE request attempt %d/%d: GET %s", attempt + 1, ATTEMPTS, uri)
            try:
                body, status, retry_after = self._send(uri, headers)
            except (OSError, httpx.HTTPError, UnicodeDecodeError):
                # Includes Failure("RESPONSE_TOO_LARGE") — like the Java
                # LimitedBody, stream faults retry as transport errors.
                LOG.info("OE request attempt %d/%d failed", attempt + 1, ATTEMPTS)
                if attempt == ATTEMPTS - 1:
                    raise Failure("TRANSPORT_RETRIES_EXHAUSTED") from None
                self._sleeper(1000 << attempt)
                continue
            LOG.info("OE response: HTTP %d", status)
            if status == 200:
                return body
            if (status == 429 or status >= 500) and attempt < ATTEMPTS - 1:
                delay = max(1000 << attempt, _retry_after_ms(retry_after, self._clock))
                if delay > 60_000:
                    raise Failure("RETRY_AFTER_EXCEEDS_BUDGET")
                self._sleeper(delay)
                continue
            raise Failure(f"HTTP_{status}")
        raise RuntimeError("unreachable retry state")

    def _send(self, uri: str, headers: dict[str, str]) -> tuple[str, int, str]:
        """One GET; bodies over the cap are cancelled mid-stream and raised
        as transport failures, exactly like the Java ``LimitedBody``."""
        with self._client.stream("GET", uri, headers=headers) as response:
            if response.status_code != 200:
                response.read()
                return "", response.status_code, response.headers.get("retry-after", "")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BODY_BYTES:
                    raise Failure("RESPONSE_TOO_LARGE")
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8"), 200, ""


def _retry_after_ms(header: str, clock: Clock) -> int:
    """Java: integer seconds else RFC-1123 instant; malformed → 0."""
    try:
        return int(header) * 1000
    except ValueError:
        pass
    try:
        at = email.utils.parsedate_to_datetime(header)
        return int((at - clock()).total_seconds() * 1000)
    except (TypeError, ValueError):
        return 0


def parse(region: Region, day: date, body: str, retrieved: datetime) -> Fetch:
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("OE price response too large")
    try:
        root = json.loads(body, parse_float=Decimal, parse_constant=_reject_constant)
        if root.get("success") is not True:
            raise ValueError
        series = root["data"]
        if len(series) != 1:
            raise ValueError
        s = series[0]
        if (
            s.get("network_code") != "NEM"
            or s.get("metric") != "price"
            or s.get("interval") != "5m"
            or s.get("unit") != "$/MWh"
        ):
            raise ValueError
        results = s["results"]
        if len(results) != 1 or results[0]["columns"].get("region") != region.name:
            raise ValueError
        slots = [Slot(Kind.MISSING, None)] * 288
        seen: set[datetime] = set()
        start = datetime(day.year, day.month, day.day, tzinfo=NEM_OFFSET)
        end = start + timedelta(days=1)
        for row in results[0]["data"]:
            if len(row) != 2:
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
            if timestamp == start or timestamp == end + timedelta(seconds=300):
                continue
            seconds = int((timestamp - start).total_seconds())
            if (
                timestamp.microsecond != 0
                or _sub_micro_nonzero(timestamp_text)
                or seconds <= 0
                or seconds > 86400
                or seconds % 300 != 0
            ):
                raise ValueError
            if raw is not None and (
                not isinstance(raw, (int, float, Decimal)) or isinstance(raw, bool)
            ):
                raise ValueError
            slots[seconds // 300 - 1] = (
                Slot(Kind.SOURCE_NULL, None)
                if raw is None
                else Slot(Kind.VALUE, Decimal(str(raw)))
            )
        return Fetch(
            PriceBatch(region, day, tuple(slots)), retrieved, hash(body), _version(root)
        )
    except Exception as ex:
        raise ValueError(
            "Invalid OE price response (metadata, duplicate, timestamp or value)"
        ) from ex


def _sub_micro_nonzero(timestamp_text: str) -> bool:
    """fromisoformat truncates past microseconds; Java rejects any nonzero
    nanos, so a truncated-but-nonzero sub-micro fraction is still invalid."""
    fraction = timestamp_text.split(".", 1)[-1]
    fraction = re.split(r"[+-]", fraction, maxsplit=1)[0]
    return "." in timestamp_text and int(fraction) != 0


def _reject_constant(_constant: str) -> None:
    """Jackson rejects NaN/Infinity literals; Python json accepts them."""
    raise ValueError


def _version(root: dict[str, Any]) -> str:
    version = root.get("version")
    if not isinstance(version, str):
        raise ValueError
    return version
