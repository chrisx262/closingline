"""
ENDZONE EDGE AGENT — the owner's real model, wired into the Pick API.

This is HANDOFF task 2 ("wire in the owner's real model") and it is also
EndZone Edge's own task T7. That project's invariant 6 says the two repos
must not merge and that the ONE sanctioned connection is submitting its
config as an agent to ClosingLine's pick API. So the model is PORTED here,
not imported across repos: ~/projects/endzone-edge/scripts/honest_backtest.py
is the reference implementation and this file must match its method.

THE MODEL (points-proxy ratings, offence/defence only):
  off(t) = points scored per game so far      -> z-scored across the league
  def(t) = -points allowed per game so far    -> z-scored across the league
  rating(t) = W_OFF * z_off(t) + (1 - W_OFF) * z_def(t)
  pick home iff  rating(home) - rating(away) + HFA > 0

FROZEN PARAMETERS — fitted on 2024, never refit here:
  W_OFF = 0.70, HFA = 0.4
Re-running the fit inside this file would be the exact in-sample trap the
harness exists to warn about, so the numbers are hardcoded and the fit stays
in the EndZone repo.

WHAT THE HARNESS ALREADY TOLD US (do not re-discover it, do not spin it):
  2024 in-sample fit ....... 72.6%   <- never show this as accuracy
  2025 honest, frozen ...... 59.6%   <- THE number
  always pick the home team  51.4%
  Vegas favourite .......... 63.0%   <- the model LOSES to the market
The point of putting it on the board is not that it wins. It is that its
record is public, out-of-sample and measured against the closing line, per
invariant 6. A model that trails the market is a result, not a failure to
hide.

MARKET: moneyline. The model predicts winners straight up, so moneyline is
the only market it has an opinion about — and it is the market the moneyline
leaderboard needs rows in. It does NOT pick spreads: the research run on
2026-08-10 found no ATS edge (48.7%, -7% ROI), so submitting spread picks
would be pretending to a skill the backtest says is absent.

DISCIPLINE:
  - Ratings for a week use ONLY games from strictly earlier weeks.
  - Weeks 1-4 are skipped (MIN_WEEK): rolling stats have not stabilised.
  - as_of = kickoff - 24h, matching elo_agent.py, so the server prices the
    pick from a snapshot that existed before kickoff and CLV is measured
    against the close.
  - stake_units is flat 1.0. The model has no sizing signal; varying stake
    would invent one.

Run:
  python systems/endzone_agent.py --dry-run              # in-process, no writes
  python systems/endzone_agent.py --dry-run --url URL    # against a deployment
  python systems/endzone_agent.py --submit               # in-process, WRITES
  python systems/endzone_agent.py --submit --url URL     # WRITES to that deployment

--dry-run prices every pick through the real odds endpoint and prints the
report it would produce, without creating an agent or a single pick. Picks
are immutable (invariant 1), so a --submit run cannot be undone: it is
deliberately not the default.
"""

import argparse
import statistics
import sys
from datetime import timedelta

sys.path.insert(0, ".")

W_OFF = 0.70          # frozen: fitted on 2024 in the EndZone harness
HFA = 0.4             # frozen: same fit
MIN_WEEK = 5          # rolling stats need a few weeks to mean anything
TEST_SEASON = 2025
AGENT_NAME = "endzone_edge_v1"


# ---------------------------------------------------------------- transport
class Local:
    """In-process against this repo's app + database."""

    def __init__(self):
        from fastapi.testclient import TestClient
        from app import app
        self.c = TestClient(app)

    def get(self, path, **params):
        return self.c.get(path, params=params).json()

    def post(self, path, json=None, headers=None):
        r = self.c.post(path, json=json, headers=headers or {})
        return r.status_code, (r.json() if r.content else {})


