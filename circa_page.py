"""Circa's own field, week by week — served at /circa.

Circa publishes every entry's pick after the Saturday lock. That is the real
field for the contest the Survivor Helper is built around, as opposed to the
public-pool popularity numbers this project has always refused to use on the
grounds that a $1,000-a-head crowd behaves nothing like a free Yahoo pool.

Parsed from Circa's Selections PDF rather than their summary graphic. The
graphic is not reliable: the Week 1 image omitted the Ravens and the Broncos
because 29 teams plus a NO PICK row fit its three-by-ten layout and 31 did not.

Decision support only — RG footer, no hype, and the source is named on the page
so a reader can check it rather than take our word for it.
"""

from survivor_core import shell

EXTRA_CSS = """<style>
.cstat{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:.6rem;margin:.8rem 0 1rem}
.cstat .c{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.7rem .85rem;box-shadow:var(--shadow)}
.cstat .lab{color:var(--dim);font-size:.6rem;font-weight:900;letter-spacing:.06em;
  text-transform:uppercase}
.cstat .val{font-size:1.5rem;font-weight:900;line-height:1.15;margin-top:.1rem}
.cstat .c.out .val{color:var(--down)}
table.cf{width:100%;border-collapse:collapse}
table.cf th{text-align:left;font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;
  color:var(--dim);padding:.35rem .4rem;border-bottom:1px solid var(--line)}
table.cf td{padding:.32rem .4rem;border-bottom:1px solid var(--line);font-size:.76rem;
  font-weight:700}
table.cf td.n{text-align:right;font-variant-numeric:tabular-nums}
table.cf td.rk{color:var(--dim);width:2rem}
table.cf tr.dead td{color:var(--dim)}
table.cf tr.dead td.team b{text-decoration:line-through}
.res{font-weight:900;font-size:.62rem;letter-spacing:.06em;text-transform:uppercase;
  white-space:nowrap}
.res.won{color:var(--up)}
.res.lost,.res.tie,.res.nopick{color:var(--down)}
.res.pending{color:var(--dim)}
.bar{display:block;height:.5rem;border-radius:3px;background:var(--ink);min-width:1px}
tr.dead .bar{background:var(--down);opacity:.5}
tr.won .bar{background:var(--up)}
.csrc{color:var(--dim);font-size:.68rem;line-height:1.6;margin-top:.8rem;max-width:70ch}
</style>
"""

CONTENT = """
<div class="hero">
  <h1>Circa <em>Field</em></h1>
  <p>What the other twenty-five thousand entries actually did. Circa publishes every
  entry's pick once the Saturday lock passes, so unlike a public pool this is the real
  field for the contest &mdash; the thing worth knowing when you are deciding whether to
  be on the same team as a third of the room.</p>
  <div class="countdown" id="cweek">Loading&hellip;</div>
</div>

<section>
  <div class="cstat" id="cstat"></div>
  <div class="asofbar" id="asof"></div>
  <div id="cfield"></div>
  <p class="csrc" id="csrc"></p>
</section>

<p class="footnote">
<b>Where this comes from:</b> Circa Sports' own weekly Selections PDF, linked from
<span>@CircaSports</span> after picks lock. We parse the document rather than their summary
graphic &mdash; the Week 1 image left two teams off entirely. <b>A tie eliminates in Circa</b>,
so a tie is counted as out. Entries that never submitted a pick are shown as
<b>NO PICK</b>: they paid and were eliminated without playing.
<div class="rg"><span>21+.</span> Informational only, not financial or betting advice.
If gambling is a problem, call <span>1-800-GAMBLER</span>.</div>
</p>
"""

PAGE_JS = """
function pc(x){return (x*100).toFixed(2)+'%';}
function esc(s){return String(s).replace(/[&<>"]/g,function(m){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m];});}

function renderCirca(d){
  var wk=document.getElementById('cweek');
  if(!d.rows||!d.rows.length){
    wk.textContent='No Circa selections loaded yet.';
    document.getElementById('cfield').innerHTML=
      '<div class="empty">Circa posts the week\\u2019s selections after the Saturday '+
      'lock. Nothing loaded for this week yet.</div>';
    return;
  }
  wk.innerHTML='Season <b>'+d.season+'</b> &middot; Week <b>'+d.week+'</b>';
  var LAB={won:'\\u2713 won',lost:'out',tie:'out \\u2014 tie',
           pending:'not played',unknown:'\\u2014','no pick':'out \\u2014 no pick'};
  var top=d.rows[0]?d.rows[0].entries:1;
  var h='<div class="c"><div class="lab">Entries</div><div class="val">'+
        d.entries.toLocaleString()+'</div></div>'+
        '<div class="c"><div class="lab">Still alive</div><div class="val">'+
        d.live.toLocaleString()+'</div></div>'+
        '<div class="c out"><div class="lab">Eliminated</div><div class="val">'+
        d.eliminated.toLocaleString()+'</div></div>';
  document.getElementById('cstat').innerHTML=h;

  var t='<table class="cf"><tr><th></th><th>Team</th><th>Entries</th><th>Share</th>'+
        '<th></th><th>Result</th></tr>';
  d.rows.forEach(function(r,i){
    var cls=r.alive?(r.result==='won'?'won':''):'dead';
    var nop=r.team==='NO_PICK';
    t+='<tr class="'+cls+'">'+
      '<td class="rk">'+(nop?'':(i+1))+'</td>'+
      '<td class="team">'+(nop?'<b>NO PICK</b>':
        ('<span class="tchip" style="background:'+tcol(r.team)+
         ';min-width:2.2rem;height:1.3rem;font-size:.62rem">'+esc(r.team)+
         '</span> <b>'+esc(r.team)+'</b>'))+'</td>'+
      '<td class="n">'+r.entries.toLocaleString()+'</td>'+
      '<td class="n">'+pc(r.share)+'</td>'+
      '<td style="width:34%"><span class="bar" style="width:'+
        Math.max(1,r.entries/top*100)+'%"></span></td>'+
      '<td><span class="res '+(nop?'nopick':r.result.replace(' ',''))+'">'+
        (LAB[r.result]||r.result)+'</span></td></tr>';
  });
  document.getElementById('cfield').innerHTML=t+'</table>';
  document.getElementById('csrc').textContent=d.source||'';
}

function loadCirca(){
  fetch('/data/circa/selections')
    .then(function(r){return r.json();}).then(renderCirca)
    .catch(function(){document.getElementById('cfield').innerHTML=
      '<div class="empty">Could not load the Circa field.</div>';});
}
function renderAll(){loadCirca();}
loadCirca();
"""

CIRCA_HTML = shell(
    title="ClosingLine — Circa Survivor field",
    description=("What Circa Survivor's own 25,000 entries actually picked each week, "
                 "with results, parsed from Circa's published selections."),
    nav_active="/circa",
    head_extra=EXTRA_CSS,
    body_html=CONTENT,
    page_js=PAGE_JS,
)
