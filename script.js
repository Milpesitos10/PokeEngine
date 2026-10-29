'use strict';
/* ===== Utilidades y datos ===== */
const $=(s,r=document)=>r.querySelector(s), sleep=ms=>new Promise(r=>setTimeout(r,ms));
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const API=document.querySelector('meta[name=api-base]')?.content||'/api'; // URL del backend (meta api-base en index.html)
const STATS=['PS','Ataque','Defensa','Ataque Especial','Defensa Especial','Velocidad'];
const SH=['','Atq','Def','At. Esp','Def. Esp','Vel'];
const CAT={physical:'Físico',special:'Especial',status:'Estado'};
const TYPES={normal:['Normal','#8a8a5c'],fire:['Fuego','#e8741f'],water:['Agua','#4a78e0'],electric:['Eléctrico','#c9a400'],grass:['Planta','#4fa73a'],ice:['Hielo','#5bb5b5'],fighting:['Lucha','#b02a22'],poison:['Veneno','#92308f'],ground:['Tierra','#b8962f'],flying:['Volador','#8570dd'],psychic:['Psíquico','#e03f72'],bug:['Bicho','#8a9a10'],rock:['Roca','#9a8328'],ghost:['Fantasma','#5e4780'],dragon:['Dragón','#5a28d8'],dark:['Siniestro','#5a4638'],steel:['Acero','#7d7da0']};
const esc=x=>String(x).replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';');
const chip=t=>`<span class="chip" style="background:${TYPES[t]?.[1]||'#666'}">${esc(TYPES[t]?.[0]||t)}</span>`;
/* Naturalezas oficiales: [nombre, estadística que sube, estadística que baja] (índices 1-5; 0 = neutra) */
const NAT=[['Fuerte',0,0],['Huraña',1,2],['Audaz',1,5],['Firme',1,3],['Pícara',1,4],['Osada',2,1],['Dócil',0,0],['Plácida',2,5],['Agitada',2,3],['Floja',2,4],['Miedosa',5,1],['Activa',5,2],['Seria',0,0],['Alegre',5,3],['Ingenua',5,4],['Modesta',3,1],['Afable',3,2],['Mansa',3,5],['Tímida',0,0],['Alocada',3,4],['Serena',4,1],['Amable',4,2],['Grosera',4,5],['Cauta',4,3],['Rara',0,0]];
/* ===== Capa de datos: backend Python con respaldo de demostración ===== */
const SPR='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/';
const mk=(id,name,types,base)=>({id,name,types,base,sprites:{front:SPR+id+'.gif',back:SPR+'back/'+id+'.gif'}});
const DEMO={
 mons:[mk(6,'Charizard',['fire','flying'],[78,84,78,109,85,100]),mk(94,'Gengar',['ghost','poison'],[60,65,60,130,75,110]),mk(392,'Infernape',['fire','fighting'],[76,104,71,104,71,108]),mk(445,'Garchomp',['dragon','ground'],[108,130,95,80,85,102]),mk(448,'Lucario',['fighting','steel'],[70,110,70,115,70,90])],
 moves:[['Terremoto','ground','physical',100,100,10],['Garra Dragón','dragon','physical',80,100,15],['Lanzallamas','fire','special',95,100,15],['Bola Sombra','ghost','special',80,100,15],['Rayo','electric','special',95,100,15],['Foco Resplandor','steel','special',80,100,10],['A Bocajarro','fighting','physical',120,100,5],['Danza Espada','normal','status',null,null,30]].map(([name,type,category,power,accuracy,pp])=>({name,type,category,power,accuracy,pp}))
};
/* Sin backend: datos reales directo de PokeAPI (solo 1-493). Si tampoco hay internet, 5 Pokémon de ejemplo. */
const PA='https://pokeapi.co/api/v2';let dexList=null;
async function demoSearch(q){
 try{if(!dexList){const r=await fetch(PA+'/pokemon?limit=493');dexList=(await r.json()).results.map(x=>({id:+x.url.split('/').filter(Boolean).pop(),name:x.name}))}
  return dexList.filter(m=>m.name.includes(q)||String(m.id)===q).slice(0,20)}
 catch{return DEMO.mons.filter(m=>m.name.toLowerCase().includes(q)||String(m.id)===q).map(({id,name})=>({id,name}))}}
async function demoPokemon(id){
 try{const d=await(await fetch(PA+'/pokemon/'+id)).json();return mk(d.id,d.name,d.types.map(t=>t.type.name),d.stats.map(x=>x.base_stat))}
 catch{return DEMO.mons.find(m=>m.id==id)}}
