"""
OPENING-LINE BACKFILL — buy the pre-kickoff market for a season already played.

WHY THIS EXISTS
---------------
nflverse games.csv carries ONE line per game: the close. nflverse_loader.py
writes that same dict into BOTH snapshots it creates (kickoff-120h as the
"available" price and kickoff as the close), because there is nothing else to
write. Identical prices mean no line movement, and no line movement means CLV
grades to exactly 0.0 for every backtest pick — see the 2026-08-26 note in
PROGRESS.md, found when the EndZone agent's 208 picks all came back 0.0.

A LIVE season does not have this problem and does not need this file:
scheduler.py's `tue-open` slot captures a genuine opener every week at 1
credit. Only a season already played has to be bought back, from The Odds API
historical archive at 10 credits per region per market.

COST, one season, all three markets:
    18 weeks x 1 call x 3 markets x 10 credits = 540 credits
(One call returns every game at that timestamp, so it is per WEEK, not
per game.)

TIMESTAMP: Tuesday 12:00 ET, deliberately matching scheduler.py's `tue-open`
slot so backfilled history looks exactly like what the live cadence will
produce from Week 1 onward. It also sits before kickoff-24h for every slot
including Thursday night (TNF's kickoff-24h is Wednesday evening), which is
when agents price their picks.

THE SYNTHETIC ROWS: `apply` deletes the fabricated kickoff-120h snapshot for a
game only when its numbers are byte-identical to that game's closing snapshot,
which is the signature nflverse_loader leaves. A row that differs is real data
and is never touched. Nothing else is deleted, and the closing snapshot always
survives.

Run:
    python loaders/opening_lines.py fetch 2025           # SPENDS ~540 credits
    python loaders/opening_lines.py apply 2025           # dry run, no writes
    python loaders/opening_lines.py apply 2025 --write   # writes to the DB
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from loaders.circa_historical import (            # noqa: E402
    API_KEY, HIST_URL, _et_to_utc, week_anchors,
)
from loaders.real_data import TEAM_ABBR, _consensus, _match_game  # noqa: E402

import requests                                    # noqa: E402

OPEN_ET = (12, 0)               # Tuesday 12:00 ET == scheduler.py `tue-open`
MARKETS = "spreads,totals,h2h"
OUT_DIR = os.environ.get("OPENING_LINES_DIR", "data/opening_lines")


def tuesday_before(sunday):
    """The Tuesday of that game week (the Sunday slate anchors the week)."""
    return sunday - timedelta(days=5)


def fetch(season: int):
    if not API_KEY:
        print("ODDS_API_KEY not set — nothing spent."); return
    os.makedirs(OUT_DIR, exist_ok=True)
    anchors = week_anchors([season])
    weeks = sorted(w for (s, w) in anchors if s == season and 1 <= w <= 18)
    print(f"{season}: {len(weeks)} weeks, one call each, markets={MARKETS}")
    print(f"estimated spend: {len(weeks)} x 30 = {len(weeks) * 30} credits\n")

    left = None
    for w in weeks:
        path = os.path.join(OUT_DIR, f"{season}_W{w:02d}.json")
        if os.path.exists(path):
            print(f"  W{w:02d} already on disk, skipping (no credits spent)")
            continue
        ts = _et_to_utc(tuesday_before(anchors[(season, w)]),
                        *OPEN_ET).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(HIST_URL, timeout=90, params={
            "apiKey": API_KEY, "regions": "us", "markets": MARKETS,
            "oddsFormat": "american", "date": ts,
        })
        left = r.headers.get("x-requests-remaining", left)
        if r.status_code != 200:
            print(f"  W{w:02d} {ts} HTTP {r.status_code} — {r.text[:120]}")
            continue
        body = r.json()
        events = body.get("data", [])
        with open(path, "w") as fh:
            json.dump({"requested_ts": ts, "snapshot_ts": body.get("timestamp"),
                       "data": events}, fh)
        print(f"  W{w:02d} {ts}  events={len(events):<4} credits left={left}")
    print(f"\nsaved to {OUT_DIR}/  — credits remaining: {left}")


def _iter_snapshots(season):
    """Yield (event, snapshot_dt) for every stored week file.

    Books post the WHOLE season months ahead, so a single Tuesday call comes
    back with all 272 games. Taking all of them would price a January game off
    a September line and call the intervening four months of information
    "CLV" — flattering nonsense. Each week's call therefore contributes only
    the games that kick off in the 7 days after it, which is exactly the
    opener the live `tue-open` slot will capture from Week 1 onward.
    """
    for w in range(1, 19):
        path = os.path.join(OUT_DIR, f"{season}_W{w:02d}.json")
        if not os.path.exists(path):
            continue
        blob = json.load(open(path))
        ts = blob.get("snapshot_ts") or blob["requested_ts"]
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        horizon = dt + timedelta(days=7)
        for ev in blob["data"]:
            commence = datetime.fromisoformat(
                ev["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
            if dt <= commence < horizon:
                yield ev, dt


def apply(season: int, write: bool = False):
    from app import SessionLocal, Game, OddsSnapshot

    s = SessionLocal()
    games = s.query(Game).filter(Game.season == season).all()
    by_id = {g.id: g for g in games}
    print(f"{season}: {len(games)} games in the database")

    matched = unmatched = no_consensus = 0
    inserts = []
    for ev, snap_dt in _iter_snapshots(season):
        home = TEAM_ABBR.get(ev.get("home_team", ""))
        away = TEAM_ABBR.get(ev.get("away_team", ""))
        if not home or not away:
            continue
        commence = datetime.fromisoformat(
            ev["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
        g = _match_game(games, home, away, commence)
        if g is None:
            unmatched += 1
            continue
        vals = _consensus(ev)
        if vals is None:
            no_consensus += 1
            continue
        matched += 1
        inserts.append((g, snap_dt, vals))

    print(f"  matched {matched}, unmatched {unmatched}, "
          f"no consensus {no_consensus}")

    # How much did the market actually move? This is the whole point, so
    # measure it before writing anything.
    moved = flat = 0
    for g, _dt, vals in inserts:
        close = (s.query(OddsSnapshot)
                  .filter(OddsSnapshot.game_id == g.id)
                  .order_by(OddsSnapshot.captured_at.desc()).first())
        if not close:
            continue
        if (vals.get("ml_home") != close.ml_home
                or vals.get("spread_home_line") != close.spread_home_line):
            moved += 1
        else:
            flat += 1
    tot = moved + flat
    if tot:
        print(f"  line moved between open and close on {moved}/{tot} games "
              f"({100 * moved / tot:.0f}%)")

    # Synthetic rows: identical to the close, at exactly kickoff-120h.
    doomed = []
    for g in {i[0].id: i[0] for i in inserts}.values():
        rows = (s.query(OddsSnapshot)
                 .filter(OddsSnapshot.game_id == g.id)
                 .order_by(OddsSnapshot.captured_at).all())
        if len(rows) < 2:
            continue
        close = rows[-1]
        for r in rows[:-1]:
            same = (r.spread_home_line == close.spread_home_line
                    and r.ml_home == close.ml_home
                    and r.ml_away == close.ml_away
                    and r.total_line == close.total_line)
            if same and abs((close.captured_at - r.captured_at)
                            - timedelta(hours=120)).total_seconds() < 60:
                doomed.append(r)
    print(f"  synthetic duplicate-of-close rows to remove: {len(doomed)}")

    if not write:
        print("\nDRY RUN — nothing written. Re-run with --write to apply.")
        s.close()
        return

    for r in doomed:
        s.delete(r)
    for g, dt, vals in inserts:
        s.add(OddsSnapshot(game_id=g.id, captured_at=dt, **vals))
    s.commit()
    print(f"\nwrote {len(inserts)} real opening snapshots, "
          f"removed {len(doomed)} synthetic ones")
    s.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    season = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
    if cmd == "fetch":
        fetch(season)
    elif cmd == "apply":
        apply(season, write="--write" in sys.argv)
    else:
        print(__doc__)
