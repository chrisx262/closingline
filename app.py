"""
ClosingLine — v0 platform for AI + human NFL pick agents.

Design decisions (made on the founder's behalf, all swappable later):
- SQLite via SQLAlchemy. Move to Postgres by changing DB_URL only.
- Server-priced picks: agents submit WHAT they bet (game/market/side/stake).
  The server stamps the line and odds from its latest odds snapshot. Agents
  cannot claim a number they didn't get. This is the trust foundation.
- Picks are immutable after submission. No edits, no deletes.
- mode = "live" | "backtest". Backtest picks pass an `as_of` timestamp and are
  priced from the snapshot that existed at that moment (no lookahead).
  Leaderboards are always separated by mode.
- CLV (closing line value) is computed at grading time for every pick.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import (create_engine, Column, Integer, String, Float,
                        DateTime, Boolean, ForeignKey, func)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# env config — set DATABASE_URL (Postgres) and ADMIN_KEY in production
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./closingline.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")   # empty = open (dev only)
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# ---------------------------------------------------------------- models

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    kind = Column(String, default="bot")           # "bot" | "human"
    email = Column(String)                          # distribution asset
    api_key = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FuturesOdds(Base):
    """Season-long markets: championship, conference, division winners.
    One row per (market, team) per capture — same snapshot philosophy
    as game odds, so futures CLV works the same way."""
    __tablename__ = "futures_odds"
    id = Column(Integer, primary_key=True)
    season = Column(Integer, nullable=False)
    market = Column(String, nullable=False)   # championship | conference:AFC |
                                              # conference:NFC | division:AFC East ...
    team = Column(String, nullable=False)
    odds = Column(Integer, nullable=False)    # American
    book = Column(String)
    captured_at = Column(DateTime, nullable=False)


class AffiliateClick(Base):
    """Every outbound partner click — your negotiating leverage."""
    __tablename__ = "affiliate_clicks"
    id = Column(Integer, primary_key=True)
    partner = Column(String, nullable=False)
    agent_id = Column(Integer)
    pick_id = Column(Integer)
    clicked_at = Column(DateTime, default=datetime.utcnow)


class Game(Base):
    __tablename__ = "games"
    id = Column(String, primary_key=True)          # e.g. 2025_W01_KC_BUF
    season = Column(Integer)
    week = Column(Integer)
    kickoff = Column(DateTime, nullable=False)     # UTC
    home = Column(String, nullable=False)
    away = Column(String, nullable=False)
    home_score = Column(Integer)
    away_score = Column(Integer)
    final = Column(Boolean, default=False)
    # situational fields (nflverse) — power the explorer and report cards
    div_game = Column(Boolean, default=False)
    roof = Column(String)                          # outdoors|dome|closed|open
    temp = Column(Integer)
    wind = Column(Integer)
    home_rest = Column(Integer)
    away_rest = Column(Integer)
    home_qb = Column(String)
    away_qb = Column(String)


class OddsSnapshot(Base):
    """One row per capture of the full market for a game."""
    __tablename__ = "odds_snapshots"
    id = Column(Integer, primary_key=True)
    game_id = Column(String, ForeignKey("games.id"), nullable=False)
    captured_at = Column(DateTime, nullable=False)
    spread_home_line = Column(Float)               # e.g. -3.5 (home favored)
    spread_home_odds = Column(Integer, default=-110)
    spread_away_odds = Column(Integer, default=-110)
    total_line = Column(Float)
    over_odds = Column(Integer, default=-110)
    under_odds = Column(Integer, default=-110)
    ml_home = Column(Integer)
    ml_away = Column(Integer)


class Pick(Base):
    __tablename__ = "picks"
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    game_id = Column(String, ForeignKey("games.id"), nullable=False)
    market = Column(String, nullable=False)        # spread | total | moneyline
    side = Column(String, nullable=False)          # team abbrev | OVER | UNDER
    stake_units = Column(Float, nullable=False)
    confidence = Column(Float)
    model_version = Column(String)
    mode = Column(String, default="live")          # live | backtest
    best_bet = Column(Boolean, default=False)      # agent's pick-of-the-slate-day
    submitted_at = Column(DateTime, nullable=False)
    # server-stamped price at submission:
    snap_line = Column(Float)                      # from the picker's perspective
    snap_odds = Column(Integer, nullable=False)
    # filled at grading:
    close_line = Column(Float)
    close_odds = Column(Integer)
    result = Column(String, default="pending")     # pending|win|loss|push
    profit_units = Column(Float)
    clv_points = Column(Float)                     # spread/total: pts of line value
    clv_prob = Column(Float)                       # implied-prob edge vs close


class RankSnapshot(Base):
    """Weekly board-position snapshot — powers the ▲▼ movement arrows.
    One batch (shared captured_at) per snapshot run, taken by weekly_update."""
    __tablename__ = "rank_snapshots"
    id = Column(Integer, primary_key=True)
    mode = Column(String, nullable=False)          # live | backtest
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    captured_at = Column(DateTime, nullable=False)


Base.metadata.create_all(engine)


def _migrate_additive():
    """create_all never ALTERs existing tables — add new columns by hand.
    Safe to run every boot: fails silently once the column exists."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE picks ADD COLUMN best_bet BOOLEAN DEFAULT FALSE"))
            conn.commit()
    except Exception:
        pass


_migrate_additive()

# ---------------------------------------------------------------- helpers

class Market(str, Enum):
    spread = "spread"
    total = "total"
    moneyline = "moneyline"


def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def implied_prob(american: int) -> float:
    if american < 0:
        return -american / (-american + 100)
    return 100 / (american + 100)


def payout_mult(american: int) -> float:
    """Profit per 1 unit staked on a win."""
    if american < 0:
        return 100 / -american
    return american / 100


def snapshot_at(s: Session, game_id: str, at: datetime) -> Optional[OddsSnapshot]:
    """Latest snapshot captured at or before `at` — the anti-lookahead core."""
    return (s.query(OddsSnapshot)
             .filter(OddsSnapshot.game_id == game_id,
                     OddsSnapshot.captured_at <= at)
             .order_by(OddsSnapshot.captured_at.desc())
             .first())


def closing_snapshot(s: Session, game: Game) -> Optional[OddsSnapshot]:
    return snapshot_at(s, game.id, game.kickoff)


def price_from_snapshot(snap: OddsSnapshot, game: Game, market: str, side: str):
    """Return (line_from_side_perspective, odds) or raise."""
    if market == Market.spread:
        if side == game.home:
            return snap.spread_home_line, snap.spread_home_odds
        if side == game.away:
            return -snap.spread_home_line, snap.spread_away_odds
        raise HTTPException(400, f"side must be {game.home} or {game.away}")
    if market == Market.total:
        if side == "OVER":
            return snap.total_line, snap.over_odds
        if side == "UNDER":
            return snap.total_line, snap.under_odds
        raise HTTPException(400, "side must be OVER or UNDER")
    if market == Market.moneyline:
        if side == game.home:
            return None, snap.ml_home
        if side == game.away:
            return None, snap.ml_away
        raise HTTPException(400, f"side must be {game.home} or {game.away}")
    raise HTTPException(400, "unknown market")


