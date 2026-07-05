"""
ELO AGENT — "our own system", built the honest way.

Method (FiveThirtyEight-style Elo):
  - Every team starts at 1500; ratings update after each game using a
    K-factor scaled by margin of victory. Ratings regress 25% to the mean
    between seasons. Home field is worth a fixed Elo bonus.
  - Rating gap / 25 ≈ predicted point margin. We compare our predicted
    margin to the market spread and bet the side only when we disagree
    by at least `threshold` points.

Discipline (this is the part that keeps us honest):
  - 2021-2022: burn-in (ratings warm up, no betting evaluated)
  - 2023-2024: TRAIN — small grid search over (K, home-field, threshold)
  - 2025:      TEST — parameters frozen, picks submitted through the real
               Pick API in backtest mode with as_of = kickoff - 24h.
               Ratings for a 2025 game use only games played before it.

Run:  python systems/elo_agent.py   (after loading seasons 2021-2025)
"""

import math
import sys
from datetime import timedelta

sys.path.insert(0, ".")
from fastapi.testclient import TestClient          # noqa: E402
from app import app, SessionLocal, Game           # noqa: E402

client = TestClient(app)

BURN_IN = {2021, 2022}
TRAIN = {2023, 2024}
TEST = {2025}
ELO_PER_POINT = 25.0


def all_games():
    s = SessionLocal()
    gs = (s.query(Game).filter(Game.final == True)
           .order_by(Game.kickoff).all())
    out = [dict(id=g.id, season=g.season, week=g.week, kickoff=g.kickoff,
                home=g.home, away=g.away, hs=g.home_score, as_=g.away_score)
           for g in gs]
    s.close()
    return out


def closing_home_line(game_id):
    """Closing spread for offline train evaluation (train seasons only)."""
    r = client.get(f"/data/odds?game_id={game_id}").json()
    return r["spread"]["home_line"]


class Elo:
    def __init__(self, k, hfa):
        self.k, self.hfa, self.r = k, hfa, {}

    def rating(self, team):
        return self.r.setdefault(team, 1500.0)

    def new_season(self):
        for t in self.r:
            self.r[t] = 1500 + 0.75 * (self.r[t] - 1500)

    def predict_margin(self, home, away):
        return (self.rating(home) + self.hfa - self.rating(away)) / ELO_PER_POINT

    def update(self, home, away, hs, as_):
        ra, rb = self.rating(home) + self.hfa, self.rating(away)
        exp_home = 1 / (1 + 10 ** (-(ra - rb) / 400))
        margin = hs - as_
        result = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        winner_diff = (ra - rb) if margin > 0 else (rb - ra)
        mov = math.log(abs(margin) + 1) * 2.2 / (winner_diff * 0.001 + 2.2)
        delta = self.k * mov * (result - exp_home)
        self.r[home] = self.rating(home) + delta
        self.r[away] = self.rating(away) - delta


def simulate(k, hfa, threshold, games, lines):
    """Offline walk-forward sim used ONLY on train seasons."""
    elo, season = Elo(k, hfa), None
    bets = wins = losses = 0
    profit = 0.0
    for g in games:
        if g["season"] != season:
            season, _ = g["season"], elo.new_season()
        if g["season"] in TRAIN and g["id"] in lines:
            hl = lines[g["id"]]
            edge = elo.predict_margin(g["home"], g["away"]) - (-hl)
            side_line = None
            if edge >= threshold:      # we like home more than market
                side_line, team_m = hl, g["hs"] + hl - g["as_"]
            elif edge <= -threshold:   # we like away
                side_line, team_m = -hl, g["as_"] - hl - g["hs"]
            if side_line is not None:
                bets += 1
                if team_m > 0:
                    wins += 1; profit += 100 / 110
                elif team_m < 0:
                    losses += 1; profit -= 1
        elo.update(g["home"], g["away"], g["hs"], g["as_"])
    roi = 100 * profit / bets if bets else 0
    return dict(k=k, hfa=hfa, thr=threshold, bets=bets, wins=wins,
                losses=losses, roi=round(roi, 2))


def run():
    games = all_games()
    train_lines = {g["id"]: closing_home_line(g["id"])
                   for g in games if g["season"] in TRAIN}

    print("TRAIN 2023-24 — grid search (never touches 2025):")
    results = [simulate(k, hfa, thr, games, train_lines)
               for k in (15, 20, 25)
               for hfa in (40, 55, 65)
               for thr in (1.5, 2.5, 3.5)]
    # pick best train ROI among configs with a usable sample
    viable = [r for r in results if r["bets"] >= 60] or results
    best = max(viable, key=lambda r: r["roi"])
    for r in sorted(results, key=lambda r: -r["roi"])[:5]:
        print(f"  K={r['k']} HFA={r['hfa']} thr={r['thr']}: "
              f"{r['wins']}-{r['losses']} ROI {r['roi']}%")
    print(f"\nFROZEN: K={best['k']} HFA={best['hfa']} thr={best['thr']} "
          f"(train ROI {best['roi']}% on {best['bets']} bets)")

    # ---- TEST: replay 2025 through the real API, parameters frozen ----
    reg = client.post("/agents/register",
                      json={"name": "elo_edge_v1", "kind": "bot"}).json()
    key, agent_id = reg["api_key"], reg["agent_id"]

    elo, season = Elo(best["k"], best["hfa"]), None
    submitted = 0
    for g in games:
        if g["season"] != season:
            season, _ = g["season"], elo.new_season()
        if g["season"] in TEST:
            as_of = (g["kickoff"] - timedelta(hours=24)).isoformat()
            odds = client.get(f"/data/odds?game_id={g['id']}"
                              f"&as_of={as_of}").json()
            hl = odds["spread"]["home_line"]
            edge = elo.predict_margin(g["home"], g["away"]) - (-hl)
            side = g["home"] if edge >= best["thr"] else \
                   g["away"] if edge <= -best["thr"] else None
            if side:
                r = client.post("/picks", headers={"x-api-key": key},
                                json={"game_id": g["id"], "market": "spread",
                                      "side": side, "stake_units": 1.0,
                                      "confidence": min(0.99, 0.5 + abs(edge) / 30),
                                      "model_version": "elo-v1",
                                      "mode": "backtest", "as_of": as_of})
                submitted += r.status_code == 200
        elo.update(g["home"], g["away"], g["hs"], g["as_"])

    client.post("/admin/grade")
    print(f"\nTEST 2025 — {submitted} picks submitted through the API, frozen params")
    rep = client.get(f"/agents/{agent_id}/report?mode=backtest").json()
    o = rep["overall"]
    print(f"  RESULT: {o['wins']}-{o['losses']}"
          f"{'-' + str(o['pushes']) if o['pushes'] else ''} "
          f"ROI {o['roi_pct']}% on {o['picks']} bets "
          f"({o['profit_units']} units)")
    print("  by side type:")
    for seg, st in rep["by_side_type"].items():
        print(f"    {seg:<10} n={st['picks']:<3} ROI {st['roi_pct']}%")
    print("\n", rep["caution"])


if __name__ == "__main__":
    run()
