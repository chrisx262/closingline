"""
Futures odds seeder — 2026 season preseason board.

Championship numbers below were verified against published sportsbook
boards as of early July 2026 (mix of DraftKings and Caesars via CBS/ESPN
reporting — noted per row). Conference and division markets are scaffolded
with the market keys the platform expects; fill them from a book's board
and re-run. Every run appends a new snapshot (captured_at=now), so odds
history accumulates — exactly like game lines.

Update workflow (weekly in-season, or whenever news moves boards):
    1. Edit the CHAMPIONSHIP / CONFERENCE / DIVISIONS lists below
       (or wire a feed later — HANDOFF task 10).
    2. python loaders/futures_seed.py

Market keys: "championship", "conference:AFC", "conference:NFC",
"division:AFC East" ... "division:NFC West".
"""

import sys
from datetime import datetime

sys.path.insert(0, ".")
from app import SessionLocal, Base, engine, FuturesOdds  # noqa: E402

SEASON = 2026

# team, american odds, book  — verified early July 2026
CHAMPIONSHIP = [
    ("LA",  +550,  "draftkings"),   # Rams: lone single-digit favorite
    ("BUF", +1000, "draftkings"),
    ("SEA", +1200, "consensus"),    # defending champs
    ("KC",  +1800, "draftkings"),
    ("NE",  +1600, "caesars"),
    ("PHI", +1600, "caesars"),
    ("GB",  +1700, "caesars"),
    ("LAC", +1700, "caesars"),
    ("BAL", +2000, "consensus"),
    ("DET", +2200, "consensus"),
    ("ARI", +40000, "caesars"),     # longest shot on the board
]

# Fill these from a sportsbook futures board, then re-run this file.
CONFERENCE = [
    # ("conference:AFC", "BUF", +450, "book"),
    # ("conference:NFC", "LA",  +300, "book"),
]

DIVISIONS = [
    # ("division:AFC West", "LAC", +170, "book"),
    # ("division:NFC West", "LA",  +150, "book"),
]


def run():
    Base.metadata.create_all(engine)
    s = SessionLocal()
    now = datetime.utcnow()
    n = 0
    for team, odds, book in CHAMPIONSHIP:
        s.add(FuturesOdds(season=SEASON, market="championship", team=team,
                          odds=odds, book=book, captured_at=now))
        n += 1
    for market, team, odds, book in CONFERENCE + DIVISIONS:
        s.add(FuturesOdds(season=SEASON, market=market, team=team,
                          odds=odds, book=book, captured_at=now))
        n += 1
    s.commit()
    s.close()
    print(f"snapshot: {n} futures rows captured at {now.isoformat()}")


if __name__ == "__main__":
    run()
