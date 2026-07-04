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

DB_URL = "sqlite:///./closingline.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# ---------------------------------------------------------------- models

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    kind = Column(String, default="bot")           # "bot" | "human"
    api_key = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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


def auth_agent(s: Session, x_api_key: str) -> Agent:
    agent = s.query(Agent).filter(Agent.api_key == x_api_key).first()
    if not agent:
        raise HTTPException(401, "invalid API key")
    return agent

# ---------------------------------------------------------------- schemas

class RegisterIn(BaseModel):
    name: str = Field(min_length=3, max_length=40)
    kind: str = "bot"


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


@app.post("/agents/register")
def register(body: RegisterIn, s: Session = Depends(db)):
    if s.query(Agent).filter(Agent.name == body.name).first():
        raise HTTPException(409, "agent name taken")
    agent = Agent(name=body.name, kind=body.kind,
                  api_key="cl_" + secrets.token_hex(16))
    s.add(agent)
    s.commit()
    return {"agent_id": agent.id, "name": agent.name, "api_key": agent.api_key,
            "note": "Store this key. It is shown once."}


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
def grade_all(s: Session = Depends(db)):
    """Grade every pending pick on a final game. Run after results load."""
    pending = (s.query(Pick, Game)
                .join(Game, Pick.game_id == Game.id)
                .filter(Pick.result == "pending", Game.final == True).all())
    for pick, game in pending:
        _grade_one(pick, game, closing_snapshot(s, game))
    s.commit()
    return {"graded": len(pending)}

# ---------------------------------------------------------------- boards

MIN_PICKS_FOR_BOARD = 5    # raise to ~30 for a real season


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

    return {
        "agent": agent.name, "mode": mode,
        "overall": _agg([p for p, _ in rows]),
        "by_market": bucket(lambda p, g: p.market),
        "by_side_type": bucket(fav_dog),
        "by_home_away": bucket(
            lambda p, g: "n/a-total" if p.market == Market.total
            else ("home" if p.side == g.home else "away")),
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

# ---------------------------------------------------------------- UI

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
<button id="b-backtest" onclick="load('backtest')">Backtest board</button></nav>
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
</script></body></html>"""
