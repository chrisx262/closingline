"""Buy historical QB prop lines for the backtest games (paid Odds API plan).

One events call per week (1 credit) to find event ids, then one event-odds
call per game for pass yards / attempts / completions (10 credits per market
returned). Raw JSON is saved to data/props_lines/<season>/<game_id>.json and
never fetched twice, so a rerun after an interruption spends nothing extra.

Usage: python3 systems/props_lines.py PBP_CSV_GZ GAMES_CSV SEASON [--buy]
       (without --buy it only prints what it would spend)
"""
import csv
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "systems"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(ROOT, ".env"))
from loaders.real_data import TEAM_ABBR  # noqa: E402
import props_backtest  # noqa: E402

KEY = os.environ.get("ODDS_API_KEY")
BASE = "https://api.the-odds-api.com/v4/historical/sports/americanfootball_nfl"
MARKETS = "player_pass_yds,player_pass_attempts,player_pass_completions"
ET, UTC = ZoneInfo("America/New_York"), ZoneInfo("UTC")
BEFORE_KICK = timedelta(minutes=90)


def kickoffs(games_csv, season):
    out = {}
    for r in csv.DictReader(open(games_csv)):
        if r["season"] == str(season) and r["game_type"] == "REG":
            et = datetime.fromisoformat(f"{r['gameday']}T{r['gametime']}")
            out[r["game_id"]] = (et.replace(tzinfo=ET).astimezone(UTC)
                                 .replace(tzinfo=None), r["home_team"],
                                 r["away_team"], int(r["week"]))
    return out


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    pbp, games_csv, season = sys.argv[1], sys.argv[2], int(sys.argv[3])
    buy = "--buy" in sys.argv
    rows = props_backtest.run(pbp)[2]
    ko = kickoffs(games_csv, season)
    wanted = sorted({r["game_id"] for r in rows})
    outdir = os.path.join(ROOT, "data", "props_lines", str(season))
    os.makedirs(outdir, exist_ok=True)
    todo = [g for g in wanted
            if not os.path.exists(os.path.join(outdir, g + ".json"))]
    weeks = sorted({ko[g][3] for g in todo})
    print(f"{season}: {len(wanted)} games, {len(todo)} not yet bought, "
          f"{len(weeks)} weeks -> at most {len(weeks) + 30 * len(todo)} credits")
    if not buy or not todo:
        return

    left = None
    for w in weeks:
        games = [g for g in todo if ko[g][3] == w]
        first = min(ko[g][0] for g in games)
        r = requests.get(f"{BASE}/events", params={
            "apiKey": KEY, "date": iso(first - timedelta(hours=6))}, timeout=30)
        r.raise_for_status()
        events = r.json().get("data", [])
        for g in games:
            kick, home, away, _ = ko[g]
            ev = next((e for e in events
                       if TEAM_ABBR.get(e["home_team"]) == home
                       and TEAM_ABBR.get(e["away_team"]) == away
                       and abs(datetime.fromisoformat(
                           e["commence_time"].replace("Z", "+00:00"))
                           .replace(tzinfo=None) - kick) < timedelta(hours=36)),
                      None)
            if not ev:
                print(f"  W{w} {g}: no event found")
                continue
            r = requests.get(f"{BASE}/events/{ev['id']}/odds", params={
                "apiKey": KEY, "regions": "us", "markets": MARKETS,
                "oddsFormat": "american", "date": iso(kick - BEFORE_KICK)},
                timeout=30)
            if r.status_code != 200:
                print(f"  W{w} {g}: HTTP {r.status_code} {r.text[:120]}")
                continue
            left = r.headers.get("x-requests-remaining")
            json.dump(r.json(), open(os.path.join(outdir, g + ".json"), "w"))
        print(f"  W{w}: {len(games)} games, credits left {left}")


if __name__ == "__main__":
    main()