class Remote:
    """HTTP against a deployed instance."""

    def __init__(self, url):
        import requests
        self.url = url.rstrip("/")
        self.s = requests.Session()

    def get(self, path, **params):
        return self.s.get(self.url + path, params=params, timeout=30).json()

    def post(self, path, json=None, headers=None):
        r = self.s.post(self.url + path, json=json,
                        headers=headers or {}, timeout=30)
        return r.status_code, (r.json() if r.content else {})


# ------------------------------------------------------------------- model
def zscorer(values):
    """Return f(v) -> z. Population sd, and a flat league collapses to 0."""
    m = statistics.mean(values)
    sd = statistics.pstdev(values) or 1.0
    return lambda v: (v - m) / sd


def ratings_through(results):
    """Ratings from a list of completed games. Caller controls which games
    are in the list — that is where the no-lookahead guarantee lives."""
    pf, pa, n = {}, {}, {}
    for g in results:
        for t, f, a in ((g["home"], g["hs"], g["as"]),
                        (g["away"], g["as"], g["hs"])):
            pf[t] = pf.get(t, 0) + f
            pa[t] = pa.get(t, 0) + a
            n[t] = n.get(t, 0) + 1
    if not n:
        return {}
    off = {t: pf[t] / n[t] for t in n}
    dfn = {t: -pa[t] / n[t] for t in n}          # fewer allowed = better
    zo = zscorer(list(off.values()))
    zd = zscorer(list(dfn.values()))
    return {t: W_OFF * zo(off[t]) + (1 - W_OFF) * zd(dfn[t]) for t in n}


def predict(rat, home, away):
    """(picked_team, edge) or None when a team has no rating yet."""
    if home not in rat or away not in rat:
        return None
    edge = rat[home] - rat[away] + HFA
    return (home if edge > 0 else away), abs(edge)


# -------------------------------------------------------------------- data
def season_games(api, season):
    """Every regular-season game we know about, oldest first."""
    out, seen = [], set()
    for wk in range(1, 19):
        try:
            rows = api.get("/data/slate", week=wk, season=season)
        except Exception:
            continue
        rows = rows if isinstance(rows, list) else rows.get("games", [])
        for g in rows:
            gid = g.get("game_id")
            if not gid or gid in seen:
                continue
            seen.add(gid)
            out.append({
                "id": gid, "week": g.get("week", wk),
                "kickoff": g.get("kickoff"),
                "home": g.get("home"), "away": g.get("away"),
                "hs": g.get("home_score"), "as": g.get("away_score"),
                "final": bool(g.get("final")),
            })
    out.sort(key=lambda g: (g["week"], g["kickoff"] or ""))
    return out


def as_of_for(kickoff_iso):
    from datetime import datetime
    return (datetime.fromisoformat(kickoff_iso) - timedelta(hours=24)).isoformat()


# --------------------------------------------------------------------- run
def build_picks(api, games):
    """Walk the season. For each week >= MIN_WEEK, rate on earlier weeks
    only, then pick a moneyline side for every game that has a pre-kickoff
    snapshot. Returns (picks, skipped_reasons)."""
    picks, skipped = [], {}
    for wk in range(MIN_WEEK, 19):
        prior = [g for g in games if g["week"] < wk and g["final"]
                 and g["hs"] is not None]
        rat = ratings_through(prior)
        if not rat:
            skipped["no ratings yet"] = skipped.get("no ratings yet", 0) + 1
            continue
        for g in [x for x in games if x["week"] == wk]:
            if not g["kickoff"]:
                skipped["no kickoff"] = skipped.get("no kickoff", 0) + 1
                continue
            p = predict(rat, g["home"], g["away"])
            if not p:
                skipped["team unrated"] = skipped.get("team unrated", 0) + 1
                continue
            side, edge = p
            as_of = as_of_for(g["kickoff"])
            odds = api.get("/data/odds", game_id=g["id"], as_of=as_of)
            ml = (odds or {}).get("moneyline") or {}
            if ml.get("home") is None:
                skipped["no pre-kickoff moneyline"] = \
                    skipped.get("no pre-kickoff moneyline", 0) + 1
                continue
            picks.append({"game_id": g["id"], "market": "moneyline",
                          "side": side, "stake_units": 1.0,
                          "model_version": "endzone_v1_woff70_hfa04",
                          "mode": "backtest", "as_of": as_of,
                          "_edge": round(edge, 3), "_week": wk,
                          "_price": ml["home"] if side == g["home"] else ml["away"],
                          "_actual": (g["home"] if (g["hs"] or 0) > (g["as"] or 0)
                                      else g["away"]) if g["final"] else None})
    return picks, skipped


