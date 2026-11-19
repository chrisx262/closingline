"""Player props against the 8 worst defenses — served at /props.

Chris's method, tested against real sportsbook lines before any of it went on
the page. Two leads survived (QB attempts unders, RB rushing yards); receivers
did not, and the page says so. Every pick is logged before kickoff and the
record is shown win or lose. Decision support only — RG footer, no hype.
"""

from survivor_core import shell

EXTRA_CSS = """<style>
.pstat{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:.6rem;margin:.8rem 0 1rem}
.pstat .c{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.7rem .85rem;box-shadow:var(--shadow)}
.pstat .lab{color:var(--dim);font-size:.6rem;font-weight:900;letter-spacing:.06em;
  text-transform:uppercase}
.pstat .val{font-size:1.4rem;font-weight:900;line-height:1.15;margin-top:.1rem}
table.pp{width:100%;border-collapse:collapse;margin-bottom:1.2rem}
table.pp th{text-align:left;font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;
  color:var(--dim);padding:.35rem .4rem;border-bottom:1px solid var(--line)}
table.pp td{padding:.34rem .4rem;border-bottom:1px solid var(--line);font-size:.76rem;
  font-weight:700;vertical-align:top}
table.pp td.n{text-align:right;font-variant-numeric:tabular-nums}
.tier{font-size:.6rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase;
  padding:.12rem .4rem;border-radius:4px;white-space:nowrap;border:1px solid var(--line)}
.tier.best{background:var(--up);color:#fff;border-color:var(--up)}
.tier.small{color:var(--up);border-color:var(--up)}
.tier.track{color:var(--dim)}
.res.win{color:var(--up);font-weight:900}.res.loss{color:var(--down);font-weight:900}
.res.pend{color:var(--dim)}
.dgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem;
  margin:.6rem 0 1.2rem}
@media (max-width:640px){.dgrid{grid-template-columns:1fr}}
.dbox{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:.7rem .85rem}
.dbox h3{font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;margin:0 0 .4rem}
.dbox .basis{color:var(--dim);font-size:.64rem;margin-bottom:.4rem}
.chips span{display:inline-block;font-size:.66rem;font-weight:800;padding:.12rem .38rem;
  margin:.1rem .12rem .1rem 0;border:1px solid var(--line);border-radius:4px}
.chips span.both{border-color:var(--up);color:var(--up)}
.lead{border-left:3px solid var(--line);padding:.2rem 0 .2rem .7rem;margin:.5rem 0}
.lead.best{border-color:var(--up)}.lead.no{border-color:var(--down)}
.lead b{font-size:.78rem}.lead p{margin:.15rem 0;font-size:.72rem;color:var(--dim)}
.pscroll{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
.pscroll table.pp{min-width:560px}
.dbox .pscroll table.pp{min-width:400px;margin:0}
.hit{color:var(--up);font-weight:900}.miss{color:var(--down);font-weight:900}
.lean{font-size:.62rem;font-weight:900;color:var(--up)}
.fin{font-size:.6rem;font-weight:800;color:var(--dim)}.fin.ok{color:var(--up)}
.fin.bad,.fin.warn{color:var(--down)}
.pnote{color:var(--dim);font-size:.68rem;line-height:1.6;max-width:72ch}
</style>
"""