const setMode=d=>{const m=$('#mode');m.textContent=d?'Demo: datos directos de PokeAPI (sin backend)':'Conectado al backend';m.dataset.demo=d};
async function get(path,fallback,empty=null){
 let r,d;try{r=await fetch(API+path);d=await r.json()}catch{setMode(true);return fallback()} // sin backend (o el servidor estático devolvió HTML) -> demo
 setMode(false);return r.ok?d:empty} // con backend: un 404/422 NO activa la demo
async function getDex(){
 if(dexList)return dexList;
 try{const r=await fetch(PA+'/pokemon?limit=493');dexList=(await r.json()).results.map(x=>({id:+x.url.split('/').filter(Boolean).pop(),name:x.name}))}
 catch{dexList=DEMO.mons.map(({id,name})=>({id,name}))}
 return dexList}
async function demoPokedex(p){
 const q=(p.search||'').toLowerCase();let r=(await getDex()).filter(m=>!q||m.name.includes(q)||String(m.id)===q);
 if(p.sort==='name')r=[...r].sort((a,b)=>a.name.localeCompare(b.name));
 if(p.order==='desc')r=[...r].reverse();
 const i=(p.page-1)*p.page_size;
 return{total:r.length,page:p.page,page_size:p.page_size,items:r.slice(i,i+p.page_size).map(m=>({...m,types:[],total:null,generation:null})),
  note:'Modo demostración: los filtros por tipo y generación y el total base requieren el backend.'}}
