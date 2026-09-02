"""Scenario Simulator page — imported by app.py, served at /survivor/sim.

Split out of survivor_page because the helper had grown past the point of being
usable: thirty-odd board rows sat between the button you pressed and the number
it moved, so you could not watch a value change while causing it to change.

This page is therefore SELF-CONTAINED for picking. The comparison table carries
its own Use buttons and a pinned bar follows you down the page, so a plan can be
tried and abandoned without ever leaving. Entries are shared with /survivor
through localStorage — a pick on either page shows up on the other.

What it models, and the reasoning behind each choice, is documented at the top
of the SCENARIO SIMULATOR block in the JavaScript below. The short version: a
Circa season is 20 legs rather than 18 weeks, the metric that matters is the
team you FIELD at each holiday leg rather than whether you survive to it, and
the ordering of options is trustworthy while the percentages are not.
"""

from survivor_core import shell

SURVIVOR_SIM_HTML = shell(
    title="ClosingLine — Survivor Scenario Simulator (Circa 2026)",
    description=("Season simulator for Circa Survivor: plays the remaining legs ten "
                 "thousand times across your entries, shows what a pick costs you at "
                 "the Thanksgiving and Christmas legs, and tracks how many holiday "
                 "options you have left. Decision support, not betting advice."),
    nav_active="/survivor/sim",
    head_extra="""<style>
.bpwrap{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:.85rem 1rem;box-shadow:var(--shadow);overflow-x:auto}
.bphead{display:flex;flex-wrap:wrap;gap:1.4rem;padding-bottom:.7rem;margin-bottom:.5rem;
  border-bottom:1px solid var(--line)}
.bphead span{white-space:nowrap}
.bphead i{display:block;color:var(--dim);font-size:.58rem;font-style:normal;font-weight:900;
  letter-spacing:.06em;text-transform:uppercase}
.bphead b{font-size:1.15rem;font-weight:900}
table.bp{border-collapse:collapse;width:100%;min-width:360px}
table.bp th{text-align:left;font-size:.6rem;letter-spacing:.06em;text-transform:uppercase;
  color:var(--dim);padding:.3rem .4rem;border-bottom:1px solid var(--line)}
table.bp td{padding:.3rem .4rem;border-bottom:1px solid var(--line);font-size:.74rem;
  font-weight:700}
table.bp td.n{text-align:right;font-variant-numeric:tabular-nums}
table.bp td.bl{color:var(--dim);white-space:nowrap}
table.bp tr.hol td.bl{color:var(--down);font-weight:900}
table.bp td.gd{color:var(--down);font-weight:800;font-size:.68rem}
table.bp td.gd .same{color:var(--dim);font-weight:700}
.bphead small{display:block;color:var(--dim);font-size:.58rem;font-weight:700}
table.bp.pp td.pc{text-align:center;padding:.22rem .25rem}
table.bp.pp th.me,table.bp.pp td.me{background:color-mix(in srgb,var(--save) 14%,transparent)}
table.bp.pp th{text-align:center}
.bpstart{margin-bottom:.9rem}
.bpslab{color:var(--dim);font-size:.6rem;font-weight:900;letter-spacing:.06em;
  text-transform:uppercase;margin-bottom:.35rem}
table.bp tr.sel td{background:color-mix(in srgb,var(--save) 12%,transparent)}
table.bp .same{color:var(--up);font-weight:900}
table.bp .delta.dn{color:var(--down);font-weight:800}
.usebtn{font:inherit;font-weight:800;font-size:.62rem;padding:.22rem .6rem;
  border-radius:999px;border:1px solid var(--line);background:var(--panel);
  color:var(--ink);cursor:pointer;white-space:nowrap}
.usebtn:hover{background:var(--ink);color:var(--panel);border-color:var(--ink)}
</style>
""",
    body_html="""
<div class="hero">
  <h1>Scenario <em>Simulator</em></h1>
  <p>Plays the rest of the season out ten thousand times on your actual entries, so you
  can try a plan and back out of it. Pick straight from the table below and every number
  on the page rebuilds. <b>Read the ordering, not the number</b> &mdash; which option beats
  which is far sturdier than by how much.</p>
  <div class="facts">
    <div class="fact"><b>20</b> legs, not 18 weeks</div>
    <div class="fact warn">Tie = OUT</div>
    <div class="fact"><b>10</b> teams play &#127860;</div>
    <div class="fact"><b>8</b> teams play &#127876;</div>
    <div class="fact"><b>6</b> play both</div>
  </div>
</div>

<section>
  <h2>Your <em>Entries</em> <span class="alivecount" id="alivecount"></span></h2>
  <p class="subnote">The same entries as the <a href="/survivor">weekly helper</a> &mdash;
  a pick made on either page shows on the other. Tap an entry to make it active.</p>
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
    <button onclick="stepWeek(-1)">&lsaquo; Prev</button>
    <span class="wtitle" id="wtitle">Week &mdash;</span>
    <button onclick="stepWeek(1)">Next &rsaquo;</button>
    <span class="src" id="wsrc"></span>
  </div>
  <div id="simentry"></div>
  <h3 style="font-size:.95rem;margin:.2rem 0 .5rem">If you pick this now, what happens later?</h3>
  <p class="subnote" style="margin-top:0">Each option re-runs the whole season with that team
  spent here. The two middle columns are the team you would still have for each holiday leg
  &mdash; a red number is what this pick costs you there. Most picks cost nothing; the ones
  that do are the decision.</p>
  <div id="simcompare"></div>
  <div id="simhold"></div>
</section>

<section>
  <h2>Best possible <em>path</em></h2>
  <p class="subnote">The single best way to spend your remaining teams across every leg,
  solved exactly rather than simulated &mdash; the simulator's greedy rule takes the best
  team available each week, which can burn a team that was the only good option in
  November. <b>This is not a script to follow.</b> Over half these legs are still
  estimates and one injury voids any fixed plan. Read it for the one thing a single week
  cannot tell you: which week the schedule actually wants each team for.</p>
  <div id="bestpath"></div>
</section>

<section>
  <h2>Ten paths, <em>not one</em></h2>
  <p class="subnote">Entries that pick the same team share the same result &mdash; if it
  loses, they all die together, so ten copies of the best plan are worth about one entry.
  These paths are solved one after another, each charged for every team it would share
  with an entry already placed. Most entries end up on worse teams on purpose; the point
  is not that each survives, it is that <b>one of them</b> does. Your active entry's
  column is highlighted.</p>
  <div id="portpaths"></div>
</section>

<section>
  <h2>Across <em>all entries</em></h2>
  <p class="subnote">Whether <b>any</b> of your entries is still standing. With several
  entries that is the question that matters, and it is not the same as any one of them
  surviving.</p>
  <div class="simctl">
    <button id="simReserve" class="on" onclick="toggleReserve()">Holding holiday teams back</button>
    <span class="simnote" id="simstatus"></span>
  </div>
  <div class="simcards" id="simcards"></div>
  <div id="simcurve"></div>
</section>

<p class="footnote">
<b>What to trust here:</b> win probability comes from the de-vigged market moneyline where
a book has posted one, and from a power rating fitted to this season's real spreads where
none exists yet. Estimated legs are marked. Against real 2025 results these probabilities
ran about <b>11 points optimistic in the 60&ndash;70% band</b>, so percentages are rounded
hard and are a ranking, not a forecast. This is decision support, not a prediction &mdash;
ties eliminate you and no pick is ever safe.
<div class="rg"><span>21+.</span> Informational only, not financial or betting advice.
If gambling is a problem, call <span>1-800-GAMBLER</span>.</div>
</p>
""",
    page_js="""/* ================= SCENARIO SIMULATOR =================
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
/* previous pinned-bar values, so a changed number can flash, and the pick that
   caused it, so the bar can say what that pick cost -- including when it cost
   nothing, which is the common case and otherwise looks like a broken tool */
var LASTBAR=null, LASTPICK=null;

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
    /* Where each leg's numbers come from. A market line already prices today's
       injuries; a prior cannot, because it is fitted to lines posted before the
       news. Callers must be able to tell them apart. */
    function priced(list){
      var m=0;list.forEach(function(p){if(p.src==='ml'||p.src==='spread')m++;});
      return list.length?m/list.length:0;
    }
    if(li<0){legs.push({id:'W'+w.week,label:'Week '+w.week,hol:-1,teams:all,
      week:w.week,mkt:priced(all)});return;}
    var hol=[],rest=[];
    all.forEach(function(p){(isLegGame(w.week,p)?hol:rest).push(p);});
    if(hol.length)legs.push({id:'H'+li,hol:li,teams:hol,mkt:priced(hol),week:w.week,
      label:HOLIDAY_LEGS[li].emoji+' '+HOLIDAY_LEGS[li].name});
    if(rest.length)legs.push({id:'W'+w.week,label:'Week '+w.week,hol:-1,teams:rest,
      week:w.week,mkt:priced(rest)});
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
function runEntry(legs,used,res,rnd,forceTeam,rec,out){
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
    /* ONE GAME, ONE RESULT. Entries that pick the same team in the same leg
       must live or die together -- that shared fate is the entire risk a
       multi-entry portfolio is built to manage, and drawing separately for each
       entry quietly deletes it. The 2025 backtest is the cautionary tale: a
       field lost 32.6% of its entries in week 3 alone, on one Green Bay
       result. */
    var key=i+':'+pick.team, won;
    if(out&&key in out){won=out[key];}
    else{won=rnd()<pick.wp*(1-TIE_RATE);if(out)out[key]=won;}
    if(!won)return i;
  }
  return -1;
}
function simulate(n,reserve,forceTeam,forceEntry,onlyId,omitTeam){
  var legs=buildLegs();
  if(!legs.length)return null;
  var ids=aliveIds();
  /* Restricting to one entry is what makes a single pick visible. Across ten
     entries any one choice is lost in the aggregate, which reads as the tool
     ignoring you. */
  if(onlyId)ids=ids.filter(function(x){return x===onlyId;});
  if(!ids.length)return null;
  var pre=ids.map(function(id){
    var u={};
    usedBy(id).forEach(function(t){
      /* omitTeam re-runs an entry as if it had never spent that team, which is
         how the exact cost of the pick just made is measured -- rather than
         diffing against whatever happened to be on screen before. */
      if(omitTeam&&id===onlyId&&t===omitTeam)return;
      u[t]=1;
    });
    return {id:id,used:u,res:reserve?reservationsFor(legs,u):{}};
  });
  var alive=[],i;
  for(i=0;i<legs.length;i++)alive.push(0);
  var rnd=mulberry32(2026),reachSum=0;
  var rec={n:[0,0],sum:[0,0]};
  for(var s=0;s<n;s++){
    var best=-1, out={};   /* this season's game results, shared by every entry */
    for(var e=0;e<pre.length;e++){
      var ft=(forceTeam&&pre[e].id===forceEntry)?forceTeam:null;
      var d=runEntry(legs,pre[e].used,pre[e].res,rnd,ft,rec,out);
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
  /* HTML entities, not '<' and '>'. These strings go into innerHTML, and a
     literal '<1%' is parsed as the start of a tag and silently swallowed --
     which showed a blank where the rarest and most interesting numbers go. */
  if(x>0&&x<0.005)return '&lt;1%';
  if(x<1&&x>0.995)return '&gt;99%';
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
    curve.innerHTML='';cmp.innerHTML='';hold.innerHTML='';st.textContent='';
    document.getElementById('simentry').innerHTML='';
    document.getElementById('livebar').hidden=true;LASTBAR=null;LASTPICK=null;return;
  }
  var t0=(window.performance&&performance.now)?performance.now():0;
  var r=simulate(SIM_SEASONS,RESERVE,null,null);
  if(!r){cards.innerHTML='';curve.innerHTML='';cmp.innerHTML='';hold.innerHTML='';return;}
  var legs=r.legs,last=legs.length-1;
  var iT=legIdx(legs,'H0'),iX=legIdx(legs,'H1');
  var other=simulate(2500,!RESERVE,null,null);

  /* THE ACTIVE ENTRY, ON ITS OWN.
     Everything below this is a "do any of my entries survive" number, and with
     ten entries a single pick cannot move one. That made the tool look inert
     after a click. These numbers are for the one entry you are actually
     picking for, so using a team visibly changes them. */
  var actId=active();
  var me=simulate(SIM_SEASONS,RESERVE,null,null,actId);
  var spent=usedBy(actId);
  /* HOW MANY HOLIDAY TEAMS ARE LEFT, not just the best one.
     The policy holds a single team per leg, so on its own arithmetic burning a
     worse holiday team is free. That is only true if the held team's number
     never moves. Both holiday legs ARE priced by the real market -- all nine
     games -- so those numbers are not guesses. But a line posted in September
     for a game in December is an early line, and it moves on every injury and
     three months of form. Lose Philadelphia's quarterback in November and the
     team you held is a dog while the fallbacks are gone. Depth in an
     eight-team pool is worth something, so it gets counted and shown. */
  function legDepth(i){
    var all=teamsInLeg(HOLIDAY_LEGS[i]),n=0;
    all.forEach(function(t){if(spent.indexOf(t)<0)n++;});
    return {left:n,of:all.length};
  }
  var depth=[legDepth(0),legDepth(1)];
  var iTm=iT,iXm=iX;
  var chips=spent.map(function(t){
    return '<span class="holdchip" style="background:'+tcol(t)+'">'+t+'</span>';}).join('');
  var meH='<div class="entrypanel"><div class="eptop"><b>Entry '+actId+'</b>'+
    '<span class="epsub">'+spent.length+' of '+legs.length+' legs spent &middot; '+
    (32-spent.length)+' teams still available</span></div>';
  meH+='<div class="epspent">'+(chips?'Spent: '+chips:
    '<span class="epsub">Nothing spent yet &mdash; use a team on the board above.</span>')+'</div>';
  if(me){
    function em(i){return me.fielded[i]==null?'&mdash;':Math.round(me.fielded[i]*100)+'%';}
    function legsrc(i){
      var L=(i===0)?(iTm>=0?legs[iTm]:null):(iXm>=0?legs[iXm]:null);
      return (L&&L.mkt>=0.5)?'real line':'estimate';
    }
    meH+='<div class="epstats">'+
      '<span><i>reaches &#127860;</i> '+(iTm>0?pc(me.alive[iTm-1]/me.n):'--')+
        ' <small>with a '+em(0)+' team &middot; '+legsrc(0)+'</small></span>'+
      '<span><i>reaches &#127876;</i> '+(iXm>0?pc(me.alive[iXm-1]/me.n):'--')+
        ' <small>with a '+em(1)+' team &middot; '+legsrc(1)+'</small></span>'+
      '<span><i>&#127860; options left</i> '+depth[0].left+' <small>of '+depth[0].of+'</small></span>'+
      '<span><i>&#127876; options left</i> '+depth[1].left+' <small>of '+depth[1].of+'</small></span>'+
      '<span><i>runs the table</i> '+pc(me.alive[legs.length-1]/me.n)+'</span>'+
      '<span><i>typical exit</i> leg '+Math.round(me.avgReach)+'</span></div>';
  }
  document.getElementById('simentry').innerHTML=meH+'</div>';

  /* The pinned bar. The board is 30-odd rows long, so the panel above is off
     screen by the time you are clicking a team -- you cannot see a number move
     while you are causing it to move. This follows you down the page and
     flashes whatever changed. */
  var bar=document.getElementById('livebar');
  if(me){
    var now={sp:spent.length,
             t:iTm>0?Math.round(me.alive[iTm-1]/me.n*100):null,
             x:iXm>0?Math.round(me.alive[iXm-1]/me.n*100):null,
             ft:me.fielded[0]==null?null:Math.round(me.fielded[0]*100),
             fx:me.fielded[1]==null?null:Math.round(me.fielded[1]*100),
             dt:depth[0].left,dx:depth[1].left};
    var prev=(LASTBAR&&LASTBAR[actId])||{};
    function fl(k,html){
      return '<span class="lbstat'+(prev[k]!=null&&prev[k]!==now[k]?' bump':'')+'">'+html+'</span>';
    }
    var lb='<span class="lbwho">Entry '+actId+'<small>'+now.sp+' of '+legs.length+
      ' legs spent</small></span>';
    lb+=fl('ft','<i>&#127860; you would field</i><b>'+(now.ft==null?'--':now.ft+'%')+'</b>');
    lb+=fl('fx','<i>&#127876; you would field</i><b>'+(now.fx==null?'--':now.fx+'%')+'</b>');
    lb+=fl('dt','<i>&#127860; left</i><b>'+depth[0].left+'/'+depth[0].of+'</b>');
    lb+=fl('dx','<i>&#127876; left</i><b>'+depth[1].left+'/'+depth[1].of+'</b>');
    /* Say what the last pick cost. A holiday-leg team you were not holding
       costs nothing, and silence about that is indistinguishable from a bug. */
    var verdict='';
    if(LASTPICK&&LASTPICK.n===actId&&spent.indexOf(LASTPICK.t)>=0){
      var wo=simulate(SIM_SEASONS,RESERVE,null,null,actId,LASTPICK.t);
      if(wo){
        var wt=wo.fielded[0]==null?null:Math.round(wo.fielded[0]*100);
        var wx=wo.fielded[1]==null?null:Math.round(wo.fielded[1]*100);
        var bits=[];
        if(wt!=null&&now.ft!=null&&now.ft<wt)
          bits.push('&#127860; '+wt+'% &rarr; '+now.ft+'%');
        if(wx!=null&&now.fx!=null&&now.fx<wx)
          bits.push('&#127876; '+wx+'% &rarr; '+now.fx+'%');
        /* A team can cost nothing today and still cost you depth, which is the
           thing the single-team reservation cannot see. Say both. */
        var legsOf=holidayLegsFor(LASTPICK.t);
        if(bits.length){
          verdict='<span class="lbcost bad">'+LASTPICK.t+' cost you '+bits.join(', ')+'</span>';
        }else if(legsOf.length){
          var d=legsOf.map(function(l){
            var i=(l===HOLIDAY_LEGS[0])?0:1;
            return l.emoji+' '+depth[i].left+' left of '+depth[i].of;}).join(', ');
          verdict='<span class="lbcost warn">'+LASTPICK.t+' does not change who you field'+
            ', but it was a holiday team &mdash; '+d+'</span>';
        }else{
          verdict='<span class="lbcost ok">'+LASTPICK.t+' costs you nothing at either holiday leg</span>';
        }
      }
    }
    lb+=verdict||('<span class="lbspent">'+(spent.length?'spent: '+spent.join(' &middot; '):
      'nothing spent yet')+'</span>');
    bar.innerHTML=lb;
    bar.hidden=false;
    if(!LASTBAR)LASTBAR={};
    LASTBAR[actId]=now;
  }else{bar.hidden=true;LASTBAR=null;}

  /* headline numbers, across every entry you still have alive */
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
  cards.innerHTML='<div class="simcaption">Across all '+r.entries+
    (r.entries===1?' entry':' entries')+'</div>'+cardsH;

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
  var est=0;
  legs.forEach(function(L){if(L.mkt<0.5)est++;});
  var ch='<div class="curve"><div class="csrc">'+
    (est?('<b>'+est+' of '+legs.length+'</b> legs are still priced by estimate, marked '+
          '<i class="estdot">est</i> below. Those cannot know about an injury &mdash; '+
          'they are fitted to lines posted before the news. They firm up as books '+
          'post them.')
        :'Every leg is priced by a real market line.')+
    ' Both holiday legs are real lines.</div><table>';
  legs.forEach(function(L,i){
    var v=r.alive[i]/r.n;
    ch+='<tr class="'+(L.hol>=0?'hol':'')+'"><td class="cl">'+L.label+
        (L.mkt<0.5?' <i class="estdot">est</i>':'')+'</td>'+
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
         '<th>Left for &#127860;</th><th>Left for &#127876;</th><th></th></tr>';
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
      costCell(o.f0,base.f0)+costCell(o.f1,base.f1)+
      '<td class="n"><button class="usebtn" onclick="useTeam(&#39;'+o.team+'&#39;,'+
        act+')">Use</button></td>'+'</tr>';
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


function renderAll(){renderEntries();renderLegTitle();renderSim();renderBestPath();renderPortfolio2();}
function renderPortfolio2(){
  var el=document.getElementById('portpaths');
  if(!el)return;
  var ids=aliveIds();
  if(!WEEKS.length||!ids.length){el.innerHTML='';return;}
  if(ids.length<2){
    el.innerHTML='<div class="empty">With one entry there is nothing to spread. '+
      'Add entries above and this shows how they should differ.</div>';return;}
  var legs=buildLegs();
  var port=portfolioPaths(legs,ids);
  var one=bestPath(legs,usedBy(ids[0]),null,null,null,settledFor(ids[0],legs));
  var same=ids.map(function(id){return {id:id,path:one};});
  var A=simulatePaths(same,6000), B=simulatePaths(port,6000);
  var iT=legIdx(legs,'H0'), iX=legIdx(legs,'H1');
  function pct(r,i){return (i>0&&r.alive[i-1]!=null)?pc(r.alive[i-1]/r.n):'--';}
  var act=active();
  var h='<div class="bpwrap"><div class="bphead">'+
    '<span><i>any of the '+ids.length+' reaches &#127860;</i><b>'+pct(B,iT)+'</b>'+
      '<small>all on one plan: '+pct(A,iT)+'</small></span>'+
    '<span><i>any reaches &#127876;</i><b>'+pct(B,iX)+'</b>'+
      '<small>all on one plan: '+pct(A,iX)+'</small></span>'+
    '<span><i>any runs the table</i><b>'+(B.all*100).toFixed(2)+'%</b>'+
      '<small>all on one plan: '+(A.all*100).toFixed(2)+'%</small></span></div>';
  h+='<table class="bp pp"><tr><th>Leg</th>'+
     ids.map(function(id){return '<th class="'+(id===act?'me':'')+'">E'+id+'</th>';}).join('')+
     '</tr>';
  legs.forEach(function(L,i){
    h+='<tr class="'+(L.hol>=0?'hol':'')+'"><td class="bl">'+L.label+
       (L.mkt<0.5?' <i class="estdot">est</i>':'')+'</td>';
    port.forEach(function(p){
      var r=p.path&&p.path.rows?p.path.rows[i]:null;
      var t=r&&r.team;
      h+='<td class="pc '+(p.id===act?'me':'')+'">'+(t?
        '<span class="tchip" style="background:'+tcol(t)+
        ';min-width:2.1rem;height:1.2rem;font-size:.58rem" title="'+
        (r.home?'vs ':'at ')+r.opp+' &middot; '+Math.round(r.wp*100)+'%">'+t+'</span>'
        :'<span style="color:var(--down)">&mdash;</span>')+'</td>';
    });
    h+='</tr>';
  });
  el.innerHTML=h+'</table></div>';
}

/* ================= BEST POSSIBLE PATH =================
   The simulator's policy is greedy: each leg it takes the best team still legal
   to it, minus whatever is being held for a holiday. Greedy is not optimal and
   is not close to it. Spending a 78% team in week 3 can cost you the only team
   that was any good in week 14, and no amount of looking one leg ahead sees it.

   Assigning 20 legs from 32 teams, each team used at most once, maximising the
   chance of surviving all of them, is an assignment problem. Maximising a
   product of win probabilities is the same as maximising the sum of their logs,
   so it is a plain max-weight bipartite matching and the Hungarian algorithm
   solves it exactly in well under a millisecond at this size. No simulation
   required -- and no simulation could match it, because sampling cannot search
   a space this shape.

   READ THIS FOR WHAT IT IS. It is the best path THROUGH TODAY'S NUMBERS, and
   more than half of those numbers are estimates for weeks nobody has priced.
   It is not a script to follow -- a quarterback injury in November voids any
   fixed 20-week plan, which is the whole reason the tool's real output is a
   hold-back list re-run weekly. What it IS good for is the question you cannot
   answer by staring at one week: which weeks does the schedule actually want
   each team for. If the optimum spends Buffalo in week 11, that is a real
   argument against spending Buffalo in week 3, and greedy will never tell you.
*/
var BIG=1000;   /* stands in for "this team does not play this leg" */

function hungarian(cost,n,m){
  /* Standard O(n^3) Kuhn-Munkres with potentials. Rows are legs, columns are
     teams, n <= m. Returns assign[i] = column matched to row i, 1-indexed. */
  var INF=Infinity;
  var u=new Array(n+1).fill(0), v=new Array(m+1).fill(0);
  var p=new Array(m+1).fill(0), way=new Array(m+1).fill(0);
  for(var i=1;i<=n;i++){
    p[0]=i;
    var j0=0;
    var minv=new Array(m+1).fill(INF), used=new Array(m+1).fill(false);
    do{
      used[j0]=true;
      var i0=p[j0], delta=INF, j1=-1;
      for(var j=1;j<=m;j++){
        if(used[j])continue;
        var cur=cost[i0][j]-u[i0]-v[j];
        if(cur<minv[j]){minv[j]=cur;way[j]=j0;}
        if(minv[j]<delta){delta=minv[j];j1=j;}
      }
      for(var j2=0;j2<=m;j2++){
        if(used[j2]){u[p[j2]]+=delta;v[j2]-=delta;}
        else minv[j2]-=delta;
      }
      j0=j1;
    }while(p[j0]!==0);
    do{var j3=way[j0];p[j0]=p[j3];j0=j3;}while(j0);
  }
  var assign=new Array(n+1).fill(0);
  for(var j4=1;j4<=m;j4++)if(p[j4])assign[p[j4]]=j4;
  return assign;
}

/* Best assignment of remaining teams to remaining legs for ONE entry. */
/* Legs this entry has already decided, as legIndex -> team. A pick is stored as
   {t:team, w:week}, and weeks 12 and 16 hold two legs each, so the team itself
   settles which one: if it plays the holiday game that week the pick belongs to
   the holiday leg, otherwise to the ordinary one. */
function settledFor(id,legs){
  var out={};
  picksOf(id).forEach(function(p){
    if(!p.w)return;
    for(var i=0;i<legs.length;i++){
      var L=legs[i];
      if(L.id!=='W'+p.w&&!(L.hol>=0&&L.week===p.w))continue;
      var here=false;
      L.teams.forEach(function(x){if(x.team===p.t)here=true;});
      if(here){out[i]=p.t;break;}
    }
  });
  return out;
}

function bestPath(legs,usedList,forceFirst,taken,penalty,settled){
  var used={};(usedList||[]).forEach(function(t){used[t]=1;});
  /* A leg you have already picked is not a decision any more. Re-optimising it
     produced a path that silently disagreed with the pick the owner had just
     made, which is the opposite of a tool that tracks the season. */
  settled=settled||{};
  var openLegs=[],map=[];
  legs.forEach(function(L,i){if(settled[i]==null){openLegs.push(L);map.push(i);}});
  /* every team that could still be played somewhere ahead */
  var teams=[],seen={};
  openLegs.forEach(function(L){L.teams.forEach(function(p){
    if(used[p.team]||seen[p.team])return;seen[p.team]=1;teams.push(p.team);});});
  var n=openLegs.length,m=teams.length;
  if(!n){   /* nothing left to decide */
    var only=legs.map(function(L,i){
      var t=settled[i],pk=null;
      L.teams.forEach(function(x){if(x.team===t)pk=x;});
      return {leg:L,team:t||null,wp:pk?pk.wp:null,opp:pk?pk.opp:null,
              home:pk?pk.home:false,settled:true};});
    return {rows:only,survive:1,feasible:true};
  }
  if(!n||m<n)return null;         /* cannot field a legal team for every leg */
  var idx={};teams.forEach(function(t,k){idx[t]=k+1;});
  var cost=[];
  for(var i=0;i<=n;i++){cost.push(new Array(m+1).fill(BIG));}
  openLegs.forEach(function(L,i){
    L.teams.forEach(function(p){
      var j=idx[p.team];
      if(!j)return;
      var wp=Math.min(0.999,Math.max(0.001,p.wp));
      /* `taken` counts how many other entries already hold this team in this
         leg. Charging for a collision is what pulls a portfolio apart: two
         entries on one team share one result, so the second copy buys no
         protection at all. */
      var clash=(taken&&taken[map[i]+':'+p.team])||0;
      cost[i+1][j]=-Math.log(wp)+clash*(penalty||0);
    });
  });
  /* Pin the first leg to a chosen team and let the solver find the best
     continuation from there. That is the difference between "what is the best
     path" and "what is the best path if I start with Jacksonville", and only
     the second one is a decision you can actually take this week. */
  if(forceFirst){
    if(!idx[forceFirst])return null;
    for(var jf=1;jf<=m;jf++){if(teams[jf-1]!==forceFirst)cost[1][jf]=BIG;}
  }
  var assign=hungarian(cost,n,m);
  var byLeg={},logsum=0,ok=true;
  for(var i2=1;i2<=n;i2++){
    var j=assign[i2],L=openLegs[i2-1],gi=map[i2-1];
    if(!j||cost[i2][j]>=BIG){byLeg[gi]={leg:L,team:null,wp:null};ok=false;continue;}
    var team=teams[j-1],pick=null;
    L.teams.forEach(function(p){if(p.team===team)pick=p;});
    logsum+=-Math.log(Math.min(0.999,Math.max(0.001,pick?pick.wp:0.5)));
    byLeg[gi]={leg:L,team:team,wp:pick?pick.wp:null,opp:pick?pick.opp:null,
               home:pick?pick.home:false};
  }
  var out=legs.map(function(L,i){
    if(settled[i]!=null){
      var t=settled[i],pk=null;
      L.teams.forEach(function(x){if(x.team===t)pk=x;});
      return {leg:L,team:t,wp:pk?pk.wp:null,opp:pk?pk.opp:null,
              home:pk?pk.home:false,settled:true};
    }
    return byLeg[i]||{leg:L,team:null,wp:null};
  });
  /* Survival is over the legs STILL TO PLAY. A leg already picked has either
     been won or the entry is out, so folding its probability back in would
     charge the owner twice for a game he has already survived. */
  return {rows:out,survive:ok?Math.exp(-logsum)*Math.pow(1-TIE_RATE,n):0,
          feasible:ok,open:n};
}

/* The greedy policy's path, worked out exactly rather than sampled.
   Which teams greedy takes is deterministic -- the randomness in the simulator
   only decides WHEN it dies, not what it would have picked. So its true
   survival probability is just the product along that fixed sequence, and
   comparing it to the optimum is then exact-against-exact. Comparing against a
   Monte Carlo estimate is useless here: surviving all twenty legs happens about
   twice in a thousand seasons, so at any sample size we can afford the noise is
   larger than the effect. */
function greedyPath(legs,usedList,settled){
  var u={};(usedList||[]).forEach(function(t){u[t]=1;});
  settled=settled||{};
  var res=RESERVE?reservationsFor(legs,u):{};
  var rows=[],logsum=0,ok=true,open=0;
  for(var i=0;i<legs.length;i++){
    var L=legs[i],pick=null,j,p;
    if(settled[i]!=null){
      var st=settled[i],sp=null;
      L.teams.forEach(function(x){if(x.team===st)sp=x;});
      rows.push({leg:L,team:st,wp:sp?sp.wp:null,opp:sp?sp.opp:null,
                 home:sp?sp.home:false,settled:true});
      continue;
    }
    open++;
    for(j=0;j<L.teams.length;j++){
      p=L.teams[j];
      if(u[p.team])continue;
      if(res[p.team]&&res[p.team]!==L.id)continue;
      pick=p;break;
    }
    if(!pick){for(j=0;j<L.teams.length;j++){p=L.teams[j];if(!u[p.team]){pick=p;break;}}}
    if(!pick){rows.push({leg:L,team:null,wp:null});ok=false;continue;}
    u[pick.team]=1;
    logsum+=-Math.log(Math.min(0.999,Math.max(0.001,pick.wp)));
    rows.push({leg:L,team:pick.team,wp:pick.wp,opp:pick.opp,home:pick.home});
  }
  return {rows:rows,survive:ok?Math.exp(-logsum)*Math.pow(1-TIE_RATE,open):0,
          feasible:ok,open:open};
}

var BPSTART=null;   /* team pinned to the first remaining leg, or null */
function setBpStart(t){BPSTART=(t===BPSTART||t==='')?null:t;renderBestPath();}


/* ================= PORTFOLIO OF PATHS =================
   Ten entries running the same plan are worth one entry. They pick the same
   team, that team loses, and all ten die on the same afternoon -- the simulator
   now models exactly that, because entries picking the same team in the same
   leg share the one result.

   So the portfolio's job is not to maximise each entry. Each entry maximised
   alone gives you ten copies of the same path. It is to maximise the chance
   that AT LEAST ONE is still alive, which means deliberately putting entries on
   different teams and accepting that most of them are then on worse teams.

   The exact joint optimum is not separable and not worth chasing. Solving the
   entries in turn, each one charged for every collision with the entries
   already placed, is the standard practical answer and it is explainable, which
   matters more here than the last fraction of a percent. */
var CLASH=0.35;   /* cost of doubling up, in log-probability. Roughly the price
                     of dropping from a 78% team to a 55% one. */

function portfolioPaths(legs,ids){
  var taken={},out=[];
  ids.forEach(function(id){
    var r=bestPath(legs,usedBy(id),null,taken,CLASH,settledFor(id,legs));
    out.push({id:id,path:r});
    if(r&&r.rows)r.rows.forEach(function(row,i){
      if(row.team)taken[i+':'+row.team]=(taken[i+':'+row.team]||0)+1;});
  });
  return out;
}

/* Play a set of prescribed paths, sharing one result per game per season, and
   report how often at least one entry is still standing. This is the only
   honest way to score a portfolio: the whole effect being measured is the
   correlation between entries, so it cannot be computed entry by entry. */
function simulatePaths(paths,n){
  var alive=null,rnd=mulberry32(7),survivors=0;
  for(var s=0;s<n;s++){
    var out={},best=-1;
    for(var e=0;e<paths.length;e++){
      var rows=paths[e]&&paths[e].path?paths[e].path.rows:null;
      if(!rows)continue;
      if(!alive)alive=new Array(rows.length).fill(0);
      var died=-1;
      for(var i=0;i<rows.length;i++){
        var r=rows[i];
        if(!r.team){died=i;break;}
        var key=i+':'+r.team,won;
        if(key in out)won=out[key];
        else{won=rnd()<Math.min(0.999,r.wp)*(1-TIE_RATE);out[key]=won;}
        if(!won){died=i;break;}
      }
      var reach=(died<0)?rows.length:died;
      if(reach>best)best=reach;
    }
    if(alive)for(var k=0;k<alive.length;k++){if(best>k)alive[k]++;}
    if(alive&&best>=alive.length)survivors++;
  }
  return {alive:alive||[],n:n,all:survivors/n};
}

function renderBestPath(){
  var el=document.getElementById('bestpath');
  if(!el)return;
  if(!WEEKS.length||!aliveIds().length){el.innerHTML='';return;}
  var legs=buildLegs(),act=active();
  var settled=settledFor(act,legs);
  var free=bestPath(legs,usedBy(act),null,null,null,settled);
  var firstOpen=null;
  for(var fi=0;fi<legs.length;fi++){if(settled[fi]==null){firstOpen=legs[fi];break;}}
  /* Every team you could open with, each followed by ITS best continuation.
     Ranked by where you end up, not by this week's win probability -- the
     whole point is that those two orders are not the same. */
  var usedAct={};usedBy(act).forEach(function(t){usedAct[t]=1;});
  var opts=[];
  if(firstOpen)firstOpen.teams.forEach(function(p){
    if(usedAct[p.team])return;
    var r=bestPath(legs,usedBy(act),p.team,null,null,settled);
    if(r&&r.feasible)opts.push({team:p.team,wp:p.wp,opp:p.opp,home:p.home,s:r.survive});
  });
  opts.sort(function(a,b){return b.s-a.s;});
  if(BPSTART&&!opts.some(function(o){return o.team===BPSTART;}))BPSTART=null;
  var top=opts.length?opts[0].s:0;
  var startH='';
  if(opts.length){
    startH='<div class="bpstart"><div class="bpslab">Open with &mdash; ranked by where the '+
      'whole season ends up, not by this week</div><table class="bp"><tr><th>Team</th>'+
      '<th>This leg</th><th>Best path from there</th><th>vs best</th><th></th></tr>';
    opts.slice(0,10).forEach(function(o,i){
      var d=o.s-top, sel=(BPSTART===o.team)||(!BPSTART&&i===0);
      startH+='<tr class="'+(sel?'sel':'')+'"><td>'+
        '<span class="tchip" style="background:'+tcol(o.team)+
        ';min-width:2.2rem;height:1.3rem;font-size:.62rem">'+o.team+'</span> '+
        (o.home?'vs ':'at ')+o.opp+'</td>'+
        '<td class="n">'+Math.round(o.wp*100)+'%</td>'+
        '<td class="n">'+(o.s*100).toFixed(3)+'%</td>'+
        '<td class="n">'+(i===0?'<span class="same">best</span>':
          '<span class="delta dn">'+(d/top*100).toFixed(0)+'%</span>')+'</td>'+
        '<td class="n"><button class="usebtn" onclick="setBpStart(&#39;'+o.team+'&#39;)">'+
        (BPSTART===o.team?'clear':'show')+'</button></td></tr>';
    });
    startH+='</table></div>';
  }
  var bp=BPSTART?bestPath(legs,usedBy(act),BPSTART,null,null,settled):free;
  if(!bp){el.innerHTML='<div class="empty">Not enough unused teams left to fill every '+
    'remaining leg &mdash; this entry cannot legally finish the season.</div>';return;}
  /* exact against exact -- see greedyPath */
  var gp=greedyPath(legs,usedBy(act),settled);
  var gs=gp?gp.survive:0;
  var gmap={};if(gp)gp.rows.forEach(function(r,i){gmap[i]=r.team;});
  var est=0;bp.rows.forEach(function(r){if(r.leg.mkt<0.5)est++;});
  var h='<div class="bpwrap">'+startH+'<div class="bphead">'+
    '<span><i>'+(BPSTART?('path if you open with '+BPSTART):'best path')+
      ' survives all '+legs.length+'</i><b>'+(bp.survive*100).toFixed(3)+'%</b></span>'+
    '<span><i>greedy policy manages</i><b>'+pc(gs)+'</b></span>'+
    '<span><i>legs still estimated</i><b>'+est+' of '+legs.length+'</b></span></div>';
  h+='<table class="bp"><tr><th>Leg</th><th>Take</th><th>Win%</th>'+
     '<th>Greedy would take</th></tr>';
  bp.rows.forEach(function(r,i){
    var hl=r.team?holidayLegsFor(r.team):[];
    h+='<tr class="'+(r.leg.hol>=0?'hol':'')+'"><td class="bl">'+r.leg.label+
       (r.leg.mkt<0.5?' <i class="estdot">est</i>':'')+'</td><td>'+
       (r.team?('<span class="tchip" style="background:'+tcol(r.team)+
         ';min-width:2.2rem;height:1.3rem;font-size:.62rem">'+r.team+'</span> '+
         (r.home?'vs ':'at ')+r.opp+
         (hl.length>1?' <span class="dbl" title="plays both holiday legs">&#9733;</span>':''))
        :'<span style="color:var(--down)">no legal team</span>')+
       '</td><td class="n">'+(r.wp==null?'&mdash;':Math.round(r.wp*100)+'%')+'</td>'+
       '<td class="gd">'+((gmap[i]&&gmap[i]!==r.team)?gmap[i]:'<span class="same">same</span>')+
       '</td></tr>';
  });
  el.innerHTML=h+'</table></div>';
}


/* The leg you are deciding, mirrored from the shared week cursor. */
function renderLegTitle(){
  var t=document.getElementById('wtitle');
  if(!t)return;
  if(!WEEKS.length){t.textContent='Week —';return;}
  var w=WEEKS[curIdx];
  t.textContent='Week '+w.week;
  var real=0;(w.games||[]).forEach(function(g){
    if(g.wp_source==='ml'||g.wp_source==='spread')real++;});
  var s=document.getElementById('wsrc');
  if(s)s.textContent=real===(w.games||[]).length?'real market lines'
    :(real?real+' of '+w.games.length+' priced, rest estimated':'all estimated');
}
""",
    after_wrap='<div class="livebar" id="livebar" hidden></div>\n',
)