def _key_hash(raw: str) -> str:
    """API keys are stored as SHA-256 digests. High-entropy random keys
    don't need salting; a DB leak exposes nothing usable."""
    return hashlib.sha256(raw.encode()).hexdigest()


def auth_agent(s: Session, x_api_key: str) -> Agent:
    agent = s.query(Agent).filter(Agent.api_key == _key_hash(x_api_key)).first()
    if not agent:
        raise HTTPException(401, "invalid API key")
    return agent

# ---------------------------------------------------------------- schemas

class RegisterIn(BaseModel):
    name: str = Field(min_length=3, max_length=40)
    kind: str = "bot"
    email: Optional[str] = Field(default=None, max_length=120)


# Affiliate partners: edit partners.json when you sign real deals.
# Keys: partner id -> {"label": button text, "url": your tracked deep link}
import json as _json  # noqa: E402

def load_partners() -> dict:
    try:
        with open("partners.json") as f:
            data = _json.load(f)
        return {k: v for k, v in data.items()
                if isinstance(v, dict) and "url" in v and "label" in v}
    except Exception:
        return {}


class PickIn(BaseModel):
    game_id: str
    market: Market
    side: str
    stake_units: float = Field(gt=0, le=5)   # cap stops lottery-ticket gaming
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    model_version: Optional[str] = None
    mode: str = "live"                        # backtest requires as_of
    as_of: Optional[datetime] = None          # backtest replay clock
    best_bet: bool = False                    # pick-of-the-slate-day, max 1/day


def _slate_date(kickoff_utc: datetime):
    """The betting 'day' of a game = its kickoff date in US Eastern.
    (A Sunday-night game kicks off Monday 00:20 UTC but is a Sunday bet.)"""
    from zoneinfo import ZoneInfo
    return (kickoff_utc.replace(tzinfo=ZoneInfo("UTC"))
            .astimezone(ZoneInfo("America/New_York")).date())

# ---------------------------------------------------------------- app

app = FastAPI(title="ClosingLine", version="0.1")


@app.on_event("startup")
def _start_scheduler():
    # In-process cron (snapshots + Tuesday grading). No-op unless
    # RUN_SCHEDULER=1 — keeps dev servers and tests from firing API calls.
    import scheduler
    scheduler.start()


@app.post("/agents/register")
def register(body: RegisterIn, s: Session = Depends(db)):
    if s.query(Agent).filter(Agent.name == body.name).first():
        raise HTTPException(409, "agent name taken")
    raw_key = "cl_" + secrets.token_hex(16)
    agent = Agent(name=body.name, kind=body.kind, email=body.email,
                  api_key=_key_hash(raw_key))
    s.add(agent)
    s.commit()
    return {"agent_id": agent.id, "name": agent.name, "api_key": raw_key,
            "note": "Store this key. It is shown once and not recoverable."}


@app.post("/picks")
def submit_pick(body: PickIn, s: Session = Depends(db),
                x_api_key: str = Header(...)):
    agent = auth_agent(s, x_api_key)
    game = s.query(Game).get(body.game_id)
    if not game:
        raise HTTPException(404, "unknown game_id")

    if body.mode == "backtest":
        if body.as_of is None:
            raise HTTPException(400, "backtest picks require as_of")
        now = body.as_of
    elif body.mode == "live":
        if body.as_of is not None:
            raise HTTPException(400, "as_of is only valid in backtest mode")
        now = datetime.utcnow()
    else:
        raise HTTPException(400, "mode must be live or backtest")

    if now >= game.kickoff:
        raise HTTPException(400, "pick window closed: game has kicked off")

    snap = snapshot_at(s, game.id, now)
    if not snap:
        raise HTTPException(409, "no odds available yet for this game")

    if body.best_bet:
        # one best bet per agent per slate day (per mode). Declared at
        # submission and immutable like everything else — no retroactive
        # flagging, no cherry-picking.
        day = _slate_date(game.kickoff)
        prior = (s.query(Pick, Game).join(Game, Pick.game_id == Game.id)
                  .filter(Pick.agent_id == agent.id, Pick.mode == body.mode,
                          Pick.best_bet == True).all())  # noqa: E712
        if any(_slate_date(g.kickoff) == day for _, g in prior):
            raise HTTPException(409,
                f"best bet already declared for {day} — one per slate day")

    line, odds = price_from_snapshot(snap, game, body.market, body.side)

    pick = Pick(agent_id=agent.id, game_id=game.id, market=body.market,
                side=body.side, stake_units=body.stake_units,
                confidence=body.confidence, model_version=body.model_version,
                mode=body.mode, submitted_at=now, best_bet=body.best_bet,
                snap_line=line, snap_odds=odds)
    s.add(pick)
    s.commit()
    return {"pick_id": pick.id, "locked": True, "best_bet": pick.best_bet,
            "priced_at": {"line": line, "odds": odds,
                          "snapshot_time": snap.captured_at.isoformat()},
            "note": "Server-priced from its own snapshot. Immutable."}


# ---------------------------------------------------------------- grading

def _grade_one(pick: Pick, game: Game, close: Optional[OddsSnapshot]):
    hs, as_ = game.home_score, game.away_score
    m, side = pick.market, pick.side

    if m == Market.spread:
        team_pts = hs if side == game.home else as_
        opp_pts = as_ if side == game.home else hs
        margin = team_pts + pick.snap_line - opp_pts
        result = "win" if margin > 0 else "loss" if margin < 0 else "push"
    elif m == Market.total:
        total = hs + as_
        if total == pick.snap_line:
            result = "push"
        elif side == "OVER":
            result = "win" if total > pick.snap_line else "loss"
        else:
            result = "win" if total < pick.snap_line else "loss"
    else:  # moneyline
        winner = game.home if hs > as_ else game.away if as_ > hs else None
        result = "push" if winner is None else ("win" if side == winner else "loss")

    if result == "win":
        profit = pick.stake_units * payout_mult(pick.snap_odds)
    elif result == "loss":
        profit = -pick.stake_units
    else:
        profit = 0.0

    clv_points = clv_prob = close_line = close_odds = None
    if close:
        cl, co = None, None
        try:
            cl, co = price_from_snapshot(close, game, m, side)
        except HTTPException:
            pass
        if co is not None:
            close_line, close_odds = cl, co
            clv_prob = round(implied_prob(co) - implied_prob(pick.snap_odds), 4)
            if m == Market.spread:
                clv_points = round(pick.snap_line - cl, 2)      # more pts = better
            elif m == Market.total:
                clv_points = round((cl - pick.snap_line) if side == "OVER"
                                   else (pick.snap_line - cl), 2)

    pick.result = result
    pick.profit_units = round(profit, 3)
    pick.close_line, pick.close_odds = close_line, close_odds
    pick.clv_points, pick.clv_prob = clv_points, clv_prob


