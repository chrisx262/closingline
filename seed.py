"""
Seed a deterministic synthetic mini-season so the platform runs instantly
with zero API keys. Weeks 1-3 are final (backtestable); week 4 kicks off
in the future (live-pickable). Swap in loaders/ for real data later.
"""

import random
from datetime import datetime, timedelta
from app import SessionLocal, Base, engine, Game, OddsSnapshot, Agent, Pick

random.seed(42)

TEAMS = ["KC", "BUF", "PHI", "DAL", "SF", "DET", "BAL", "GB"]


def matchups(week_teams):
    t = week_teams[:]
    random.shuffle(t)
    return [(t[i], t[i + 1]) for i in range(0, len(t), 2)]


def run():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    now = datetime.utcnow()

    # true (hidden) team strength drives simulated scores
    strength = {t: random.uniform(-4, 4) for t in TEAMS}

    for week in range(1, 5):
        # weeks 1-3 in the past, week 4 kicks off ~3 days from now
        base = now - timedelta(days=(4 - week) * 7) + timedelta(days=3)
        for i, (home, away) in enumerate(matchups(TEAMS)):
            kickoff = base + timedelta(hours=3 * i)
            gid = f"2025_W{week:02d}_{away}_{home}"
            g = Game(id=gid, season=2025, week=week, kickoff=kickoff,
                     home=home, away=away)

            true_margin = strength[home] - strength[away] + 2.0  # home field
            open_spread = round((true_margin + random.uniform(-2, 2)) * 2) / 2
            open_total = round(random.uniform(41, 51) * 2) / 2

            # 4 snapshots: open (-120h), two moves, close (at kickoff)
            spread, total = -open_spread, open_total  # home_line convention
            for hours_out, drift in [(120, 0), (48, 1), (12, 1), (0, 1)]:
                if drift:
                    spread += random.choice([-1, -0.5, 0, 0, 0.5, 1])
                    total += random.choice([-1, -0.5, 0, 0, 0.5, 1])
                fav_ml = -int(110 + abs(spread) * 28)
                dog_ml = int(100 + abs(spread) * 24)
                home_fav = spread < 0
                s.add(OddsSnapshot(
                    game_id=gid,
                    captured_at=kickoff - timedelta(hours=hours_out),
                    spread_home_line=spread,
                    spread_home_odds=-110, spread_away_odds=-110,
                    total_line=total, over_odds=-110, under_odds=-110,
                    ml_home=fav_ml if home_fav else dog_ml,
                    ml_away=dog_ml if home_fav else fav_ml))

            if week <= 3:  # simulate final score around true margin
                margin = round(true_margin + random.gauss(0, 10))
                total_pts = max(20, round(open_total + random.gauss(0, 9)))
                g.home_score = max(0, (total_pts + margin) // 2)
                g.away_score = max(0, g.home_score - margin)
                g.final = True
            s.add(g)

    s.commit()
    games = s.query(Game).count()
    snaps = s.query(OddsSnapshot).count()
    s.close()
    print(f"Seeded {games} games, {snaps} odds snapshots. "
          f"Weeks 1-3 final, week 4 upcoming.")


if __name__ == "__main__":
    run()
