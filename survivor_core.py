"""Shared guts of the two survivor pages.

/survivor is the weekly helper: the ranked board, the portfolio split, the
holiday-leg panel, the multi-week planner. /survivor/sim is the season
simulator, on its own page because the helper had grown too long to work --
you could not see a number move while you were causing it to move.

Both pages read and write the SAME localStorage entries, so a pick made on
either shows up on the other. What lives here is everything that has to agree
between them: the theme, team colours, the Circa holiday-leg definitions, entry
state and elimination, the win-probability feed, and the shared value helpers.

CONTRACT: this module calls renderAll() whenever state changes. Each page
defines its own renderAll() over whatever panels it actually has. Nothing here
may name a page-specific renderer -- that was the coupling that made splitting
these two apart necessary in the first place.
"""

CORE_CSS = """
:root{
  --bg:#fbfcfd; --panel:#ffffff; --panel2:#f2f5f9; --ink:#122036;
  --dim:#64748b; --line:#dde4ec; --rule:#122036;
  --up:#0b9a72; --down:#d43d2a; --gold:#c8901f; --mid:#2f6fd0; --save:#1f6feb;
  --tickbg:#122036; --tickfg:#dbe4f0; --tickhi:#f5b53f;
  --shadow:0 1px 3px rgba(18,32,54,.05);
}
[data-theme="dark"]{
  --bg:#12100b; --panel:#1b1712; --panel2:#241e15; --ink:#efe7d5;
  --dim:#a1957c; --line:#352c1f; --rule:#4a3e2b;
  --up:#5fb56d; --down:#e2694f; --gold:#e8b64c; --mid:#d3a94f; --save:#7cb0ff;
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
/* alive = green edge, out = red edge, at a glance. The active entry keeps the
   gold ring on top of its green border, so "which one am I picking for" and
   "is it still alive" stay two separate signals. */
.entry{background:var(--panel);border:1px solid var(--up);border-radius:10px;
  padding:.9rem 1rem;box-shadow:var(--shadow);cursor:pointer;
  transition:border-color .2s,transform .15s}
.entry:hover{transform:translateY(-2px)}
/* no var(--shadow) in this list -- it is `none` in dark mode, which would make
   the whole box-shadow declaration invalid and drop the ring */
.entry.active{box-shadow:0 0 0 2px color-mix(in srgb,var(--gold) 45%,transparent)}
.entry .etop{display:flex;justify-content:space-between;align-items:center}
.entry .etitle{font-weight:800;font-size:.82rem}
.entry .ecount{font-size:.62rem;font-weight:800;letter-spacing:.1em;
  text-transform:uppercase;color:var(--dim)}
.usedchips{display:flex;gap:.3rem;flex-wrap:wrap;margin-top:.55rem;min-height:1.6rem}
.uchip{display:inline-flex;align-items:center;gap:.25rem;font-weight:800;
  font-size:.62rem;color:#fff;padding:.2rem .4rem;border-radius:5px}
.uchip .cwk{font-style:normal;font-size:.52rem;font-weight:900;opacity:.72;
  margin-right:.25rem;letter-spacing:.02em}
.uchip.thisweek{box-shadow:0 0 0 2px var(--ink)}
.uchip button{all:unset;cursor:pointer;opacity:.8;font-size:.7rem;line-height:1}
.uchip button:hover{opacity:1}
.entry .ehint{color:var(--dim);font-size:.64rem;margin-top:.4rem}
.entry{position:relative}
.linkbtn{all:unset;cursor:pointer;font-size:.6rem;font-weight:800;letter-spacing:.06em;
  text-transform:uppercase;color:var(--dim);border-bottom:1px dotted var(--line)}
.linkbtn:hover{color:var(--down);border-bottom-color:var(--down)}
.outbtn{position:absolute;right:1rem;bottom:.55rem;opacity:0;transition:opacity .15s}
.entry:hover .outbtn,.entry.active .outbtn{opacity:1}
.entry .ecount b{color:var(--up)}
.alivecount{font-size:.68rem;font-weight:800;letter-spacing:.06em;color:var(--down);
  text-transform:uppercase;margin-left:.5rem}

/* knocked-out entries: one slim strip each, tap to see the history back */
.deadentries{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:.35rem;margin-top:.7rem;align-items:start}
.entry.dead.open{grid-column:1/-1}
@media (hover:none){.outbtn{opacity:1}}   /* no hover on a phone */
.entry.dead{padding:.45rem .8rem;opacity:.72;box-shadow:none;background:transparent;
  border-color:color-mix(in srgb,var(--down) 55%,transparent)}
.entry.dead:hover{transform:none;opacity:1;border-color:var(--down)}
.entry.dead .etop{gap:.6rem;justify-content:flex-start}
.entry.dead .etitle{text-decoration:line-through;font-size:.76rem}
.entry.dead .ecount{color:var(--down);letter-spacing:.06em;margin-right:auto}
.entry.dead .caret{color:var(--dim);font-size:.7rem}
.entry.dead .usedchips{margin-top:.5rem;min-height:0;filter:grayscale(.55)}

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
.pick.holiday{border-color:var(--down);box-shadow:0 0 0 1px color-mix(in srgb,var(--down) 35%,transparent)}
.rank{font-weight:900;color:var(--dim);text-align:center;font-variant-numeric:tabular-nums}
.matchup{min-width:0}
.mteam{display:flex;align-items:center;gap:.5rem}
.tchip{display:inline-flex;align-items:center;justify-content:center;min-width:2.4rem;
  height:1.7rem;padding:0 .45rem;border-radius:6px;font-weight:900;font-size:.72rem;
  color:#fff;flex:none;letter-spacing:.02em}
.mteam b{font-size:1.02rem;font-weight:800}
.vs{color:var(--dim);font-size:.78rem;font-weight:600;margin-top:.2rem}
.asofbar{margin-bottom:.5rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.asof{color:var(--dim);font-size:.66rem;font-weight:800}
.asof.stale{color:var(--down)}
.flags{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.35rem}
.flag{font-weight:800;font-size:.58rem;letter-spacing:.06em;text-transform:uppercase;
  padding:.16rem .42rem;border-radius:5px;border:1px solid var(--line);color:var(--dim)}
.flag.save{color:var(--save);font-weight:900;
  border-color:color-mix(in srgb,var(--save) 55%,var(--line));
  background:color-mix(in srgb,var(--save) 12%,transparent)}
.flag.fv{color:var(--mid);border-color:color-mix(in srgb,var(--mid) 45%,var(--line));
  letter-spacing:.02em}
.flag.contra{color:var(--mid);border-color:color-mix(in srgb,var(--mid) 45%,var(--line))}
.flag.used{color:var(--down);border-color:color-mix(in srgb,var(--down) 45%,var(--line))}
.flag.home{color:var(--up);border-color:color-mix(in srgb,var(--up) 45%,var(--line))}
.flag.road{color:var(--dim)}
.flag.hol{color:var(--down);border-color:color-mix(in srgb,var(--down) 45%,var(--line))}
/* holiday legs panel */
.hleg{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.85rem 1rem;box-shadow:var(--shadow);margin-bottom:.7rem}
.hleg .htop{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.4rem}
.hleg .hname{font-weight:900;font-size:.95rem}
.hleg .hwhen{color:var(--dim);font-size:.7rem;font-weight:700}
.hleg .havail{font-weight:900;font-size:.6rem;letter-spacing:.06em;text-transform:uppercase}
.hgames{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.45rem;margin-top:.6rem}
.hgame{display:flex;flex-direction:column;gap:.15rem;background:var(--panel2);
  border:1px solid var(--line);border-radius:7px;padding:.4rem .5rem}
.hrow{display:flex;align-items:center;justify-content:space-between;gap:.5rem}
.hat{color:var(--dim);font-size:.52rem;font-weight:800;text-align:center;line-height:.5;opacity:.65}
.hwp{font-style:normal;font-weight:900;font-size:.66rem;font-variant-numeric:tabular-nums;color:var(--dim)}
.hwp.fav{color:var(--up)}
.hteam{display:inline-flex;align-items:center;gap:.2rem;font-weight:800;font-size:.66rem;
  color:#fff;padding:.24rem .48rem;border-radius:6px}
.hteam.spent{opacity:.32;text-decoration:line-through}
.hteam .dbl{font-size:.62rem;line-height:1}
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
/* "use this team" buttons -- one per entry. Stacked vertically, ten of them made
   every pick row three times taller than the pick itself, so they run across in
   a grid of at most five columns (JS sets the column count from the entry count). */
.usebtns{display:grid;gap:.25rem;justify-content:end;align-content:center}
.usebtns button{all:unset;cursor:pointer;font-weight:800;font-size:.6rem;
  letter-spacing:.03em;text-align:center;padding:.24rem .4rem;border-radius:6px;
  border:1px solid var(--line);color:var(--dim);min-width:3.1rem;white-space:nowrap;
  font-variant-numeric:tabular-nums}
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
/* an entry that has already locked this week's pick */
.alloc.done{border-color:color-mix(in srgb,var(--up) 45%,var(--line));
  background:color-mix(in srgb,var(--up) 6%,var(--panel))}
.alloc.done .awp{font-size:.6rem;font-weight:900;letter-spacing:.1em;
  text-transform:uppercase;color:var(--up)}
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
  margin-top:.2rem}
  /* keep five "Use E10" buttons across on a phone: tighter type, no min-width */
  .usebtns{gap:.16rem}
  .usebtns button{min-width:0;padding:.22rem .14rem;font-size:.5rem;letter-spacing:0}
  .wp{min-width:3.6rem;padding:.4rem .3rem}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important;
  transition:none!important}}

.ecount-ctl{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;
  margin:.2rem 0 .9rem;font-size:.82rem}
.ecount-ctl label{font-weight:800}
.ecount-ctl button{width:2rem;height:2rem;border-radius:8px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);font-weight:900;cursor:pointer;font-size:1rem}
.ecount-ctl button:hover{border-color:var(--up)}
.ecount-ctl input{width:3.4rem;text-align:center;font-weight:900;font-size:.95rem;
  padding:.35rem;border-radius:8px;border:1px solid var(--line);
  background:var(--panel);color:var(--ink)}
.ecount-ctl .ehintsm{color:var(--dim);font-size:.72rem}
/* live bar -- pinned so the numbers are visible while you work the board */
body{padding-bottom:4.2rem}
.livebar{position:fixed;left:0;right:0;bottom:0;z-index:60;
  background:var(--panel);border-top:1px solid var(--line);
  box-shadow:0 -6px 18px rgba(0,0,0,.10);padding:.5rem .9rem;
  display:flex;align-items:center;gap:.9rem;flex-wrap:wrap;
  font-size:.72rem;font-weight:800}
.livebar .lbwho{font-weight:900;font-size:.8rem;white-space:nowrap}
.livebar .lbwho small{display:block;color:var(--dim);font-size:.6rem;font-weight:700}
.livebar .lbstat{display:flex;flex-direction:column;line-height:1.15;white-space:nowrap}
.livebar .lbstat i{color:var(--dim);font-size:.55rem;font-style:normal;font-weight:900;
  letter-spacing:.05em;text-transform:uppercase}
.livebar .lbstat b{font-size:.86rem}
.livebar .lbspent{color:var(--dim);font-weight:700;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;flex:1;min-width:0}
.livebar .lbcost{flex:1;min-width:0;font-weight:800;font-size:.7rem;
  padding:.22rem .55rem;border-radius:999px;border:1px solid var(--line)}
.livebar .lbcost.ok{color:var(--dim)}
.livebar .lbcost.warn{color:var(--ink);
  border-color:color-mix(in srgb,var(--down) 30%,var(--line));
  background:color-mix(in srgb,var(--down) 8%,transparent)}
.livebar .lbcost.bad{color:var(--down);
  border-color:color-mix(in srgb,var(--down) 45%,var(--line))}
.livebar .bump{animation:lbflash .9s ease-out}
@keyframes lbflash{0%{background:color-mix(in srgb,var(--up) 45%,transparent);
  border-radius:5px}100%{background:transparent;border-radius:5px}}
@media (prefers-reduced-motion:reduce){.livebar .bump{animation:none}}
@media (max-width:640px){.livebar{gap:.6rem;font-size:.66rem}
  .livebar .lbspent{display:none}}
/* scenario simulator */
.entrypanel{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.8rem 1rem;box-shadow:var(--shadow);margin-bottom:.9rem}
.entrypanel .eptop{display:flex;justify-content:space-between;align-items:baseline;
  flex-wrap:wrap;gap:.4rem}
.entrypanel .eptop b{font-size:1rem}
.entrypanel .epsub{color:var(--dim);font-size:.68rem;font-weight:700}
.entrypanel .epspent{margin:.5rem 0 .6rem;display:flex;flex-wrap:wrap;gap:.35rem;
  align-items:center;font-size:.7rem;font-weight:700;color:var(--dim)}
.entrypanel .epstats{display:flex;flex-wrap:wrap;gap:1.1rem;padding-top:.55rem;
  border-top:1px solid var(--line)}
.entrypanel .epstats span{font-size:.9rem;font-weight:900;white-space:nowrap}
.entrypanel .epstats i{display:block;color:var(--dim);font-size:.58rem;font-style:normal;
  font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.entrypanel .epstats small{color:var(--dim);font-size:.62rem;font-weight:700}
.simcaption{grid-column:1/-1;color:var(--dim);font-size:.6rem;font-weight:900;
  letter-spacing:.06em;text-transform:uppercase;margin-bottom:-.2rem}
.simctl{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-bottom:.8rem}
.simctl button{font:inherit;font-weight:800;font-size:.72rem;padding:.4rem .8rem;
  border-radius:999px;border:1px solid var(--line);background:var(--panel);
  color:var(--ink);cursor:pointer}
.simctl button.on{background:var(--ink);color:var(--panel);border-color:var(--ink)}
.simctl .simnote{color:var(--dim);font-size:.68rem;font-weight:700}
.simcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin-bottom:.9rem}
.simcard{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.7rem .85rem;box-shadow:var(--shadow)}
.simcard .sclab{color:var(--dim);font-size:.6rem;font-weight:900;letter-spacing:.06em;
  text-transform:uppercase}
.simcard .scval{font-size:1.5rem;font-weight:900;line-height:1.15;margin-top:.15rem}
.simcard .scsub{color:var(--dim);font-size:.66rem;font-weight:700}
.simcard.warn .scval{color:var(--down)}
.curve{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.85rem 1rem;box-shadow:var(--shadow);margin-bottom:.9rem;overflow-x:auto}
.curve table{border-collapse:collapse;width:100%;min-width:520px}
.curve td{padding:.16rem .3rem;font-size:.68rem;font-weight:700;vertical-align:middle}
.curve td.cl{color:var(--dim);white-space:nowrap;width:9rem}
.curve td.cv{text-align:right;width:3.2rem;font-variant-numeric:tabular-nums}
.curve .bar{height:.62rem;border-radius:3px;background:var(--ink);display:block}
.curve .csrc{color:var(--dim);font-size:.68rem;font-weight:700;line-height:1.5;
  margin-bottom:.6rem}
.estdot{font-style:normal;font-size:.55rem;font-weight:900;letter-spacing:.05em;
  text-transform:uppercase;border:1px solid var(--line);border-radius:3px;
  padding:0 .25rem;color:var(--dim);vertical-align:middle}
.curve tr.hol td.cl{color:var(--down)}
.curve tr.hol .bar{background:var(--down)}
.cmp{width:100%;border-collapse:collapse}
.cmp th{text-align:left;font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;
  color:var(--dim);padding:.3rem .4rem;border-bottom:1px solid var(--line)}
.cmp td{padding:.34rem .4rem;border-bottom:1px solid var(--line);font-size:.74rem;font-weight:700}
.cmp td.n{text-align:right;font-variant-numeric:tabular-nums}
.cmp tr.best td{background:color-mix(in srgb,var(--up) 12%,transparent)}
.cmp .delta.up{color:var(--up)}
.cmp .delta.dn{color:var(--down)}
.holdlist{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem}
.holdchip{display:inline-flex;align-items:center;gap:.3rem;border-radius:999px;
  padding:.2rem .6rem;font-size:.7rem;font-weight:900;color:#fff}
.holdchip small{font-weight:700;opacity:.85}
.simwarn{color:var(--dim);font-size:.68rem;font-weight:700;margin-top:.5rem;line-height:1.5}
"""