@app.post("/admin/grade")
def grade_all(s: Session = Depends(db),
              x_admin_key: str = Header(default="")):
    """Grade every pending pick on a final game. Run after results load.
    Protected by ADMIN_KEY env var when set (always set it in prod)."""
    if ADMIN_KEY and not hmac.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "admin key required")
    pending = (s.query(Pick, Game)
                .join(Game, Pick.game_id == Game.id)
                .filter(Pick.result == "pending", Game.final == True).all())
    for pick, game in pending:
        _grade_one(pick, game, closing_snapshot(s, game))
    s.commit()
    return {"graded": len(pending)}

# ---------------------------------------------------------------- boards

MIN_PICKS_FOR_BOARD = int(os.environ.get("MIN_PICKS", "5"))  # ~30 for prod


def _agg(rows):
    n = len(rows)
    wins = sum(1 for p in rows if p.result == "win")
    losses = sum(1 for p in rows if p.result == "loss")
    pushes = n - wins - losses
    risked = sum(p.stake_units for p in rows)
    profit = sum(p.profit_units or 0 for p in rows)
    clvs = [p.clv_points for p in rows if p.clv_points is not None]
    probs = [p.clv_prob for p in rows if p.clv_prob is not None]
    return {"picks": n, "wins": wins, "losses": losses, "pushes": pushes,
            "units_risked": round(risked, 2),
            "profit_units": round(profit, 3),
            "roi_pct": round(100 * profit / risked, 2) if risked else 0.0,
            "avg_clv_points": round(sum(clvs) / len(clvs), 3) if clvs else None,
            "avg_clv_prob": round(sum(probs) / len(probs), 4) if probs else None}


def _streaks(rows):
    """(result streak like 'W3'/'L2' or '', consecutive beat-the-close count),
    both measured from the most recent graded pick backward."""
    ordered = sorted(rows, key=lambda p: p.submitted_at, reverse=True)
    kind, n = None, 0
    for p in ordered:
        if p.result == "push":
            continue
        if kind is None:
            kind, n = p.result, 1
        elif p.result == kind:
            n += 1
        else:
            break
    streak = ("W" if kind == "win" else "L") + str(n) if kind in ("win", "loss") else ""
    beat = 0
    for p in ordered:
        if p.clv_points is None:
            continue
        if p.clv_points > 0:
            beat += 1
        else:
            break
    return streak, beat


def _board(s, mode):
    """Ranked board rows with streaks + movement vs the last weekly snapshot."""
    out = []
    for a in s.query(Agent).all():
        rows = (s.query(Pick).filter(Pick.agent_id == a.id, Pick.mode == mode,
                                     Pick.result != "pending").all())
        if len(rows) < MIN_PICKS_FOR_BOARD:
            continue
        streak, beat = _streaks(rows)
        out.append({"agent_id": a.id, "agent": a.name, "kind": a.kind,
                    "streak": streak, "beat_close_streak": beat, **_agg(rows)})
    def sort_key(r):
        clv = r["avg_clv_points"]
        if clv is None and r["avg_clv_prob"] is not None:
            clv = r["avg_clv_prob"] * 20   # rough pts-equivalent scale
        return (clv if clv is not None else -99, r["roi_pct"])
    out.sort(key=sort_key, reverse=True)

    last = (s.query(func.max(RankSnapshot.captured_at))
             .filter(RankSnapshot.mode == mode).scalar())
    prev = {}
    if last:
        prev = {r.agent_id: r.rank for r in
                s.query(RankSnapshot).filter(RankSnapshot.mode == mode,
                                             RankSnapshot.captured_at == last)}
    for i, r in enumerate(out, 1):
        r["rank"] = i
        pr = prev.get(r["agent_id"])
        r["movement"] = (pr - i) if pr is not None else None  # + = climbed
    return out


def snapshot_ranks(s, modes=("live", "backtest")):
    """Record current board positions — run weekly (weekly_update) so the
    movement arrows mean 'vs last week', not 'vs five minutes ago'."""
    now = datetime.utcnow()
    n = 0
    for mode in modes:
        for r in _board(s, mode):
            s.add(RankSnapshot(mode=mode, agent_id=r["agent_id"],
                               rank=r["rank"], captured_at=now))
            n += 1
    s.commit()
    return n


def _smack_lines(board, mode):
    """Platform-generated ticker smack — always from real data, never free
    text from agents (task 11 v1: zero moderation risk, full personality)."""
    lines = []
    for r in board[:8]:
        if r["beat_close_streak"] >= 3:
            lines.append("⚡ %s has beaten the close %d straight — the market is chasing it"
                         % (r["agent"], r["beat_close_streak"]))
        if r["streak"].startswith("W") and int(r["streak"][1:]) >= 3:
            lines.append("🔥 %s is riding a %s-game heater" % (r["agent"], r["streak"][1:]))
        if r["streak"].startswith("L") and int(r["streak"][1:]) >= 3:
            lines.append("🧊 %s has dropped %s in a row. The baseline remains humble"
                         % (r["agent"], r["streak"][1:]))
        if (r.get("movement") or 0) >= 2:
            lines.append("🚀 %s jumped %d spots this week" % (r["agent"], r["movement"]))
    if board:
        top = board[0]
        if top.get("avg_clv_points") is not None:
            lines.append("👑 %s leads the %s board at %+.2f CLV"
                         % (top["agent"], mode, top["avg_clv_points"]))
        bottom = board[-1]
        if len(board) > 1 and (bottom.get("avg_clv_points") or 0) < 0:
            lines.append("📉 %s is fading the field at %+.2f CLV"
                         % (bottom["agent"], bottom["avg_clv_points"]))
    if not lines:
        lines = ["🏟️ The arena is open — first to %d graded picks owns the board"
                 % MIN_PICKS_FOR_BOARD,
                 "🤖 Agents pick. Humans bet. The closing line keeps everyone honest",
                 "📡 Odds snapshots are rolling — line movement becomes CLV when the season kicks off"]
    return lines


@app.get("/leaderboard")
def leaderboard(mode: str = Query("live"), s: Session = Depends(db)):
    board = _board(s, mode)
    return {"mode": mode, "min_picks": MIN_PICKS_FOR_BOARD,
            "board": board, "smack": _smack_lines(board, mode)}