CONTENT = """
<div class="hero">
  <h1>Player <em>Props</em></h1>
  <p>QBs facing the 8 worst pass defenses and running backs facing the 8 worst run defenses, projected with a trimmed average (drop each
  group's highest and lowest game) and tested against real sportsbook lines from 2025
  and 2026 before anything went on this page. Two leads survived. Receivers did not.</p>
  <div class="countdown" id="pweek">Loading&hellip;</div>
</div>

<section>
  <div class="pstat" id="pstat"></div>
  <h2>This week's <em>picks</em></h2>
  <div id="ppicks"></div>
  <h2>Projections, floor &amp; <em>ceiling</em></h2>
  <p class="pnote">First look early in the week, updated as injury news lands and confirmed
  90 minutes before kickoff. Proj = our projected yards; line = the sportsbooks' consensus;
  the green note is the lean (yardage overs only). Each QB's passing yards and lead back's rushing
  yards this season (lowest, typical, highest), next to the fewest and most yards that defense
  has allowed. Logged before kickoff; after the game we mark whether he cleared his floor and
  whether he reached his typical number &mdash; the two things we actually bet on. <span id="pzones"></span></p>
  <div class="dgrid" id="pranges"></div>
  <h2>The worst <em>defenses</em></h2>
  <div class="dgrid" id="pdef"></div>
  <h2>Defense <em>form</em></h2>
  <p class="pnote">Season vs the last 3 games, and how each pass rush works (FTN charting):
  blitz rate, yards per attempt when they rush only 4, sacks and hits per dropback, and 20+
  yard completions. Flagged when recent form moves a long way from the season. A defense
  changed by a roster move is measured only since the move.</p>
  <div id="pform"></div>
  <h2>What the <em>testing</em> said</h2>
  <div id="pleads"></div>
  <p class="pnote" id="pnote"></p>
</section>

<p class="footnote">
<b>How picks are logged:</b> each pick is written to a file in the public repository before
kickoff and never edited afterwards, then graded after the game. <b>Final check:</b> 90 minutes
before kickoff, when teams post their inactives, every player is re-checked against the
inactive list and the depth chart: active and starting, OUT (don't bet; graded void), or
backup? (not first on the depth chart &mdash; check the news before betting). Best bet = our strongest
tested lead; small = weaker lead, small stakes; track only = shown for the record, not a bet.
<div class="rg"><span>21+.</span> Informational only, not financial or betting advice.
If gambling is a problem, call <span>1-800-GAMBLER</span>.</div>
</p>
"""

