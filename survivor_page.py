"""Survivor Helper page — imported by app.py, served at /survivor.

Circa Survivor is a straight-up (moneyline) contest: pick one team to win each
week, never reuse a team, a loss OR a tie eliminates you. Straight-up win
probability is exactly the signal, and in our own backtests the market beat our
model at picking winners — so this tool leans on de-vigged market moneyline win
probabilities (served by /data/survivor) and layers the survivor strategy on
top: future value, an (estimated) pick-popularity read, and per-entry used-team
tracking for a multi-entry portfolio.

Design matches the main board (broadcast-light + Vegas-dark, CSS-only motion).
Decision support only — see the responsible-gambling footer; the product voice
never says "lock" or "guaranteed."
"""

SURVIVOR_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClosingLine — Survivor Helper (Circa 2026)</title>
<meta name="description" content="Circa Survivor pick helper: teams ranked by de-vigged market win probability, with future-value flags, an estimated pick-popularity read, and used-team tracking across multiple entries. Decision support, not betting advice.">
<link rel="canonical" href="https://closinglinehq.com/survivor">
<style>
:root{
  --bg:#fbfcfd; --panel:#ffffff; --panel2:#f2f5f9; --ink:#122036;
  --dim:#64748b; --line:#dde4ec; --rule:#122036;
  --up:#0b9a72; --down:#d43d2a; --gold:#c8901f; --mid:#2f6fd0;
  --tickbg:#122036; --tickfg:#dbe4f0; --tickhi:#f5b53f;
  --shadow:0 1px 3px rgba(18,32,54,.05);
}
[data-theme="dark"]{
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
header{display:flex;align-items:center;justify-content:space-between;gap:1rem;
  padding:1.2rem 0;border-bottom:2px solid var(--rule);flex-wrap:wrap}
.logo{font-size:1.5rem;font-weight:900;letter-spacing:-.03em}
.logo span{color:var(--up)}
nav{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
nav a,#themeBtn{font-weight:700;font-size:.78rem;text-decoration:none;
  padding:.42rem .75rem;border-radius:8px;border:1px solid var(--line);
  background:var(--panel);cursor:pointer;color:var(--ink);
  transition:transform .15s,border-color .15s}
nav a:hover,#themeBtn:hover{transform:translateY(-2px);border-color:var(--up)}
nav a.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}

/* hero */
.hero{margin-top:1.4rem;background:
  linear-gradient(135deg,color-mix(in srgb,var(--gold) 12%,var(--panel)),var(--panel));
  border:1px solid var(--line);border-radius:12px;padding:1.3rem 1.4rem;
  box-shadow:var(--shadow)}
.hero h1{margin:0;font-size:1.7rem;font-weight:900;letter-spacing:-.02em}
.hero h1 em{font-style:normal;color:var(--gold)}
.hero p{margin:.35rem 0 0;color:var(--dim);font-size:.9rem;max-width:56ch}
.facts{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:1rem}
.fact{font-weight:800;font-size:.66rem;letter-spacing:.05em;text-transform:uppercase;
  padding:.4rem .6rem;border-radius:7px;background:var(--panel2);
  border:1px solid var(--line);color:var(--dim)}
.fact b{color:var(--ink)}
.fact.warn{color:var(--down);border-color:color-mix(in srgb,var(--down) 45%,var(--line))}
.countdown{margin-top:.9rem;font-family:ui-monospace,Menlo,Consolas,monospace;
  font-size:.8rem;font-weight:700;color:var(--ink)}
.countdown b{color:var(--gold);font-variant-numeric:tabular-nums}

section{margin-top:2rem}
h2{font-size:1.05rem;font-weight:800;margin:0 0 .2rem;text-transform:uppercase}
h2 em{font-style:normal;color:var(--up)}
.subnote{color:var(--dim);font-size:.8rem;margin:0 0 1rem}

/* entry manager */
.entries{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem}
.entry{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.9rem 1rem;box-shadow:var(--shadow);cursor:pointer;
  transition:border-color .2s,transform .15s}
.entry:hover{transform:translateY(-2px)}
.entry.active{border-color:var(--gold);box-shadow:0 0 0 2px color-mix(in srgb,var(--gold) 30%,transparent)}
.entry .etop{display:flex;justify-content:space-between;align-items:center}
.entry .etitle{font-weight:800;font-size:.82rem}
.entry .ecount{font-size:.62rem;font-weight:800;letter-spacing:.1em;
  text-transform:uppercase;color:var(--dim)}