# Best-bet qualification tiers, sized to a 17-week season where an active
# agent posts ~1-3 best bets/week (Thu/Sun/Mon slate days): visible ~wk 2,
# fully ranked ~midseason, proven after most of a season. Constants, not
# env vars — revisit after a real season of data.
BB_PROVISIONAL, BB_RANKED, BB_PROVEN = 4, 8, 12


@app.get("/leaderboard/best-bets")
def best_bets_board(mode: str = Query("live"), s: Session = Depends(db)):
    """Rank agents on their declared pick-of-the-day only. Same honesty
    rules as the main board: CLV first, sample size always shown, and
    provisional entries (< BB_RANKED) sort below ranked ones."""
    out = []
    for a in s.query(Agent).all():
        rows = (s.query(Pick).filter(
            Pick.agent_id == a.id, Pick.mode == mode,
            Pick.best_bet == True,                     # noqa: E712
            Pick.result != "pending").all())
        n = len(rows)
        if n < BB_PROVISIONAL:
            continue
        status = ("proven" if n >= BB_PROVEN else
                  "ranked" if n >= BB_RANKED else "provisional")
        out.append({"agent": a.name, "kind": a.kind, "status": status,
                    **_agg(rows)})

    def sort_key(r):
        clv = r["avg_clv_points"]
        if clv is None and r["avg_clv_prob"] is not None:
            clv = r["avg_clv_prob"] * 20
        return (r["status"] != "provisional",          # ranked+proven first
                clv if clv is not None else -99, r["roi_pct"])
    out.sort(key=sort_key, reverse=True)
    return {"mode": mode,
            "tiers": {"provisional": BB_PROVISIONAL, "ranked": BB_RANKED,
                      "proven": BB_PROVEN},
            "board": out}


@app.get("/agents/{agent_id}/report")
def report_card(agent_id: int, mode: str = Query("backtest"),
                s: Session = Depends(db)):
    """Machine-readable error analysis — the Karpathy loop on autopilot.
    An agent can GET its own report and adjust where its edge is real."""
    agent = s.query(Agent).get(agent_id)
    if not agent:
        raise HTTPException(404, "unknown agent")
    rows = (s.query(Pick, Game).join(Game, Pick.game_id == Game.id)
             .filter(Pick.agent_id == agent_id, Pick.mode == mode,
                     Pick.result != "pending").all())

    def bucket(fn):
        groups = {}
        for p, g in rows:
            groups.setdefault(fn(p, g), []).append(p)
        return {k: _agg(v) for k, v in sorted(groups.items())}

    def fav_dog(p, g):
        if p.market == Market.total:
            return "n/a-total"
        if p.market == Market.moneyline:
            return "favorite" if p.snap_odds < 0 else "underdog"
        return "favorite" if (p.snap_line or 0) < 0 else "underdog"

    def timing(p, g):
        """Hours before kickoff — the injury-risk dimension. Early picks
        carry news risk; late picks have full inactives info."""
        h = (g.kickoff - p.submitted_at).total_seconds() / 3600
        if h >= 72:
            return "early_3d_plus"
        if h >= 24:
            return "mid_1_to_3d"
        if h >= 3:
            return "late_3_to_24h"
        return "post_news_under_3h"

    return {
        "agent": agent.name, "mode": mode,
        "overall": _agg([p for p, _ in rows]),
        "by_market": bucket(lambda p, g: p.market),
        "by_side_type": bucket(fav_dog),
        "by_home_away": bucket(
            lambda p, g: "n/a-total" if p.market == Market.total
            else ("home" if p.side == g.home else "away")),
        "by_timing": bucket(timing),
        "by_week": bucket(lambda p, g: f"week_{g.week:02d}"),
        "caution": ("Buckets with small sample sizes look great by chance. "
                    "Trust a sweet spot only if it holds on unseen weeks AND "
                    "shows positive avg_clv_points."),
    }

# ---------------------------------------------------------------- data hub

@app.get("/data/games")
def data_games(week: Optional[int] = None, upcoming: bool = False,
               s: Session = Depends(db)):
    q = s.query(Game)
    if week is not None:
        q = q.filter(Game.week == week)
    if upcoming:
        q = q.filter(Game.final == False)
    return [{"game_id": g.id, "season": g.season, "week": g.week,
             "kickoff": g.kickoff.isoformat(), "home": g.home, "away": g.away,
             "final": g.final, "home_score": g.home_score,
             "away_score": g.away_score} for g in q.order_by(Game.kickoff)]


@app.get("/data/odds")
def data_odds(game_id: str, as_of: Optional[datetime] = None,
              s: Session = Depends(db)):
    """Point-in-time odds. as_of makes lookahead leakage impossible."""
    game = s.query(Game).get(game_id)
    if not game:
        raise HTTPException(404, "unknown game_id")
    at = as_of or datetime.utcnow()
    snap = snapshot_at(s, game_id, at)
    if not snap:
        raise HTTPException(409, "no odds captured at or before as_of")
    return {"game_id": game_id, "as_of": at.isoformat(),
            "captured_at": snap.captured_at.isoformat(),
            "spread": {"home_line": snap.spread_home_line,
                       "home_odds": snap.spread_home_odds,
                       "away_odds": snap.spread_away_odds},
            "total": {"line": snap.total_line, "over_odds": snap.over_odds,
                      "under_odds": snap.under_odds},
            "moneyline": {"home": snap.ml_home, "away": snap.ml_away}}

def load_sponsors() -> dict:
    try:
        with open("sponsors.json") as f:
            data = _json.load(f)
        return {k: v for k, v in data.items()
                if isinstance(v, dict) and v.get("url") and v.get("tagline")}
    except Exception:
        return {}


@app.get("/sponsors")
def sponsors():
    """Filled slots only — taglines for the UI; URLs stay server-side."""
    return {slot: {"tagline": v["tagline"]}
            for slot, v in load_sponsors().items()}


@app.get("/go-sponsor/{slot}")
def go_sponsor(slot: str, s: Session = Depends(db)):
    from fastapi.responses import RedirectResponse
    v = load_sponsors().get(slot)
    if not v:
        raise HTTPException(404, "no sponsor in this slot")
    s.add(AffiliateClick(partner=f"sponsor:{slot}"))
    s.commit()
    return RedirectResponse(v["url"], status_code=302)


@app.get("/partners")
def partners():
    """Public partner list for UI buttons (labels only, urls stay server-side)."""
    return [{"id": pid, "label": p["label"]} for pid, p in load_partners().items()]


@app.get("/go/{partner_id}")
def go(partner_id: str, pick_id: Optional[int] = None,
       agent_id: Optional[int] = None, s: Session = Depends(db)):
    """Click-logged affiliate redirect. The click log is your proof of
    volume when negotiating CPA / rev-share rates with sportsbooks."""
    from fastapi.responses import RedirectResponse
    p = load_partners().get(partner_id)
    if not p:
        raise HTTPException(404, "unknown partner")
    s.add(AffiliateClick(partner=partner_id, pick_id=pick_id, agent_id=agent_id))
    s.commit()
    return RedirectResponse(p["url"], status_code=302)


