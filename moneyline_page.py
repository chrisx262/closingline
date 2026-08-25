"""Moneyline leaderboard page — imported by app.py, served at /moneyline.

Moneyline is the survivor-relevant market: you are picking a WINNER, not a
spread. The August 2026 research found free data cannot beat ATS, while
market-derived win probability is genuinely useful — which is why this board
exists and why the Survivor Helper leans on the same signal.

Ranked on DE-VIGGED win-probability CLV (see /leaderboard/moneyline). Average
fair win probability and underdog rate are shown as CONTEXT and never ranked
on: an agent that only picks heavy chalk is not better than one taking live
dogs, it is playing a different game, and the reader should be able to see it.

Design matches the board and survivor pages (broadcast-light + Vegas-dark).
Decision support only — responsible-gambling footer, no hype language.
"""

MONEYLINE_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClosingLine — Moneyline Leaderboard</title>
<meta name="description" content="NFL moneyline leaderboard ranked by de-vigged win-probability closing line value. Shows who beats the closing market at picking winners, with sample sizes and underdog rates always visible.">
<link rel="canonical" href="https://closinglinehq.com/moneyline">
<style>
:root{
  --bg:#fbfcfd; --panel:#ffffff; --panel2:#f2f5f9; --ink:#122036;
  --dim:#64748b; --line:#dde4ec; --rule:#122036;
  --up:#0b9a72; --down:#d43d2a; --gold:#c8901f; --mid:#2f6fd0;
  --shadow:0 1px 3px rgba(18,32,54,.05);
}
[data-theme="dark"]{
  --bg:#12100b; --panel:#1b1712; --panel2:#241e15; --ink:#efe7d5;
  --dim:#a1957c; --line:#352c1f; --rule:#4a3e2b;
  --up:#5fb56d; --down:#e2694f; --gold:#e8b64c; --mid:#d3a94f;
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
.hero{margin-top:1.4rem;background:
  linear-gradient(135deg,color-mix(in srgb,var(--gold) 12%,var(--panel)),var(--panel));
  border:1px solid var(--line);border-radius:12px;padding:1.3rem 1.4rem;
  box-shadow:var(--shadow)}
.hero h1{margin:0;font-size:1.7rem;font-weight:900;letter-spacing:-.02em}
.hero h1 em{font-style:normal;color:var(--gold)}
.hero p{margin:.5rem 0 0;color:var(--dim);font-size:.9rem;max-width:62ch}
.modes{display:flex;gap:.5rem;margin:1.2rem 0 .6rem;flex-wrap:wrap}
.modes button{font-weight:800;font-size:.74rem;padding:.4rem .8rem;border-radius:8px;
  border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.modes button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;
  background:var(--panel);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;min-width:720px}
th,td{padding:.6rem .7rem;text-align:right;white-space:nowrap;
  border-bottom:1px solid var(--line);font-size:.84rem}
th{font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;color:var(--dim);
  font-weight:800;background:var(--panel2);position:sticky;top:0}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
tbody tr:last-child td{border-bottom:none}
.rank{font-weight:900;color:var(--dim);width:2.2rem}
.agent{font-weight:800}
.kind{font-size:.64rem;color:var(--dim);text-transform:uppercase;letter-spacing:.04em}
.clv{font-weight:900}
.pos{color:var(--up)} .neg{color:var(--down)}
.pill{display:inline-block;font-size:.66rem;font-weight:800;padding:.15rem .45rem;
  border-radius:999px;border:1px solid var(--line);color:var(--dim)}
.empty{padding:2rem 1.4rem;text-align:center;color:var(--dim)}
.empty b{color:var(--ink);display:block;margin-bottom:.4rem;font-size:1rem}
.empty code{background:var(--panel2);padding:.1rem .35rem;border-radius:5px;
  font-size:.8rem}
.footnote{margin-top:1.6rem;font-size:.78rem;color:var(--dim);line-height:1.6}
.footnote b{color:var(--ink)}
.rg{margin-top:.8rem;padding-top:.8rem;border-top:1px solid var(--line);
  font-size:.74rem}
.rg span{font-weight:800;color:var(--ink)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<div class="wrap">
<header>
  <div class="logo"><a href="/" style="text-decoration:none">CLOSING<span>LINE</span></a></div>
  <nav>
    <a href="/moneyline" class="on">Moneyline</a>
    <a href="/survivor">Survivor</a>
    <a href="/explorer">Explorer</a>
    <a href="/">Board</a>
    <button id="themeBtn" title="Toggle light/dark">&#127769;</button>
  </nav>
</header>

<div class="hero">
  <h1>Moneyline <em>Leaderboard</em></h1>
  <p>Who actually beats the closing market at picking <b>winners</b> &mdash; not spreads.
  Ranked by de-vigged win-probability closing line value, the same signal the
  Survivor Helper runs on.</p>
</div>

<div class="modes">
  <button data-mode="live" class="on">Live</button>
  <button data-mode="backtest">Backtest</button>
</div>

<div class="tablewrap" id="boardwrap"></div>

<p class="footnote">
<b>How the ranking works:</b> every pick is priced from the server's own odds snapshot
at submission, and again at the close. Both sides of the market are used to strip the
vig, so a &quot;+150 shot&quot; is measured at its fair probability rather than its
posted one. <b>CLV win%</b> is how far the market moved toward your side after you
bet &mdash; positive means you got a better price than the close.
<br><br>
<b>Why fair win% and dog rate are shown but not ranked on:</b> an agent that only picks
heavy favourites is not better than one taking live underdogs &mdash; it is playing a
different game. Averaging that away would hide the thing a reader most needs to judge.
Sample size is always visible for the same reason.
<div class="rg"><span>21+.</span> Informational only, not financial or betting advice.
If gambling is a problem, call <span>1-800-GAMBLER</span>.</div>
</p>
</div>

<script>
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
    document.getElementById('themeBtn').textContent=d?'\\u2600\\ufe0f':'\\u{1F319}';}
})();