.usedchips{display:flex;gap:.3rem;flex-wrap:wrap;margin-top:.55rem;min-height:1.6rem}
.uchip{display:inline-flex;align-items:center;gap:.25rem;font-weight:800;
  font-size:.62rem;color:#fff;padding:.2rem .4rem;border-radius:5px}
.uchip button{all:unset;cursor:pointer;opacity:.8;font-size:.7rem;line-height:1}
.uchip button:hover{opacity:1}
.entry .ehint{color:var(--dim);font-size:.64rem;margin-top:.4rem}

/* week nav */
.weeknav{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:.2rem 0 1rem}
.weeknav button{font-weight:800;font-size:.74rem;padding:.4rem .7rem;border-radius:8px;
  border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.weeknav button:hover{border-color:var(--up)}
.weeknav .wtitle{font-weight:900;font-size:1rem;letter-spacing:-.01em}
.weeknav .src{font-size:.66rem;color:var(--dim);font-weight:700}
.leanbar{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin:0 0 1rem;
  background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:.6rem .8rem}
.leanbar label{font-weight:800;font-size:.7rem;letter-spacing:.05em;text-transform:uppercase;color:var(--dim)}
.leanbar input[type=range]{accent-color:var(--gold);max-width:170px;flex:none}
.leanval{font-weight:900;font-variant-numeric:tabular-nums;color:var(--gold);min-width:3rem}
.leannote{color:var(--dim);font-size:.68rem;flex:1;min-width:220px}

/* pick rows */
.picks{display:flex;flex-direction:column;gap:.55rem}
.pick{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.7rem .85rem;box-shadow:var(--shadow);display:grid;
  grid-template-columns:2.1rem 1fr auto;gap:.7rem;align-items:center;
  opacity:0;animation:fadeUp .45s ease forwards;transition:transform .15s,opacity .2s}
.pick:hover{transform:translateY(-2px)}
.pick.used{opacity:.42;filter:grayscale(.5)}
.rank{font-weight:900;color:var(--dim);text-align:center;font-variant-numeric:tabular-nums}
.matchup{min-width:0}
.mteam{display:flex;align-items:center;gap:.5rem}
.tchip{display:inline-flex;align-items:center;justify-content:center;min-width:2.4rem;
  height:1.7rem;padding:0 .45rem;border-radius:6px;font-weight:900;font-size:.72rem;
  color:#fff;flex:none;letter-spacing:.02em}
.mteam b{font-size:1.02rem;font-weight:800}
.vs{color:var(--dim);font-size:.78rem;font-weight:600;margin-top:.2rem}
.flags{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.35rem}
.flag{font-weight:800;font-size:.58rem;letter-spacing:.06em;text-transform:uppercase;
  padding:.16rem .42rem;border-radius:5px;border:1px solid var(--line);color:var(--dim)}
.flag.save{color:var(--gold);border-color:color-mix(in srgb,var(--gold) 45%,var(--line))}
.flag.contra{color:var(--mid);border-color:color-mix(in srgb,var(--mid) 45%,var(--line))}
.flag.used{color:var(--down);border-color:color-mix(in srgb,var(--down) 45%,var(--line))}
.flag.home{color:var(--up);border-color:color-mix(in srgb,var(--up) 45%,var(--line))}
.flag.road{color:var(--dim)}
.pop{display:flex;align-items:center;gap:.4rem;margin-top:.4rem;
  font-size:.62rem;color:var(--dim);font-weight:700}
.popbar{width:88px;height:5px;border-radius:99px;background:var(--panel2);overflow:hidden}
.popbar i{display:block;height:100%;background:var(--mid);border-radius:99px}

.right{display:flex;align-items:center;gap:.8rem}
.wp{display:flex;flex-direction:column;align-items:center;min-width:4.2rem;
  padding:.4rem .5rem;border-radius:8px;font-variant-numeric:tabular-nums}
.wp b{font-size:1.5rem;font-weight:900;line-height:1}
.wp .tier{font-style:normal;font-size:.54rem;font-weight:900;letter-spacing:.1em;
  text-transform:uppercase;margin-top:.22rem}
.w-safe{background:color-mix(in srgb,var(--up) 14%,transparent);color:var(--up)}
.w-solid{background:color-mix(in srgb,var(--up) 9%,transparent);color:var(--up)}
.w-lean{background:color-mix(in srgb,var(--gold) 15%,transparent);color:var(--gold)}
.w-risky{background:color-mix(in srgb,var(--down) 13%,transparent);color:var(--down)}
.usebtns{display:flex;flex-direction:column;gap:.25rem}
.usebtns button{all:unset;cursor:pointer;font-weight:800;font-size:.6rem;
  letter-spacing:.05em;text-align:center;padding:.24rem .5rem;border-radius:6px;
  border:1px solid var(--line);color:var(--dim);min-width:3.1rem}
.usebtns button:hover{border-color:var(--gold);color:var(--gold)}
.usebtns button:disabled{opacity:.3;cursor:not-allowed}

/* callouts */
.callout{background:color-mix(in srgb,var(--gold) 8%,var(--panel));
  border:1px solid color-mix(in srgb,var(--gold) 35%,var(--line));border-radius:10px;
  padding:1rem 1.15rem;box-shadow:var(--shadow)}
.callout h3{margin:0 0 .5rem;font-size:.82rem;font-weight:900;letter-spacing:.06em;
  text-transform:uppercase;color:var(--gold)}
.allocs{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}
.alloc{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:.7rem .8rem}
.alloc .ehead{font-size:.6rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
  color:var(--dim)}
.alloc .apick{display:flex;align-items:center;gap:.45rem;margin-top:.4rem}
.alloc .awp{font-weight:900;font-variant-numeric:tabular-nums}
.callout .why{color:var(--dim);font-size:.74rem;margin:.7rem 0 0}

/* planner */
.planwrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;box-shadow:var(--shadow)}
table.plan{width:100%;border-collapse:collapse;font-size:.82rem;min-width:640px}
.plan th{font-weight:800;font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--dim);text-align:left;padding:.6rem .8rem;border-bottom:2px solid var(--rule)}
.plan td{padding:.5rem .8rem;border-bottom:1px solid var(--line);vertical-align:top}
.plan tr:last-child td{border-bottom:none}
.plan .wk{font-weight:900;color:var(--dim)}
.ptop{display:inline-flex;align-items:center;gap:.35rem;margin:0 .5rem .3rem 0}
.ptop .pwp{font-weight:800;font-variant-numeric:tabular-nums;font-size:.76rem}
.ptop.spent{opacity:.4;text-decoration:line-through}

.empty{color:var(--dim);padding:2rem;text-align:center;background:var(--panel);
  border:1px dashed var(--line);border-radius:10px}
.toast{position:fixed;left:50%;bottom:1.4rem;transform:translateX(-50%) translateY(20px);
  background:var(--ink);color:var(--bg);font-weight:800;font-size:.78rem;
  padding:.6rem 1rem;border-radius:9px;opacity:0;pointer-events:none;
  transition:opacity .25s,transform .25s;z-index:20}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.footnote{margin-top:2.6rem;padding-top:1rem;border-top:2px solid var(--rule);
  color:var(--dim);font-size:.76rem}
.footnote b{color:var(--ink)}
.rg{margin-top:.7rem;font-weight:700;color:var(--dim)}
.rg span{color:var(--down)}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@media (max-width:760px){.entries,.allocs{grid-template-columns:1fr}
  .pick{grid-template-columns:1.7rem 1fr}.right{grid-column:1/-1;justify-content:space-between;
  margin-top:.2rem}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important;
  transition:none!important}}
