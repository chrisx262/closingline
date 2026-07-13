"""
Real-data loaders — skeletons ready to fill in when you have API keys.
The whole platform runs on synthetic data until then; these swap it out
without touching app.py.

SOURCES (all decisions pre-made, just add keys):
  1. The Odds API (https://the-odds-api.com) — live NFL lines.
     Free tier: 500 requests/month, enough for a few snapshots per game
     per week during the season. ~$30/mo tier when you have real users.
  2. nflverse (https://github.com/nflverse/nflverse-data) — FREE schedules,
     scores, play-by-play, EPA, injuries. No key needed; CSVs on GitHub.

CRON CADENCE (this is your snapshot schedule — it drives CLV quality):
  - Tue 12:00 ET: pull opening lines for the coming week      (snapshot 1)
  - Thu 18:00 ET: pre-TNF snapshot                            (snapshot 2)
  - Sat 12:00 ET: mid-week movement                           (snapshot 3)
  - Sun 11:35 ET: POST-INACTIVES snapshot — official inactives
    drop 90 min before kickoff (~11:30 ET for the 1pm slate);
    this capture is what prices in QB-out news              (snapshot 4)
  - Sun 12:45 ET: closing snapshot for the 1pm slate          (snapshot 5)
  - Mon 09:00 ET: pull final scores, mark games final, POST /admin/grade
"""

import os
from datetime import datetime

import requests
from app import SessionLocal, Game, OddsSnapshot

# Read the key from the environment — never hardcode it in source (this repo
# is public). Set ODDS_API_KEY in your shell or a local .env (git-ignored).
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
SCHEDULE_CSV = ("https://github.com/nflverse/nflverse-data/releases/download/"
                "schedules/sched_{season}.csv")


def load_schedule(season: int):
    """Pull season schedule + any final scores from nflverse (free)."""
    import csv, io
    r = requests.get(SCHEDULE_CSV.format(season=season), timeout=30)
    r.raise_for_status()
    s = SessionLocal()
    for row in csv.DictReader(io.StringIO(r.text)):
        gid = f"{season}_W{int(row['week']):02d}_{row['away_team']}_{row['home_team']}"
        game = s.query(Game).get(gid) or Game(id=gid)
        game.season, game.week = season, int(row["week"])
        game.home, game.away = row["home_team"], row["away_team"]
        game.kickoff = datetime.fromisoformat(row["gameday"] + "T" +
                                              (row.get("gametime") or "17:00"))
        if row.get("home_score"):
            game.home_score = int(row["home_score"])
            game.away_score = int(row["away_score"])
            game.final = True
        s.merge(game)
    s.commit()
    s.close()
    print("schedule loaded")


def snapshot_odds():
    """Capture one odds snapshot for every upcoming game. Run on the cron
    cadence above. Each run = one OddsSnapshot row per game."""
    if not ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Get a key from https://the-odds-api.com "
            "and export it before running, e.g.:\n"
            "  export ODDS_API_KEY=your_key_here\n"
            "or add it to a local .env file (git-ignored)."
        )
    params = {"apiKey": ODDS_API_KEY, "regions": "us",
              "markets": "spreads,totals,h2h", "oddsFormat": "american"}
    r = requests.get(ODDS_URL, params=params, timeout=30)
    r.raise_for_status()
    now = datetime.utcnow()
    s = SessionLocal()
    for event in r.json():
        # TODO: map event home/away team names -> your Game.id convention,
        # average or pick one book from event["bookmakers"], then:
        # s.add(OddsSnapshot(game_id=..., captured_at=now, ...))
        pass
    s.commit()
    s.close()


if __name__ == "__main__":
    load_schedule(2025)
