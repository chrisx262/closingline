"""
Backtest replay driver — the Karpathy loop, mechanically.

Replays completed weeks through the SAME Pick API used in live mode
(via FastAPI's TestClient), with as_of set to 24h before each kickoff.
Agents see only point-in-time odds; the server prices their picks from
that moment's snapshot. Then everything is graded by the same engine
that grades live picks, and each agent gets its report card.

Two demo strategies are included purely to exercise the pipeline.
Replace `STRATEGIES` entries with calls to your real systems.
"""

from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


# --- demo strategies: (name, fn(game, odds) -> pick dict or None) ---------

def home_dog_hunter(game, odds):
    """Bets the moneyline on home underdogs."""
    if odds["spread"]["home_line"] is not None and odds["spread"]["home_line"] > 0:
        return {"market": "moneyline", "side": game["home"], "stake_units": 1.0,
                "confidence": 0.55}
    return None


def under_in_big_totals(game, odds):
    """Bets UNDER whenever the total is 47 or higher."""
    if odds["total"]["line"] and odds["total"]["line"] >= 47:
        return {"market": "total", "side": "UNDER", "stake_units": 1.0,
                "confidence": 0.53}
    return None


def chalk_rider(game, odds):
    """Bets the spread favorite in every game. High volume, no edge —
    exactly the baseline your real models need to beat."""
    hl = odds["spread"]["home_line"]
    if hl is None:
        return None
    side = game["home"] if hl < 0 else game["away"]
    return {"market": "spread", "side": side, "stake_units": 1.0,
            "confidence": 0.5}


STRATEGIES = [
    ("home_dog_hunter", home_dog_hunter),
    ("under_47_plus", under_in_big_totals),
    ("chalk_rider", chalk_rider),
]


def register(name):
    r = client.post("/agents/register", json={"name": name, "kind": "bot"})
    if r.status_code == 409:
        raise SystemExit(f"{name} already registered — reseed (python seed.py) "
                         "to rerun a clean backtest.")
    d = r.json()
    return d["agent_id"], d["api_key"]


def run(weeks=None):
    if weeks is None:
        # replay every completed week in the database
        wk = {g["week"] for g in client.get("/data/games").json() if g["final"]}
        weeks = sorted(wk)
    print(f"replaying weeks: {weeks[0]}–{weeks[-1]}")
    agents = {name: register(name) for name, _ in STRATEGIES}

    submitted = 0
    for week in weeks:
        games = client.get(f"/data/games?week={week}").json()
        for game in games:
            kickoff = datetime.fromisoformat(game["kickoff"])
            as_of = (kickoff - timedelta(hours=24)).isoformat()
            odds = client.get(
                f"/data/odds?game_id={game['game_id']}&as_of={as_of}").json()
            for name, strategy in STRATEGIES:
                pick = strategy(game, odds)
                if not pick:
                    continue
                _, key = agents[name]
                r = client.post("/picks", headers={"x-api-key": key},
                                json={**pick, "game_id": game["game_id"],
                                      "mode": "backtest", "as_of": as_of,
                                      "model_version": "demo-v1"})
                if r.status_code == 200:
                    submitted += 1
                else:
                    print("  rejected:", r.json())

    graded = client.post("/admin/grade").json()["graded"]
    print(f"Submitted {submitted} backtest picks, graded {graded}.\n")

    board = client.get("/leaderboard?mode=backtest").json()
    print("BACKTEST LEADERBOARD (min", board["min_picks"], "picks)")
    for row in board["board"]:
        print(f"  {row['agent']:<18} {row['wins']}-{row['losses']}"
              f"{'-' + str(row['pushes']) if row['pushes'] else '':<4}"
              f"  ROI {row['roi_pct']:>7}%   avg CLV {row['avg_clv_points']}")

    print("\nREPORT CARDS (error analysis by segment)")
    for name, (agent_id, _) in agents.items():
        rep = client.get(f"/agents/{agent_id}/report?mode=backtest").json()
        print(f"\n  {name} — overall ROI {rep['overall']['roi_pct']}% "
              f"on {rep['overall']['picks']} picks")
        for bucket_name in ("by_market", "by_side_type", "by_week"):
            for seg, stats in rep[bucket_name].items():
                print(f"    {bucket_name[3:]:<10} {seg:<12} "
                      f"n={stats['picks']:<3} ROI {stats['roi_pct']:>7}% "
                      f" CLV {stats['avg_clv_points']}")


if __name__ == "__main__":
    run()
