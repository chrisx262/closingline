/* Brute-force check of the assignment solver used by the best-path panel.
   Random small instances, every permutation enumerated, compared against the
   Hungarian result. A matching algorithm that is subtly wrong still returns
   plausible-looking answers, so this is worth the seconds it costs. */
const fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const start=src.indexOf('var BIG=1000;');
const end=src.indexOf('function greedyPath(');
eval(src.slice(start,end));           // BIG, hungarian, bestPath

function brute(cost,n,m){
  const cols=[...Array(m).keys()].map(x=>x+1);
  let best=Infinity;
  const pick=(i,used,sum)=>{
    if(sum>=best)return;
    if(i>n){best=Math.min(best,sum);return;}
    for(const j of cols){ if(used.has(j))continue;
      used.add(j); pick(i+1,used,sum+cost[i][j]); used.delete(j); }
  };
  pick(1,new Set(),0);
  return best;
}
let bad=0,trials=0;
let seed=42; const rnd=()=>{seed=(seed*1103515245+12345)%2147483648;return seed/2147483648;};
for(let t=0;t<300;t++){
  const n=1+Math.floor(rnd()*5), m=n+Math.floor(rnd()*4);
  const cost=[[]];
  for(let i=1;i<=n;i++){ cost[i]=[0];
    for(let j=1;j<=m;j++) cost[i][j]= rnd()<0.2 ? BIG : Math.round(rnd()*100)/10; }
  const a=hungarian(cost,n,m);
  let got=0; for(let i=1;i<=n;i++) got+=cost[i][a[i]];
  const want=brute(cost,n,m);
  trials++;
  if(Math.abs(got-want)>1e-9){bad++;
    if(bad<3)console.log('  MISMATCH n='+n+' m='+m+' got '+got.toFixed(4)+' want '+want.toFixed(4));}
}
console.log(bad?('HUNGARIAN FAIL '+bad+'/'+trials):('HUNGARIAN OK '+trials+'/'+trials));
process.exit(bad?1:0);