def dry_run(api):
    games = season_games(api, TEST_SEASON)
    finals = [g for g in games if g["final"]]
    print(f"{TEST_SEASON}: {len(games)} games known, {len(finals)} final")
    picks, skipped = build_picks(api, games)
    print(f"\nwould submit {len(picks)} moneyline picks "
          f"(weeks {MIN_WEEK}-18, as_of = kickoff-24h)")
    for reason, n in sorted(skipped.items()):
        print(f"  skipped {n:>3}  {reason}")

    graded = [p for p in picks if p["_actual"]]
    if graded:
        hits = sum(p["side"] == p["_actual"] for p in graded)
        print(f"\nstraight-up accuracy on {len(graded)} graded picks: "
              f"{100 * hits / len(graded):.1f}%")
        print("  EndZone harness honest 2025 figure: 59.6%")
        print("  Vegas favourite over the same season: 63.0% — the market "
              "is still ahead, and that is the finding.")
        dogs = [p for p in graded if p["_price"] > 0]
        print(f"  underdog picks: {len(dogs)}/{len(graded)}")
    print("\nDRY RUN — nothing was created. Re-run with --submit to write.")
    return picks


def submit(api, picks):
    code, reg = api.post("/agents/register",
                         json={"name": AGENT_NAME, "kind": "bot"})
    if code != 200:
        print(f"register failed [{code}]: {reg}")
        return
    key, aid = reg["api_key"], reg["agent_id"]
    print(f"registered {AGENT_NAME} as agent {aid}")

    sent = 0
    for p in picks:
        body = {k: v for k, v in p.items() if not k.startswith("_")}
        code, resp = api.post("/picks", json=body, headers={"x-api-key": key})
        if code == 200:
            sent += 1
        else:
            print(f"  rejected {p['game_id']}: {resp}")
    print(f"submitted {sent}/{len(picks)} picks")

    # Grading is admin-gated in prod (ADMIN_KEY). Without it the picks still
    # land, they just sit ungraded until the next scheduled grade run.
    import os
    code, _ = api.post("/admin/grade",
                       headers={"x-admin-key": os.environ.get("ADMIN_KEY", "")})
    if code != 200:
        print(f"  note: grade run returned {code} — picks are stored; the "
              f"report will fill in once they are graded")
    rep = api.get(f"/agents/{aid}/report", mode="backtest")
    o = rep["overall"]
    print(f"\nREPORT CARD — {AGENT_NAME} (backtest {TEST_SEASON})")
    print(f"  {o['wins']}-{o['losses']}-{o['pushes']} over {o['picks']} picks")
    print(f"  ROI {o['roi_pct']}%   avg CLV (prob) {o['avg_clv_prob']}")
    print("\n" + rep.get("caution", ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="price and score every pick, write nothing")
    g.add_argument("--submit", action="store_true",
                   help="register the agent and POST the picks (permanent)")
    ap.add_argument("--url", help="deployment to run against; omit for in-process")
    a = ap.parse_args()

    api = Remote(a.url) if a.url else Local()
    where = a.url or "in-process"
    print(f"EndZone Edge agent — W_OFF={W_OFF} HFA={HFA} (frozen on 2024) "
          f"vs {where}\n")

    picks = dry_run(api)
    if a.submit:
        if not picks:
            print("nothing to submit")
            return
        print(f"\nSubmitting {len(picks)} immutable backtest picks…")
        submit(api, picks)


if __name__ == "__main__":
    main()
