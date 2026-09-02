"""Survivor Helper page — imported by app.py, served at /survivor.

Circa Survivor is a straight-up (moneyline) contest: pick one team to win each
week, never reuse a team, a loss OR a tie eliminates you. Straight-up win
probability is exactly the signal, and in our own backtests the market beat our
model at picking winners — so this leans on de-vigged market moneyline win
probabilities (served by /data/survivor).

This page is the WEEKLY decision: the ranked board, the portfolio split across
entries, the holiday-leg panel and the multi-week planner. The season simulator
used to live at the bottom of it and now has its own page (survivor_sim_page),
because thirty-odd board rows sat between the buttons and the numbers they
moved. Shared state lives in survivor_core; both pages read the same entries.

Decision support only — see the responsible-gambling footer; the product voice
never says "lock" or "guaranteed."
"""

from survivor_core import shell

SURVIVOR_HTML = shell(
    title="ClosingLine — Survivor Helper (Circa 2026)",
    description=("Circa Survivor pick helper: teams ranked by de-vigged market win "
                 "probability, with future-value flags, an estimated pick-popularity "
                 "read, and used-team tracking across multiple entries. Decision "
                 "support, not betting advice."),
    nav_active="/survivor",
    head_extra="""<style>
.crosslink{border:1px solid var(--line);border-radius:12px;padding:1rem 1.1rem;
  background:var(--panel);box-shadow:var(--shadow)}
.crosslink h2{margin-top:0}
.bigbtn{display:inline-block;font-weight:900;font-size:.8rem;text-decoration:none;
  padding:.55rem 1rem;border-radius:999px;background:var(--ink);color:var(--panel)}
</style>
""",
    body_html="""

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

<section class="crosslink">
  <h2>Planning the <em>whole season</em>?</h2>
  <p class="subnote">The scenario simulator moved to its own page. It plays the rest of
  the season out ten thousand times on your actual entries, shows what a pick costs you
  at the holiday legs, and lets you try a plan and back out of it. It has its own pick
  controls, so you can work entirely from there.</p>
  <p><a class="bigbtn" href="/survivor/sim">Open the Scenario Simulator &rarr;</a></p>
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

<p class="footnote">
<b>How the number is built:</b> win probability comes from the de-vigged market moneyline
(closing/latest snapshot), which beat our own model at picking winners in backtesting —
so the market is the primary signal here. <b>Popularity is an estimate</b> (no field-entry
data yet), shown only as rough contrarian context. This is decision support, not a
prediction — ties eliminate you and no pick is ever safe.
<div class="rg"><span>21+.</span> Informational only, not financial or betting advice.
If gambling is a problem, call <span>1-800-GAMBLER</span>.</div>
</p>
""",
    page_js="""function renderHolidays(){
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
    if(!used&&STARS[p.team]>=4&&FVW.total>0)
      flags+='<span class="flag fv" title="Favoured across '+FVW.total+' week'+(FVW.total===1?'':'s')+
        ' ahead — total future value '+FV[p.team].toFixed(2)+', a top band. Using it now spends all of that. '+
        'Standing on '+FVW.market+' week'+(FVW.market===1?'':'s')+' of real market lines and '+
        FVW.est+' still estimated, so treat the star count as a rough sort, not a measurement.">'+
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



function renderAll(){renderEntries();renderBoard();renderPortfolio();renderHolidays();renderPlanner();}
""",
)
