"""
Weekly update — run every Tuesday morning in-season (cron or GitHub Action):

    python weekly_update.py

1. Re-pulls nflverse games.csv (final scores appear there within a day).
2. Marks finished games final.
3. Grades every pending pick via the same engine as always.

In-season you'll also run loaders/real_data.py snapshot_odds() on the
Tue/Thu/Sat/Sun cadence to capture line movement — that's what turns on
real CLV. This script is only the results + grading half.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loaders.nflverse_loader import load                      # noqa: E402
from app import SessionLocal, Pick, Game                      # noqa: E402
from app import grade_all                                     # noqa: E402


def run(season: int = 2026):
    load([season], wipe=False)          # refresh scores, keep existing picks
    s = SessionLocal()
    pending = (s.query(Pick).join(Game, Pick.game_id == Game.id)
                .filter(Pick.result == "pending", Game.final == True).count())
    s.close()
    if pending:
        # call the endpoint logic directly (bypasses HTTP, no key needed here)
        from app import SessionLocal as SL
        s = SL()
        from app import _grade_one, closing_snapshot
        rows = (s.query(Pick, Game).join(Game, Pick.game_id == Game.id)
                 .filter(Pick.result == "pending", Game.final == True).all())
        for pick, game in rows:
            _grade_one(pick, game, closing_snapshot(s, game))
        s.commit()
        s.close()
        print(f"graded {len(rows)} picks")
    else:
        print("nothing to grade")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
