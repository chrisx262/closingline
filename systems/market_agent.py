"""MARKET AGENT — the de-vigged market favourite, one week at a time.

WHAT IT IS
Every week, back the team the market makes favourite in each game, at whatever
price is on the board when the picks go in. That is not a model and it is not
trying to be clever. It is the benchmark every other agent on this platform
should be measured against, and until now the board had no such line on it.

WHY IT IS WORTH A SLOT
Our own 2025 work found the market picks winners at 63.0% while EndZone Edge
manages 59.6%. That comparison currently lives in a commit message. Putting the
market on the board makes it permanent, public and out-of-sample, which is the
same standard invariant 6 holds our own model to.

WHAT IT ACTUALLY MEASURES
Not skill -- there is none here. It measures the ONE thing this platform was
built to measure: whether the price you get on Tuesday beats the price at
kickoff. Same 2025 picks, priced at the open, returned +15.44%; priced at the
close, -10.18%. Identical bets, identical record. The gap is entry price, and
this agent isolates it, because its selection is fixed by definition and the
only thing left varying is when it bought.

WEEK BY WEEK, ON PURPOSE
It submits one week at a time and never the season. Picks are immutable
(invariant 1), so a season submitted in September is a promise you cannot take
back in November when a quarterback goes down. A week out is a risk worth
taking for the CLV; four months out is not.

Usage:
    python systems/market_agent.py --week 1              # dry run, shows nothing sent
    python systems/market_agent.py --week 1 --submit     # actually submits
"""

import argparse
import os
import sys

import requests

sys.path.insert(0, ".")

BASE = os.environ.get("CLOSINGLINE_URL",
                      "https://closingline-production.up.railway.app")
# Two agents, same selection rule, different clocks. That is the point: the
# only thing varying between them is WHEN they bought, so the gap between their
# records is the value of the early price, measured rather than argued about.
OPEN_NAME = "closingline_open"     # Tuesday, when the week's lines post
CLOSE_NAME = "closingline_close"   # ~80 min before kickoff, after inactives
MODEL_VERSION = "market_devig_v1"
KEY_FILE = os.path.expanduser("~/closingline/.market_agent_key")
CLOSE_KEY_FILE = os.path.expanduser("~/closingline/.close_agent_key")
AGENT_NAME = OPEN_NAME


def get_key(name=None, key_file=None):
    """The agent's API key, registering it once on first use.

    Stored in a git-ignored file beside the admin key. Registration returns the
    raw key exactly once -- the server keeps only a hash -- so losing this file
    means the agent can never pick again and its record is frozen where it is.
    """
    name = name or AGENT_NAME
    key_file = key_file or KEY_FILE
    if os.path.exists(key_file):
        return open(key_file).read().strip()
    r = requests.post(f"{BASE}/agents/register",
                      json={"name": name, "kind": "bot"}, timeout=30)
    if r.status_code == 409:
        sys.exit(f"'{name}' is already registered but {key_file} is missing. "
                 "The raw key is unrecoverable; register under a new name "
                 "rather than trying to reuse this one.")
    r.raise_for_status()
    key = r.json()["api_key"]
    with open(key_file, "w") as f:
        f.write(key)
    os.chmod(key_file, 0o600)
    print(f"registered {name}; key saved to {key_file}")
    return key


def week_picks(week, season=None):
    """(game_id, side, opponent, win_prob, source, is_home) per game.

    is_home is carried so the printout can say "at" for a road favourite. A
    road pick displayed as "vs" reads as the wrong team.
    """
    p = {"start_week": week, "weeks": 1}
    if season:
        p["season"] = season
    d = requests.get(f"{BASE}/data/survivor", params=p, timeout=30).json()
    out = []
    for w in d.get("weeks", []):
        for g in w["games"]:
            if g.get("home_wp") is None:
                continue
            if g["home_wp"] >= 0.5:
                side, opp, wp, home = g["home"], g["away"], g["home_wp"], True
            else:
                side, opp, wp, home = g["away"], g["home"], g["away_wp"], False
            out.append((g["game_id"], side, opp, wp, g["wp_source"], home))
    out.sort(key=lambda x: -x[3])
    return out