</style></head><body>
<div class="wrap">
<header>
  <div class="logo"><a href="/" style="text-decoration:none">CLOSING<span>LINE</span></a></div>
  <nav>
    <a href="/survivor" class="on">Survivor</a>
    <a href="/explorer">Explorer</a>
    <a href="/picks-board">Make Picks</a>
    <a href="/">Board</a>
    <button id="themeBtn" title="Toggle light/dark">🌙</button>
  </nav>
</header>

<div class="hero">
  <h1>Survivor <em>Helper</em></h1>
  <p>Circa Survivor is a straight-up contest — pick one winner a week, never reuse a
  team, a loss <b>or a tie</b> ends the entry. Teams below are ranked by de-vigged
  <b>market win probability</b> (the sharpest public read), with future-value and
  popularity context. Track all your entries so one upset can't wipe them together.</p>
  <div class="facts">
    <div class="fact"><b>$20M</b> prize pool</div>
    <div class="fact"><b>$1,000</b> / entry</div>
    <div class="fact warn">Tie = OUT</div>
    <div class="fact">One team per entry</div>
    <div class="fact"><b>20</b> legs (Wk 1–18 + holidays)</div>
  </div>
  <div class="countdown" id="countdown">Registration deadline: Sat Sep 12, 2026 · 2:00 PM PT</div>