const data={
 pokedex:(qs,p)=>get('/pokedex?'+qs,()=>demoPokedex(p),{total:0,page:1,page_size:p.page_size,items:[]}),
 catalogs:()=>get('/catalogs',()=>({types:Object.keys(TYPES)}),null),
 search:q=>get('/pokemon?q='+encodeURIComponent(q),()=>demoSearch(q),[]),
 pokemon:id=>get('/pokemon/'+id,()=>demoPokemon(id)),
 moves:()=>get('/moves',()=>DEMO.moves,[]),
 natures:()=>get('/natures',()=>NAT.map(([name,plus,minus])=>({name,plus,minus})),[])
};
/* ===== Estadísticas (fórmulas de 4.ª generación) ===== */
function total(base,iv,ev,L,i,nat){
 const core=Math.floor((2*base+iv+Math.floor(ev/4))*L/100);
 if(i===0)return core+L+10;
 const m=nat.plus===i?1.1:nat.minus===i?0.9:1;
 return Math.floor((core+5)*m);
}
let natures=[],MOVES=[];const panels={};
/* ===== Paneles de configuración ===== */
function makePanel(side){
 const root=$('#panel-'+side);root.append($('#tpl-panel').content.cloneNode(true));
 const q=s=>$(s,root);
 const p={side,root,mon:null,sugg:[],moves:[null,null,null,null],errs:[],totals:[],q:q('.q'),dl:q('datalist'),msg:q('.msg'),err:q('.err'),lv:q('.lv'),nat:q('.nat'),evsum:q('.ev-sum b')};
 p.dl.id='dl-'+side;p.q.setAttribute('list',p.dl.id);
 natures.forEach((n,i)=>p.nat.add(new Option(n.name+(n.plus?` (+${SH[n.plus]} −${SH[n.minus]})`:' (neutra)'),i)));
 p.rows=STATS.map((s,i)=>{const tr=q('.stats').insertRow();
  tr.innerHTML=`<th scope="row">${s}</th><td>—</td><td><input class="iv" type="number" min="0" max="31" value="31" aria-label="IV ${s}"></td><td><input class="ev" type="number" min="0" max="252" value="0" aria-label="EV ${s}"></td><td>—</td>`;
  return{b:tr.cells[1],iv:tr.cells[2].firstChild,ev:tr.cells[3].firstChild,t:tr.cells[4]}});
 const mf=q('.moves');
 [0,1,2,3].forEach(j=>{const d=document.createElement('div');d.className='mv';
  d.innerHTML=`<input list="dl-moves" placeholder="Movimiento ${j+1}" aria-label="Movimiento ${j+1}" autocomplete="off"><span class="mi"></span>`;mf.append(d);
  const inp=d.firstChild,mi=d.lastChild;
  inp.addEventListener('change',()=>{const v=inp.value.trim().toLowerCase(),m=MOVES.find(m=>m.name.toLowerCase()===v);
   p.moves[j]=m||null;inp.setAttribute('aria-invalid',String(!!v&&!m));
   mi.innerHTML=m?`${chip(m.type)} ${CAT[m.category]} · Pot. ${m.power??'—'} · Prec. ${m.accuracy??'—'} · PP ${m.pp??'—'}`:(v?'Movimiento no disponible en los datos.':'')})});
 const norm=v=>{v=v.trim().toLowerCase();return /^\d+$/.test(v)?String(+v):v}; // "001" -> "1"
 const NF='No se encontró ningún Pokémon con ese nombre o número (rango 1-493; con backend debe estar sincronizado).';
 let t;p.q.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(async()=>{const v=norm(p.q.value);if(!v)return;
  p.sugg=await data.search(v);
  p.dl.replaceChildren(...p.sugg.map(m=>{const o=new Option(m.name);o.label='#'+String(m.id).padStart(3,'0');return o}));
  p.msg.textContent=p.sugg.length?'':NF},200)});
 p.q.addEventListener('change',async()=>{const v=norm(p.q.value);if(!v)return;
  let m=p.sugg.find(m=>m.name.toLowerCase()===v||String(m.id)===v);
  if(!m){p.sugg=await data.search(v);m=p.sugg.find(m=>m.name.toLowerCase()===v||String(m.id)===v)||(p.sugg.length===1?p.sugg[0]:null)}
  if(m)choose(p,m.id);else p.msg.textContent=p.sugg.length>1?'Hay varias coincidencias: elige una de la lista.':NF});
 root.addEventListener('input',e=>{if(!e.target.matches('.q,.mv input'))recalc(p)});
 return p;
}
async function choose(p,id){
 p.msg.textContent='Cargando…';const m=await data.pokemon(id);
 if(!m){p.msg.textContent='Ese Pokémon no está en la base de datos (¿ya se sincronizó?).';return}
 p.mon=m;p.q.value=m.name;p.msg.textContent='';
 const q=s=>$(s,p.root);
 q('.nm').textContent=m.name;q('.no').textContent='N.º '+String(m.id).padStart(3,'0');
 const pic=q('.pic');pic.src=m.sprites.front;pic.alt='Sprite animado de '+m.name;
 q('.types').innerHTML=m.types.map(chip).join('');
 p.rows.forEach((r,i)=>r.b.textContent=m.base[i]);
 const s=$('#spr-'+p.side);s.src=m.sprites[p.side==='user'?'back':'front'];s.alt='Sprite de combate de '+m.name;s.hidden=false;s.className='spr s-'+p.side;
 recalc(p);
}
function recalc(p){
 const errs=[],L=+p.lv.value;let sum=0;
 if(!Number.isInteger(L)||L<1||L>100||p.lv.value==='')errs.push('Nivel: entero de 1 a 100.');
 const iv=[],ev=[];
 p.rows.forEach((r,i)=>{const a=+r.iv.value,b=+r.ev.value;
  const ba=r.iv.value===''||!Number.isInteger(a)||a<0||a>31,bb=r.ev.value===''||!Number.isInteger(b)||b<0||b>252;
  r.iv.setAttribute('aria-invalid',String(ba));r.ev.setAttribute('aria-invalid',String(bb));
  if(ba)errs.push(`${STATS[i]}: IV entre 0 y 31.`);if(bb)errs.push(`${STATS[i]}: EV entre 0 y 252.`);
  iv.push(a);ev.push(b);if(!bb)sum+=b});
 if(sum>510)errs.push(`La suma de EV (${sum}) supera 510.`);
 p.evsum.textContent=sum;p.errs=errs;p.err.textContent=errs.join(' ');
 p.nat.disabled=false;p.totals=[];
 if(!p.mon)return;
 p.rows.forEach((r,i)=>{r.t.textContent=errs.length?'—':total(p.mon.base[i],iv[i],ev[i],L,i,natures[p.nat.value])});
 if(!errs.length){p.totals=p.rows.map(r=>+r.t.textContent);p.iv=iv;p.ev=ev;p.level=L;showHud(p,p.totals[0],p.totals[0])}
}
/* ===== Arena ===== */
const hudEl=s=>$('#hud-'+s);
function hud(side,cur,max){const h=hudEl(side),pct=max?Math.round(cur/max*100):0;
 $('.bar i',h).style.width=pct+'%';$('.bar',h).dataset.lv=pct>50?'ok':pct>20?'mid':'low';
 $('.hp',h).textContent=max?`${cur}/${max} PS (${pct}%)`:''}