# ------------------------------------------------------------ close agent
def submit_close_wave(minutes_ahead, window_min, dry=False):
    """Back the market favourite in every game kicking off in ~minutes_ahead.

    Run by the scheduler immediately AFTER the closing snapshot, so the price
    it buys at is the one just captured -- which is the whole difference
    between this agent and the open one. Reads games straight from the
    database (it runs inside the web process) but submits through the HTTP API
    like everyone else, so the pick is server-priced and the invariants apply
    to it exactly as they do to a stranger's bot.

    Returns (submitted, failed, skipped).
    """
    from datetime import datetime, timedelta
    from app import (SessionLocal, Game, Pick, Agent, snapshot_at,
                     devig_two_way, wp_from_spread)

    key = os.environ.get("CLOSE_AGENT_KEY")
    if not key:
        print("close agent: CLOSE_AGENT_KEY not set — skipping")
        return (0, 0, 0)

    now = datetime.utcnow()
    lo = now + timedelta(minutes=minutes_ahead)
    hi = lo + timedelta(minutes=window_min)
    s = SessionLocal()
    try:
        games = (s.query(Game)
                   .filter(Game.final == False,  # noqa: E712
                           Game.kickoff >= lo, Game.kickoff < hi)
                   .order_by(Game.kickoff).all())
        agent = s.query(Agent).filter(Agent.name == CLOSE_NAME).first()
        # A pick is immutable, so re-submitting one is not merely wasteful, it
        # is a second live position on the same game.
        already = set()
        if agent:
            already = {p.game_id for p in s.query(Pick)
                       .filter(Pick.agent_id == agent.id).all()}
        plan = []
        for g in games:
            if g.id in already:
                continue
            snap = snapshot_at(s, g.id, now)
            if not snap:
                continue
            if snap.ml_home is not None and snap.ml_away is not None:
                hw = devig_two_way(snap.ml_home, snap.ml_away)
            elif snap.spread_home_line is not None:
                hw = wp_from_spread(snap.spread_home_line)
            else:
                continue
            if hw is None:
                continue
            side, wp = (g.home, hw) if hw >= 0.5 else (g.away, 1 - hw)
            plan.append((g.id, side, round(wp, 4)))
        skipped = len(games) - len(plan)
    finally:
        s.close()

    if not plan:
        print(f"close agent: nothing to pick ({len(games)} games in window, "
              f"{skipped} already picked or unpriced)")
        return (0, 0, skipped)
    if dry:
        for gid, side, wp in plan:
            print(f"  would pick {side} ({wp*100:.1f}%) {gid}")
        return (0, 0, skipped)

    ok = fail = 0
    for gid, side, wp in plan:
        r = requests.post(f"{BASE}/picks", headers={"x-api-key": key},
                          json={"game_id": gid, "market": "moneyline",
                                "side": side, "stake_units": 1.0,
                                "confidence": wp,
                                "model_version": MODEL_VERSION,
                                "mode": "live"}, timeout=30)
        if r.status_code == 200:
            ok += 1
        else:
            fail += 1
            print(f"close agent: {side} {gid} failed {r.status_code} {r.text[:100]}")
    print(f"close agent: submitted {ok}, failed {fail}, skipped {skipped}")
    return (ok, fail, skipped)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--season", type=int)
    ap.add_argument("--submit", action="store_true",
                    help="actually send them; picks are IMMUTABLE once sent")
    a = ap.parse_args()

    picks = week_picks(a.week, a.season)
    if not picks:
        sys.exit(f"no priced games found for week {a.week}")

    # A benchmark has to take every game, including the ones nobody wants. But
    # a 50.4% pick and an 82% pick are not the same claim, and printing them in
    # the same ink invites reading the bottom of the list as advice.
    RED, AMBER, DIM, OFF = "\033[31m", "\033[33m", "\033[2m", "\033[0m"
    COIN, THIN = 0.55, 0.60

    def paint(wp):
        if wp < COIN:
            return RED, "COIN FLIP - forced side"
        if wp < THIN:
            return AMBER, "thin"
        return "", ""

    est = sum(1 for p in picks if p[4] == "prior")
    print(f"WEEK {a.week}: {len(picks)} games, backing the market favourite in each")
    if est:
        print(f"  WARNING: {est} of these are power-rating estimates, not real "
              f"lines. This agent is supposed to be the market; do not submit "
              f"estimates under its name.")
    print()
    for gid, side, opp, wp, src, home in picks:
        col, note = paint(wp)
        print(f"  {col}{side:<4} {'vs' if home else 'at'} {opp:<4} {wp*100:5.1f}%"
              f"{OFF}  {col}{note:<24}{OFF}{DIM}{gid}{OFF}")
    nc = sum(1 for p in picks if p[3] < COIN)
    nt = sum(1 for p in picks if COIN <= p[3] < THIN)
    print(f"\n  {RED}{nc} coin flip{'' if nc == 1 else 's'}{OFF} (under "
          f"{COIN*100:.0f}%), {AMBER}{nt} thin{OFF} ({COIN*100:.0f}-{THIN*100:.0f}%), "
          f"{len(picks)-nc-nt} clear.")
    print("  The benchmark takes every game on purpose. Skipping the ugly ones "
          "would make it a strategy,\n  and then it no longer measures what the "
          "market is worth.")

    if not a.submit:
        print(f"\nDRY RUN — nothing sent. Add --submit to lock these in.")
        return

    key = get_key()
    ok = fail = 0
    for gid, side, opp, wp, src, home in picks:
        r = requests.post(f"{BASE}/picks",
                          headers={"x-api-key": key},
                          json={"game_id": gid, "market": "moneyline",
                                "side": side, "stake_units": 1.0,
                                "confidence": round(wp, 4),
                                "model_version": MODEL_VERSION, "mode": "live"},
                          timeout=30)
        if r.status_code == 200:
            ok += 1
        else:
            fail += 1
            print(f"  FAILED {side} ({gid}): {r.status_code} {r.text[:120]}")
    print(f"\nsubmitted {ok}, failed {fail}")


if __name__ == "__main__":
    main()
