"""Explorer page HTML — imported by app.py, served at /explorer."""

EXPLORER_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ClosingLine — Explorer</title><style>
:root{--ink:#101418;--dim:#5b6570;--line:#d9dee4;--up:#0f6e56;--down:#a32d2d;
--accent:#185fa5;--bg:#f7f8f9;--card:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 "Iowan Old Style",Georgia,serif}
header{padding:2rem 1.5rem .4rem;max-width:1020px;margin:auto}
h1{font-size:1.7rem;margin:0}h1 span{color:var(--accent)}
h1 a{color:inherit;text-decoration:none}
p.sub{color:var(--dim);margin:.2rem 0 0;font-size:.92rem}
main{max-width:1020px;margin:auto;padding:0 1.5rem 3rem}
.trends{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
gap:.7rem;margin:1.1rem 0}
.tcard{background:var(--card);border:1px solid var(--line);padding:.8rem .9rem}
.tcard .big{font:700 1.5rem/1.1 ui-monospace,Menlo,monospace}
.tcard .pct{font:600 .8rem ui-monospace,monospace;margin-left:.4rem}
.tcard .lbl{font-size:.78rem;color:var(--dim);line-height:1.35;margin-top:.3rem}
.weeknav{display:flex;flex-wrap:wrap;gap:.25rem;margin:.9rem 0 .6rem}
.weeknav button{font:600 .72rem/1 ui-monospace,monospace;padding:.42rem .6rem;
border:1px solid var(--line);background:var(--card);cursor:pointer}
.weeknav button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.filters{display:flex;flex-wrap:wrap;gap:.9rem;font:600 .74rem/1 ui-monospace,
monospace;letter-spacing:.04em;color:var(--dim);margin:.4rem 0 .8rem}
.filters label{cursor:pointer}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);font-size:.88rem}
th{font:600 .68rem/1 ui-monospace,monospace;letter-spacing:.08em;
text-transform:uppercase;color:var(--dim);text-align:left;padding:.6rem .7rem;
border-bottom:2px solid var(--ink)}
td{padding:.55rem .7rem;border-bottom:1px solid var(--line);
font-variant-numeric:tabular-nums;vertical-align:top}
td.mu{font-weight:700}
.tag{display:inline-block;font:600 .62rem/1 ui-monospace,monospace;
letter-spacing:.05em;border:1px solid var(--line);color:var(--dim);
padding:.18rem .35rem;margin:.1rem .15rem .1rem 0;background:var(--bg)}
.cover{color:var(--up);font-weight:700}.nocover{color:var(--down)}
.note{font-size:.82rem;color:var(--dim);margin-top:.8rem}
.empty{color:var(--dim);padding:2rem;text-align:center;background:var(--card);
border:1px dashed var(--line)}
</style></head><body>
<header><h1><a href="/">Closing<span>Line</span></a> · Explorer</h1>
<p class="sub">Real season data — the free layer. Browse the slate, filter
situations, see how the season actually went.</p></header>
<main>
<div class="trends" id="trends"></div>
<div class="weeknav" id="weeknav"></div>
<div class="filters" id="filters">
 <label><input type="checkbox" value="DIV" onchange="draw()"> DIVISION</label>
 <label><input type="checkbox" value="HOME DOG" onchange="draw()"> HOME DOG</label>
 <label><input type="checkbox" value="DOME" onchange="draw()"> DOME</label>
 <label><input type="checkbox" value="REST+" onchange="draw()"> REST EDGE</label>
 <label><input type="checkbox" value="COLD" onchange="draw()"> COLD</label>
 <label><input type="checkbox" value="WIND" onchange="draw()"> WIND</label>
</div>
<div id="slate"></div>
<p class="note" id="tnote"></p>
</main><script>
let WEEK=1, DATA=[];
async function boot(){
 const t=await (await fetch('/data/trends')).json();
 document.getElementById('tnote').textContent=t.note;
 document.getElementById('trends').innerHTML=Object.values(t.trends).map(b=>
  `<div class="tcard"><span class="big">${b.record}</span>`+
  `<span class="pct">${b.pct===null?'':b.pct+'%'}</span>`+
  `<div class="lbl">${b.desc}</div></div>`).join('');
 const nav=document.getElementById('weeknav');
 for(let w=1;w<=18;w++){const b=document.createElement('button');
  b.textContent='W'+w;b.id='w'+w;b.onclick=()=>go(w);nav.appendChild(b)}
 go(1);
}
async function go(w){
 WEEK=w;
 for(let i=1;i<=18;i++)document.getElementById('w'+i).className=i===w?'on':'';
 DATA=await (await fetch('/data/slate?week='+w)).json();
 draw();
}
function draw(){
 const need=[...document.querySelectorAll('#filters input:checked')].map(x=>x.value);
 const rows=DATA.filter(g=>need.every(n=>g.tags.some(t=>t.startsWith(n))));
 const el=document.getElementById('slate');
 if(!rows.length){el.innerHTML='<div class="empty">No games match these filters in week '+WEEK+'.</div>';return}
 const s=n=>n>0?'+'+n:n;
 let h='<table><tr><th>Matchup</th><th>Close</th><th>Total</th><th>ML</th>'+
  '<th>Situations</th><th>Result</th></tr>';
 for(const g of rows){
  const res=g.final?`${g.away} ${g.away_score} — ${g.home} ${g.home_score}<br>`+
   `<span class="${g.ats==='push'?'':'cover'}">${g.ats==='push'?'ATS push':g.ats+' covers'}</span>`+
   ` · <span>${g.ou==='push'?'total push':g.ou}</span>`
   :'<span class="tag">UPCOMING</span>';
  h+=`<tr><td class="mu">${g.away} @ ${g.home}</td>`+
   `<td>${g.home} ${s(g.spread_home)}</td><td>${g.total}</td>`+
   `<td>${s(g.ml_home)} / ${s(g.ml_away)}</td>`+
   `<td>${g.tags.map(t=>'<span class="tag">'+t+'</span>').join('')||'—'}</td>`+
   `<td>${res}</td></tr>`}
 el.innerHTML=h+'</table>';
}
boot();
</script></body></html>"""