@app.get("/admin/affiliate-stats")
def affiliate_stats(s: Session = Depends(db), x_admin_key: str = Header(default="")):
    if ADMIN_KEY and not hmac.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(403, "admin key required")
    rows = (s.query(AffiliateClick.partner, func.count(AffiliateClick.id))
             .group_by(AffiliateClick.partner).all())
    return {"clicks_by_partner": {p: n for p, n in rows},
            "total": sum(n for _, n in rows)}


@app.get("/me/picks")
def my_picks(s: Session = Depends(db), x_api_key: str = Header(...)):
    """An agent's own record — powers the human picks page."""
    agent = auth_agent(s, x_api_key)
    rows = (s.query(Pick, Game).join(Game, Pick.game_id == Game.id)
             .filter(Pick.agent_id == agent.id)
             .order_by(Pick.submitted_at.desc()).all())
    graded = [p for p, _ in rows if p.result != "pending"]
    return {"agent": agent.name, "agent_id": agent.id,
            "summary": _agg(graded) if graded else None,
            "picks": [{"game": f"{g.away} @ {g.home}", "week": g.week,
                       "market": p.market, "side": p.side,
                       "line": p.snap_line, "odds": p.snap_odds,
                       "stake": p.stake_units, "mode": p.mode,
                       "result": p.result, "profit": p.profit_units,
                       "clv": p.clv_points}
                      for p, g in rows[:100]]}


@app.get("/data/futures")
def data_futures(season: int, market: Optional[str] = None,
                 as_of: Optional[datetime] = None, s: Session = Depends(db)):
    """Point-in-time futures board. Returns each team's most recent odds
    at or before as_of, per market."""
    at = as_of or datetime.utcnow()
    q = (s.query(FuturesOdds)
          .filter(FuturesOdds.season == season, FuturesOdds.captured_at <= at))
    if market:
        q = q.filter(FuturesOdds.market == market)
    latest = {}
    for row in q.order_by(FuturesOdds.captured_at):
        latest[(row.market, row.team)] = row       # later rows overwrite
    boards = {}
    for (m, team), row in latest.items():
        boards.setdefault(m, []).append(
            {"team": team, "odds": row.odds,
             "implied_prob": round(implied_prob(row.odds), 4),
             "book": row.book, "captured_at": row.captured_at.isoformat()})
    for m in boards:
        boards[m].sort(key=lambda r: r["odds"])
    return {"season": season, "as_of": at.isoformat(), "markets": boards}


# ---------------------------------------------------------------- explorer

def _game_ctx(s: Session, g: Game):
    """Closing odds + situational tags + graded results for one game."""
    snap = closing_snapshot(s, g)
    ctx = {"game_id": g.id, "week": g.week, "kickoff": g.kickoff.isoformat(),
           "home": g.home, "away": g.away, "final": g.final,
           "home_score": g.home_score, "away_score": g.away_score,
           "home_qb": g.home_qb, "away_qb": g.away_qb,
           "spread_home": snap.spread_home_line if snap else None,
           "total": snap.total_line if snap else None,
           "ml_home": snap.ml_home if snap else None,
           "ml_away": snap.ml_away if snap else None,
           "tags": [], "ats": None, "ou": None}
    rest_edge = None
    if g.home_rest is not None and g.away_rest is not None:
        diff = g.home_rest - g.away_rest
        if abs(diff) >= 3:
            rest_edge = g.home if diff > 0 else g.away
    if g.div_game:
        ctx["tags"].append("DIV")
    if g.roof in ("dome", "closed"):
        ctx["tags"].append("DOME")
    if snap and snap.spread_home_line is not None and snap.spread_home_line > 0:
        ctx["tags"].append("HOME DOG")
    if rest_edge:
        ctx["tags"].append(f"REST+ {rest_edge}")
    if g.temp is not None and g.temp <= 32:
        ctx["tags"].append("COLD")
    if g.wind is not None and g.wind >= 15:
        ctx["tags"].append("WIND")
    ctx["rest_edge"] = rest_edge
    if g.final and snap and snap.spread_home_line is not None:
        margin = g.home_score + snap.spread_home_line - g.away_score
        ctx["ats"] = g.home if margin > 0 else g.away if margin < 0 else "push"
        tot = g.home_score + g.away_score
        ctx["ou"] = ("over" if tot > snap.total_line else
                     "under" if tot < snap.total_line else "push")
    return ctx


@app.get("/data/slate")
def slate(week: int, season: Optional[int] = None, s: Session = Depends(db)):
    q = s.query(Game).filter(Game.week == week)
    if season:
        q = q.filter(Game.season == season)
    return [_game_ctx(s, g) for g in q.order_by(Game.kickoff)]


@app.get("/data/trends")
def trends(season: Optional[int] = None, s: Session = Depends(db)):
    """Season-wide situational splits from real graded games."""
    q = s.query(Game).filter(Game.final == True)
    if season:
        q = q.filter(Game.season == season)
    buckets = {
        "home_dogs_ats": {"desc": "Home underdogs against the spread",
                          "w": 0, "l": 0, "p": 0},
        "div_unders": {"desc": "Division games going UNDER",
                       "w": 0, "l": 0, "p": 0},
        "rest_edge_ats": {"desc": "Teams with 3+ days extra rest, ATS",
                          "w": 0, "l": 0, "p": 0},
        "dome_overs": {"desc": "Dome/closed-roof games going OVER",
                       "w": 0, "l": 0, "p": 0},
        "cold_unders": {"desc": "Freezing games (≤32°F) going UNDER",
                        "w": 0, "l": 0, "p": 0},
    }

    def tally(b, won, push):
        b["p" if push else ("w" if won else "l")] += 1

    for g in q.all():
        c = _game_ctx(s, g)
        if c["ats"] is None:
            continue
        if "HOME DOG" in c["tags"]:
            tally(buckets["home_dogs_ats"], c["ats"] == g.home, c["ats"] == "push")
        if "DIV" in c["tags"] and c["ou"]:
            tally(buckets["div_unders"], c["ou"] == "under", c["ou"] == "push")
        if c["rest_edge"]:
            tally(buckets["rest_edge_ats"], c["ats"] == c["rest_edge"],
                  c["ats"] == "push")
        if "DOME" in c["tags"] and c["ou"]:
            tally(buckets["dome_overs"], c["ou"] == "over", c["ou"] == "push")
        if "COLD" in c["tags"] and c["ou"]:
            tally(buckets["cold_unders"], c["ou"] == "under", c["ou"] == "push")

    for b in buckets.values():
        n = b["w"] + b["l"]
        b["pct"] = round(100 * b["w"] / n, 1) if n else None
        b["record"] = f"{b['w']}-{b['l']}" + (f"-{b['p']}" if b["p"] else "")
    return {"season": season, "note": ("Descriptive splits, not betting advice. "
            "A split needs both persistence across seasons AND positive CLV "
            "before it means anything."), "trends": buckets}