function showHud(p,cur,max){const h=hudEl(p.side);$('.n',h).textContent=p.mon.name;$('.l',h).textContent=p.level;hud(p.side,cur,max)}
function log(text,cls=''){const d=document.createElement('p');d.className=cls;d.textContent=text;$('#log').append(d);$('#log').scrollTop=1e9}
/* ===== Reproductor de eventos del combate =====
   El backend devuelve {events:[...]} con:
   {type:'log',text}  |  {type:'move',actor:'user'|'rival',text,hit:bool,status:bool,
    hp:{user,rival},extra:[textos],fainted:'user'|'rival'|null}
   La interfaz solo anima y muestra lo que llega; no calcula daño. */
let run=0,paused=false,running=false,maxhp={};
async function wait(ms,id){await sleep(ms);while(paused&&id===run)await sleep(100);return id===run}
function burst(el,cls=''){const b=document.createElement('div');b.className='burst '+cls;
 b.style.left=el.offsetLeft+el.offsetWidth/2+'px';b.style.top=el.offsetTop+el.offsetHeight/2+'px';el.parentElement.append(b);setTimeout(()=>b.remove(),500)}
async function attack(e,id){
 const o=e.actor==='user'?'rival':'user',a=$('#spr-'+e.actor),d=$('#spr-'+o);
 if(!await wait(400,id))return false;
 if(e.status){burst(a,'buff');if(!await wait(600,id))return false}
 else{
  if(!RM){const k=a.parentElement.clientWidth*.4,s=e.actor==='user'?1:-1;a.style.setProperty('--dx',k*s+'px');a.style.setProperty('--dy',-k*.2*s+'px');a.classList.add('lunge');if(!await wait(200,id))return false}
  if(e.hit!==false){burst(d);d.classList.add('hit');setTimeout(()=>d.classList.remove('hit'),500);hud(o,e.hp[o],maxhp[o]);hud(e.actor,e.hp[e.actor],maxhp[e.actor])}
  a.classList.remove('lunge');if(!await wait(900,id))return false}
 (e.extra||[]).forEach(t=>log(t,e.actor));
 if(e.fainted){$('#spr-'+e.fainted).classList.add('faint')}
 return true;
}
async function play(events){
 const id=++run;running=true;lock(true);
 const m0=events.find(e=>e.max_hp);if(m0)maxhp=m0.max_hp;
 for(const e of events){
  if(e.text)log(e.text,e.actor||'sys');
  if(e.type==='move'&&!await attack(e,id))return;
  if(e.type==='faint')$('#spr-'+e.fainted).classList.add('faint');
  if(!await wait(500,id))return}
 if(id===run){running=false;lock(false,true)}
}
function lock(on,ended){
 Object.values(panels).forEach(p=>p.root.inert=on);$('#indice').inert=on;
 $('#btn-start').disabled=on;$('#btn-demo').disabled=on;$('#btn-pause').disabled=!on;
 if(on)$('#layout').classList.add('focus');
}
function reset(){
 run++;running=false;paused=false;lock(false);$('#btn-pause').textContent='Pausar';$('#layout').classList.remove('focus');
 $('#btn-collapse').setAttribute('aria-pressed','false');$('#btn-collapse').textContent='Contraer paneles';
 ['user','rival'].forEach(s=>{const p=panels[s];$('#spr-'+s).classList.remove('faint','lunge','hit');if(p.mon&&p.totals.length)showHud(p,p.totals[0],p.totals[0])});
 $('#log').replaceChildren();log('Configura ambos Pokémon y pulsa «Comenzar combate».','sys');
}
/* ===== Inicio de combate ===== */
function validate(){
 const bad=[];
 for(const [s,p] of Object.entries(panels)){const n=s==='user'?'Tu Pokémon':'Pokémon rival';
  if(!p.mon)bad.push(`${n}: selecciona un Pokémon.`);
  else if(p.errs.length||!p.totals.length)bad.push(`${n}: corrige los valores marcados (nivel, IV o EV).`);
  if(!p.moves.some(Boolean))bad.push(`${n}: elige al menos un movimiento.`)}
 return bad;
}
const cfg=p=>({pokemon_id:p.mon.id,level:p.level,nature:natures[p.nat.value].name,iv:p.iv,ev:p.ev,stats:p.totals,moves:p.moves.filter(Boolean).map(m=>m.name)});
async function start(){
 if(running)return;
 const bad=validate();if(bad.length){bad.forEach(b=>log(b,'sys'));return}
 maxhp={user:panels.user.totals[0],rival:panels.rival.totals[0]};
 const body=JSON.stringify({ruleset:'gen4',user:cfg(panels.user),rival:cfg(panels.rival)});
 const post=async p=>{const r=await fetch(API+p,{method:'POST',headers:{'Content-Type':'application/json'},body});return{r,j:await r.json().catch(()=>({}))}};
 let res;
 try{
  const v=await post('/battles/preview');
  if(!v.r.ok){(v.j.error?.details||[v.j.error?.message||'Configuración no válida.']).forEach(m=>log(m,'sys'));return}
  const s=await post('/battles/simulate');
  if(s.r.status===501){log('Configuración validada por el backend. El motor de combate de 4.ª generación aún no está conectado.','sys');return}
  if(!s.r.ok)throw 0;res=s.j}
 catch{log('No se pudo contactar con el backend (POST /api/battles/preview). Puedes usar la vista previa de animaciones.','sys');return}
 $('#log').replaceChildren();play(res.events);
}
/* Vista previa visual: porcentajes ilustrativos, NO es un resultado de combate */
function demo(){
 if(running)return;
 const bad=validate().filter(b=>b.includes('selecciona'));if(bad.length){bad.forEach(b=>log(b,'sys'));return}
 const u=panels.user,r=panels.rival,mu=u.totals[0]||100,mr=r.totals[0]||100;
 maxhp={user:mu,rival:mr};
 const mv=(a,hu,hr,f)=>({type:'move',actor:a,text:`[DEMO] ${(a==='user'?u:r).mon.name} ataca (animación ilustrativa, sin cálculo real).`,hp:{user:Math.round(mu*hu),rival:Math.round(mr*hr)},fainted:f||null});
 $('#log').replaceChildren();
 play([{type:'log',text:'[DEMO] Vista previa de animaciones. Los PS mostrados no provienen del motor de combate.'},mv('user',1,.6),mv('rival',.7,.6),{...mv('user',.7,.3),status:false},mv('rival',.4,.3),mv('user',.4,0,'rival'),{type:'log',text:'[DEMO] Fin de la vista previa.'}]);
}
/* ===== Arranque ===== */