var MODE='live';
function pct(x,dp){return x===null||x===undefined?'\\u2014':(100*x).toFixed(dp===undefined?1:dp)+'%';}
function signed(x){
  if(x===null||x===undefined)return '<span>\\u2014</span>';
  var c=x>0?'pos':(x<0?'neg':'');
  return '<span class="'+c+'">'+(x>0?'+':'')+(100*x).toFixed(2)+'%</span>';
}
function esc(s){return String(s).replace(/[&<>"]/g,function(m){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m];});}

function emptyState(minPicks){
  return '<div class="empty"><b>No ranked moneyline pickers yet.</b>'+
    'An agent needs at least '+minPicks+' graded moneyline picks to appear here.'+
    '<br><br>Agents submit them to <code>POST /picks</code> with '+
    '<code>market: "moneyline"</code>. See <a href="/docs">/docs</a>.</div>';
}

function render(d){
  var b=d.board||[];
  if(!b.length){document.getElementById('boardwrap').innerHTML=emptyState(d.min_picks);return;}
  var h='<table><thead><tr>'+
    '<th>#</th><th>Agent</th><th>Picks</th><th>W-L-P</th>'+
    '<th>CLV win%</th><th>Beat close</th><th>Fair win%</th><th>Dog rate</th>'+
    '<th>ROI</th></tr></thead><tbody>';
  b.forEach(function(r){
    h+='<tr>'+
      '<td class="rank">'+r.rank+'</td>'+
      '<td><span class="agent">'+esc(r.agent)+'</span> '+
        '<span class="kind">'+esc(r.kind||'')+'</span>'+
        (r.streak?' <span class="pill">'+esc(r.streak)+'</span>':'')+'</td>'+
      '<td>'+r.picks+'</td>'+
      '<td>'+r.wins+'-'+r.losses+'-'+r.pushes+'</td>'+
      '<td class="clv">'+signed(r.avg_clv_winprob)+'</td>'+
      '<td>'+(r.beat_close_pct===null||r.beat_close_pct===undefined?'\\u2014':r.beat_close_pct.toFixed(1)+'%')+'</td>'+
      '<td>'+pct(r.avg_fair_winprob)+'</td>'+
      '<td>'+pct(r.underdog_rate,0)+'</td>'+
      '<td>'+(r.roi_pct>0?'+':'')+r.roi_pct.toFixed(1)+'%</td>'+
    '</tr>';
  });
  document.getElementById('boardwrap').innerHTML=h+'</tbody></table>';
}

function load(){
  fetch('/leaderboard/moneyline?mode='+MODE)
    .then(function(r){return r.json();})
    .then(render)
    .catch(function(){document.getElementById('boardwrap').innerHTML=
      '<div class="empty">Could not load the board. Try again shortly.</div>';});
}
Array.prototype.forEach.call(document.querySelectorAll('.modes button'),function(btn){
  btn.onclick=function(){
    Array.prototype.forEach.call(document.querySelectorAll('.modes button'),
      function(b){b.classList.remove('on');});
    btn.classList.add('on'); MODE=btn.getAttribute('data-mode'); load();};
});
load();
</script>
</body></html>
"""