</div>

<section>
  <h2>Your <em>Entries</em></h2>
  <p class="subnote">Tap an entry to make it active, then use the picks below. Used teams
  are locked out for that entry. Stored in your browser only.</p>
  <div class="entries" id="entries"></div>
</section>

<section>
  <div class="weeknav">
    <button onclick="stepWeek(-1)">‹ Prev</button>
    <span class="wtitle" id="wtitle">Week —</span>
    <button onclick="stepWeek(1)">Next ›</button>
    <span class="src" id="wsrc"></span>
    <button id="previewBtn" style="margin-left:auto" onclick="togglePreview()">Preview with 2025 data</button>
  </div>
  <div class="leanbar">
    <label for="lean">Home-field lean</label>
    <input id="lean" type="range" min="0" max="0.05" step="0.005" oninput="setLean(this.value)">
    <span class="leanval" id="leanval">+1.5%</span>
    <span class="leannote">Floats home favorites above road favorites in the ranking. The market
    already prices home field into the moneyline — this is your lean on top, not a proven edge.</span>
  </div>
  <div id="board"></div>
</section>

<section>
  <h2>3-Entry <em>Portfolio</em></h2>
  <p class="subnote">A diversified split for this week across your active entries —
  built from the best still-available team for each, so a single upset can't end all three.</p>
  <div id="portfolio"></div>
</section>

<section>
  <h2>Multi-week <em>Planner</em></h2>
  <p class="subnote">Top available survival options each week, so you can save premium teams
  and keep unused teams for the holiday legs. Struck-through = already used by an entry.</p>
  <div class="planwrap" id="planner"></div>
</section>

<p class="footnote">
<b>How the number is built:</b> win probability comes from the de-vigged market moneyline
(closing/latest snapshot), which beat our own model at picking winners in backtesting —
so the market is the primary signal here. <b>Popularity is an estimate</b> (no field-entry
data yet), shown only as rough contrarian context. This is decision support, not a
prediction — ties eliminate you and no pick is ever safe.
<div class="rg"><span>21+.</span> Informational only, not financial or betting advice.
If gambling is a problem, call <span>1-800-GAMBLER</span>.</div>
</p>
</div>
<div class="toast" id="toast"></div>

<script>
/* ---------- theme (shared key with the board) ---------- */
(function(){
  var saved=localStorage.getItem('clhq_theme');
  var dark=saved?saved==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;
  if(dark)document.documentElement.setAttribute('data-theme','dark');
  upd();
  document.getElementById('themeBtn').onclick=function(){
    var d=document.documentElement.getAttribute('data-theme')==='dark';
    if(d)document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme','dark');
    localStorage.setItem('clhq_theme',d?'light':'dark');upd();};
  function upd(){var d=document.documentElement.getAttribute('data-theme')==='dark';
    document.getElementById('themeBtn').textContent=d?'☀️':'🌙';}
})();

/* ---------- team colors ---------- */
var TC={ARI:'#97233F',ATL:'#A71930',BAL:'#241773',BUF:'#00338D',CAR:'#0085CA',
CHI:'#0B162A',CIN:'#FB4F14',CLE:'#311D00',DAL:'#003594',DEN:'#FB4F14',DET:'#0076B6',
GB:'#203731',HOU:'#03202F',IND:'#002C5F',JAX:'#006778',KC:'#E31837',LA:'#003594',
LAR:'#003594',LAC:'#0080C6',LV:'#000000',MIA:'#008E97',MIN:'#4F2683',NE:'#002244',
NO:'#D3BC8D',NYG:'#0B2265',NYJ:'#125740',PHI:'#004C54',PIT:'#FFB612',SF:'#AA0000',
SEA:'#002244',TB:'#D50A0A',TEN:'#0C2340',WAS:'#5A1414',WSH:'#5A1414'};
function tcol(t){return TC[t]||'#475569';}