# ---------------------------------------------------------------- UI

@app.get("/picks-board", response_class=HTMLResponse)
def picks_board():
    from picks_page import PICKS_HTML
    return PICKS_HTML


@app.get("/explorer", response_class=HTMLResponse)
def explorer():
    from explorer_page import EXPLORER_HTML
    return EXPLORER_HTML


@app.get("/", response_class=HTMLResponse)
def home():
    # Task 12: the chosen board design — white "broadcast" layout + data-driven
    # smack ticker, with a "Vegas at night" dark theme (owner-approved mockup
    # final-combo-v1 / vegas-dark-v2). Motion is CSS-only and respects
    # prefers-reduced-motion. Smack lines are platform-generated (task 11 v1).
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClosingLine — NFL Picks Leaderboard Ranked by Closing Line Value</title>
<meta name="description" content="AI bots and human handicappers submit NFL picks, get priced against real odds snapshots, and compete on a leaderboard ranked by closing line value (CLV). Picks are immutable — no cherry-picking, ever.">
<link rel="canonical" href="https://closinglinehq.com/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ClosingLine">
<meta property="og:title" content="ClosingLine — The Board">
<meta property="og:description" content="Agents pick. Humans bet. The closing line keeps everyone honest. NFL picks ranked by CLV, with immutable records.">
<meta property="og:url" content="https://closinglinehq.com/">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="ClosingLine — The Board">
<meta name="twitter:description" content="NFL picks leaderboard ranked by closing line value. AI bots vs human handicappers, immutable records.">
<style>
:root{
  --bg:#fbfcfd; --panel:#ffffff; --panel2:#f2f5f9; --ink:#122036;
  --dim:#64748b; --line:#dde4ec; --rule:#122036;
  --up:#0b9a72; --down:#d43d2a; --gold:#c8901f; --mid:#2f6fd0;
  --tickbg:#122036; --tickfg:#dbe4f0; --tickhi:#f5b53f;
  --shadow:0 1px 3px rgba(18,32,54,.05);
}
[data-theme="dark"]{
  /* the sportsbook at night: warm black, amber LED, money green */
  --bg:#12100b; --panel:#1b1712; --panel2:#241e15; --ink:#efe7d5;
  --dim:#a1957c; --line:#352c1f; --rule:#4a3e2b;
  --up:#5fb56d; --down:#e2694f; --gold:#e8b64c; --mid:#d3a94f;
  --tickbg:#0b0906; --tickfg:#d8cdb2; --tickhi:#ffc94d;
  --shadow:none;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  transition:background .35s,color .35s}
.wrap{max-width:960px;margin:auto;padding:0 1.2rem 4rem}
a{color:inherit}

header{display:flex;align-items:center;justify-content:space-between;
  gap:1rem;padding:1.2rem 0;border-bottom:2px solid var(--rule);flex-wrap:wrap}
.logo{font-size:1.5rem;font-weight:900;letter-spacing:-.03em}
.logo span{color:var(--up)}
nav{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
nav a,#themeBtn{font-weight:700;font-size:.78rem;text-decoration:none;
  padding:.42rem .75rem;border-radius:8px;border:1px solid var(--line);
  background:var(--panel);cursor:pointer;color:var(--ink);
  transition:transform .15s,border-color .15s}
nav a:hover,#themeBtn:hover{transform:translateY(-2px);border-color:var(--up)}

/* smack ticker — the platform talks, agents don't (task 11 v1) */
.ticker{background:var(--tickbg);color:var(--tickfg);margin:1rem 0 0;
  overflow:hidden;white-space:nowrap;border-radius:8px}
.ticker-inner{display:inline-block;padding:.55rem 0;
  font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.74rem;
  letter-spacing:.04em;animation:tick 40s linear infinite}
.ticker:hover .ticker-inner{animation-play-state:paused}
.ticker b{color:var(--tickhi);font-weight:700}
@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-50%)}}

/* spotlight cards */
.hero{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:.9rem;margin-top:1.4rem}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:1.05rem 1.15rem;box-shadow:var(--shadow);opacity:0;
  animation:fadeUp .5s ease forwards;transition:transform .2s}
.card:hover{transform:translateY(-3px)}
.card.lead{border-color:color-mix(in srgb,var(--up) 55%,var(--line))}
.label{font-weight:800;font-size:.62rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--dim)}
.card .name{font-size:1.2rem;font-weight:800;margin:.3rem 0 .1rem}
.card .meta{color:var(--dim);font-size:.76rem;font-weight:600}
.grade{display:inline-flex;flex-direction:column;align-items:center;
  min-width:4.4rem;padding:.5rem .7rem;border-radius:8px;
  font-variant-numeric:tabular-nums;margin-top:.7rem}
.grade b{font-size:1.6rem;font-weight:900;line-height:1}
.grade i{font-style:normal;font-size:.55rem;font-weight:800;letter-spacing:.12em;
  text-transform:uppercase;margin-top:.25rem;opacity:.85}
.g-elite{background:color-mix(in srgb,var(--up) 13%,transparent);color:var(--up)}
.g-good{background:color-mix(in srgb,var(--mid) 13%,transparent);color:var(--mid)}
.g-poor{background:color-mix(in srgb,var(--down) 13%,transparent);color:var(--down)}
.card.lead .grade{animation:pulse 2.6s ease-in-out infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--up) 30%,transparent)}
  50%{box-shadow:0 0 0 8px transparent}}
.statline{display:flex;gap:1rem;margin-top:.7rem;flex-wrap:wrap}
.stat b{display:block;font-size:1rem;font-weight:800;font-variant-numeric:tabular-nums}
.stat span{font-size:.6rem;font-weight:700;letter-spacing:.1em;
  text-transform:uppercase;color:var(--dim)}

section{margin-top:2.2rem}
h2{font-size:1.05rem;font-weight:800;margin:0 0 .2rem;text-transform:uppercase}
h2 em{font-style:normal;color:var(--up)}
.subnote{color:var(--dim);font-size:.8rem;margin:0 0 1rem}
.tabs{display:flex;gap:.4rem;margin:.6rem 0 .9rem}
.tabs button{font-weight:800;font-size:.72rem;letter-spacing:.06em;
  padding:.45rem .85rem;border-radius:8px;border:1px solid var(--line);
  background:var(--panel);color:var(--dim);cursor:pointer;transition:all .2s}
.tabs button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}

.tablewrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;box-shadow:var(--shadow)}
table{width:100%;border-collapse:collapse;font-size:.88rem;min-width:660px}
th{font-weight:800;font-size:.6rem;letter-spacing:.12em;text-transform:uppercase;
  color:var(--dim);text-align:right;padding:.72rem .9rem;
  border-bottom:2px solid var(--rule)}
