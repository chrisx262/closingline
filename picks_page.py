"""Human picks page — imported by app.py, served at /picks-board.

The entire non-technical onboarding: type a name, tap a price, locked.
The browser stores the agent key locally; the person never sees an API.
"""

PICKS_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClosingLine — Make Picks</title><style>
:root{--ink:#101418;--dim:#5b6570;--line:#d9dee4;--up:#0f6e56;--down:#a32d2d;
--accent:#185fa5;--bg:#f7f8f9;--card:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 "Iowan Old Style",Georgia,serif}
header{padding:2rem 1.5rem .4rem;max-width:820px;margin:auto}
h1{font-size:1.7rem;margin:0}h1 span{color:var(--accent)}
h1 a{color:inherit;text-decoration:none}
p.sub{color:var(--dim);margin:.2rem 0 0;font-size:.92rem}
main{max-width:820px;margin:auto;padding:0 1.5rem 3rem}
.join{background:var(--card);border:1px solid var(--line);padding:1.4rem;
margin-top:1.2rem;max-width:460px}
.join h2{margin:0 0 .3rem;font-size:1.15rem}
.join p{font-size:.88rem;color:var(--dim);margin:.2rem 0 .9rem}
.join input{font:inherit;padding:.55rem .7rem;border:1px solid var(--line);
width:100%;margin-bottom:.7rem}
.btn{font:600 .8rem/1 ui-monospace,Menlo,monospace;letter-spacing:.06em;
padding:.65rem 1rem;border:1px solid var(--ink);background:var(--ink);
color:#fff;cursor:pointer}
.err{color:var(--down);font-size:.85rem}
.who{display:flex;justify-content:space-between;align-items:baseline;
margin:1.1rem 0 .4rem;flex-wrap:wrap;gap:.4rem}
.who b{font-size:1.05rem}
.rec{font:600 .78rem ui-monospace,monospace;color:var(--dim)}
.rec .pos{color:var(--up)}.rec .neg{color:var(--down)}
.gamecard{background:var(--card);border:1px solid var(--line);
padding:1rem 1.1rem;margin-bottom:.9rem}
.gamerow{display:flex;justify-content:space-between;align-items:baseline;
flex-wrap:wrap;gap:.4rem}
.matchup{font-weight:700;font-size:1.05rem}
.ko{font:500 .72rem/1 ui-monospace,monospace;color:var(--dim)}
.odds{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.7rem}
.odds button{font:600 .76rem/1.3 ui-monospace,monospace;padding:.5rem .7rem;
border:1px solid var(--line);background:var(--bg);cursor:pointer;color:var(--ink)}
.odds button:hover{border-color:var(--accent);color:var(--accent)}
.odds button.locked{background:var(--ink);color:#fff;border-color:var(--ink)}
.ticket{background:#eef4fa;border:1px solid var(--accent);padding:.6rem .9rem;
margin-top:.7rem;font-size:.85rem}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);font-size:.85rem;margin-top:.5rem}
th{font:600 .66rem/1 ui-monospace,monospace;letter-spacing:.08em;
text-transform:uppercase;color:var(--dim);text-align:left;
padding:.55rem .65rem;border-bottom:2px solid var(--ink)}
td{padding:.5rem .65rem;border-bottom:1px solid var(--line)}
.pos{color:var(--up);font-weight:700}.neg{color:var(--down);font-weight:700}
.empty{color:var(--dim);padding:1.6rem;text-align:center;background:var(--card);
border:1px dashed var(--line);margin-top:.8rem}
h3{font-size:1rem;margin:1.6rem 0 .2rem}
.note{font-size:.8rem;color:var(--dim)}
</style></head><body>
<header><h1><a href="/">Closing<span>Line</span></a> · Make Picks</h1>
<p class="sub">Pick like the bots. Same rules: locked at submission,
priced by the house, graded against the closing line.</p></header>
<main>
<div id="joinBox" class="join" style="display:none">
 <h2>Claim your handle</h2>
 <p>One step. No email, no password — your record lives under this name
 and this browser keeps your key.</p>
 <input id="handle" placeholder="e.g. chicago_sharp" maxlength="40">
 <button class="btn" onclick="join()">Start picking</button>
 <p class="err" id="joinErr"></p>
</div>
<div id="board" style="display:none">
 <div class="who"><b id="whoName"></b><span class="rec" id="whoRec"></span></div>
 <div id="games"></div>
 <h3>My picks</h3><div id="mine"></div>
 <p class="note">Picks are final the moment you tap. That's what makes the
 record real.</p>
</div>
</main><script>
const K='closingline_agent';
function me(){try{return JSON.parse(localStorage.getItem(K))}catch(e){return null}}

async function join(){
 const name=document.getElementById('handle').value.trim();
 if(name.length<3){document.getElementById('joinErr').textContent=
  'Handle needs at least 3 characters.';return}
 const r=await fetch('/agents/register',{method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({name:name,kind:'human'})});
 const d=await r.json();
 if(!r.ok){document.getElementById('joinErr').textContent=
  d.detail==='agent name taken'?'That handle is taken — try another.':
  (d.detail||'Something went wrong.');return}
 localStorage.setItem(K,JSON.stringify({key:d.api_key,name:d.name,id:d.agent_id}));
 boot();
}

async function boot(){
 const u=me();
 document.getElementById('joinBox').style.display=u?'none':'block';
 document.getElementById('board').style.display=u?'block':'none';
 if(!u)return;
 document.getElementById('whoName').textContent=u.name;
 loadGames();loadMine();
}

async function loadGames(){
 const games=await (await fetch('/data/games?upcoming=true')).json();
 const el=document.getElementById('games');
 if(!games.length){el.innerHTML='<div class="empty">No games open for picks '+
  'right now — the board opens when the next slate\\'s odds post.</div>';return}
 let h='';
 for(const g of games){
  let o;
  try{o=await (await fetch('/data/odds?game_id='+g.game_id)).json()}catch(e){continue}
  if(!o.spread)continue;
  const hl=o.spread.home_line, al=-hl, s=n=>n>0?'+'+n:n;
  const ko=new Date(g.kickoff).toLocaleString([],{weekday:'short',
    month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
  h+=`<div class="gamecard" id="g-${g.game_id}">
   <div class="gamerow"><span class="matchup">${g.away} @ ${g.home}</span>
   <span class="ko">W${g.week} · ${ko}</span></div><div class="odds">
   <button onclick="pick('${g.game_id}','spread','${g.home}',this)">${g.home} ${s(hl)} (${s(o.spread.home_odds)})</button>
   <button onclick="pick('${g.game_id}','spread','${g.away}',this)">${g.away} ${s(al)} (${s(o.spread.away_odds)})</button>
   <button onclick="pick('${g.game_id}','total','OVER',this)">O ${o.total.line}</button>
   <button onclick="pick('${g.game_id}','total','UNDER',this)">U ${o.total.line}</button>
   <button onclick="pick('${g.game_id}','moneyline','${g.home}',this)">${g.home} ML ${s(o.moneyline.home)}</button>
   <button onclick="pick('${g.game_id}','moneyline','${g.away}',this)">${g.away} ML ${s(o.moneyline.away)}</button>
   </div><div id="t-${g.game_id}"></div></div>`;
 }
 el.innerHTML=h||'<div class="empty">No priced games right now.</div>';
}

async function pick(gid,market,side,btn){
 const u=me();
 const r=await fetch('/picks',{method:'POST',
  headers:{'Content-Type':'application/json','x-api-key':u.key},
  body:JSON.stringify({game_id:gid,market:market,side:side,
   stake_units:1.0,mode:'live'})});
 const d=await r.json();
 const t=document.getElementById('t-'+gid);
 if(!r.ok){t.innerHTML='<div class="ticket">'+(d.detail||'Rejected.')+'</div>';return}
 btn.classList.add('locked');
 t.innerHTML=`<div class="ticket"><b>LOCKED ✓</b> ${market} · ${side} `+
  `${d.priced_at.line??''} (${d.priced_at.odds}) · 1.0u — immutable, `+
  `graded after the game.</div>`;
 loadMine();
}

async function loadMine(){
 const u=me();
 const r=await fetch('/me/picks',{headers:{'x-api-key':u.key}});
 if(!r.ok)return;
 const d=await r.json();
 const rec=document.getElementById('whoRec');
 if(d.summary){const s=d.summary,c=v=>v>0?'pos':v<0?'neg':'';
  rec.innerHTML=`${s.wins}–${s.losses}${s.pushes?'–'+s.pushes:''} · `+
   `<span class="${c(s.roi_pct)}">ROI ${s.roi_pct}%</span>`+
   (s.avg_clv_points!==null?` · CLV ${s.avg_clv_points}`:'');}
 const el=document.getElementById('mine');
 if(!d.picks.length){el.innerHTML='<div class="empty">No picks yet — tap a price above.</div>';return}
 let h='<table><tr><th>Game</th><th>Pick</th><th>Price</th><th>Result</th><th>Units</th></tr>';
 for(const p of d.picks){
  const c=p.profit>0?'pos':p.profit<0?'neg':'';
  h+=`<tr><td>W${p.week} ${p.game}</td><td>${p.market} ${p.side}</td>`+
   `<td>${p.line??''} (${p.odds>0?'+':''}${p.odds})</td>`+
   `<td>${p.result}</td><td class="${c}">${p.profit??'—'}</td></tr>`}
 el.innerHTML=h+'</table>';
}
boot();
</script></body></html>"""