/* ---------- entry state ---------- */
var EK='survivor_entries_v1', AK='survivor_active_v1';
function entries(){try{return JSON.parse(localStorage.getItem(EK))||{1:[],2:[],3:[]}}catch(e){return{1:[],2:[],3:[]}}}
function saveEntries(e){localStorage.setItem(EK,JSON.stringify(e))}
function active(){return localStorage.getItem(AK)||'1'}
function setActive(n){localStorage.setItem(AK,String(n));renderEntries();renderBoard();renderPortfolio();renderPlanner()}
function usedBy(n){return entries()[n]||[]}
function usedAny(t){var e=entries();return['1','2','3'].some(function(n){return e[n].indexOf(t)>=0})}

function useTeam(team,n){
  var e=entries();if(e[n].indexOf(team)>=0)return;
  e[n].push(team);saveEntries(e);
  toast(team+' → Entry '+n);
  renderEntries();renderBoard();renderPortfolio();renderPlanner();
}
function dropTeam(team,n){
  var e=entries();e[n]=e[n].filter(function(t){return t!==team});saveEntries(e);
  renderEntries();renderBoard();renderPortfolio();renderPlanner();
}
function toast(msg){var t=document.getElementById('toast');t.textContent=msg;
  t.classList.add('show');clearTimeout(t._h);t._h=setTimeout(function(){t.classList.remove('show')},1600)}

function renderEntries(){
  var e=entries(),act=active(),h='';
  ['1','2','3'].forEach(function(n){
    var used=e[n];
    var chips=used.map(function(t){return '<span class="uchip" style="background:'+tcol(t)+
      '">'+t+' <button title="remove" onclick="event.stopPropagation();dropTeam(\\''+t+'\\','+n+')">✕</button></span>';}).join('')
      || '<span class="ehint">No teams used yet</span>';
    h+='<div class="entry'+(act===n?' active':'')+'" onclick="setActive('+n+')">'+
       '<div class="etop"><span class="etitle">Entry '+n+(act===n?' · active':'')+'</span>'+
       '<span class="ecount">'+used.length+'/20 used</span></div>'+
       '<div class="usedchips">'+chips+'</div></div>';
  });
  document.getElementById('entries').innerHTML=h;
}

/* ---------- home-field lean (subjective ranking tilt, not the market number) ---------- */
var LK='survivor_lean_v1';
var LEAN=(function(){var v=parseFloat(localStorage.getItem(LK));return isNaN(v)?0.015:v;})();
function setLean(v){LEAN=parseFloat(v);localStorage.setItem(LK,String(LEAN));
  document.getElementById('leanval').textContent=(LEAN>0?'+':'')+(LEAN*100).toFixed(1)+'%';
  renderBoard();renderPortfolio();renderPlanner();}

/* ---------- data ---------- */
var DATA=null, WEEKS=[], curIdx=0, PREVIEW=false;
async function load(){
  var url=PREVIEW?'/data/survivor?season=2025&start_week=6&weeks=8':'/data/survivor?weeks=8';
  try{DATA=await (await fetch(url)).json();}catch(e){DATA={weeks:[]};}
  WEEKS=(DATA.weeks||[]).filter(function(w){return w.games&&w.games.length;});
  curIdx=0;
  renderAll();
}
function renderAll(){renderEntries();renderBoard();renderPortfolio();renderPlanner();}

/* teams for a week as {team,opp,wp,home,gid} sorted by wp desc, wp!=null */
function weekTeams(w){
  var out=[];
  (w.games||[]).forEach(function(g){
    if(g.home_wp==null)return;
    out.push({team:g.home,opp:g.away,home:true,wp:g.home_wp,gid:g.game_id});
    out.push({team:g.away,opp:g.home,home:false,wp:g.away_wp,gid:g.game_id});
  });
  // wp stays the honest market number; score = wp tilted by the home-field lean.
  out.forEach(function(p){p.score=p.wp+(p.home?LEAN:-LEAN);});
  out.sort(function(a,b){return b.score-a.score});
  return out;
}
/* team -> best (week,wp) across the window, for future value */
function futureMap(){
  var m={};
  WEEKS.forEach(function(w){weekTeams(w).forEach(function(p){
    if(!m[p.team]||p.wp>m[p.team].wp)m[p.team]={week:w.week,wp:p.wp};
  });});
  return m;
}
function tier(wp){
  if(wp>=0.80)return['SAFE','w-safe'];
  if(wp>=0.70)return['SOLID','w-solid'];
  if(wp>=0.62)return['LEAN','w-lean'];
  return['RISKY','w-risky'];
}
/* rough popularity estimate within a week (NOT field data) */
function popEstimates(teams){
  var raw=teams.map(function(p){return Math.pow(Math.max(0,p.wp-0.5),1.6);});
  var sum=raw.reduce(function(a,b){return a+b;},0)||1;
  return raw.map(function(r,i){return Math.min(45,Math.round(r/sum*100*1.15));});
}

