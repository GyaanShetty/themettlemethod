/* The Mettle Method — live layer (Supabase). Publishable key only; access is enforced by row-level security. */
(function(){
const URL='https://zcdszmvktizxydwgehsr.supabase.co',KEY='sb_publishable_JehALhvfz9RkH83hvAERvQ_t79YwqbO';
const RANKS=['Unranked','Tiro','Neophytos','Discipulus','Hoplites','Centurio','Praefectus','Strategos','Archon','Sophos'];
const ROMAN=['','I','II','III','IV','V','VI','VII','VIII','IX'];
const page=(location.pathname.split('/').pop()||'index.html').replace('.html','')||'index';
const PUBLIC=['index','about',''];
const sb=window.supabase.createClient(URL,KEY,{auth:{persistSession:true,detectSessionInUrl:true,flowType:'pkce'}});
const today=()=>new Date().toLocaleDateString('en-CA');
const MM=window.MM={sb,user:null,profile:null,standing:null,ready:null};
MM.signIn=()=>sb.auth.signInWithOAuth({provider:'google',options:{redirectTo:location.origin+location.pathname.replace(/[^/]*$/,'')+'home.html'}});
MM.signOut=async()=>{await sb.auth.signOut();try{Object.keys(localStorage).filter(k=>k.startsWith('tmm.')).forEach(k=>localStorage.removeItem(k))}catch(e){};location.href='index.html'};
function swapText(map){const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;const ns=[];while(n=w.nextNode())ns.push(n);
  ns.forEach(t=>{let s=t.nodeValue,o=s;for(const[a,b]of map)s=s.split(a).join(b);if(s!==o)t.nodeValue=s});
  document.querySelectorAll('input[placeholder="Gyaan"]').forEach(i=>i.placeholder=map[0][1]);
  document.querySelectorAll('[aria-label*="Gyaan"]').forEach(e=>e.setAttribute('aria-label',e.getAttribute('aria-label').replace('Gyaan',map[0][1])))}
async function load(){
  const {data:{session}}=await sb.auth.getSession();
  if(!session){if(!PUBLIC.includes(page))location.replace('index.html');return}
  MM.user=session.user;
  const [p,s,d]=await Promise.all([
    sb.from('profiles').select('*').eq('id',MM.user.id).single(),
    sb.from('standings').select('*').eq('user_id',MM.user.id).single(),
    sb.from('days').select('day,oath_at,sealed_at,review').eq('user_id',MM.user.id).order('day',{ascending:false}).limit(60)]);
  MM.profile=p.data;MM.standing=s.data||{days_kept:0,rank:0,flame_lit:false};MM.days=d.data||[];
  if(page==='index'){location.replace('home.html');return}
  const first=(MM.profile&&MM.profile.display_name||'Initiate').split(' ')[0];
  const kept=MM.standing.days_kept,dayNo=kept+(MM.days[0]&&MM.days[0].day===today()&&MM.days[0].sealed_at?0:1);
  const r=MM.standing.rank;
  swapText([['Gyaan',first],['Day 37','Day '+dayNo]]);
  document.querySelectorAll('.av,.h-av').forEach(e=>e.textContent=first[0]||'M');
  const g=document.querySelector('.greet');
  if(g){const h=new Date().getHours();g.textContent=(h<12?'Good morning, ':h<18?'Good afternoon, ':'Good evening, ')+first+'. '+(kept?kept+(kept===1?' day':' days')+' kept. ':'Your first day. ')+(MM.standing.flame_lit||!kept?'Keep the flame lit.':'Your flame has gone out. Light it again today.')}
  document.querySelectorAll('[data-mm=rank]').forEach(e=>e.textContent=r?ROMAN[r]+' · '+RANKS[r]:'Not yet ranked');
  document.querySelectorAll('[data-mm=member]').forEach(e=>e.textContent='No. '+String(MM.profile.member_no).padStart(4,'0'));
  document.querySelectorAll('[data-mm=tier]').forEach(e=>e.textContent=MM.profile.tier==='inner'?'The Inner Order':'The Outer Court');
  // local cache for the page's own state
  const t=MM.days.find(x=>x.day===today());let changed=false;
  try{
    if(t&&t.oath_at&&JSON.parse(localStorage.getItem('tmm.oath'))!==today()){localStorage.setItem('tmm.oath',JSON.stringify(today()));changed=true}
    if(t&&t.sealed_at&&t.review){const v=JSON.parse(localStorage.getItem('tmm.review'));if(!v||v.d!==today()){localStorage.setItem('tmm.review',JSON.stringify({d:today(),a:t.review}));changed=true}}
    if(changed&&!sessionStorage.getItem('mm.r')){sessionStorage.setItem('mm.r','1');location.reload();return}
  }catch(e){}
  document.dispatchEvent(new CustomEvent('mm:ready',{detail:MM}));
}
MM.sync=async(k,v)=>{if(!MM.user)return;const u=MM.user.id,d=today();
  if(k==='oath')await sb.from('days').upsert({user_id:u,day:d,oath_at:new Date().toISOString()},{onConflict:'user_id,day'});
  if(k==='review')await sb.from('days').upsert({user_id:u,day:d,sealed_at:new Date().toISOString(),review:v.a},{onConflict:'user_id,day'});
  if(k==='vow')await sb.from('vows').insert({user_id:u,length_days:+v.n||v.len||7,text:v.t||v.text||''});
  if(k==='ticks')await sb.from('days').upsert({user_id:u,day:d,ticks:v},{onConflict:'user_id,day'});};
MM.post=(body,council)=>sb.from('posts').insert({user_id:MM.user.id,body,council});
MM.feed=()=>sb.from('posts').select('id,body,council,created_at,profiles(display_name,member_no)').order('created_at',{ascending:false}).limit(30);
MM.ready=load();
})();
