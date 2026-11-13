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
MM.signIn=async()=>{
  let on=true;try{const r=await fetch(URL+'/auth/v1/settings',{headers:{apikey:KEY}});on=!!((await r.json()).external||{}).google}catch(e){}
  if(!on){document.querySelectorAll('#signup,#login').forEach(b=>{b.disabled=true;b.setAttribute('aria-disabled','true')});
    let n=document.getElementById('mm-gate');if(!n){n=document.createElement('p');n.id='mm-gate';n.setAttribute('role','status');n.style.cssText='margin:14px 0 0;font:400 14px/1.4 "Marcellus SC",Georgia,serif;letter-spacing:.14em;color:#A9A7A0';const at=document.getElementById('login')||document.getElementById('signup');if(at)at.after(n)}
    if(n)n.textContent='Google sign-in is not open yet. Enter by email below.';const m=document.querySelector('#mm-mail input');if(m)m.focus();return}
  return sb.auth.signInWithOAuth({provider:'google',options:{redirectTo:location.origin+location.pathname.replace(/[^/]*$/,'')+'home.html'}})};
// entry by email: a one-time link, no password
MM.emailSignIn=email=>sb.auth.signInWithOtp({email,options:{emailRedirectTo:location.origin+location.pathname.replace(/[^/]*$/,'')+'home.html'}});
function mailForm(){
  const at=document.getElementById('login')||document.getElementById('signup');if(!at||document.getElementById('mm-mail'))return;
  const f=document.createElement('form');f.id='mm-mail';f.noValidate=true;f.style.cssText='margin:22px 0 0;display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;max-width:420px';
  const caps='font:400 13px/1.3 "Marcellus SC",Georgia,serif;letter-spacing:.14em;';
  const l=document.createElement('label');l.htmlFor='mm-email';l.textContent='Or enter by email';l.style.cssText=caps+'flex:1 0 100%;opacity:.75';
  const i=document.createElement('input');i.type='email';i.id='mm-email';i.name='email';i.required=true;i.autocomplete='email';i.placeholder='you@example.com';
  i.style.cssText='flex:1 1 200px;min-width:0;min-height:44px;padding:10px 12px;background:transparent;color:inherit;border:1px solid currentColor;border-radius:2px;font:400 16px/1.2 "Hanken Grotesk",Arial,sans-serif';
  const b=document.createElement('button');b.type='submit';b.textContent='Send me a link';
  b.style.cssText='min-height:44px;padding:10px 16px;background:transparent;color:inherit;border:1px solid currentColor;border-radius:2px;cursor:pointer;font:600 15px/1 "Hanken Grotesk",Arial,sans-serif';
  const st=document.createElement('p');st.setAttribute('role','status');st.style.cssText=caps+'flex:1 0 100%;margin:0;min-height:18px';
  f.append(l,i,b,st);at.after(f);
  f.addEventListener('submit',async e=>{e.preventDefault();
    if(!i.value||!i.checkValidity()){st.textContent='Enter a full email address.';i.focus();return}
    b.disabled=true;st.textContent='Sending.';
    const {error}=await MM.emailSignIn(i.value.trim());b.disabled=false;
    st.textContent=error?(error.status===429?'Too many links asked for. Try again in an hour.':'That did not go through. Try again in a minute.'):'A link is on its way. Open it on this device to enter.'});
}
MM.signOut=async()=>{await sb.auth.signOut();try{Object.keys(localStorage).filter(k=>k.startsWith('tmm.')).forEach(k=>localStorage.removeItem(k))}catch(e){};location.href='index.html'};
function swapText(map){const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;const ns=[];while(n=w.nextNode())ns.push(n);
  ns.forEach(t=>{let s=t.nodeValue,o=s;for(const[a,b]of map)s=s.split(a).join(b);if(s!==o)t.nodeValue=s});
  document.querySelectorAll('input[placeholder="Gyaan"]').forEach(i=>i.placeholder=map[0][1]);
  document.querySelectorAll('[aria-label*="Gyaan"]').forEach(e=>e.setAttribute('aria-label',e.getAttribute('aria-label').replace('Gyaan',map[0][1])))}
async function load(){
  const {data:{session}}=await sb.auth.getSession();
  if(!session){if(!PUBLIC.includes(page))location.replace('index.html');else if(page==='index'||page==='')mailForm();return}
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
// ---- events: what the dashboard counts. No personal data beyond the member's own id.
const CLIENT_EVENTS=['visit','signup','oath','seal','vow','post','upgrade_view','invite_sent'];
MM.track=(name,props)=>{if(!CLIENT_EVENTS.includes(name))return Promise.resolve();
  return sb.from('events').insert({name,props:props||{},user_id:MM.user?MM.user.id:null}).then(()=>{},()=>{})};
const _sync=MM.sync;
MM.sync=async(k,v)=>{await _sync(k,v);if(k==='oath')MM.track('oath');if(k==='review')MM.track('seal');if(k==='vow')MM.track('vow',{days:+(v&&(v.n||v.len))||7})};
const _post=MM.post;
MM.post=(body,council)=>{MM.track('post',{council:council||null});return _post(body,council)};
// invites: a member's link carries ?ref=<code>; the code is claimed once the invited person has signed in
try{const ref=new URLSearchParams(location.search).get('ref');if(ref&&/^[a-f0-9]{12}$/.test(ref))localStorage.setItem('tmm.ref',ref)}catch(e){}
MM.invite=async()=>{const {data,error}=await sb.from('referrals').insert({inviter_id:MM.user.id}).select('code').single();
  if(error)throw error;MM.track('invite_sent');return location.origin+location.pathname.replace(/[^/]*$/,'')+'index.html?ref='+data.code};
document.addEventListener('mm:ready',async()=>{
  try{
    if(!MM.profile.timezone){const tz=Intl.DateTimeFormat().resolvedOptions().timeZone;if(tz)sb.from('profiles').update({timezone:tz}).eq('id',MM.user.id).then(()=>{},()=>{})}
    if(Date.now()-new Date(MM.profile.created_at).getTime()<10*60*1000&&!localStorage.getItem('tmm.signup')){localStorage.setItem('tmm.signup','1');MM.track('signup')}
    const ref=localStorage.getItem('tmm.ref');if(ref){localStorage.removeItem('tmm.ref');sb.rpc('claim_invite',{p_code:ref}).then(()=>{},()=>{})}
  }catch(e){}
});
try{if(!sessionStorage.getItem('mm.v.'+page)){sessionStorage.setItem('mm.v.'+page,'1');
  let from='';try{from=document.referrer?new URL(document.referrer).hostname:''}catch(e){}
  MM.ready=load().then(()=>MM.track('visit',{page,from}))}else MM.ready=load()}catch(e){MM.ready=load()}
// the pages' live wiring lives in order.js
const o=document.createElement('script');o.src='assets/js/order.js';document.head.appendChild(o);
})();