function stepWeek(d){if(!WEEKS.length)return;curIdx=Math.max(0,Math.min(WEEKS.length-1,curIdx+d));
  renderBoard();renderPortfolio();}
function togglePreview(){PREVIEW=!PREVIEW;
  document.getElementById('previewBtn').textContent=PREVIEW?'Use live schedule':'Preview with 2025 data';
  load();}

function renderBoard(){
  var el=document.getElementById('board');
  if(!WEEKS.length){el.innerHTML='<div class="empty">Lines aren\\'t posted yet. '+
    'The board fills in once the market prices the slate (usually the Wednesday before '+
    'kickoff). Tap <b>Preview with 2025 data</b> above to see it in action.</div>';
    document.getElementById('wtitle').textContent='Week —';
    document.getElementById('wsrc').textContent='';return;}
  var w=WEEKS[curIdx], teams=weekTeams(w), fut=futureMap(), pops=popEstimates(teams), act=active();
  document.getElementById('wtitle').textContent='Week '+w.week;
  var src=(w.games.find(function(g){return g.wp_source;})||{}).wp_source;
  document.getElementById('wsrc').textContent=src?('win prob from '+(src==='ml'?'market moneyline':'market spread')):'';
  var h='<div class="picks">';
  teams.forEach(function(p,i){
    var used=usedBy(act).indexOf(p.team)>=0;
    var t=tier(p.wp), fv=fut[p.team];
    var flags='';
    if(used)flags+='<span class="flag used">used · E'+act+'</span>';
    if(!used&&fv&&fv.week>w.week&&fv.wp-p.wp>=0.05)
      flags+='<span class="flag save">bigger edge Wk '+fv.week+' ('+Math.round(fv.wp*100)+'%) — consider saving</span>';
    if(!used&&p.wp>=0.62&&pops[i]<=8)flags+='<span class="flag contra">lower-owned · leverage</span>';
    if(!used&&LEAN>0&&p.wp>=0.5)
      flags+=p.home?('<span class="flag home">home lean +'+(LEAN*100).toFixed(1)+'%</span>')
                   :('<span class="flag road">road −'+(LEAN*100).toFixed(1)+'%</span>');
    var pop=pops[i];
    h+='<div class="pick'+(used?' used':'')+'">'+
       '<div class="rank">'+(i+1)+'</div>'+
       '<div class="matchup"><div class="mteam"><span class="tchip" style="background:'+tcol(p.team)+
       '">'+p.team+'</span><b>'+p.team+'</b><span class="vs">'+(p.home?'vs':'@')+' '+p.opp+'</span></div>'+
       (flags?'<div class="flags">'+flags+'</div>':'')+
       '<div class="pop">est. popularity <span class="popbar"><i style="width:'+Math.max(3,pop)+'%"></i></span> ~'+pop+'%</div>'+
       '</div>'+
       '<div class="right"><div class="wp '+t[1]+'"><b>'+Math.round(p.wp*100)+'%</b><i class="tier">'+t[0]+'</i></div>'+
       '<div class="usebtns">'+
       ['1','2','3'].map(function(n){var u=usedBy(n).indexOf(p.team)>=0;
         return '<button '+(u?'disabled':'')+' onclick="useTeam(\\''+p.team+'\\','+n+')">'+(u?'E'+n+' ✓':'Use E'+n)+'</button>';}).join('')+
       '</div></div></div>';
  });
  el.innerHTML=h+'</div>';
}

