"""NEM-054 bounded coverage probe: NSW1, September 2023, 5-minute series.

Six GETs against OpenElectricity — market metrics (price, demand,
flow_imports, flow_exports) in one request and generation power grouped by
fueltech split into five weekly windows to keep bodies bounded. Computes
per-market-day completeness per series; raw responses are not saved (the
script is the regeneration path).

Day grids follow the M1 conventions: price uses the interval-end grid
(00:05..24:00, end-labelled); grid metrics use the source-label grid
[00:00, 24:00).
"""

import json
import math
import os
import sys
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

MARKET = "https://api.openelectricity.org.au/v4/market/network/NEM"
DATA = "https://api.openelectricity.org.au/v4/data/network/NEM"
OUT = Path(__file__).resolve().parent
NEM = timezone(timedelta(hours=10))


def get(client, endpoint, metrics, start, end, extra=""):
    params = [(m, v) for m, v in {
        "interval": "5m",
        "network_region": "NSW1",
        "primary_grouping": "network_region",
        "date_start": start,
        "date_end": end,
    }.items()]
    params += [("metrics", m) for m in metrics.split(",")]
    uri = f"{endpoint}?{urllib.parse.urlencode(params)}{extra}"
    print("GET", uri)
    r = client.get(uri)
    r.raise_for_status()
    return r.json()


def days_grid(series_rows, end_labelled):
    """Return {market_day: {expected, present, null, min, max}} per series."""
    per_day = defaultdict(list)
    for ts_text, value in series_rows:
        ts = datetime.fromisoformat(ts_text).astimezone(NEM)
        if end_labelled:
            day = (ts.date() if ts.time() != datetime.min.time() else
                   ts.date() - timedelta(days=1))
            in_day = (
                datetime(day.year, day.month, day.day, tzinfo=NEM)
                < ts
                <= datetime(day.year, day.month, day.day, tzinfo=NEM)
                + timedelta(days=1)
            )
        else:
            day = ts.date()
            in_day = True
        if in_day and ts.second == 0 and ts.microsecond == 0:
            per_day[day].append(value)
    out = {}
    for day, values in sorted(per_day.items()):
        numeric = [
            v
            for v in values
            if isinstance(v, (int, float))
            and not isinstance(v, bool)
            and math.isfinite(v)
        ]
        out[str(day)] = {
            "rows": len(values),
            "null": sum(1 for v in values if v is None),
            "numeric": len(numeric),
            "min": min(numeric, default=None),
            "max": max(numeric, default=None),
        }
    return out


def main() -> int:
    key = os.environ.get("OPEN_ELECTRICITY_API_KEY", "")
    if not key.strip():
        print("OPEN_ELECTRICITY_API_KEY required", file=sys.stderr)
        return 1
    client = httpx.Client(
        headers={
            "Authorization": f"Bearer {key}",
            "User-Agent": "NEMLab-coverage-probe/0.1",
        },
        timeout=httpx.Timeout(60.0, connect=10.0),
    )
    summary = {"region": "NSW1", "month": "2023-09", "requests": [], "series": {}}

    market = get(
        client,
        MARKET,
        "price,demand,flow_imports,flow_exports",
        "2023-09-01T00:00:00",
        "2023-10-01T01:00:00",
    )
    summary["requests"].append({"endpoint": MARKET, "metrics": "price,demand,flow_imports,flow_exports", "window": "2023-09-01..2023-10-01"})
    for s in market["data"]:
        for r in s["results"]:
            name = s["metric"] if len(s["results"]) == 1 else f"{s['metric']}:{r['columns']}"
            summary["series"][name] = {
                "unit": s["unit"],
                "days": days_grid(r["data"], end_labelled=(s["metric"] == "price")),
            }

    start = date(2023, 9, 1)
    for week in range(5):
        ws = start + timedelta(days=7 * week)
        we = min(ws + timedelta(days=7), date(2023, 10, 1))
        gen = get(
            client,
            DATA,
            "power",
            f"{ws}T00:00:00",
            f"{we}T01:00:00",
            "&secondary_grouping=fueltech",
        )
        summary["requests"].append({"endpoint": DATA, "metrics": "power", "window": f"{ws}..{we}"})
        for s in gen["data"]:
            for r in s["results"]:
                name = f"power:{r['columns'].get('fueltech', '?')}"
                days = summary["series"].setdefault(
                    name, {"unit": s["unit"], "days": {}}
                )["days"]
                days.update(days_grid(r["data"], end_labelled=False))

    (OUT / "sep2023-nsw1-coverage.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    # Compact per-series overview
    for name, s in sorted(summary["series"].items()):
        d = s["days"]
        full = sum(1 for v in d.values() if v["numeric"] == 288)
        partial = sum(1 for v in d.values() if 0 < v["numeric"] < 288)
        print(f"{name:40s} days={len(d):2d} full={full:2d} partial={partial:2d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