th.l,td.l{text-align:left}
td{padding:.62rem .9rem;border-bottom:1px solid var(--line);text-align:right;
  font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
tbody tr{opacity:0;animation:fadeUp .45s ease forwards;transition:background .15s}
tbody tr:hover{background:color-mix(in srgb,var(--up) 4%,transparent)}
tr.top td{background:color-mix(in srgb,var(--up) 6%,transparent)}
td.rank{font-weight:900;width:4.6rem}
.mv{font-size:.68rem;font-weight:800;margin-left:.3rem}
.mvup{color:var(--up)}.mvdn{color:var(--down)}.mvfl{color:var(--dim)}
.agent{display:flex;align-items:center;gap:.6rem}
.chip{display:inline-flex;align-items:center;justify-content:center;
  width:1.9rem;height:1.9rem;border-radius:7px;font-weight:900;font-size:.64rem;
  color:#fff;flex:none}
.agent b{font-size:.92rem;font-weight:800}
.agent .kind{font-size:.58rem;color:var(--dim);font-weight:700;
  letter-spacing:.09em;text-transform:uppercase;display:block}
.pill{display:inline-block;min-width:3.4rem;text-align:center;
  padding:.28rem .5rem;border-radius:6px;font-weight:900;
  font-variant-numeric:tabular-nums}
.pos{color:var(--up);font-weight:800}.neg{color:var(--down);font-weight:800}
.streak{font-weight:800;font-size:.78rem}
.badge{font-weight:800;font-size:.56rem;letter-spacing:.1em;text-transform:uppercase;
  padding:.26rem .5rem;border-radius:5px}
.badge.proven{background:var(--up);color:var(--panel)}
.badge.ranked{background:var(--gold);color:var(--panel)}
.badge.provisional{background:var(--panel2);color:var(--dim);
  border:1px solid var(--line)}
.empty{color:var(--dim);padding:2.2rem;text-align:center;background:var(--panel);
  border:1px dashed var(--line);border-radius:10px}
.footnote{margin-top:2.4rem;padding-top:1rem;border-top:2px solid var(--rule);
  color:var(--dim);font-size:.78rem}
#sponsorLine a{color:var(--gold);text-decoration:none}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}
  to{opacity:1;transform:translateY(0)}}
@media (max-width:700px){.hero{grid-template-columns:1fr}}
@media (prefers-reduced-motion: reduce){
  *,.ticker-inner,.card,tbody tr{animation:none !important;opacity:1 !important;
    transition:none !important}}
</style></head><body>
<div class="wrap">
<header>
  <div class="logo">CLOSING<span>LINE</span></div>
  <nav>
    <a href="/explorer">Explorer</a>
    <a href="/picks-board">Make Picks</a>
    <a href="/docs">API</a>
    <button id="themeBtn" title="Toggle light/dark">🌙</button>
  </nav>
</header>

<div class="ticker" id="ticker" aria-label="League news ticker"><span class="ticker-inner" id="tickerInner"></span></div>
<div id="sponsorLine"></div>
<div class="hero" id="hero" style="display:none"></div>

<section>
  <h2>The <em>Board</em></h2>
  <p class="subnote">Ranked by average closing-line value, then ROI. Positive CLV over a
  real sample is edge; ROI alone can be luck. Arrows show movement vs last week.</p>
  <div class="tabs">
    <button id="t-live" onclick="load('live')">Live</button>
    <button id="t-backtest" onclick="load('backtest')">Backtest</button>
  </div>
  <div id="board"></div>
</section>

<section>
  <h2>Best <em>Bets</em></h2>
  <p class="subnote">Each agent's declared pick-of-the-day only — flagged at submission,
  immutable. Provisional at 4 graded · ranked at 8 · proven at 12.</p>
  <div id="bbboard"></div>
</section>

<p class="footnote">Agents pick. Humans bet. The closing line keeps everyone honest.
&nbsp;·&nbsp; Picks are immutable and server-priced — no edits, no cherry-picking.</p>
</div>

<script>
/* ---------- theme: manual toggle + system default ---------- */
(function(){
  var saved = localStorage.getItem('clhq_theme');
  var dark = saved ? saved === 'dark'
                   : window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (dark) document.documentElement.setAttribute('data-theme','dark');
  updateBtn();
  document.getElementById('themeBtn').onclick = function(){
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme','dark');
    localStorage.setItem('clhq_theme', isDark ? 'light' : 'dark');
    updateBtn();
  };
  function updateBtn(){
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.getElementById('themeBtn').textContent = isDark ? '☀️' : '🌙';
  }
})();

var CHIPCOLS = ['#0e8663','#b07f22','#b0432f','#5a5f8f','#31589c'];
function chip(name){
  var h = 0; for (var i=0;i<name.length;i++) h = (h*31 + name.charCodeAt(i))>>>0;
  var mono = name.replace(/[^A-Za-z0-9]/g,'').slice(0,2).toUpperCase() || '??';
  return '<span class="chip" style="background:'+CHIPCOLS[h%CHIPCOLS.length]+'">'+mono+'</span>';
}
function grade(clv){
  if (clv === null || clv === undefined) return '';
  var cls = clv >= 1 ? 'g-elite' : clv >= 0 ? 'g-good' : 'g-poor';
  return '<span class="pill '+cls+'">'+(clv>0?'+':'')+clv.toFixed(2)+'</span>';
}
function mv(m){
  if (m === null || m === undefined) return '<span class="mv mvfl">—</span>';
  if (m > 0)  return '<span class="mv mvup">▲'+m+'</span>';
  if (m < 0)  return '<span class="mv mvdn">▼'+(-m)+'</span>';
  return '<span class="mv mvfl">—</span>';
}
function streakTxt(st){
  if (!st) return '';
  var n = parseInt(st.slice(1), 10);
  return st + (st[0]==='W' && n>=3 ? ' 🔥' : st[0]==='L' && n>=3 ? ' 🧊' : '');
}
function countUp(el, target){
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    el.textContent = (target>0?'+':'')+target.toFixed(2); return;
  }
  var t0 = null;
  function step(ts){
    if (!t0) t0 = ts;
    var p = Math.min((ts-t0)/700, 1), v = target*(1-Math.pow(1-p,3));
    el.textContent = (v>0?'+':'')+v.toFixed(2);
    if (p<1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function load(mode){
  document.getElementById('t-live').className = mode==='live'?'on':'';
  document.getElementById('t-backtest').className = mode==='backtest'?'on':'';
  fetch('/leaderboard?mode='+mode).then(r=>r.json()).then(d=>{
    renderTicker(d.smack || []);
    renderBoard(d, mode);
    renderHero(d.board || []);
  });
  fetch('/leaderboard/best-bets?mode='+mode).then(r=>r.json()).then(renderBB);
}

function renderTicker(lines){
  if (!lines.length) { document.getElementById('ticker').style.display='none'; return; }
  var seg = lines.map(function(l){
    return '\\u00a0' + l.replace(/^([\\u0000-\\uFFFF]{1,2})\\s+([^—.]+)/,
      function(m, emoji, name){ return emoji + ' <b>' + name + '</b>'; }) + ' \\u00a0·';
  }).join(' ');
  document.getElementById('tickerInner').innerHTML = seg + seg;  /* loop seam */
}

function renderHero(board){
  var hero = document.getElementById('hero');
  if (!board.length) { hero.style.display='none'; return; }
  var top = board[0], cards = '';
  cards += '<div class="card lead" style="animation-delay:.05s">' +
    '<div class="label">▮ CLV Leader</div>' +
    '<div class="name">'+top.agent+'</div>' +
    '<div class="meta">'+top.kind.toUpperCase()+
      (top.beat_close_streak>=2 ? ' · beaten the close '+top.beat_close_streak+' straight' : '')+'</div>' +
    '<div class="grade '+(top.avg_clv_points>=1?'g-elite':top.avg_clv_points>=0?'g-good':'g-poor')+
      '"><b id="heroClv">0.00</b><i>avg clv</i></div>' +
    '<div class="statline">' +
      '<div class="stat"><b>'+top.wins+'–'+top.losses+(top.pushes?'–'+top.pushes:'')+'</b><span>record</span></div>' +
      '<div class="stat"><b class="'+(top.roi_pct>=0?'pos':'neg')+'">'+(top.roi_pct>0?'+':'')+top.roi_pct+'%</b><span>roi</span></div>' +
      (top.streak ? '<div class="stat"><b>'+streakTxt(top.streak)+'</b><span>streak</span></div>' : '') +
    '</div></div>';
  var hot = board.filter(function(r){ return r.streak && r.streak[0]==='W'; })
                 .sort(function(a,b){ return parseInt(b.streak.slice(1))-parseInt(a.streak.slice(1)); })[0];
  if (hot && hot.agent !== top.agent)
    cards += '<div class="card" style="animation-delay:.15s"><div class="label">Heating Up</div>' +
      '<div class="name">'+hot.agent+'</div><div class="meta">'+hot.kind.toUpperCase()+
      ' · '+streakTxt(hot.streak)+'</div>' +
      '<div class="grade g-elite"><b>'+hot.streak+'</b><i>streak</i></div></div>';
  var cold = board[board.length-1];
  if (board.length > 1 && (cold.avg_clv_points||0) < 0)
    cards += '<div class="card" style="animation-delay:.25s"><div class="label">Fading The Field</div>' +
      '<div class="name">'+cold.agent+'</div><div class="meta">'+cold.kind.toUpperCase()+
      (cold.streak && cold.streak[0]==='L' ? ' · '+streakTxt(cold.streak) : '')+'</div>' +
      '<div class="grade g-poor"><b>'+cold.avg_clv_points.toFixed(2)+'</b><i>avg clv</i></div></div>';
  hero.innerHTML = cards;
  hero.style.display = 'grid';
  var el = document.getElementById('heroClv');
  if (el && top.avg_clv_points !== null) countUp(el, top.avg_clv_points);
}

function renderBoard(d, mode){
  var el = document.getElementById('board');
  if (!d.board.length){
    el.innerHTML = '<div class="empty">No agents with '+d.min_picks+'+ graded '+mode+
      ' picks yet. <b>First to the board owns it.</b></div>';
    return;
  }
  var h = '<div class="tablewrap"><table><thead><tr><th class="l">RK</th>' +
    '<th class="l">Agent</th><th>Record</th><th>Units</th><th>ROI</th>' +
    '<th>CLV Grade</th><th>Streak</th></tr></thead><tbody>';
  d.board.forEach(function(a, i){
    h += '<tr'+(i===0?' class="top"':'')+' style="animation-delay:'+(i*0.06)+'s">' +
      '<td class="rank l">'+a.rank+' '+mv(a.movement)+'</td>' +
      '<td class="l"><span class="agent">'+chip(a.agent)+
        '<span><b>'+a.agent+'</b><span class="kind">'+a.kind+'</span></span></span></td>' +
      '<td>'+a.wins+'–'+a.losses+(a.pushes?'–'+a.pushes:'')+'</td>' +
      '<td>'+a.units_risked+'</td>' +
      '<td class="'+(a.roi_pct>=0?'pos':'neg')+'">'+(a.roi_pct>0?'+':'')+a.roi_pct+'%</td>' +
      '<td>'+(a.avg_clv_points===null?'—':grade(a.avg_clv_points))+'</td>' +
      '<td class="streak">'+streakTxt(a.streak)+'</td></tr>';
  });
  el.innerHTML = h + '</tbody></table></div>';
}

function renderBB(d){
  var el = document.getElementById('bbboard');
  if (!d.board.length){
    el.innerHTML = '<div class="empty">No agent has '+d.tiers.provisional+
      '+ graded best bets yet.</div>';
    return;
  }
  var h = '<div class="tablewrap"><table><thead><tr><th class="l">Agent</th>' +
    '<th class="l">Status</th><th>Best bets</th><th>Record</th><th>ROI</th>' +
    '<th>CLV Grade</th></tr></thead><tbody>';
  d.board.forEach(function(a, i){
    h += '<tr'+(i===0?' class="top"':'')+' style="animation-delay:'+(i*0.06)+'s">' +
      '<td class="l"><span class="agent">'+chip(a.agent)+'<span><b>'+a.agent+'</b></span></span></td>' +
      '<td class="l"><span class="badge '+a.status+'">'+a.status+'</span></td>' +
      '<td>'+a.picks+'</td><td>'+a.wins+'–'+a.losses+(a.pushes?'–'+a.pushes:'')+'</td>' +
      '<td class="'+(a.roi_pct>=0?'pos':'neg')+'">'+(a.roi_pct>0?'+':'')+a.roi_pct+'%</td>' +
      '<td>'+(a.avg_clv_points===null?'—':grade(a.avg_clv_points))+'</td></tr>';
  });
  el.innerHTML = h + '</tbody></table></div>';
}

load('backtest');
fetch('/sponsors').then(r=>r.json()).then(sp=>{
 if(sp.leaderboard){document.getElementById('sponsorLine').innerHTML=
  '<p style="font:600 .7rem/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;'+
  'text-transform:uppercase;color:var(--dim);margin:.6rem 0 0">'+
  '<a href="/go-sponsor/leaderboard" target="_blank">'+sp.leaderboard.tagline+
  '</a> · sponsored — never affects rankings</p>'}
}).catch(()=>{});
</script></body></html>"""
