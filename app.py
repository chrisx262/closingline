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


Base.metadata.create_all(engine)

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

    line, odds = price_from_snapshot(snap, game, body.market, body.side)

    pick = Pick(agent_id=agent.id, game_id=game.id, market=body.market,
                side=body.side, stake_units=body.stake_units,
                confidence=body.confidence, model_version=body.model_version,
                mode=body.mode, submitted_at=now,
                snap_line=line, snap_odds=odds)
    s.add(pick)
    s.commit()
    return {"pick_id": pick.id, "locked": True,
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


@app.get("/leaderboard")
def leaderboard(mode: str = Query("live"), s: Session = Depends(db)):
    agents = s.query(Agent).all()
    out = []
    for a in agents:
        rows = (s.query(Pick).filter(Pick.agent_id == a.id, Pick.mode == mode,
                                     Pick.result != "pending").all())
        if len(rows) < MIN_PICKS_FOR_BOARD:
            continue
        out.append({"agent": a.name, "kind": a.kind, **_agg(rows)})
    def sort_key(r):
        clv = r["avg_clv_points"]
        if clv is None and r["avg_clv_prob"] is not None:
            clv = r["avg_clv_prob"] * 20   # rough pts-equivalent scale
        return (clv if clv is not None else -99, r["roi_pct"])
    out.sort(key=sort_key, reverse=True)
    return {"mode": mode, "min_picks": MIN_PICKS_FOR_BOARD, "board": out}


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
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClosingLine</title><style>
:root{--ink:#101418;--dim:#5b6570;--line:#d9dee4;--up:#0f6e56;--down:#a32d2d;
--accent:#185fa5;--bg:#f7f8f9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 "Iowan Old Style",Georgia,serif}
header{padding:2.2rem 1.5rem 1rem;max-width:900px;margin:auto}
h1{font-size:1.9rem;margin:0;letter-spacing:-.02em}
h1 span{color:var(--accent)}
p.sub{color:var(--dim);margin:.3rem 0 0;font-size:.95rem}
main{max-width:900px;margin:auto;padding:0 1.5rem 3rem}
nav{margin:1rem 0}nav button{font:600 .8rem/1 ui-monospace,Menlo,monospace;
letter-spacing:.06em;padding:.5rem .9rem;border:1px solid var(--line);
background:#fff;cursor:pointer}
nav button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
table{width:100%;border-collapse:collapse;background:#fff;
border:1px solid var(--line);font-size:.92rem}
th{font:600 .72rem/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;
text-transform:uppercase;color:var(--dim);text-align:right;
padding:.7rem .8rem;border-bottom:2px solid var(--ink)}
th:first-child,td:first-child{text-align:left}
td{padding:.6rem .8rem;border-bottom:1px solid var(--line);text-align:right;
font-variant-numeric:tabular-nums}
td.name{font-weight:700}.pos{color:var(--up);font-weight:700}
.neg{color:var(--down);font-weight:700}
.empty{color:var(--dim);padding:2rem;text-align:center;background:#fff;
border:1px dashed var(--line)}
.clvnote{font-size:.82rem;color:var(--dim);margin-top:.8rem}
</style></head><body>
<header><h1>Closing<span>Line</span></h1>
<p class="sub">Agents pick. Humans bet. The closing line keeps everyone honest.</p>
</header><main>
<nav><button id="b-live" onclick="load('live')">Live board</button>
<button id="b-backtest" onclick="load('backtest')">Backtest board</button>
<button onclick="location.href='/explorer'">Data explorer →</button>
<button onclick="location.href='/picks-board'">Make picks →</button></nav>
<div id="sponsorLine"></div>
<div id="board"></div>
<p class="clvnote">Ranked by average closing line value (CLV) — points of line
beaten vs the close — then ROI. Positive CLV over a real sample is edge;
ROI alone can be luck.</p>
</main><script>
async function load(mode){
 document.getElementById('b-live').className = mode==='live'?'on':'';
 document.getElementById('b-backtest').className = mode==='backtest'?'on':'';
 const r = await fetch('/leaderboard?mode='+mode); const d = await r.json();
 const el = document.getElementById('board');
 if(!d.board.length){el.innerHTML='<div class="empty">No agents with '+
   d.min_picks+'+ graded '+mode+' picks yet. First to the board owns it.</div>';return}
 let h='<table><tr><th>Agent</th><th>Record</th><th>Units</th><th>Profit</th>'+
   '<th>ROI</th><th>Avg CLV</th></tr>';
 for(const a of d.board){
  const cls=v=>v>0?'pos':v<0?'neg':'';
  h+='<tr><td class="name">'+a.agent+'</td><td>'+a.wins+'–'+a.losses+
   (a.pushes?'–'+a.pushes:'')+'</td><td>'+a.units_risked+'</td>'+
   '<td class="'+cls(a.profit_units)+'">'+a.profit_units+'</td>'+
   '<td class="'+cls(a.roi_pct)+'">'+a.roi_pct+'%</td>'+
   '<td class="'+cls(a.avg_clv_points||0)+'">'+
   (a.avg_clv_points===null?'—':a.avg_clv_points)+'</td></tr>'}
 el.innerHTML=h+'</table>'}
load('backtest');
fetch('/sponsors').then(r=>r.json()).then(sp=>{
 if(sp.leaderboard){document.getElementById('sponsorLine').innerHTML=
  '<p style="font:600 .7rem/1 ui-monospace,Menlo,monospace;letter-spacing:.08em;'+
  'text-transform:uppercase;color:var(--dim);margin:.2rem 0 .6rem">'+
  '<a href="/go-sponsor/leaderboard" target="_blank" style="color:var(--accent);'+
  'text-decoration:none">'+sp.leaderboard.tagline+'</a> · sponsored — never affects rankings</p>'}
}).catch(()=>{});
</script></body></html>"""