PAGE_JS = """
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(m){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m];});}
var STAT={pass_attempts:'pass attempts',rush_yds:'rushing yds',rec_yds:'receiving yds'};

function recTxt(r){
  if(!r)return '0-0';
  var s=r.wins+'-'+r.losses+(r.pushes?'-'+r.pushes:'');
  return s+(r.pending?' <span style="font-size:.7rem;color:var(--dim)">('+r.pending+' pending)</span>':'');
}

function finTxt(f){
  if(!f)return '<br><span class="fin">final check: pending</span>';
  var c=f.status==='confirmed'?'ok':(f.status==='backup?'?'warn':'bad');
  return '<br><span class="fin '+c+'">'+(f.status==='confirmed'?'&#10003; ':'')+
    esc(f.status==='confirmed'?'active, starting':f.status+' &ndash; '+f.note)+'</span>';
}

function renderProps(d){
  document.getElementById('pweek').innerHTML=
    'Season <b>'+esc(d.season)+'</b> &middot; Week <b>'+esc(d.week)+'</b>'+
    ' &middot; defenses ranked through week '+esc(d.through_week);
  var R=d.record||{};
  document.getElementById('pstat').innerHTML=
    '<div class="c"><div class="lab">Best bets</div><div class="val">'+recTxt(R['BEST BET'])+'</div></div>'+
    '<div class="c"><div class="lab">Small bets</div><div class="val">'+recTxt(R['small'])+'</div></div>'+
    '<div class="c"><div class="lab">All bets</div><div class="val">'+recTxt(R['all bets'])+'</div></div>'+
    '<div class="c"><div class="lab">Track only</div><div class="val">'+recTxt(R['track only'])+'</div></div>';

  var wk=(d.picks||[]).filter(function(p){return String(p.week)===String(d.week);});
  var order={'BEST BET':0,'small':1,'track only':2};
  wk.sort(function(a,b){return order[a.tier]-order[b.tier];});
  var t='<table class="pp"><tr><th>Tier</th><th>Player</th><th>Bet</th><th>Price</th>'+
        '<th>Our number</th><th>Result</th></tr>';
  wk.forEach(function(p){
    var cls=p.tier==='BEST BET'?'best':(p.tier==='small'?'small':'track');
    var res=p.result?('<span class="res '+esc(p.result)+'">'+esc(p.result)+
             (p.actual?' ('+esc(p.actual)+')':'')+'</span>'):'<span class="res pend">pending</span>';
    t+='<tr><td><span class="tier '+cls+'">'+esc(p.tier)+'</span></td>'+
       '<td><b>'+esc(p.player)+'</b><br><span style="color:var(--dim);font-size:.66rem">'+
       esc(p.team)+' vs '+esc(p.opp)+'</span>'+finTxt(p.final)+'</td>'+
       '<td>'+esc(p.side)+' '+esc(p.line)+' '+esc(STAT[p.stat]||p.stat)+'</td>'+
       '<td class="n">'+esc(p.best_price)+'</td>'+
       '<td class="n">'+esc(p.projection)+' <span style="color:var(--dim)">('+esc(p.gap)+')</span></td>'+
       '<td>'+res+'</td></tr>';
  });
  document.getElementById('ppicks').innerHTML=wk.length?'<div class="pscroll">'+t+'</table></div>':
    '<div class="empty">No picks logged for this week yet.</div>';

  var rg=(d.ranges||[]).filter(function(r){return String(r.week)===String(d.week)&&r.zone!=='void';});
  var Z=d.range_zones||{};
  document.getElementById('pzones').innerHTML=Z.graded?
    'So far: <b>'+Z.floor+' of '+Z.graded+'</b> at or above the floor, <b>'+Z.typical+' of '+
    Z.graded+'</b> reached typical.':'';
  var rh='';
  [['ours','Our list'],['eric',"Eric's list"]].forEach(function(L){
    var rs=rg.filter(function(r){return r.list===L[0]||r.list==='both';});
    var t='<table class="pp"><tr><th>Player</th><th class="n">Floor</th><th class="n">Typical</th>'+
          '<th class="n">Ceiling</th><th class="n">Proj</th><th class="n">Line</th>'+
          '<th class="n">D allowed</th><th>Result</th></tr>';
    ['QB','RB'].forEach(function(pos){
      rs.filter(function(r){return r.pos===pos;}).forEach(function(r){
        function mk(ok,lab){return '<span class="'+(ok?'hit':'miss')+'">'+(ok?'&#10003; ':'&#10007; ')+lab+'</span>';}
        var res=r.hit_floor!==null&&r.hit_floor!==undefined?'<b>'+esc(r.actual)+'</b><br>'+
                mk(r.hit_floor,'floor')+' '+mk(r.hit_typical,'typical'):
                '<span class="res pend">pending</span>';
        t+='<tr><td><b>'+esc(r.player)+'</b><br><span style="color:var(--dim);font-size:.66rem">'+
           esc(r.pos)+' &middot; '+esc(r.team)+' vs '+esc(r.opp)+' &middot; '+esc(r.games)+
           (r.games==='1'?' game':' games')+
           (r.fav_by?' &middot; '+(parseFloat(r.fav_by)>0?'fav ':'dog ')+esc(r.fav_by.replace(/^[+-]/,'')):'')+
           (r.status?' &middot; <b>'+esc(r.status)+'</b>':'')+'</span>'+
           (r.lean?'<br><span class="lean">'+esc(r.lean)+'</span>':'')+finTxt(r.final)+'</td>'+
           '<td class="n">'+esc(r.floor)+'</td><td class="n">'+esc(r.typical)+'</td>'+
           '<td class="n">'+esc(r.ceiling)+'</td><td class="n"><b>'+esc(r.proj||'')+'</b></td>'+
           '<td class="n">'+esc(r.line||'')+'</td><td class="n">'+esc(r.def_floor)+'&ndash;'+
           esc(r.def_ceiling)+'</td><td>'+res+'</td></tr>';
      });
    });
    rh+='<div class="dbox"><h3>'+L[1]+'</h3><div class="pscroll">'+t+'</table></div></div>';
  });
  document.getElementById('pranges').innerHTML=rg.length?rh:
    '<div class="empty">No floor / ceiling rows logged for this week yet.</div>';

  var h='';
  ['pass','run'].forEach(function(k){
    var x=(d.defenses||{})[k]; if(!x)return;
    function chips(list,other){return list.map(function(t){
      return '<span class="'+(other.indexOf(t)>=0?'both':'')+'">'+esc(t)+'</span>';}).join('');}
    h+='<div class="dbox"><h3>'+k+' defense &mdash; ours</h3><div class="basis">'+esc(x.ours_basis)+
       '</div><div class="chips">'+chips(x.ours,x.eric)+'</div></div>'+
       '<div class="dbox"><h3>'+k+" defense &mdash; Eric's</h3><div class=\\"basis\\">"+esc(x.eric_basis)+
       '</div><div class="chips">'+chips(x.eric,x.ours)+'</div></div>';
  });
  document.getElementById('pdef').innerHTML=h+
    '<p class="pnote" style="grid-column:1/-1">Worst first. Green = on both lists. Per-game '+
    'numbers punish defenses whose teams are winning (opponents throw late); per-play numbers do not.</p>';

  var DS=d.defense_stats||{}, ft=Object.keys(DS).sort();
  var f='<table class="pp"><tr><th>D</th><th class="n">Yds/att</th><th class="n">Last 3</th>'+
        '<th class="n">Yds/carry</th><th class="n">Last 3</th><th class="n">Blitz</th>'+
        '<th class="n">4-man yds/att</th><th class="n">Sack</th><th class="n">Hit</th>'+
        '<th class="n">20+</th><th>Note</th></tr>';
  function v(x,suf){return x===null||x===undefined?'':esc(x)+(suf||'');}
  ft.forEach(function(t){var x=DS[t];
    f+='<tr><td><b>'+esc(t)+'</b></td><td class="n">'+v(x.ypa)+'</td><td class="n">'+v(x.ypa_last3)+
       '</td><td class="n">'+v(x.ypc)+'</td><td class="n">'+v(x.ypc_last3)+'</td><td class="n">'+
       v(x.blitz,'%')+'</td><td class="n">'+v(x.four_ypa)+'</td><td class="n">'+v(x.sack,'%')+
       '</td><td class="n">'+v(x.hit,'%')+'</td><td class="n">'+v(x.big,'%')+'</td><td>'+
       (x.trend?'<span class="lean">'+esc(x.trend)+'</span> ':'')+
       (x.since?'<span style="color:var(--dim);font-size:.64rem">since wk '+esc(x.since)+': '+esc(x.why)+'</span>':'')+
       '</td></tr>';});
  document.getElementById('pform').innerHTML=ft.length?'<div class="pscroll">'+f+'</table></div>':'';

  document.getElementById('pleads').innerHTML=(d.leads||[]).map(function(l){
    var c=l.status.indexOf('best')===0?'best':(l.status.indexOf('no edge')===0?'no':'');
    return '<div class="lead '+c+'"><b>'+esc(l.name)+'</b> &mdash; <i>'+esc(l.status)+'</i>'+
      '<p>'+esc(l.rule)+'</p><p>Backtest: '+esc(l.backtest)+'</p></div>';
  }).join('');
  document.getElementById('pnote').textContent=d.note||'';
}

function loadProps(){
  fetch('/data/props').then(function(r){return r.json();}).then(renderProps)
    .catch(function(){document.getElementById('ppicks').innerHTML=
      '<div class="empty">Could not load the props board.</div>';});
}
function renderAll(){loadProps();}
loadProps();
"""

PROPS_HTML = shell(
    title="ClosingLine — Player props vs the 8 worst defenses",
    description=("QB, RB and WR props against the league's 8 worst defenses, tested "
                 "against real sportsbook lines, with every pick logged before kickoff."),
    nav_active="/props",
    head_extra=EXTRA_CSS,
    body_html=CONTENT,
    page_js=PAGE_JS,
)
