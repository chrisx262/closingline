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

# Auto-load a local .env (git-ignored) so the key is picked up seamlessly.
# Optional dependency — if python-dotenv isn't installed, fall back to the
# ambient environment.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


# The Odds API returns full names; games use nflverse abbreviations
# (note: LA = Rams, WAS = Commanders).
TEAM_ABBR = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
    "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Los Angeles Rams": "LA", "Los Angeles Chargers": "LAC",
    "Las Vegas Raiders": "LV", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE",
    "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT", "Seattle Seahawks": "SEA",
    "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

TOP_BOOKS = 3  # consensus = average of the first N books carrying a market


def _consensus(event: dict) -> dict | None:
    """Average the first TOP_BOOKS books' spread/total/h2h for one event.
    Returns OddsSnapshot field values, or None if no book has a spread."""
    home, away = event["home_team"], event["away_team"]
    fields = {"spread_home_line": [], "spread_home_odds": [],
              "spread_away_odds": [], "total_line": [], "over_odds": [],
              "under_odds": [], "ml_home": [], "ml_away": []}
    for book in event.get("bookmakers", [])[:TOP_BOOKS]:
        markets = {m["key"]: m["outcomes"] for m in book.get("markets", [])}
        for o in markets.get("spreads", []):
            if o["name"] == home:
                fields["spread_home_line"].append(o["point"])
                fields["spread_home_odds"].append(o["price"])
            elif o["name"] == away:
                fields["spread_away_odds"].append(o["price"])
        for o in markets.get("totals", []):
            if o["name"] == "Over":
                fields["total_line"].append(o["point"])
                fields["over_odds"].append(o["price"])
            elif o["name"] == "Under":
                fields["under_odds"].append(o["price"])
        for o in markets.get("h2h", []):
            if o["name"] == home:
                fields["ml_home"].append(o["price"])
            elif o["name"] == away:
                fields["ml_away"].append(o["price"])
    if not fields["spread_home_line"]:
        return None
    out = {}
    for k, vals in fields.items():
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        # lines keep halves (e.g. -3.5); odds round to whole american prices
        out[k] = round(avg * 2) / 2 if k.endswith("_line") else int(round(avg))
    return out


def _match_game(games: list, home_abbr: str, away_abbr: str,
                commence: datetime):
    """Find the Game row for an event: same home/away, kickoff within 36h
    of the event's commence time (absorbs feed-vs-schedule drift)."""
    for g in games:
        if (g.home == home_abbr and g.away == away_abbr
                and abs((g.kickoff - commence).total_seconds()) <= 36 * 3600):
            return g
    return None


def snapshot_odds():
    """Capture one odds snapshot for every upcoming game. Run on the cron
    cadence above. One call covers ALL games and costs 3 credits (markets x
    regions) — the 5/week cadence is ~66 credits/month vs the free 500."""
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
    remaining = r.headers.get("x-requests-remaining")
    now = datetime.utcnow()
    s = SessionLocal()
    games = s.query(Game).filter(Game.final == False).all()  # noqa: E712
    captured = unmatched = 0
    for event in r.json():
        home = TEAM_ABBR.get(event.get("home_team", ""))
        away = TEAM_ABBR.get(event.get("away_team", ""))
        if not home or not away:
            continue  # non-NFL or unrecognized name
        commence = datetime.fromisoformat(
            event["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
        game = _match_game(games, home, away, commence)
        if game is None:
            unmatched += 1
            continue
        vals = _consensus(event)
        if vals is None:
            continue
        s.add(OddsSnapshot(game_id=game.id, captured_at=now, **vals))
        captured += 1
    s.commit()
    s.close()
    print(f"snapshot_odds: {captured} games captured, {unmatched} unmatched, "
          f"API requests remaining this month: {remaining}")
    return captured


if __name__ == "__main__":
    load_schedule(2025)
