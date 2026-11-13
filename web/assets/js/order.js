/* The Mettle Method — page wiring. Replaces every sample figure on the member pages with the member's
   own record, or with "No data yet" when there is none. Reads only; rank, tier and circle are set by the server. */
(function(){
const MM=window.MM;if(!MM)return;
const sb=MM.sb;
const page=(location.pathname.split('/').pop()||'index.html').replace('.html','')||'index';
const RANKS=[null,
  {n:'Tiro',t:'of the Outer Court',d:1,f:'rank-01-tiro'},{n:'Neophytos',t:'Keeper of the First Flame',d:7,f:'rank-02-neophytos'},
  {n:'Discipulus',t:'of the Lettered Hall',d:21,f:'rank-03-discipulus'},{n:'Hoplites',t:'Bearer of the Iron Vow',d:40,f:'rank-04-hoplites'},
  {n:'Centurio',t:'Warden of the Hundred Days',d:100,f:'rank-05-centurio'},{n:'Praefectus',t:'Steward of the Four Pillars',d:180,f:'rank-06-praefectus'},
  {n:'Strategos',t:'Commander of the Unbroken Line',d:300,f:'rank-07-strategos'},{n:'Archon',t:'Lord of the Temple',d:500,f:'rank-08-archon'},
  {n:'Sophos',t:'The Sage Who Endured',d:1000,f:'rank-09-sophos'}];
const ROMAN=['','I','II','III','IV','V','VI','VII','VIII','IX'];
const PILLARS=['mind','body','faith','relationships'];
const $=(s,r)=>(r||document).querySelector(s),$$=(s,r)=>[...(r||document).querySelectorAll(s)];
const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e};
const iso=d=>d.toLocaleDateString('en-CA');
const first=n=>(n||'Member').split(' ')[0];
const empty=(node,text)=>{const s=el('span','lab',text||'No data yet');node.replaceChildren(s);
  if(/Inner Order/.test(text||'')){const a=el('a','lab','See the Inner Order');a.href='inner.html';a.style.cssText='display:block;margin-top:8px;color:inherit';node.appendChild(a)}};
const medal=r=>'assets/ranks/'+RANKS[r].f+'.png';

// ---------------------------------------------------------------- home
async function home(){
  const {data:L}=await sb.rpc('my_ledger');
  const days=(L&&L.days)||[],byDay=new Map(days.map(d=>[d.day,d]));
  const today=iso(new Date());

  // the ledger: from the day of initiation, twelve weeks at most
  const cal=$('.cal');
  if(cal){
    const start=new Date(MM.profile.initiated_on+'T00:00:00'),now=new Date(today+'T00:00:00');
    const span=Math.min(84,Math.round((now-start)/864e5)+1);
    const cells=[];let kept=0;
    for(let i=span-1;i>=0;i--){const d=new Date(now);d.setDate(d.getDate()-i);const k=iso(d),rec=byDay.get(k),on=!!(rec&&rec.sealed);
      const c=el('span','c'+(k===today?' now'+(on?' sealed':''):on?' on':''));c.title=d.toLocaleDateString(undefined,{day:'numeric',month:'short'})+(on?' · kept':k===today?' · today':' · missed');
      if(on)kept++;cells.push(c)}
    cal.replaceChildren(...cells);cal.classList.add('in');
    cal.setAttribute('aria-label',span+(span===1?' day: ':' days: ')+kept+' kept, '+(span-kept-(byDay.get(today)&&byDay.get(today).sealed?0:1))+' missed');
    const lab=$('#ledger .head .lab');
    if(lab){const a=new Date(now);a.setDate(a.getDate()-span+1);const m=d=>d.toLocaleDateString(undefined,{month:'long'});lab.textContent=m(a)===m(now)?m(now):m(a)+' to '+m(now)}
  }

  // the four pillars: of the last thirty sealed days, how many had each pillar marked
  const cards=$$('.pils .pil');
  if(cards.length===4){
    const sealed=days.filter(d=>d.sealed).slice(-30);
    cards.forEach((card,i)=>{const key=PILLARS[i],n=sealed.filter(d=>d.ticks&&d.ticks[key]===true).length;
      const bar=$('.bar span',card),lab=$$('.lab',card).pop();card.setAttribute('href','build.html');
      if(bar)bar.style.setProperty('--w',sealed.length?Math.round(100*n/sealed.length)+'%':'0%');
      if(lab)lab.textContent=sealed.length?n+' of '+sealed.length+(sealed.length===1?' sealed day':' sealed days'):'No data yet'});
    const head=$('#pillars .head .lab');if(head)head.textContent='Your last thirty sealed days';
    // mark today's pillars
    const row=el('div');row.style.cssText='display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:24px';
    row.appendChild(el('span','lab','Kept today'));
    const state=Object.assign({},(byDay.get(today)||{}).ticks||{});
    PILLARS.forEach(key=>{const b=el('button','lab',key[0].toUpperCase()+key.slice(1));b.type='button';
      const paint=()=>{b.setAttribute('aria-pressed',state[key]===true?'true':'false');b.style.cssText='background:'+(state[key]===true?'var(--fg);color:var(--bg)':'transparent;color:var(--fg)')+';border:1px solid var(--hl);padding:10px 14px;cursor:pointer;min-height:44px'};
      b.onclick=()=>{state[key]=!(state[key]===true);paint();MM.sync('ticks',state)};paint();row.appendChild(b)});
    $('.pils').after(row);
  }

  // the circle
  const box=$('.circle');
  if(box){const {data:c}=await sb.rpc('my_circle');
    if(!c||!c.length)empty(box,MM.profile.tier==='inner'?'Your circle is being formed.':'Circles open in the Inner Order.');
    else box.replaceChildren(...c.map(m=>{const r=el('div',null,first(m.display_name)+(m.is_me?' (you)':'')+' · Day '+m.days_kept);r.appendChild(el('span',null,m.kept_today?'kept today':'not yet'));return r}));
  }
}

// ---------------------------------------------------------------- ranks
function ranks(){
  const s=MM.standing,r=s.rank||0,earned=s.rank_earned||0,kept=s.days_kept||0,outer=MM.profile.tier!=='inner';
  const next=RANKS[earned+1];
  const lab=$('.hg .lab');if(lab)lab.textContent='✠ Your rank · '+kept+(kept===1?' day':' days')+' kept ✠';
  const h1=$('.hg h1');if(h1)h1.textContent=r?RANKS[r].n:'Not yet ranked';
  const tt=$('.hg .tt');if(tt)tt.textContent=r?RANKS[r].t:'Seal your first day to become Tiro.';
  const labs=$$('.prog .lab'),bar=$('.prog .bar span');
  if(labs.length===2){
    if(!next){labs[0].textContent='The highest rank';labs[1].textContent='Kept by practice';if(bar)bar.style.width='100%'}
    else{const from=earned?RANKS[earned].d:0,pct=Math.max(0,Math.min(100,Math.round(100*(kept-from)/(next.d-from)))),left=Math.max(0,next.d-kept);
      labs[0].textContent='Next: Rank '+ROMAN[earned+1]+' · '+next.n+', '+next.t;
      labs[1].textContent=left+(left===1?' day':' days')+' to go · '+pct+'%'+(outer&&earned>=3?' · shown in the Inner Order':'');
      if(bar)bar.style.width=pct+'%'}
  }
  const coin=$('.coin3 img');if(coin){if(r){coin.src=medal(r);coin.alt='Insignia of rank '+ROMAN[r]+', '+RANKS[r].n}else coin.style.opacity='.35'}
  $$('.ladder .rk').forEach((a,i)=>{const n=i+1,tag=$('.tag',a);a.classList.remove('done','cur','lock');
    if(n<r){a.classList.add('done');if(tag)tag.textContent='✓ Attained'}
    else if(n===r){a.classList.add('cur');if(tag)tag.textContent='✠ Your rank'}
    else{a.classList.add('lock');if(tag)tag.textContent=(outer&&n>3?'Inner Order · ':'')+'Day '+RANKS[n].d}});
}

// ---------------------------------------------------------------- reliquary
async function reliquary(){
  const {data:R}=await sb.rpc('my_relics');const v=R||{};
  // title -> [have, need, rule]. The rules are written out in docs/RELICS.md.
  const RULES={
    'The Iron Ring':[v.body_days,30,'Thirty sealed days with the Body pillar marked.'],
    'The Owl of Athena':[v.mind_days,50,'Fifty sealed days with the Mind pillar marked.'],
    'The Vigil Lamp':[v.reviews,30,'Thirty evening reviews sealed.'],
    'The Sealed Vow':[v.vow30_days,30,'A thirty-day vow, reached to its end.'],
    'The Broken Chain':[v.drops>=1?Math.min(30,v.current||0):0,30,'Fall a rank, then keep thirty days unbroken.'],
    'The Hourglass of Seneca':[v.early_oaths,30,'The oath taken before six, on thirty mornings.'],
    'The Laurel of the Hundred':[v.longest,100,'One hundred days unbroken.'],
    'The Helm of the Three Hundred':[null,null,'A forty-day campaign with your house.']};
  let held=0;
  $$('.vault .case').forEach(b=>{const title=($('h3',b)||{}).textContent,rule=RULES[title];if(!rule)return;
    const have=rule[0]||0,need=rule[1],got=need!=null&&have>=need,pr=need==null?'Not open yet':got?'✠ In your reliquary':Math.min(have,need)+' / '+need;
    b.classList.toggle('got',got);b.classList.toggle('lock',!got);if(got)held++;
    const p=$('p',b);if(p)p.textContent=rule[2];const t=$('.pr',b);if(t)t.textContent=pr;
    try{const d=D[+b.dataset.i];if(d){d.g=got;d.c=rule[2];d.pr=need==null?'Not open yet':Math.min(have,need)+' / '+need}}catch(e){}});
  const counts=$$('.count b');if(counts.length===3){counts[0].textContent=held;counts[1].textContent=$$('.vault .case').length;counts[2].textContent='0'}
  // the ceremony shows the member's own next rise
  const earned=MM.standing.rank_earned||0,next=RANKS[earned+1],name=first(MM.profile.display_name);
  const play=$('#play');
  if(!next){if(play){play.disabled=true;play.textContent='You hold the highest rank'}return}
  const set=(s,t)=>{const e=$(s);if(e)e.textContent=t};
  set('#sl','✠ Day '+next.d+' · '+(earned?'The rank of '+RANKS[earned].n+' is complete':'The first day is sealed')+' ✠');
  const old=$('#old'),nw=$('.med .new');if(old)old.src=medal(Math.max(1,earned));if(nw){nw.src=medal(earned+1);nw.alt='Insignia of '+next.n}
  set('.ttl .lab','Rank '+ROMAN[earned+1]);set('.ttl h2',next.n);set('.ttl p',next.t);
  set('.cert .lab','Certificate of rank · No. '+String(MM.profile.member_no).padStart(4,'0'));
  const cp=$('.cert p');if(cp)cp.textContent='Let it be recorded that '+name+', having kept the practice '+next.d+(next.d===1?' day':' days')+', is raised to the rank of '+next.n+'.';
  if(play)play.textContent='See the rise to '+next.n;
}

// ---------------------------------------------------------------- the order
async function order(){
  const ul=$('ul.circle');
  if(ul){const {data:c}=await sb.rpc('my_circle');
    if(!c||!c.length){const li=el('li');li.style.width='auto';li.appendChild(el('span','lab',MM.profile.tier==='inner'?'Your circle is being formed.':'Circles open in the Inner Order.'));ul.replaceChildren(li)}
    else{const flame=$('li svg',ul);ul.replaceChildren(...c.map(m=>{const li=el('li',m.kept_today?'lit':'out');
      if(flame)li.appendChild(flame.cloneNode(true));const im=el('img');im.src=m.rank?medal(m.rank):'assets/seal.png';im.alt='';li.appendChild(im);
      li.appendChild(el('b',null,first(m.display_name)));li.appendChild(el('span','lab',m.kept_today?'kept':'not yet'));return li}))}
  }
  // initiation: seven days, counted by days kept
  const kept=MM.standing.days_kept||0;
  $$('.trial li').forEach((li,i)=>{const lab=$('.lab',li);li.classList.remove('ok','now','no');
    if(i<kept){li.classList.add('ok');if(lab)lab.textContent='Kept'}else if(i===kept){li.classList.add('now');if(lab)lab.textContent='Today'}else{li.classList.add('no');if(lab)lab.textContent='Ahead'}});
}

// ---------------------------------------------------------------- the hall
async function community(){
  const [{data:t},{data:roll}]=await Promise.all([sb.rpc('hall_tally'),sb.rpc('hall_roll')]);
  const b=$$('.tally b');
  if(b.length===3&&t){b[0].textContent=Number(t.members).toLocaleString();b[1].textContent=Number(t.kept_today).toLocaleString();b[2].textContent=Number(t.longest_unbroken).toLocaleString()}
  const ol=$('.roll');
  if(ol){if(!roll||!roll.length){const li=el('li');li.style.display='block';li.appendChild(el('span','lab','No data yet'));ol.replaceChildren(li)}
    else ol.replaceChildren(...roll.map((m,i)=>{const li=el('li');li.appendChild(el('span','pos',ROMAN[i+1]||String(i+1)));
      const im=el('img','med sm');im.src=m.rank?medal(m.rank):'assets/seal.png';im.alt=m.rank?RANKS[m.rank].n:'';li.appendChild(im);
      li.appendChild(el('span','nm',first(m.display_name)));li.appendChild(el('span','lab',m.rank?RANKS[m.rank].n:'Not yet ranked'));li.appendChild(el('span','d',String(m.unbroken)));return li}))}
}

// ---------------------------------------------------------------- the Inner Order page
async function inner(){
  MM.track('upgrade_view');
  const {data}=await sb.from('config').select('key,value').in('key',['price_inner_monthly','price_inner_yearly','price_currency','inner_checkout_url']);
  const c=Object.fromEntries((data||[]).map(r=>[r.key,r.value]));
  const money=v=>v==null?'[PRICE]':new Intl.NumberFormat(undefined,{style:'currency',currency:c.price_currency||'USD',maximumFractionDigits:2}).format(v);
  const set=(s,t)=>{const e=$(s);if(e)e.textContent=t};
  set('[data-price=month]',money(c.price_inner_monthly));set('[data-price=year]',money(c.price_inner_yearly));
  const join=$('#join'),note=$('#join-note');
  if(MM.profile.tier==='inner'){if(join)join.remove();if(note)note.textContent='You are in the Inner Order.';return}
  if(!c.inner_checkout_url||c.price_inner_monthly==null){if(join){join.setAttribute('aria-disabled','true');join.removeAttribute('href')}if(note)note.textContent='The gates are not open yet.';return}
  if(join){const u=new URL(c.inner_checkout_url);u.searchParams.set('user_id',MM.user.id);u.searchParams.set('email',MM.user.email||'');join.href=u.toString()}
}

const run={home,ranks,reliquary,order,community,inner}[page];
if(run){const go=()=>Promise.resolve(run()).catch(e=>console.warn('order.js',e));
  if(MM.profile)go();else document.addEventListener('mm:ready',go,{once:true})}
})();
