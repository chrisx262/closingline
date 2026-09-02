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
      mkt:priced(all)});return;}
    var hol=[],rest=[];
    all.forEach(function(p){(isLegGame(w.week,p)?hol:rest).push(p);});
    if(hol.length)legs.push({id:'H'+li,hol:li,teams:hol,mkt:priced(hol),
      label:HOLIDAY_LEGS[li].emoji+' '+HOLIDAY_LEGS[li].name});
    if(rest.length)legs.push({id:'W'+w.week,label:'Week '+w.week,hol:-1,teams:rest,
      mkt:priced(rest)});
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


function renderAll(){renderEntries();renderLegTitle();renderSim();}

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
