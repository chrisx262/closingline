"""Survivor Helper page — imported by app.py, served at /survivor.

Circa Survivor is a straight-up (moneyline) contest: pick one team to win each
week, never reuse a team, a loss OR a tie eliminates you. Straight-up win
probability is exactly the signal, and in our own backtests the market beat our
model at picking winners — so this tool leans on de-vigged market moneyline win
probabilities (served by /data/survivor) and layers the survivor strategy on
top: future value, an (estimated) pick-popularity read, and per-entry used-team
tracking for a multi-entry portfolio (1-10 entries; Circa's per-person cap).

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
.flags{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.35rem}
.flag{font-weight:800;font-size:.58rem;letter-spacing:.06em;text-transform:uppercase;
  padding:.16rem .42rem;border-radius:5px;border:1px solid var(--line);color:var(--dim)}
.flag.save{color:var(--gold);border-color:color-mix(in srgb,var(--gold) 45%,var(--line))}
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
/* scenario simulator */
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
</style></head><body>
<div class="wrap">
<header>
  <div class="logo"><a href="/" style="text-decoration:none">CLOSING<span>LINE</span></a></div>
  <nav>
    
    <a href="/moneyline">Moneyline</a><a href="/survivor" class="on">Survivor</a>
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
  <h2>Your <em>Entries</em> <span class="alivecount" id="alivecount"></span></h2>
  <p class="subnote">Tap an entry to make it active, then use the picks below. Used teams
  are locked out for that entry. Lose one and hit <b>mark out</b> — it collapses out of
  the way and stops counting toward the weekly split. Stored in your browser only.</p>
  <div class="ecount-ctl">
    <label for="nentries">How many entries do you play?</label>
    <button type="button" id="eminus" aria-label="one fewer entry">&minus;</button>
    <input id="nentries" type="number" min="1" max="10" step="1" value="3"
           inputmode="numeric" aria-label="number of survivor entries">
    <button type="button" id="eplus" aria-label="one more entry">+</button>
    <span class="ehintsm">Circa allows up to 10 per person.</span>
  </div>
  <div class="entries" id="entries"></div>
  <div class="deadentries" id="deadentries"></div>
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
  <h2>Entry <em>Portfolio</em></h2>
  <p class="subnote">A diversified split for this week across all of your entries —
  concentrating some on the safest board and spreading the rest, so a single upset
  can't end them all. With a lot of entries you will be pushed onto weaker teams;
  the split says so rather than dressing it up.</p>
  <div id="portfolio"></div>
</section>

<section>
  <h2>Holiday <em>Legs</em> — don't burn these</h2>
  <p class="subnote">The Thanksgiving & Christmas legs only let you pick from the teams playing
  those days. Keep at least one strong option unused for each. Showing the <b>active entry</b>;
  a leg turns red when you're down to your last couple of options.</p>
  <div id="holidays"></div>
</section>

<section>
  <h2>Multi-week <em>Planner</em></h2>
  <p class="subnote">Top available survival options each week, so you can save premium teams
  and keep unused teams for the holiday legs. Struck-through = already used by a live entry.</p>
  <div class="planwrap" id="planner"></div>
</section>

<section>
  <h2>Scenario <em>Simulator</em></h2>
  <p class="subnote">Plays out the rest of the season ten thousand times over, using your
  actual entries and the teams you have already spent. Change anything above &mdash; use a
  team, mark an entry out &mdash; and this rebuilds. Use it to compare two plans, not to
  predict a week: the ordering is trustworthy, the exact percentages are not.</p>
  <div class="simctl">
    <button id="simReserve" class="on" onclick="toggleReserve()">Holding holiday teams back</button>
    <span class="simnote" id="simstatus"></span>
  </div>
  <div class="simcards" id="simcards"></div>
  <div id="simcurve"></div>
  <h3 style="font-size:.95rem;margin:.2rem 0 .5rem">If you pick this now, what happens later?</h3>
  <p class="subnote" style="margin-top:0">Each option re-runs the whole season with that team
  spent here. The last two columns are the team you would still have for each holiday leg
  &mdash; a red number is what taking this pick costs you there. Most picks cost nothing;
  the ones that do are the decision.</p>
  <div id="simcompare"></div>
  <div id="simhold"></div>
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
function setActive(n){localStorage.setItem(AK,String(n));renderEntries();renderBoard();renderPortfolio();renderHolidays();renderPlanner();renderSim()}
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
  var hl=holidayLegsFor(team);
  toast(team+' → Entry '+n+(wk?' (week '+wk+')':'')+
        (hl.length?' — note: plays the '+hl.map(function(l){return l.name;}).join(' & '):''));
  renderEntries();renderBoard();renderPortfolio();renderHolidays();renderPlanner();renderSim();
}
function dropTeam(team,n){
  var e=entries();e[n]=e[n].filter(function(p){return p.t!==team});saveEntries(e);
  renderEntries();renderBoard();renderPortfolio();renderHolidays();renderPlanner();renderSim();
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
  renderBoard();renderPortfolio();renderPlanner();renderSim();}

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
async function load(){
  var url=PREVIEW?'/data/survivor?season=2025&start_week=6&weeks=8':'/data/survivor?weeks=18';
  try{DATA=await (await fetch(url)).json();}catch(e){DATA={weeks:[]};}
  WEEKS=(DATA.weeks||[]).filter(function(w){return w.games&&w.games.length;});
  indexHol(DATA.weeks);
  curIdx=0;
  renderAll();
  // holiday legs are weeks 12 & 16 — usually outside the 8-week board window, so
  // pull those weeks' win probs on their own (fills in once the market posts them).
  if(!PREVIEW){[12,16].forEach(function(wk){
    fetch('/data/survivor?start_week='+wk+'&weeks=1'+(DATA.season?'&season='+DATA.season:''))
      .then(function(r){return r.json();}).then(function(d){indexHol(d.weeks);renderHolidays();})
      .catch(function(){});
  });}
}
function renderAll(){renderEntries();renderBoard();renderPortfolio();renderHolidays();renderPlanner();renderSim();}

function renderHolidays(){
  var act=active(), used=usedBy(act), el=document.getElementById('holidays'), h='';
  function chip(t){
    var spent=used.indexOf(t)>=0;
    var dbl=holidayLegsFor(t).length>1?'<span class="dbl" title="plays BOTH holiday legs">★</span>':'';
    return '<span class="hteam'+(spent?' spent':'')+'" style="background:'+tcol(t)+'">'+t+dbl+'</span>';
  }
  HOLIDAY_LEGS.forEach(function(leg){
    var teams=teamsInLeg(leg);
    var avail=teams.filter(function(t){return used.indexOf(t)<0;}).length;
    var warn=avail<=2;
    var rows=leg.games.map(function(g){          // g = [away, home]
      var wp=HOLWP[g[0]+'@'+g[1]];
      var aw=wp?Math.round(wp.aw*100):null, hw=wp?Math.round(wp.hw*100):null;
      var favA=(aw!=null&&hw!=null&&aw>hw), favH=(aw!=null&&hw!=null&&hw>=aw);
      function pct(v,fav){return '<i class="hwp'+(fav?' fav':'')+'">'+(v!=null?v+'%':'—')+'</i>';}
      return '<div class="hgame">'+
        '<div class="hrow">'+chip(g[0])+pct(aw,favA)+'</div>'+
        '<div class="hat">@</div>'+
        '<div class="hrow">'+chip(g[1])+pct(hw,favH)+'</div></div>';
    }).join('');
    h+='<div class="hleg"><div class="htop"><span class="hname">'+leg.emoji+' '+leg.name+'</span>'+
       '<span class="hwhen">'+leg.when+'</span>'+
       '<span class="havail" style="color:'+(warn?'var(--down)':'var(--up)')+'">'+avail+' of '+teams.length+
       ' still open · E'+act+'</span></div><div class="hgames">'+rows+'</div></div>';
  });
  el.innerHTML=h+'<p class="subnote" style="margin-top:.4rem">Each box is a game (away @ home) — only these '+
    'teams are pickable on the leg. ★ = plays BOTH legs. Struck-through = already used by Entry '+act+'.</p>';
}

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
/* ---------- future value ----------
   futureMap() above finds a team's single best week ahead, which misses the
   team that is favoured in eight straight weeks without ever being a standout.
   This is SurvivorGrid's definition instead: sum (wp - 0.5) over EVERY
   remaining game the team is favoured in. Higher = more useful later = more
   reason not to burn it now. Only counts weeks the market has actually priced,
   so it grows as lines post. */
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
function fvWeeksAhead(afterWeek){
  return WEEKS.filter(function(w){return w.week>afterWeek;}).length;
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
  var wkNo=w.week;
  var FV=futureValue(w.week), STARS=fvStars(FV), FVW=fvWeeksAhead(w.week);
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
    if(!used&&STARS[p.team]>=4&&FVW>0)
      flags+='<span class="flag fv" title="favoured in '+FVW+' priced week'+(FVW===1?'':'s')+
        ' ahead — total future value '+FV[p.team].toFixed(2)+', a top band. Using it now spends all of that.">'+
        '★'.repeat(STARS[p.team])+'☆'.repeat(5-STARS[p.team])+' future value</span>';
    if(!used&&p.wp>=0.62&&pops[i]<=8)flags+='<span class="flag contra">lower-owned · leverage</span>';
    if(!used&&LEAN>0&&p.wp>=0.5)
      flags+=p.home?('<span class="flag home">home lean +'+(LEAN*100).toFixed(1)+'%</span>')
                   :('<span class="flag road">road −'+(LEAN*100).toFixed(1)+'%</span>');
    var hl=holidayLegsFor(p.team);
    if(!used&&hl.length)flags+='<span class="flag hol" title="only teams playing that day are pickable on the leg — think twice before using this early">'+
      hl.map(function(l){return l.emoji;}).join('')+' holiday-leg team</span>';
    var pop=pops[i];
    h+='<div class="pick'+(used?' used':'')+((!used&&hl.length)?' holiday':'')+'">'+
       '<div class="rank">'+(i+1)+'</div>'+
       '<div class="matchup"><div class="mteam"><span class="tchip" style="background:'+tcol(p.team)+
       '">'+p.team+'</span><b>'+p.team+'</b><span class="vs">'+(p.home?'vs':'@')+' '+p.opp+'</span></div>'+
       (flags?'<div class="flags">'+flags+'</div>':'')+
       '<div class="pop">est. popularity <span class="popbar"><i style="width:'+Math.max(3,pop)+'%"></i></span> ~'+pop+'%</div>'+
       '</div>'+
       '<div class="right"><div class="wp '+t[1]+'"><b>'+Math.round(p.wp*100)+'%</b><i class="tier">'+t[0]+'</i></div>'+
       '<div class="usebtns" style="grid-template-columns:repeat('+useCols()+',1fr)">'+
       aliveIds().map(function(n){
         var u=usedBy(n).indexOf(p.team)>=0;
         /* already spent this week on someone else -- locked until that pick is removed */
         var lk=!u&&pickForWeek(n,wkNo);
         var ttl=u?('already used by entry '+n):
                 lk?('entry '+n+' already has '+lk.t+' for week '+wkNo+' — remove it to switch'):
                    ('use '+p.team+' on entry '+n);
         return '<button '+(u||lk?'disabled':'')+' title="'+ttl+'"'+
           ' onclick="useTeam(\\''+p.team+'\\','+n+')">'+(u?'E'+n+' ✓':'Use E'+n)+'</button>';}).join('')+
       '</div></div></div>';
  });
  el.innerHTML=h+'</div>';
}

function renderPortfolio(){
  var el=document.getElementById('portfolio');
  if(!WEEKS.length){el.innerHTML='<div class="empty">Portfolio suggestion appears once lines post.</div>';return;}
  var w=WEEKS[curIdx], teams=weekTeams(w);
  if(!teams.length){el.innerHTML='<div class="empty">No games to allocate this week.</div>';return;}
  if(!aliveIds().length){el.innerHTML='<div class="empty">Every entry is marked out — nothing left to split.</div>';return;}
  /* entries that already made this week's pick are settled -- the split is for
     the ones still to choose, so it never suggests a second team for a week */
  var settled=aliveIds().filter(function(n){return !!pickForWeek(n,w.week);});
  var ids=aliveIds().filter(function(n){return settled.indexOf(n)<0;}), N=ids.length;
  var settledCards=settled.map(function(n){var p=pickForWeek(n,w.week);
    return '<div class="alloc done"><div class="ehead">Entry '+n+'</div>'+
      '<div class="apick"><span class="tchip" style="background:'+tcol(p.t)+'">'+p.t+
      '</span><b>'+p.t+'</b> <span class="awp">picked</span></div></div>';}).join('');
  if(!N){el.innerHTML='<div class="callout"><h3>Week '+w.week+' is set</h3>'+
    '<div class="allocs">'+settledCards+'</div>'+
    '<p class="why">Every live entry already has a pick for this week. Remove one with '+
    'the ✕ on its chip if you want to change it.</p></div>';return;}

  /* ---- how many entries go on each team ------------------------------
     Real multi-entry play STACKS: several entries on the safest board, a
     few on the next, tapering down -- not one big block and then a long
     tail of singletons. Weight each candidate by how far its win% sits
     above a coin flip, then hand out entries by largest remainder.
     Two hard rules:
       - no team may take more than half the entries, so one upset can
         never wipe the portfolio;
       - only teams that are actually plausible get weight.            */
  var pool=teams.filter(function(p){return p.wp>=0.60;});
  if(pool.length<2)pool=teams.slice(0,Math.max(2,Math.min(3,teams.length)));
  pool=pool.slice(0,Math.max(1,Math.min(pool.length,N)));

  var cap=Math.max(1,Math.floor(N/2));
  var wts=pool.map(function(p){return Math.max(0.01,p.wp-0.5);});
  var tot=wts.reduce(function(a,b){return a+b;},0);
  var raw=wts.map(function(x){return x/tot*N;});
  var counts=raw.map(function(x){return Math.min(cap,Math.floor(x));});
  var left=N-counts.reduce(function(a,b){return a+b;},0);
  /* largest-remainder pass, respecting the cap */
  var order=raw.map(function(x,i){return [x-Math.floor(x),i];})
               .sort(function(a,b){return b[0]-a[0];});
  var gi=0;
  while(left>0){
    var i=order[gi%order.length][1];
    if(counts[i]<cap){counts[i]++;left--;}
    else if(order.every(function(o){return counts[o[1]]>=cap;})){
      /* every candidate is capped -- widen the pool rather than break a rule */
      var extra=teams.filter(function(p){return pool.indexOf(p)<0;})[0];
      if(!extra)break;
      pool.push(extra);counts.push(0);order.push([0,counts.length-1]);
    }
    gi++;
    if(gi>500)break;
  }

  /* ---- assign those blocks to actual entries -------------------------
     An entry cannot reuse a team it has already burned, so this is a
     matching problem, not a straight slice.                            */
  var picks={}, unassigned=ids.slice();
  pool.forEach(function(p,i){
    var need=counts[i];
    for(var k=0;k<unassigned.length&&need>0;k++){
      var n=unassigned[k];
      if(usedBy(n).indexOf(p.team)>=0)continue;
      picks[n]=p;unassigned.splice(k,1);k--;need--;
    }
  });
  unassigned.forEach(function(n){          /* fallback for burned-out entries */
    for(var i=0;i<teams.length;i++){
      if(usedBy(n).indexOf(teams[i].team)<0){picks[n]=teams[i];return;}
    }
    picks[n]=null;
  });

  /* ---- explain the shape --------------------------------------------- */
  var byTeam={};
  ids.forEach(function(n){if(picks[n]){byTeam[picks[n].team]=(byTeam[picks[n].team]||0)+1;}});
  var blocks=Object.keys(byTeam).map(function(t){
      var p=teams.filter(function(x){return x.team===t;})[0];
      return {team:t,n:byTeam[t],wp:p?p.wp:null};})
    .sort(function(a,b){return b.n-a.n;});
  var weakest=null;
  ids.forEach(function(n){if(picks[n]&&(!weakest||picks[n].wp<weakest.wp))weakest=picks[n];});

  var why;
  if(N===1){
    why='One entry, so this is simply the strongest team still available to you.';
  }else{
    why=blocks.map(function(b){
      return b.n+(b.n===1?' entry on ':' entries on ')+b.team+
             (b.wp!=null?' ('+Math.round(b.wp*100)+'%)':'');}).join(', ')+'. ';
    why+='Entries are stacked on the safer boards and tapered down, which is how '+
         'multi-entry play actually works — but no team takes more than half your '+
         'entries, so a single upset cannot wipe the portfolio.';
  }
  if(weakest&&weakest.wp<0.6){
    why+=' Note: with '+N+' entries you are forced down to '+weakest.team+' at '+
         Math.round(weakest.wp*100)+'% — that is a real risk of losing an entry, '+
         'not a recommendation to like it.';
  }

  var cards=ids.map(function(n){var p=picks[n];
    return '<div class="alloc"><div class="ehead">Entry '+n+'</div>'+
      (p?'<div class="apick"><span class="tchip" style="background:'+tcol(p.team)+'">'+p.team+
        '</span><b>'+p.team+'</b> <span class="awp">'+Math.round(p.wp*100)+'%</span></div>':
        '<div class="apick" style="color:var(--dim)">No team left — plan ahead</div>')+'</div>';}).join('');
  el.innerHTML='<div class="callout"><h3>Suggested Week '+w.week+' split'+
    (N<entryIds().length?' — '+N+(N===1?' entry still to pick':' entries still to pick'):'')+'</h3>'+
    '<div class="allocs">'+settledCards+cards+'</div><p class="why">'+why+'</p></div>';
}

function renderPlanner(){
  var el=document.getElementById('planner');
  if(!WEEKS.length){el.innerHTML='<div class="empty" style="border:none">No schedule loaded.</div>';return;}
  var h='<table class="plan"><tr><th>Week</th><th>Top available survival picks</th></tr>';
  // Eight weeks keeps this readable. The simulator below reasons over all of them.
  WEEKS.slice(0,8).forEach(function(w){
    var teams=weekTeams(w).filter(function(p){return !usedAny(p.team)||true;}).slice(0,6);
    var cells=teams.slice(0,5).map(function(p){var spent=usedAny(p.team);
      return '<span class="ptop'+(spent?' spent':'')+'"><span class="tchip" style="background:'+tcol(p.team)+
        ';min-width:2rem;height:1.4rem;font-size:.64rem">'+p.team+'</span>'+
        '<span class="pwp">'+Math.round(p.wp*100)+'%</span></span>';}).join('');
    h+='<tr><td class="wk">Wk '+w.week+'</td><td>'+(cells||'<span style="color:var(--dim)">lines pending</span>')+'</td></tr>';
  });
  el.innerHTML=h+'</table>';
}


/* ================= SCENARIO SIMULATOR =================
   Plays the rest of the season out many times and counts how often at least one
   of your entries is still standing.

   WHY SIMULATE AT ALL. For a single entry you do not need to: survival is just
   the win probabilities multiplied together. It earns its keep on several
   entries, where the question is not "does this entry live" but "does ANY of
   them live", and that depends on how the entries overlap.

   A CIRCA SEASON IS 20 LEGS, NOT 18 WEEKS. Weeks 1-18, plus a Thanksgiving and
   a Christmas leg drawn from those days' games. Each leg needs its own team you
   have never used, so weeks 12 and 16 ask you for two different teams: one from
   the holiday games and one from the rest of that week. That is the whole
   squeeze -- 20 teams out of 32, and two of them have to come from small pools.

   WHAT THE POLICY DOES. Each leg it takes the best team still legal to it,
   except that teams it is holding for a holiday leg are off limits until that
   leg arrives. That is deliberately a simple rule. It is not meant to be the
   best strategy available; it is meant to be a consistent one, so that when you
   compare two of your own choices the difference you see comes from the choice
   and not from the policy wandering.

   READ THE ORDERING, NOT THE NUMBER. Backtesting 2025 showed our win
   probabilities run about 11 points optimistic in the 60-70 band, so a
   percentage here is not to be trusted at face value and is never shown to
   decimals. Which option beats which is far more robust than by how much. */

var TIE_RATE=0.0035;      /* NFL ties run about 1 game in 285, and a tie ends a
                             Circa entry outright. Small per leg, not small
                             across twenty of them. */
var SIM_SEASONS=10000, SIM_COMPARE=1500, RESERVE=true;

/* Seeded so the same board always gives the same answer -- if a number moves,
   it moved because you changed something, not because the dice rolled again. */
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;
  var t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;
  return ((t^t>>>14)>>>0)/4294967296;};}

function gamePair(p){return p.home?[p.opp,p.team]:[p.team,p.opp];}
function legIndexFor(wk){return wk===12?0:(wk===16?1:-1);}
function isLegGame(wk,p){
  var i=legIndexFor(wk);if(i<0)return false;
  var pr=gamePair(p),gs=HOLIDAY_LEGS[i].games;
  for(var k=0;k<gs.length;k++){if(gs[k][0]===pr[0]&&gs[k][1]===pr[1])return true;}
  return false;
}
/* Split each week into its legs. The holiday game is played before the rest of
   that week, so it goes first. */
function buildLegs(){
  var legs=[];
  WEEKS.forEach(function(w){
    var all=weekTeams(w),li=legIndexFor(w.week);
    if(li<0){legs.push({id:'W'+w.week,label:'Week '+w.week,hol:-1,teams:all});return;}
    var hol=[],rest=[];
    all.forEach(function(p){(isLegGame(w.week,p)?hol:rest).push(p);});
    if(hol.length)legs.push({id:'H'+li,hol:li,teams:hol,
      label:HOLIDAY_LEGS[li].emoji+' '+HOLIDAY_LEGS[li].name});
    if(rest.length)legs.push({id:'W'+w.week,label:'Week '+w.week,hol:-1,teams:rest});
  });
  return legs;
}
/* Which team to hold for which holiday leg. Scarcest leg picks first: Christmas
   offers eight teams to Thanksgiving's ten, so it gets first refusal, otherwise
   a team good at both gets spent on the easier one. */
function reservationsFor(legs,used){
  var res={},taken={},hol=[];
  legs.forEach(function(L){if(L.hol>=0)hol.push(L);});
  hol.sort(function(a,b){return a.teams.length-b.teams.length;});
  hol.forEach(function(L){
    for(var i=0;i<L.teams.length;i++){
      var t=L.teams[i].team;
      if(used[t]||taken[t])continue;
      res[t]=L.id;taken[t]=1;return;
    }
  });
  return res;
}
/* One entry, one season. Returns the leg index it died at, or -1 if it ran the
   table. Dying "for lack of a legal team" is a real Circa outcome and is
   counted as death, not skipped. */
function runEntry(legs,used,res,rnd,forceTeam,rec){
  var u={},k,i,j,p;
  for(k in used)u[k]=1;
  for(i=0;i<legs.length;i++){
    var L=legs[i],pick=null;
    if(i===0&&forceTeam){
      for(j=0;j<L.teams.length;j++){if(L.teams[j].team===forceTeam){pick=L.teams[j];break;}}
    }
    if(!pick){for(j=0;j<L.teams.length;j++){
      p=L.teams[j];
      if(u[p.team])continue;
      if(res[p.team]&&res[p.team]!==L.id)continue;
      pick=p;break;}}
    if(!pick){for(j=0;j<L.teams.length;j++){p=L.teams[j];if(!u[p.team]){pick=p;break;}}}
    if(!pick)return i;
    /* Reaching a holiday leg with a good team left is the entire point of
       holding one back, so record what we actually field there. Recorded
       before the coin flip: fielding it and winning with it are different
       questions and only the first one is about reservation. */
    if(rec&&L.hol>=0){rec.n[L.hol]++;rec.sum[L.hol]+=pick.wp;}
    u[pick.team]=1;
    if(rnd()>=pick.wp*(1-TIE_RATE))return i;
  }
  return -1;
}
function simulate(n,reserve,forceTeam,forceEntry){
  var legs=buildLegs();
  if(!legs.length)return null;
  var ids=aliveIds();
  if(!ids.length)return null;
  var pre=ids.map(function(id){
    var u={};usedBy(id).forEach(function(t){u[t]=1;});
    return {id:id,used:u,res:reserve?reservationsFor(legs,u):{}};
  });
  var alive=[],i;
  for(i=0;i<legs.length;i++)alive.push(0);
  var rnd=mulberry32(2026),reachSum=0;
  var rec={n:[0,0],sum:[0,0]};
  for(var s=0;s<n;s++){
    var best=-1;
    for(var e=0;e<pre.length;e++){
      var ft=(forceTeam&&pre[e].id===forceEntry)?forceTeam:null;
      var d=runEntry(legs,pre[e].used,pre[e].res,rnd,ft,rec);
      var reach=(d<0)?legs.length:d;
      if(reach>best)best=reach;
    }
    for(i=0;i<legs.length;i++){if(best>i)alive[i]++;}
    reachSum+=best;
  }
  /* Mean win probability of the team fielded at each holiday leg, over the
     entries that got there. This is the number reservation actually moves --
     unconditional survival barely budges, because most seasons are over before
     Thanksgiving, and quoting that would say holdbacks do not matter when what
     it really says is that you probably will not get to find out. */
  var fielded=[rec.n[0]?rec.sum[0]/rec.n[0]:null, rec.n[1]?rec.sum[1]/rec.n[1]:null];
  return {legs:legs,alive:alive,n:n,avgReach:reachSum/n,entries:pre.length,
          fielded:fielded,reached:rec.n};
}
function legIdx(legs,id){for(var i=0;i<legs.length;i++){if(legs[i].id===id)return i;}return -1;}
/* Rounded to whole points on purpose -- our probabilities are not accurate
   enough to justify a decimal. But a real chance must never round to a flat 0%:
   running the table is genuinely rare, and "0%" reads as impossible when the
   honest answer is "unlikely". */
function pc(x){
  if(x>0&&x<0.005)return '<1%';
  if(x<1&&x>0.995)return '>99%';
  return Math.round(x*100)+'%';
}

function toggleReserve(){
  RESERVE=!RESERVE;
  var b=document.getElementById('simReserve');
  b.className=RESERVE?'on':'';
  b.textContent=RESERVE?'Holding holiday teams back':'Spending freely, no holdbacks';
  renderSim();
}

function renderSim(){
  var cards=document.getElementById('simcards'),curve=document.getElementById('simcurve'),
      cmp=document.getElementById('simcompare'),hold=document.getElementById('simhold'),
      st=document.getElementById('simstatus');
  if(!WEEKS.length||!aliveIds().length){
    cards.innerHTML='<div class="empty" style="grid-column:1/-1">Nothing to simulate yet.</div>';
    curve.innerHTML='';cmp.innerHTML='';hold.innerHTML='';st.textContent='';return;
  }
  var t0=(window.performance&&performance.now)?performance.now():0;
  var r=simulate(SIM_SEASONS,RESERVE,null,null);
  if(!r){cards.innerHTML='';curve.innerHTML='';cmp.innerHTML='';hold.innerHTML='';return;}
  var legs=r.legs,last=legs.length-1;
  var iT=legIdx(legs,'H0'),iX=legIdx(legs,'H1');
  var other=simulate(2500,!RESERVE,null,null);

  /* headline numbers */
  var cardsH='';
  function card(lab,val,sub,warn){
    return '<div class="simcard'+(warn?' warn':'')+'"><div class="sclab">'+lab+'</div>'+
      '<div class="scval">'+val+'</div><div class="scsub">'+sub+'</div></div>';
  }
  function fld(i){return r.fielded[i]==null?'no entry gets there':
    'you field a '+Math.round(r.fielded[i]*100)+'% team there';}
  cardsH+=card('Any entry reaches Thanksgiving',iT>=0?pc(r.alive[iT-1>=0?iT-1:0]/r.n):'--',
    iT>=0?fld(0):'not in range');
  cardsH+=card('Any entry reaches Christmas',iX>=0?pc(r.alive[iX-1>=0?iX-1:0]/r.n):'--',
    iX>=0?fld(1):'not in range',true);
  cardsH+=card('Any entry runs the table',pc(r.alive[last]/r.n),
    r.entries+(r.entries===1?' entry':' entries')+', all '+legs.length+' legs');
  cardsH+=card('Typical furthest entry','leg '+Math.round(r.avgReach),
    'of '+legs.length+' -- most seasons end early');
  cards.innerHTML=cardsH;

  /* Compare holdbacks on the team you FIELD at the holiday legs, not on whether
     you survive to them. Survival barely moves either way because most seasons
     are over by November, and reporting that would say holdbacks are pointless
     when what it really says is you probably will not get to find out. */
  var dx=(other&&r.fielded[1]!=null&&other.fielded[1]!=null)
    ?(r.fielded[1]-other.fielded[1]):null;
  st.textContent=(dx===null)?'':
    (RESERVE?'Holding back leaves you ':'Holding back would leave you ')+
    (dx>=0?'+':'')+Math.round(dx*100)+' points better at Christmas'+
    (dx<0?' -- it is costing you here':'')+'.';

  /* survival curve */
  var ch='<div class="curve"><table>';
  legs.forEach(function(L,i){
    var v=r.alive[i]/r.n;
    ch+='<tr class="'+(L.hol>=0?'hol':'')+'"><td class="cl">'+L.label+'</td>'+
        '<td><span class="bar" style="width:'+Math.max(1,v*100)+'%"></span></td>'+
        '<td class="cv">'+pc(v)+'</td></tr>';
  });
  curve.innerHTML=ch+'</table></div>';

  /* this leg's options, each re-simulated */
  var act=active(),usedAct={};usedBy(act).forEach(function(t){usedAct[t]=1;});
  var L0=legs[0];
  var cands=L0.teams.filter(function(p){return !usedAct[p.team];}).slice(0,8);
  var rows=cands.map(function(p){
    var sr=simulate(SIM_COMPARE,RESERVE,p.team,act);
    return {team:p.team,opp:p.opp,home:p.home,wp:p.wp,src:p.src,
            f0:sr?sr.fielded[0]:null,f1:sr?sr.fielded[1]:null};
  });
  /* Best this leg first. The holiday columns are the cost of taking it. */
  rows.sort(function(a,b){return b.wp-a.wp;});
  var base={f0:r.fielded[0],f1:r.fielded[1]};
  var th='<table class="cmp"><tr><th>Pick now (entry '+act+')</th><th>This leg</th>'+
         '<th>Left for &#127860;</th><th>Left for &#127876;</th></tr>';
  function costCell(v,ref){
    if(v==null)return '<td class="n">--</td>';
    var d=(ref==null)?0:(v-ref),s=Math.round(d*100);
    return '<td class="n">'+Math.round(v*100)+'%'+
      (s<0?' <span class="delta dn">'+s+'</span>':'')+'</td>';
  }
  rows.forEach(function(o,i){
    var hl=holidayLegsFor(o.team);
    var mark=hl.length?' <span title="plays a holiday leg">'+
      hl.map(function(l){return l.emoji;}).join('')+'</span>':'';
    var free=(o.f0==null||base.f0==null||o.f0>=base.f0-0.005)&&
             (o.f1==null||base.f1==null||o.f1>=base.f1-0.005);
    th+='<tr class="'+(i===0&&free?'best':'')+'"><td>'+
      '<span class="tchip" style="background:'+tcol(o.team)+
      ';min-width:2.2rem;height:1.3rem;font-size:.62rem">'+o.team+'</span> '+
      (o.home?'vs ':'at ')+o.opp+mark+'</td>'+
      '<td class="n">'+Math.round(o.wp*100)+'%</td>'+
      costCell(o.f0,base.f0)+costCell(o.f1,base.f1)+'</tr>';
  });
  cmp.innerHTML=(rows.length?th+'</table>':'<div class="empty">No legal team left for this entry.</div>');

  /* what the policy is holding, and why */
  var res=reservationsFor(legs,usedAct),chips='';
  Object.keys(res).forEach(function(t){
    var L=legs[legIdx(legs,res[t])];
    var me=null;L.teams.forEach(function(p){if(p.team===t)me=p;});
    chips+='<span class="holdchip" style="background:'+tcol(t)+'">'+t+
      ' <small>'+(L.hol===0?'Thanksgiving':'Christmas')+
      (me?' '+Math.round(me.wp*100)+'%':'')+'</small></span>';
  });
  var t1=(window.performance&&performance.now)?performance.now():0;
  hold.innerHTML='<h3 style="font-size:.95rem;margin:1rem 0 .3rem">Do not spend these'+
    ' (entry '+act+')</h3><div class="holdlist">'+
    (chips||'<span class="simnote">Nothing left to hold -- both holiday pools are spent.</span>')+
    '</div><div class="simwarn">Percentages are rounded hard on purpose. Against real 2025'+
    ' results our win probabilities ran about 11 points optimistic in the 60-70 band, so'+
    ' treat these as a ranking of your options rather than a forecast. Weeks the market has'+
    ' not priced yet use an estimate, and firm up as lines post.'+
    (t0?' Ran '+(SIM_SEASONS/1000)+'k seasons in '+Math.round(t1-t0)+' ms.':'')+'</div>';
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
