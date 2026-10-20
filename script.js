'use strict';
/* ===== Utilidades y datos ===== */
const $=(s,r=document)=>r.querySelector(s), sleep=ms=>new Promise(r=>setTimeout(r,ms));
const RM=matchMedia('(prefers-reduced-motion: reduce)').matches;
const API='/api'; // Backend Python: cambiar si vive en otro origen
const STATS=['PS','Ataque','Defensa','Ataque Especial','Defensa Especial','Velocidad'];
const SH=['','Atq','Def','At. Esp','Def. Esp','Vel'];
const CAT={physical:'Físico',special:'Especial',status:'Estado'};
const TYPES={normal:['Normal','#8a8a5c'],fire:['Fuego','#e8741f'],water:['Agua','#4a78e0'],electric:['Eléctrico','#c9a400'],grass:['Planta','#4fa73a'],ice:['Hielo','#5bb5b5'],fighting:['Lucha','#b02a22'],poison:['Veneno','#92308f'],ground:['Tierra','#b8962f'],flying:['Volador','#8570dd'],psychic:['Psíquico','#e03f72'],bug:['Bicho','#8a9a10'],rock:['Roca','#9a8328'],ghost:['Fantasma','#5e4780'],dragon:['Dragón','#5a28d8'],dark:['Siniestro','#5a4638'],steel:['Acero','#7d7da0']};
const chip=t=>`<span class="chip" style="background:${TYPES[t]?.[1]||'#666'}">${TYPES[t]?.[0]||t}</span>`;
/* Naturalezas oficiales: [nombre, estadística que sube, estadística que baja] (índices 1-5; 0 = neutra) */
const NAT=[['Fuerte',0,0],['Huraña',1,2],['Audaz',1,5],['Firme',1,3],['Pícara',1,4],['Osada',2,1],['Dócil',0,0],['Plácida',2,5],['Agitada',2,3],['Floja',2,4],['Miedosa',5,1],['Activa',5,2],['Seria',0,0],['Alegre',5,3],['Ingenua',5,4],['Modesta',3,1],['Afable',3,2],['Mansa',3,5],['Tímida',0,0],['Alocada',3,4],['Serena',4,1],['Amable',4,2],['Grosera',4,5],['Cauta',4,3],['Rara',0,0]];
/* ===== Capa de datos: backend Python con respaldo de demostración ===== */
const SPR='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/';
const mk=(id,name,types,base)=>({id,name,types,base,sprites:{front:SPR+id+'.gif',back:SPR+'back/'+id+'.gif'}});
const DEMO={
 mons:[mk(6,'Charizard',['fire','flying'],[78,84,78,109,85,100]),mk(94,'Gengar',['ghost','poison'],[60,65,60,130,75,110]),mk(392,'Infernape',['fire','fighting'],[76,104,71,104,71,108]),mk(445,'Garchomp',['dragon','ground'],[108,130,95,80,85,102]),mk(448,'Lucario',['fighting','steel'],[70,110,70,115,70,90])],
 moves:[['Terremoto','ground','physical',100,100,10],['Garra Dragón','dragon','physical',80,100,15],['Lanzallamas','fire','special',95,100,15],['Bola Sombra','ghost','special',80,100,15],['Rayo','electric','special',95,100,15],['Foco Resplandor','steel','special',80,100,10],['A Bocajarro','fighting','physical',120,100,5],['Danza Espada','normal','status',null,null,30]].map(([name,type,category,power,accuracy,pp])=>({name,type,category,power,accuracy,pp}))
};
const setMode=d=>{const m=$('#mode');m.textContent=d?'Modo demostración (sin backend)':'Conectado al backend';m.dataset.demo=d};
async function get(path,fallback){try{const r=await fetch(API+path);if(!r.ok)throw 0;const d=await r.json();setMode(false);return d}catch{setMode(true);return fallback()}}
const data={
 search:q=>get('/pokemon?q='+encodeURIComponent(q),()=>DEMO.mons.filter(m=>m.name.toLowerCase().includes(q.toLowerCase())||String(m.id)===q).map(({id,name})=>({id,name}))),
 pokemon:id=>get('/pokemon/'+id,()=>DEMO.mons.find(m=>m.id==id)),
 moves:()=>get('/moves',()=>DEMO.moves),
 natures:()=>get('/natures',()=>NAT.map(([name,plus,minus])=>({name,plus,minus})))
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
 let t;p.q.addEventListener('input',()=>{clearTimeout(t);t=setTimeout(async()=>{const v=p.q.value.trim();if(!v)return;
  p.sugg=await data.search(v);p.dl.replaceChildren(...p.sugg.map(m=>new Option(m.name)));
  p.msg.textContent=p.sugg.length?'':'No se encontró ningún Pokémon con ese nombre o número.'},200)});
 p.q.addEventListener('change',async()=>{const v=p.q.value.trim().toLowerCase();if(!v)return;
  let m=p.sugg.find(m=>m.name.toLowerCase()===v||String(m.id)===v);
  if(!m){p.sugg=await data.search(v);m=p.sugg.length===1?p.sugg[0]:p.sugg.find(m=>m.name.toLowerCase()===v)}
  m?choose(p,m.id):p.msg.textContent='No se encontró ningún Pokémon con ese nombre o número.'});
 root.addEventListener('input',e=>{if(!e.target.matches('.q,.mv input'))recalc(p)});
 return p;
}
async function choose(p,id){
 p.msg.textContent='Cargando…';const m=await data.pokemon(id);
 if(!m){p.msg.textContent='No se pudo cargar el Pokémon.';return}
 p.mon=m;p.msg.textContent='';
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
  if(e.hit!==false){burst(d);d.classList.add('hit');setTimeout(()=>d.classList.remove('hit'),500);hud(o,e.hp[o],maxhp[o])}
  a.classList.remove('lunge');if(!await wait(900,id))return false}
 (e.extra||[]).forEach(t=>log(t,e.actor));
 if(e.fainted){$('#spr-'+e.fainted).classList.add('faint')}
 return true;
}
async function play(events){
 const id=++run;running=true;lock(true);
 for(const e of events){
  if(e.text)log(e.text,e.actor||'sys');
  if(e.type==='move'&&!await attack(e,id))return;
  if(!await wait(500,id))return}
 if(id===run){running=false;lock(false,true)}
}
function lock(on,ended){
 Object.values(panels).forEach(p=>p.root.inert=on);
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
 let res;
 try{const r=await fetch(API+'/battle/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ruleset:'gen4',user:cfg(panels.user),rival:cfg(panels.rival)})});
  if(!r.ok)throw 0;res=await r.json()}
 catch{log('El motor de combate aún no está conectado (POST /api/battle/simulate). Puedes usar la vista previa de animaciones.','sys');return}
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
(async()=>{
 natures=await data.natures();MOVES=await data.moves();
 $('#dl-moves').replaceChildren(...MOVES.map(m=>new Option(m.name)));
 ['user','rival'].forEach(s=>panels[s]=makePanel(s));
 $('#btn-start').onclick=start;$('#btn-demo').onclick=demo;$('#btn-reset').onclick=reset;
 $('#btn-pause').onclick=e=>{paused=!paused;e.target.textContent=paused?'Reanudar':'Pausar'};
 $('#btn-collapse').onclick=e=>{const f=$('#layout').classList.toggle('focus');e.target.setAttribute('aria-pressed',f);e.target.textContent=f?'Mostrar paneles':'Contraer paneles'};
 log('Configura ambos Pokémon y pulsa «Comenzar combate».','sys');
})();