CORE_JS = """
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
var NFL_TEAMS=32;   /* franchises, for the "teams left" count (TC has aliases) */

/* ---------- Circa 2026 holiday legs (only these teams are pickable those days) ---------- */
var HOLIDAY_LEGS=[
 {name:'Thanksgiving Leg',emoji:'🦃',when:'Wk 12 · Wed 11/25 – Fri 11/27',
  games:[['GB','LA'],['CHI','DET'],['PHI','DAL'],['KC','BUF'],['DEN','PIT']]},
 {name:'Christmas Leg',emoji:'🎄',when:'Wk 16 · Thu 12/24 – Fri 12/25',
  games:[['HOU','PHI'],['GB','CHI'],['BUF','DEN'],['LA','SEA']]}
];
function teamsInLeg(leg){var s={};leg.games.forEach(function(g){s[g[0]]=1;s[g[1]]=1;});return Object.keys(s);}
function holidayLegsFor(team){return HOLIDAY_LEGS.filter(function(l){return teamsInLeg(l).indexOf(team)>=0;});}

/* ---------- entry state ---------- */
var EK='survivor_entries_v1', AK='survivor_active_v1', NK='survivor_count_v1';
/* Circa caps a person at 10 entries. Mark plays 10; the tool defaults to 3
   but must scale to the cap without the planner or portfolio assuming three. */
var MAX_ENTRIES=10;
function entryCount(){var n=parseInt(localStorage.getItem(NK),10);
  return (isNaN(n)||n<1)?3:Math.min(n,MAX_ENTRIES);}
function entryIds(){var a=[],n=entryCount();for(var i=1;i<=n;i++)a.push(String(i));return a;}
function blankEntries(){var o={};entryIds().forEach(function(n){o[n]=[];});return o;}
/* at most five "use on entry" buttons per row, so ten entries make two short
   rows instead of one tall column */
function useCols(){return Math.max(1,Math.min(aliveIds().length,5));}
/* A pick is {t:team, w:week}. It used to be a bare team name, which meant the
   tool could not tell WHICH week a team was used in -- so nothing stopped an
   entry taking two teams in the same week, which is not a thing you can do.
   Old flat lists migrate to w:0 ("week unknown"): they still burn the team
   for the season, they just do not lock any particular week. */
function normPicks(a){
  if(!Array.isArray(a))return [];
  return a.map(function(x){
    if(typeof x==='string')return {t:x,w:0};
    if(x&&typeof x.t==='string')return {t:x.t,w:(typeof x.w==='number'?x.w:0)};
    return null;}).filter(Boolean);
}
function entries(){
  var o;try{o=JSON.parse(localStorage.getItem(EK))||{}}catch(e){o={}}
  entryIds().forEach(function(n){o[n]=normPicks(o[n]);});
  return o;}
function picksOf(n){return entries()[n]||[]}
/* the pick this entry already made in a given week, if any */
function pickForWeek(n,wk){
  if(!wk)return null;
  var f=picksOf(n).filter(function(p){return p.w===wk;});
  return f.length?f[0]:null;}
function setEntryCount(n){
  n=Math.max(1,Math.min(MAX_ENTRIES,parseInt(n,10)||1));
  localStorage.setItem(NK,String(n));
  /* keep any teams already recorded on entries that still exist; never wipe
     silently -- a dropped entry's history stays in storage if they add it back */
  if(parseInt(active(),10)>n){var al=aliveIds();setActive(al.length?al[0]:'1');}
  renderAll();}
function saveEntries(e){localStorage.setItem(EK,JSON.stringify(e))}
function active(){var a=localStorage.getItem(AK)||'1';
  if(isOut(a)){var al=aliveIds();if(al.length)return al[0];}
  return a;}
function setActive(n){localStorage.setItem(AK,String(n));renderAll()}
function usedBy(n){return picksOf(n).map(function(p){return p.t;})}
/* only LIVE entries lock a team out of the planner -- a dead entry's history
   must not steer the entries that are still playing */
function usedAny(t){var e=entries();return aliveIds().some(function(n){
  return (e[n]||[]).some(function(p){return p.t===t;});})}

/* ---------- elimination ----------
   A loss OR a tie ends an entry, but the entry's used teams stay on record.
   Out entries collapse to a strip, drop off the per-pick Use buttons, and are
   excluded from the weekly split -- otherwise the split keeps diversifying
   against entries that are already dead and pushes the live ones onto worse
   teams. Storage: {entryId: weekNumber} (0 when the week is unknown). */
var OUTK='survivor_out_v1';
function outMap(){var o;try{o=JSON.parse(localStorage.getItem(OUTK))||{}}catch(e){o={}}
  return (o&&typeof o==='object')?o:{};}
function isOut(n){return outMap()[n]!=null;}
function outWeek(n){var w=outMap()[n];return (typeof w==='number'&&w>0)?w:null;}
function aliveIds(){return entryIds().filter(function(n){return !isOut(n);});}
function curWeekNo(){return (WEEKS.length&&WEEKS[curIdx])?WEEKS[curIdx].week:0;}
function markOut(n){
  n=String(n);
  var o=outMap();o[n]=curWeekNo();localStorage.setItem(OUTK,JSON.stringify(o));
  /* never leave the active entry pointing at a dead one */
  if(active()===n){var a=aliveIds();if(a.length)localStorage.setItem(AK,a[0]);}
  toast('Entry '+n+' marked out'+(o[n]?' (week '+o[n]+')':''));
  renderAll();
}
function reviveEntry(n){
  n=String(n);var o=outMap();delete o[n];localStorage.setItem(OUTK,JSON.stringify(o));
  toast('Entry '+n+' is back in');renderAll();
}
/* which dead entries are expanded to show their history -- view state only */
var EXPANDED={};
function toggleDead(n){n=String(n);EXPANDED[n]=!EXPANDED[n];renderEntries();}

function useTeam(team,n){
  var e=entries(),wk=curWeekNo();
  if(usedBy(n).indexOf(team)>=0)return;
  /* one team per entry per week -- swap by removing the existing pick first */
  var have=pickForWeek(n,wk);
  if(have){toast('Entry '+n+' already has '+have.t+' for week '+wk+' — ✕ it first to switch');return;}
  e[n].push({t:team,w:wk});saveEntries(e);
  /* Follow the click. Picking on entry 3 while the panel stayed pinned to
     entry 1 meant two clicks out of three showed the owner nothing move. */
  localStorage.setItem(AK,String(n));
  LASTPICK={t:team,n:String(n)};
  var hl=holidayLegsFor(team);
  toast(team+' → Entry '+n+(wk?' (week '+wk+')':'')+
        (hl.length?' — note: plays the '+hl.map(function(l){return l.name;}).join(' & '):''));
  renderAll();
}
function dropTeam(team,n){
  var e=entries();e[n]=e[n].filter(function(p){return p.t!==team});saveEntries(e);
  renderAll();
}
function toast(msg){var t=document.getElementById('toast');t.textContent=msg;
  t.classList.add('show');clearTimeout(t._h);t._h=setTimeout(function(){t.classList.remove('show')},1600)}

function renderEntries(){
  var e=entries(),act=active(),h='',dead='';
  var wkNow=curWeekNo();
  function chipsFor(n,picks,removable){
    return picks.map(function(p){
      var t=p.t, ttl=p.w?('week '+p.w):'week not recorded';
      return '<span class="uchip'+(p.w&&p.w===wkNow?' thisweek':'')+'" title="'+t+' · '+ttl+
        '" style="background:'+tcol(t)+'">'+(p.w?'<i class="cwk">W'+p.w+'</i>':'')+t+
        (removable?' <button title="remove '+t+'" onclick="event.stopPropagation();dropTeam(\\''+t+'\\','+n+')">✕</button>':'')+
        '</span>';}).join('') || '<span class="ehint">No teams used yet</span>';
  }
  entryIds().forEach(function(n){
    var used=e[n]||[];
    if(isOut(n)){
      var wk=outWeek(n);
      dead+='<div class="entry dead'+(EXPANDED[n]?' open':'')+'" onclick="toggleDead('+n+')">'+
        '<div class="etop"><span class="etitle">Entry '+n+'</span>'+
        '<span class="ecount">out'+(wk?' · wk '+wk:'')+' · '+used.length+' used</span>'+
        '<button class="linkbtn" onclick="event.stopPropagation();reviveEntry('+n+')">back in</button>'+
        '<span class="caret">'+(EXPANDED[n]?'▴':'▾')+'</span></div>'+
        (EXPANDED[n]?'<div class="usedchips">'+chipsFor(n,used,false)+'</div>':'')+
        '</div>';
      return;
    }
    h+='<div class="entry'+(act===n?' active':'')+'" onclick="setActive('+n+')">'+
       '<div class="etop"><span class="etitle">Entry '+n+(act===n?' · active':'')+'</span>'+
       '<span class="ecount">'+used.length+'/20 used · <b>'+(NFL_TEAMS-used.length)+' left</b></span></div>'+
       '<div class="usedchips">'+chipsFor(n,used,true)+'</div>'+
       '<button class="linkbtn outbtn" onclick="event.stopPropagation();markOut('+n+')">mark out</button>'+
       '</div>';
  });
  document.getElementById('entries').innerHTML=h;
  document.getElementById('deadentries').innerHTML=dead;
  var alive=aliveIds().length, total=entryIds().length;
  document.getElementById('alivecount').textContent=
    alive===total ? '' : alive+' of '+total+' alive';
}

/* ---------- home-field lean (subjective ranking tilt, not the market number) ---------- */
var LK='survivor_lean_v1';
var LEAN=(function(){var v=parseFloat(localStorage.getItem(LK));return isNaN(v)?0.015:v;})();
function setLean(v){LEAN=parseFloat(v);localStorage.setItem(LK,String(LEAN));
  document.getElementById('leanval').textContent=(LEAN>0?'+':'')+(LEAN*100).toFixed(1)+'%';
  renderAll();}

/* ---------- entry-count control ---------- */
(function(){
  var inp=document.getElementById('nentries');
  if(!inp)return;
  inp.value=entryCount();
  function apply(v){setEntryCount(v);inp.value=entryCount();}
  inp.onchange=function(){apply(inp.value);};
  document.getElementById('eplus').onclick=function(){apply(entryCount()+1);};
  document.getElementById('eminus').onclick=function(){apply(entryCount()-1);};
})();

/* ---------- data ---------- */
var DATA=null, WEEKS=[], curIdx=0, PREVIEW=false;
var HOLWP={};                                  // "AWAY@HOME" -> {aw, hw} for holiday games
function indexHol(weeksArr){
  (weeksArr||[]).forEach(function(w){(w.games||[]).forEach(function(g){
    if(g.home_wp!=null)HOLWP[g.away+'@'+g.home]={aw:g.away_wp,hw:g.home_wp};});});
}
/* How old the numbers are, and a way to go and get new ones. After a
   quarterback goes down the only question is whether the market has repriced
   yet and whether we have that price -- a page that cannot answer it is worse
   than useless, because it looks current. */
function renderAsOf(){
  var el=document.getElementById('asof');
  if(!el)return;
  if(!DATA){el.innerHTML='';return;}
  if(!DATA.as_of){
    el.innerHTML='<span class="asof stale">'+(DATA.as_of_note||'No live odds capture.')+
      '</span> <button class="usebtn" onclick="reloadOdds()">Refresh</button>';
    return;
  }
  var t=new Date(DATA.as_of+'Z'), mins=Math.round((Date.now()-t.getTime())/60000);
  var age = mins<90 ? (mins+' min old')
          : mins<2880 ? (Math.round(mins/60)+' hours old')
          : (Math.round(mins/1440)+' days old');
  var stale = mins>4320;   /* three days: a snapshot slot has been missed */
  el.innerHTML='<span class="asof'+(stale?' stale':'')+'">Odds captured '+
    t.toLocaleString(undefined,{weekday:'short',month:'short',day:'numeric',
      hour:'numeric',minute:'2-digit'})+' &middot; '+age+
    (stale?' &mdash; a snapshot has been missed, an injury since then is not in these numbers':'')+
    '</span> <button class="usebtn" onclick="reloadOdds()">Refresh</button>';
}
function reloadOdds(){
  var el=document.getElementById('asof');
  if(el)el.innerHTML='<span class="asof">refreshing&hellip;</span>';
  load();
}

async function load(){
  var url=PREVIEW?'/data/survivor?season=2025&start_week=6&weeks=8':'/data/survivor?weeks=18';
  try{DATA=await (await fetch(url)).json();}catch(e){DATA={weeks:[]};}
  WEEKS=(DATA.weeks||[]).filter(function(w){return w.games&&w.games.length;});
  indexHol(DATA.weeks);
  curIdx=0;
  renderAll();
  renderAsOf();
  // holiday legs are weeks 12 & 16 — usually outside the 8-week board window, so
  // pull those weeks' win probs on their own (fills in once the market posts them).
  if(!PREVIEW){[12,16].forEach(function(wk){
    fetch('/data/survivor?start_week='+wk+'&weeks=1'+(DATA.season?'&season='+DATA.season:''))
      .then(function(r){return r.json();}).then(function(d){indexHol(d.weeks);if(typeof renderHolidays==='function')renderHolidays();})
      .catch(function(){});
  });}
}

function weekTeams(w){
  var out=[];
  (w.games||[]).forEach(function(g){
    if(g.home_wp==null)return;
    out.push({team:g.home,opp:g.away,home:true,wp:g.home_wp,gid:g.game_id,src:g.wp_source});
    out.push({team:g.away,opp:g.home,home:false,wp:g.away_wp,gid:g.game_id,src:g.wp_source});
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
/* ---------- future value ----------
   futureMap() above finds a team's single best week ahead, which misses the
   team that is favoured in eight straight weeks without ever being a standout.
   This is SurvivorGrid's definition instead: sum (wp - 0.5) over EVERY
   remaining game the team is favoured in. Higher = more useful later = more
   reason not to burn it now.

   It used to cover only market-priced weeks, because those were the only ones
   with a number at all. Now that unpriced weeks carry a power-rating prior it
   spans the whole season, which is closer to the definition -- the point of
   taking it was to catch the team favoured in eight straight weeks, and you
   cannot see eight weeks of a September season without estimates. But that
   means a star rating now blends real lines with guesses, so the flag says how
   many of each it is standing on rather than implying they are the same. */
function futureValue(afterWeek){
  var fv={};
  WEEKS.forEach(function(w){
    if(w.week<=afterWeek)return;
    weekTeams(w).forEach(function(p){
      if(p.wp>0.5)fv[p.team]=(fv[p.team]||0)+(p.wp-0.5);
    });
  });
  return fv;
}
/* 1-5 stars, spread linearly across the teams that have any future value */
function fvStars(fv){
  var vals=Object.keys(fv).map(function(t){return fv[t];});
  if(!vals.length)return {};
  var lo=Math.min.apply(null,vals), hi=Math.max.apply(null,vals);
  var span=(hi-lo)||1, out={};
  Object.keys(fv).forEach(function(t){
    out[t]=Math.max(1,Math.min(5,Math.ceil((fv[t]-lo)/span*5)||1));
  });
  return out;
}
/* Weeks ahead, split by whether anyone has actually priced them. */
function fvWeeksAhead(afterWeek){
  var n=0,mkt=0;
  WEEKS.forEach(function(w){
    if(w.week<=afterWeek)return;
    n++;
    var real=0;
    (w.games||[]).forEach(function(g){
      if(g.wp_source==='ml'||g.wp_source==='spread')real++;});
    if(real*2>=(w.games||[]).length)mkt++;
  });
  return {total:n,market:mkt,est:n-mkt};
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
  renderAll();}
function togglePreview(){PREVIEW=!PREVIEW;
  document.getElementById('previewBtn').textContent=PREVIEW?'Use live schedule':'Preview with 2025 data';
  load();}

/* ---------- countdown ---------- */
(function(){
  var deadline=new Date('2026-09-12T21:00:00Z'); // 2:00 PM PT (PDT)
  function tick(){
    var el=document.getElementById('countdown');if(!el)return;var ms=deadline-new Date();
    if(ms<=0){el.innerHTML='Registration is <b>closed</b> for 2026.';return;}
    var d=Math.floor(ms/86400000),h=Math.floor(ms/3600000)%24,m=Math.floor(ms/60000)%60;
    el.innerHTML='Registration closes in <b>'+d+'d '+h+'h '+m+'m</b> · Sat Sep 12, 2026 · 2:00 PM PT';
  }
  tick();setInterval(tick,30000);
})();

/* sync the lean control to saved state */
/* Both controls are optional: the simulator page has no lean slider. */
(function(){
  var l=document.getElementById('lean');
  if(l)l.value=LEAN;
  var lv=document.getElementById('leanval');
  if(lv)lv.textContent=(LEAN>0?'+':'')+(LEAN*100).toFixed(1)+'%';
})();

renderEntries();load();
"""


