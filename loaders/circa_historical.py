"""Pull historical market odds at Circa Millions decision times.

WHY THIS EXISTS
---------------
The free backtest (docs/circa_line_value_backtest.md) could only compare
Circa's frozen contest line to the CLOSING line, which is lookahead: picks
lock Saturday 4:00pm PT and Sunday games have not closed. To measure the
*knowable* signal we need the market as it stood at the moment Circa's line
froze (Thu) and at the moment picks lock (Sat).

nflverse carries only the closing spread, so that data has to be bought.
The Odds API historical endpoint costs 10 credits per region per market
(vs 1 live), and one call returns every game at that timestamp.

COST (verified against the-odds-api.com pricing 2026-08-22):
    3 seasons x 18 weeks x 2 timestamps           = 108 calls
    108 calls x 10 credits x 1 region x 1 market  = 1,080 credits
    ... x 3 markets (spreads, h2h, totals)        = 3,240 credits
The 20K plan is $30/month. This is a ONE-TIME pull -- subscribe, run, cancel.

ALWAYS RUN `probe` FIRST. It spends a single call to confirm the archive
actually returns data for an old timestamp before you pay for a month.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_KEY = os.environ.get("ODDS_API_KEY", "")
HIST_URL = ("https://api.the-odds-api.com/v4/historical/sports/"
            "americanfootball_nfl/odds")
GAMES_CSV = ("https://raw.githubusercontent.com/nflverse/nfldata/"
             "master/data/games.csv")

# Circa Millions timing, in US Eastern:
#   contest lines post   Thu 10:00am PT = 13:00 ET  -> sample at 13:05
#   picks lock           Sat  4:00pm PT = 19:00 ET  -> sample at 18:45
THU_ET = (13, 5)
SAT_ET = (18, 45)


def week_anchors(seasons: list[int]) -> dict:
    """{(season, week): sunday_date} from nflverse, so we can derive the
    Thursday and Saturday around each slate rather than guessing dates."""
    rows = list(csv.DictReader(io.StringIO(
        requests.get(GAMES_CSV, timeout=90).text)))
    buckets: dict = {}
    for r in rows:
        try:
            s, w = int(r["season"]), int(r["week"])
        except (ValueError, TypeError):
            continue
        if s not in seasons or not r.get("gameday"):
            continue
        buckets.setdefault((s, w), []).append(r["gameday"])
    anchors = {}
    for key, days in buckets.items():
        # the modal gameday is the Sunday slate
        common = Counter(days).most_common(1)[0][0]
        anchors[key] = datetime.strptime(common, "%Y-%m-%d").date()
    return anchors


def _et_to_utc(d, hh, mm):
    """US Eastern -> UTC. NFL season spans the DST change, so pick the offset
    by date: EDT (UTC-4) through the first Sunday in November, else EST (-5)."""
    dst_end = datetime(d.year, 11, 1).date()
    while dst_end.weekday() != 6:
        dst_end += timedelta(days=1)
    offset = 4 if d < dst_end else 5
    return datetime(d.year, d.month, d.day, hh, mm,
                    tzinfo=timezone.utc) + timedelta(hours=offset)


def sample_times(sunday) -> dict:
    """The two timestamps that matter, as UTC ISO8601."""
    thu = sunday - timedelta(days=4)
    sat = sunday - timedelta(days=1)
    return {
        "thu_freeze": _et_to_utc(thu, *THU_ET).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sat_lock": _et_to_utc(sat, *SAT_ET).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _call(iso_ts: str, markets: str, regions: str = "us"):
    r = requests.get(HIST_URL, timeout=60, params={
        "apiKey": API_KEY, "regions": regions, "markets": markets,
        "oddsFormat": "american", "date": iso_ts,
    })
    used = r.headers.get("x-requests-used")
    left = r.headers.get("x-requests-remaining")
    return r, used, left


def probe(markets: str = "spreads"):
    """ONE call against an old timestamp. Verifies coverage before you pay."""
    if not API_KEY:
        print("ODDS_API_KEY not set"); return False
    ts = "2024-09-07T22:45:00Z"          # Sat before NFL 2024 week 1
    r, used, left = _call(ts, markets)
    print(f"probe {ts}  HTTP {r.status_code}  credits used={used} left={left}")
    if r.status_code != 200:
        print("body:", r.text[:400])
        if r.status_code in (401, 403):
            print("\n-> historical odds needs a PAID plan. $30 gets 20k credits;\n"
                  "   this whole pull needs ~3,240. Subscribe, run, cancel.")
        return False
    payload = r.json()
    events = payload.get("data", payload) or []
    print(f"snapshot ts: {payload.get('timestamp')}   events: {len(events)}")
    if events:
        e = events[0]
        books = e.get("bookmakers", [])
        print(f"sample: {e.get('away_team')} @ {e.get('home_team')}  "
              f"bookmakers={len(books)}")
        print("COVERAGE OK -- the archive returns real data for 2024.")
        return True
    print("NO EVENTS at that timestamp -- do NOT pay until this is understood.")
    return False


def estimate(seasons, markets_n=1, per_week=2):
    weeks = len(seasons) * 18
    calls = weeks * per_week
    credits = calls * 10 * markets_n
    print(f"seasons={seasons} weeks={weeks} calls={calls} "
          f"markets={markets_n} -> {credits} credits "
          f"({credits/20000:.1%} of the $30 20K plan)")
    return credits


def pull(seasons, markets: str = "spreads", out_dir: str = "/tmp/circa_hist"):
    """Download both snapshots for every week. Resumable: skips existing files."""
    if not API_KEY:
        print("ODDS_API_KEY not set"); return
    os.makedirs(out_dir, exist_ok=True)
    anchors = week_anchors(seasons)
    n_markets = len(markets.split(","))
    estimate(seasons, n_markets)
    saved = skipped = failed = 0
    for (season, week) in sorted(anchors):
        for label, ts in sample_times(anchors[(season, week)]).items():
            path = os.path.join(out_dir, f"{season}_wk{week:02d}_{label}.json")
            if os.path.exists(path):
                skipped += 1
                continue
            r, used, left = _call(ts, markets)
            if r.status_code != 200:
                print(f"{season} wk{week} {label}: HTTP {r.status_code}")
                failed += 1
                continue
            with open(path, "w") as fh:
                json.dump(r.json(), fh)
            saved += 1
            print(f"{season} wk{week:>2} {label:<10} ts={ts} "
                  f"credits_left={left}", flush=True)
    print(f"\nsaved={saved} skipped={skipped} failed={failed} -> {out_dir}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        probe()
    elif cmd == "estimate":
        estimate([2023, 2024, 2025], markets_n=int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    elif cmd == "pull":
        pull([2023, 2024, 2025])
    else:
        print(__doc__)