function renderPortfolio(){
  var el=document.getElementById('portfolio');
  if(!WEEKS.length){el.innerHTML='<div class="empty">Portfolio suggestion appears once lines post.</div>';return;}
  var w=WEEKS[curIdx];
  /* best still-available team per entry (respect each entry's used list) */
  var teams=weekTeams(w);
  function bestFor(n,exclude){for(var i=0;i<teams.length;i++){var p=teams[i];
    if(usedBy(n).indexOf(p.team)>=0)continue;if(exclude.indexOf(p.team)>=0)continue;return p;}return null;}
  var picks={}, chosen=[];
  var top=teams.find(function(p){return !usedBy('1').indexOf(p.team)&&true;});
  // Strategy: if the single best pick is very safe & available to all three, ride 2 + diversify 1.
  var topAllAvail=teams.length&&['1','2','3'].every(function(n){return usedBy(n).indexOf(teams[0].team)<0;});
  var why='';
  if(topAllAvail&&teams[0].wp>=0.84){
    picks['1']=teams[0];picks['2']=teams[0];
    picks['3']=bestFor('3',[teams[0].team]);
    why='Entry 1 & 2 ride '+teams[0].team+' ('+Math.round(teams[0].wp*100)+'%) — safe enough to double up — '+
        'while Entry 3 diversifies onto '+(picks['3']?picks['3'].team:'—')+' so one upset can\\'t end all three.';
  }else{
    ['1','2','3'].forEach(function(n){var ex=Object.keys(picks).map(function(k){return picks[k].team;});
      picks[n]=bestFor(n,ex);});
    why='Three different teams — maximum diversification when the top options are close in win%. '+
        'Each is the strongest team still available to that entry.';
  }
  var cards=['1','2','3'].map(function(n){var p=picks[n];
    return '<div class="alloc"><div class="ehead">Entry '+n+'</div>'+
      (p?'<div class="apick"><span class="tchip" style="background:'+tcol(p.team)+'">'+p.team+
        '</span><b>'+p.team+'</b> <span class="awp">'+Math.round(p.wp*100)+'%</span></div>':
        '<div class="apick" style="color:var(--dim)">No safe team left — plan ahead</div>')+'</div>';}).join('');
  el.innerHTML='<div class="callout"><h3>Suggested Week '+w.week+' split</h3>'+
    '<div class="allocs">'+cards+'</div><p class="why">'+why+'</p></div>';
}

function renderPlanner(){
  var el=document.getElementById('planner');
  if(!WEEKS.length){el.innerHTML='<div class="empty" style="border:none">No schedule loaded.</div>';return;}
  var h='<table class="plan"><tr><th>Week</th><th>Top available survival picks</th></tr>';
  WEEKS.forEach(function(w){
    var teams=weekTeams(w).filter(function(p){return !usedAny(p.team)||true;}).slice(0,6);
    var cells=teams.slice(0,5).map(function(p){var spent=usedAny(p.team);
      return '<span class="ptop'+(spent?' spent':'')+'"><span class="tchip" style="background:'+tcol(p.team)+
        ';min-width:2rem;height:1.4rem;font-size:.64rem">'+p.team+'</span>'+
        '<span class="pwp">'+Math.round(p.wp*100)+'%</span></span>';}).join('');
    h+='<tr><td class="wk">Wk '+w.week+'</td><td>'+(cells||'<span style="color:var(--dim)">lines pending</span>')+'</td></tr>';
  });
  el.innerHTML=h+'</table>';
}

/* ---------- countdown ---------- */
(function(){
  var deadline=new Date('2026-09-12T21:00:00Z'); // 2:00 PM PT (PDT)
  function tick(){
    var el=document.getElementById('countdown');var ms=deadline-new Date();
    if(ms<=0){el.innerHTML='Registration is <b>closed</b> for 2026.';return;}
    var d=Math.floor(ms/86400000),h=Math.floor(ms/3600000)%24,m=Math.floor(ms/60000)%60;
    el.innerHTML='Registration closes in <b>'+d+'d '+h+'h '+m+'m</b> · Sat Sep 12, 2026 · 2:00 PM PT';
  }
  tick();setInterval(tick,30000);
})();

/* sync the lean control to saved state */
document.getElementById('lean').value=LEAN;
document.getElementById('leanval').textContent=(LEAN>0?'+':'')+(LEAN*100).toFixed(1)+'%';

renderEntries();load();
</script></body></html>"""