def shell(title, description, nav_active, head_extra, body_html, page_js,
          after_wrap=""):
    """Assemble a complete page. Both survivor pages are built from this so the
    chrome, the theme toggle and the responsible-gambling footer cannot drift
    apart between them."""
    def nav(href, label):
        on = ' class="on"' if href == nav_active else ''
        return '<a href="%s"%s>%s</a>' % (href, on, label)
    links = "".join([
        nav("/moneyline", "Moneyline"),
        nav("/survivor", "Survivor"),
        nav("/survivor/sim", "Simulator"),
        nav("/explorer", "Explorer"),
        nav("/picks-board", "Make Picks"),
        nav("/", "Board"),
    ])
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>' + title + '</title>\n'
        '<meta name="description" content="' + description + '">\n'
        '<link rel="canonical" href="https://closinglinehq.com' + nav_active + '">\n'
        + head_extra +
        '<style>' + CORE_CSS + '</style></head><body>\n'
        '<div class="wrap">\n<header>\n'
        '  <div class="logo"><a href="/" style="text-decoration:none">'
        'CLOSING<span>LINE</span></a></div>\n'
        '  <nav>' + links +
        '<button id="themeBtn" title="Toggle light/dark">&#127769;</button></nav>\n'
        '</header>\n'
        + body_html + '</div>\n' + after_wrap +
        '<div class="toast" id="toast"></div>\n'
        '<script>' + CORE_JS + page_js + '</script></body></html>'
    )