/* ===== Índice de la base de datos (Pokémon · Movimientos · Naturalezas) ===== */
const IDX={page:1,size:24,pages:1};
const el=(t,a={},...k)=>{const e=document.createElement(t);Object.assign(e,a);e.append(...k);return e};
const icon=id=>`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${id}.png`;
const chipsCell=types=>{const td=el('td');td.innerHTML=types.map(chip).join(' ');return td};
const num=id=>'#'+String(id).padStart(3,'0');
async function loadPokedex(){
 const [sort,order]=$('#ix-sort').value.split(':');
 const p={search:$('#ix-q').value.trim(),type:$('#ix-type').value,generation:$('#ix-gen').value,sort,order,page:IDX.page,page_size:IDX.size};
 const qs=new URLSearchParams(Object.entries(p).filter(([,v])=>v!=='')).toString();
 const d=await data.pokedex(qs,p);
 IDX.pages=Math.max(1,Math.ceil(d.total/IDX.size));
 const filtered=p.search||p.type||p.generation;
 $('#idx-note').textContent=d.note||(d.total?'':filtered?'Ningún Pokémon coincide con los filtros.':'La base de datos aún no tiene Pokémon. Sincroniza con: python conector.py sync-pokemon 25');
 const rows=d.items.map(m=>{
  const use=(side,txt)=>el('button',{type:'button',textContent:txt,onclick:()=>{choose(panels[side],m.id);$('.stage').scrollIntoView({behavior:RM?'auto':'smooth'})}});
  return el('tr',{},el('td',{},el('img',{src:icon(m.id),alt:'',loading:'lazy',onerror(){this.style.visibility='hidden'}})),
   el('td',{className:'n',textContent:num(m.id)}),el('td',{className:'cap',textContent:m.name.replace(/-/g,' ')}),chipsCell(m.types||[]),
   el('td',{textContent:m.generation?'Gen. '+m.generation:'—'}),el('td',{textContent:m.total??'—'}),
   el('td',{className:'acts'},use('user','Tu Pokémon'),use('rival','Rival')))});
 $('#ix-rows').replaceChildren(...rows);
 $('#ix-info').textContent=`Página ${IDX.page} de ${IDX.pages} · ${d.total} Pokémon`;
 $('#ix-prev').disabled=IDX.page<=1;$('#ix-next').disabled=IDX.page>=IDX.pages;
}
function renderMoves(){
 const q=$('#im-q').value.trim().toLowerCase().replace(/\s+/g,'-'),t=$('#im-type').value,c=$('#im-cat').value;
 const r=MOVES.filter(m=>(!q||m.name.includes(q))&&(!t||m.type===t)&&(!c||m.category===c));
 $('#im-rows').replaceChildren(...r.slice(0,100).map(m=>{const td=el('td');td.innerHTML=m.type?chip(m.type):'—';
  return el('tr',{},el('td',{className:'cap',textContent:m.name.replace(/-/g,' ')}),td,el('td',{textContent:CAT[m.category]||'—'}),
   el('td',{textContent:m.power??'—'}),el('td',{textContent:m.accuracy??'—'}),el('td',{textContent:m.pp??'—'}))}));
 $('#im-info').textContent=MOVES.length?`${r.length} movimientos${r.length>100?' (se muestran 100: afina el filtro)':''}.`:'No hay movimientos en la base de datos todavía (sincroniza con: python conector.py sync-move thunderbolt).';
}
function renderNatures(){
 $('#in-rows').replaceChildren(...natures.map(n=>el('tr',{},el('td',{className:'cap',textContent:n.name}),
  el('td',{textContent:n.plus?STATS[n.plus]:'— (neutra)'}),el('td',{textContent:n.minus?STATS[n.minus]:'— (neutra)'}))));
}
async function initIndice(){
 const cat=await data.catalogs()||{};
 for(const t of cat.types||Object.keys(TYPES))for(const sel of ['#ix-type','#im-type'])$(sel).add(new Option(TYPES[t]?.[0]||t,t));
 for(const g of cat.generations||[1,2,3,4].map(id=>({id})))$('#ix-gen').add(new Option('Generación '+g.id,g.id));
 for(const [k,v] of Object.entries(CAT))$('#im-cat').add(new Option(v,k));
 if(cat.counts)$('#idx-count').textContent=`${cat.counts.pokemon} Pokémon y ${cat.counts.moves} movimientos en la base de datos.`;
 const debounce=(fn,ms=250)=>{let t;return()=>{clearTimeout(t);t=setTimeout(fn,ms)}};
 const reload=()=>{IDX.page=1;loadPokedex()};
 $('#ix-q').addEventListener('input',debounce(reload));
 for(const id of ['#ix-type','#ix-gen','#ix-sort'])$(id).addEventListener('change',reload);
 $('#ix-prev').onclick=()=>{IDX.page--;loadPokedex()};$('#ix-next').onclick=()=>{IDX.page++;loadPokedex()};
 $('#im-q').addEventListener('input',debounce(renderMoves));
 for(const id of ['#im-type','#im-cat'])$(id).addEventListener('change',renderMoves);
 for(const b of document.querySelectorAll('.tabs [data-tab]'))b.onclick=()=>{
  for(const x of document.querySelectorAll('.tabs [data-tab]'))x.setAttribute('aria-selected',String(x===b));
  for(const n of ['pokemon','moves','natures'])$('#pane-'+n).hidden=n!==b.dataset.tab;
  if(b.dataset.tab==='moves')renderMoves();if(b.dataset.tab==='natures')renderNatures();
  $('#idx-note').textContent='';if(b.dataset.tab==='pokemon')loadPokedex()};
 loadPokedex();
}

(async()=>{
 natures=await data.natures();MOVES=await data.moves();
 $('#dl-moves').replaceChildren(...MOVES.map(m=>new Option(m.name)));
 ['user','rival'].forEach(s=>panels[s]=makePanel(s));
 $('#btn-start').onclick=start;$('#btn-demo').onclick=demo;$('#btn-reset').onclick=reset;
 $('#btn-pause').onclick=e=>{paused=!paused;e.target.textContent=paused?'Reanudar':'Pausar'};
 $('#btn-collapse').onclick=e=>{const f=$('#layout').classList.toggle('focus');e.target.setAttribute('aria-pressed',f);e.target.textContent=f?'Mostrar paneles':'Contraer paneles'};
 log('Configura ambos Pokémon y pulsa «Comenzar combate».','sys');
 initIndice();
})();
