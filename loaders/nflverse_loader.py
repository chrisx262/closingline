"""
nflverse loader — real NFL games with real closing lines. Zero API keys.

Source: https://github.com/nflverse/nfldata (Lee Sharpe's games.csv),
which includes final scores plus closing spread/total/moneyline for
every game back to 1999.

Honest limitation: this archive stores only the CLOSING line, so we
create two snapshots per game (an "available" copy 120h out and the
official close at kickoff). Backtest picks get priced at the close,
which means backtest CLV is ~0 by construction. Real CLV starts when
the live cron (loaders/real_data.py) captures multiple snapshots per
week during the season. ROI, records, and report cards are fully real.

Usage:
    python loaders/nflverse_loader.py 2025          # load a season
    python loaders/nflverse_loader.py 2023 2024 2025  # several
"""

import csv
import io
import sys
from datetime import datetime, timedelta

import requests

sys.path.insert(0, ".")
from app import SessionLocal, Base, engine, Game, OddsSnapshot  # noqa: E402

URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"


def load(seasons: list[int], wipe: bool = False):
    if wipe:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    print("downloading nflverse games.csv ...")
    r = requests.get(URL, timeout=60)
    r.raise_for_status()
    rows = [x for x in csv.DictReader(io.StringIO(r.text))
            if int(x["season"]) in seasons and x["game_type"] == "REG"]

    s = SessionLocal()
    loaded = skipped = 0
    for row in rows:
        if not row.get("spread_line") or not row.get("total_line"):
            skipped += 1
            continue

        gameday = row["gameday"]
        gametime = row.get("gametime") or "17:00"
        kickoff = datetime.fromisoformat(f"{gameday}T{gametime}")

        gid = (f"{row['season']}_W{int(row['week']):02d}_"
               f"{row['away_team']}_{row['home_team']}")
        game = s.get(Game, gid) or Game(id=gid)
        game.season = int(row["season"])
        game.week = int(row["week"])
        game.kickoff = kickoff
        game.home, game.away = row["home_team"], row["away_team"]
        if row.get("home_score"):
            game.home_score = int(float(row["home_score"]))
            game.away_score = int(float(row["away_score"]))
            game.final = True
        game.div_game = row.get("div_game") == "1"
        game.roof = row.get("roof") or None
        game.temp = int(float(row["temp"])) if row.get("temp") else None
        game.wind = int(float(row["wind"])) if row.get("wind") else None
        game.home_rest = int(float(row["home_rest"])) if row.get("home_rest") else None
        game.away_rest = int(float(row["away_rest"])) if row.get("away_rest") else None
        game.home_qb = row.get("home_qb_name") or None
        game.away_qb = row.get("away_qb_name") or None
        s.merge(game)

        # nflverse convention: spread_line positive = home favored by that many
        # our convention:      spread_home_line negative = home favored
        home_line = -float(row["spread_line"])
        common = dict(
            game_id=gid,
            spread_home_line=home_line,
            spread_home_odds=int(float(row.get("home_spread_odds") or -110)),
            spread_away_odds=int(float(row.get("away_spread_odds") or -110)),
            total_line=float(row["total_line"]),
            over_odds=int(float(row.get("over_odds") or -110)),
            under_odds=int(float(row.get("under_odds") or -110)),
            ml_home=int(float(row["home_moneyline"])) if row.get("home_moneyline") else None,
            ml_away=int(float(row["away_moneyline"])) if row.get("away_moneyline") else None,
        )
        # "available" snapshot so agents picking days out find a price...
        s.add(OddsSnapshot(captured_at=kickoff - timedelta(hours=120), **common))
        # ...and the official close at kickoff.
        s.add(OddsSnapshot(captured_at=kickoff, **common))
        loaded += 1

    s.commit()
    s.close()
    print(f"loaded {loaded} games across seasons {seasons} "
          f"({skipped} skipped, no lines)")


if __name__ == "__main__":
    seasons = [int(a) for a in sys.argv[1:]] or [2025]
    load(seasons, wipe=True)
