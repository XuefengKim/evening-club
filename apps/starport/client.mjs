import{LEVELS,geometry,createGame,stars,W,H}from './engine.mjs';
import{cameraTarget,smoothCamera,worldToScreen,createPointerTracker,tryNativeFullscreen}from './view.mjs?v=mobile-2';
const $=id=>document.getElementById(id),canvas=$('world'),ctx=canvas.getContext('2d');
let state=null,role=-1,ws=null,joined=false,joining=false,reconnect=0,game=createGame(),keys={left:false,right:false,jump:false,action:false},muted=true,audio=null,lastDeath=0,lastWon=false,paintPlayers=[],pulseTime=0;
let camera=null,lastRender=0,overview=false,immersive=false,isMobile=false,view={width:1200,height:660,dpr:1,insets:{top:0,bottom:0}};
const inputTracker=createPointerTracker();
let token='';try{token=localStorage.getItem('starport-token')||'';}catch{}
const address=location.href.split('#')[0];$('address').textContent=address;$('invite').textContent=address;
// All controls and dialogs live inside the same native-fullscreen root.
$('stage').append($('touch'),...document.querySelectorAll('dialog'),$('toast'));
const mobileQuery=matchMedia('(pointer: coarse), (max-width:700px), (max-width:1100px) and (max-height:550px)');
const standalone=()=>matchMedia('(display-mode: standalone)').matches||navigator.standalone===true||matchMedia('(display-mode: fullscreen)').matches&&!(document.fullscreenElement||document.webkitFullscreenElement);
function updateViewport(){
 isMobile=mobileQuery.matches;document.body.classList.toggle('mobile-game',isMobile);document.body.classList.toggle('has-touch',matchMedia('(pointer:coarse)').matches);
 const vv=window.visualViewport,root=document.documentElement;
 root.style.setProperty('--view-width',`${vv?.width||innerWidth}px`);root.style.setProperty('--view-height',`${vv?.height||innerHeight}px`);root.style.setProperty('--view-top',`${vv?.offsetTop||0}px`);root.style.setProperty('--view-left',`${vv?.offsetLeft||0}px`);
 requestAnimationFrame(resizeCanvas);
}
function resizeCanvas(){
 const r=$('stage').getBoundingClientRect(),width=Math.max(1,r.width),height=Math.max(1,r.height),dpr=Math.min(2,devicePixelRatio||1);
 if(Math.abs(view.width-width)>.5||Math.abs(view.height-height)>.5||view.dpr!==dpr){view={width,height,dpr,insets:{left:Math.max(0,parseFloat(getComputedStyle($('gameHud')).left)-12)||0,right:Math.max(0,parseFloat(getComputedStyle($('gameHud')).right)-12)||0,top:Math.max(0,parseFloat(getComputedStyle($('gameHud')).top)-8)||0,bottom:Math.max(0,parseFloat(getComputedStyle($('touch')).bottom)-14)||0}};canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);camera=null;}
}
if(typeof ResizeObserver!=='undefined')new ResizeObserver(resizeCanvas).observe($('stage'));window.addEventListener('resize',updateViewport);window.visualViewport?.addEventListener('resize',updateViewport);window.visualViewport?.addEventListener('scroll',updateViewport);if(mobileQuery.addEventListener)mobileQuery.addEventListener('change',updateViewport);else mobileQuery.addListener(updateViewport);updateViewport();
function setImmersive(value){immersive=value;document.body.classList.toggle('immersive',value);inputTracker.clear();keys=inputTracker.state();updateViewport();}
function setOverview(value){overview=value;camera=null;$('overview').setAttribute('aria-pressed',String(value));$('overview').textContent=value?'跟随':'全图';$('menuOverview').textContent=value?'◎ 返回近景跟随':'◎ 查看完整地图';}
function updateDisplayStatus(){const native=!!(document.fullscreenElement||document.webkitFullscreenElement);$('displayStatus').textContent=standalone()?'主屏幕网页 App · 已独立运行':native?'系统全屏 · 触控操作已保留':isMobile?'手机沉浸模式 · 近景跟随 · 浏览器栏由系统管理':'电脑视图 · 支持系统全屏';$('menuFullscreen').textContent=native?'⛶ 退出系统全屏':'⛶ 全屏游玩';}
async function enterGameFullscreen(showHelp=true){
 setImmersive(true);const result=await tryNativeFullscreen($('stage'),document);updateDisplayStatus();
 if(!result.native&&showHelp){if(/iPhone|iPod/.test(navigator.userAgent)&&!standalone())$('installHelp').showModal();else toast('已进入沉浸模式；浏览器未开放系统全屏。');}
}
async function exitGameFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else if(document.webkitFullscreenElement)document.webkitExitFullscreen();}catch{}setImmersive(false);}
for(const event of ['fullscreenchange','webkitfullscreenchange'])document.addEventListener(event,()=>{if(!(document.fullscreenElement||document.webkitFullscreenElement)&&!isMobile)setImmersive(false);updateViewport();updateDisplayStatus();});
if(location.port==='8900')$('hall').href=`${location.protocol}//${location.hostname}:8780/`;else $('hall').href='/';
const toast=message=>{$('toast').textContent=message;$('toast').style.display='block';clearTimeout(toast.id);toast.id=setTimeout(()=>$('toast').style.display='none',4000);};
function send(data){if(ws?.readyState===1)ws.send(JSON.stringify(data));}
function tone(freq=440,duration=.12){if(muted)return;try{audio||=new AudioContext();audio.resume();const o=audio.createOscillator(),g=audio.createGain();o.type='sine';o.frequency.setValueAtTime(freq,audio.currentTime);o.frequency.exponentialRampToValueAtTime(freq*.6,audio.currentTime+duration);g.gain.setValueAtTime(.06,audio.currentTime);g.gain.exponentialRampToValueAtTime(.001,audio.currentTime+duration);o.connect(g).connect(audio.destination);o.start();o.stop(audio.currentTime+duration);}catch{}}
function connect(){ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}${location.pathname.startsWith('/starport/')?'/ws/starport':''}`);ws.onopen=()=>{reconnect=0;if(joined||joining||token)send({type:'join',token});};ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='joined'){role=m.role;joined=true;joining=false;token=m.token;try{localStorage.setItem('starport-token',token);}catch{}return;}if(m.type==='error'){joining=false;toast(m.message);return;}if(m.type==='state'||m.type==='hello'){const reset=!state||m.version!==state.version||m.game.deaths!==game.deaths||m.game.level!==game.level;state=m;game=m.game;if(reset){paintPlayers=game.players.map(p=>({...p}));camera=null;}if(game.deaths>lastDeath)tone(130,.3);if(game.won&&!lastWon){tone(700,.5);}lastDeath=game.deaths;lastWon=game.won;update();}};ws.onclose=e=>{keys={};if(e.code===4001){joined=false;token='';try{localStorage.removeItem('starport-token');}catch{}toast('此座位已在另一页面接回。');return;}if(joined){$('paused').classList.remove('hidden');$('pauseText').textContent='与空间站失去连接，正在自动重连…';}setTimeout(connect,Math.min(5000,500+reconnect++*500));};ws.onerror=()=>{};}
connect();
function update(){if(!state)return;const l=LEVELS[game.level],ready=state.seats.every(s=>s?.connected);$('welcome').classList.toggle('hidden',joined);$('waiting').classList.toggle('hidden',!joined||state.started);$('paused').classList.toggle('hidden',!joined||!state.started||!state.paused||game.won);$('victory').classList.toggle('hidden',!joined||!game.won);$('chapter').textContent=l.chapter;$('levelTitle').textContent=l.name;$('tip').textContent=l.tip;$('keyCount').textContent=`${game.keys.filter(Boolean).length} / 2`;$('gemCount').textContent=`${game.gems.filter(Boolean).length} / ${l.gems.length}`;const sec=Math.floor(game.time);$('timer').textContent=`${String(Math.floor(sec/60)).padStart(2,'0')}:${String(sec%60).padStart(2,'0')}`;
 if(joined){const name=role===0?'磁力搬运员':'时间侦察员';$('youAre').textContent=`你是${name}`;$('waitingText').textContent=ready?'两位已就位，准备好就出发。':'等另一位伙伴接入空间站…';$('start').disabled=!ready;$('start').textContent=ready?'开始维修 ↗':'等待伙伴';$('identity').innerHTML=`<span class="${role===0?'flame':'water'}">${role===0?'▣':'◉'} 你是${name}</span><span>${role===0?(game.players[0].carrying>=0?'E 放下货箱':'E 磁吸货箱'):(game.cooldown>0?`脉冲 ${Math.ceil(game.cooldown/60)} 秒后就绪`:'E 时间脉冲 · W 二段跳')}</span>`;$('seats').replaceChildren(...state.seats.map((s,i)=>{const el=document.createElement('div');el.className='seat';const b=document.createElement('b');b.style.color=i?'#81dbe4':'#ffbd7a';b.textContent=['▣ 搬运员','◉ 侦察员'][i];const small=document.createElement('span');small.textContent=s?.connected?'已接入'+(role===i?' · 你':''):s?'暂时离线':'等待接入';el.append(b,small);return el;}));}
 if(!joined)$('identity').innerHTML='<span class="flame">▣ 搬运员</span><span class="water">◉ 侦察员</span><span>等你们一起接入空间站</span>';
 if(game.won){$('winStars').textContent='★ '.repeat(stars(game))+'☆ '.repeat(3-stars(game));$('winTitle').textContent=game.level===7?'信号恢复。我们回家。':'这一舱段，重新上线。';$('winSummary').textContent=`用时 ${Math.floor(game.time/60)} 分 ${Math.floor(game.time%60)} 秒 · 失误 ${game.deaths} 次 · 数据 ${game.gems.filter(Boolean).length}/${l.gems.length}`;$('next').classList.toggle('hidden',game.level===7);}
 document.body.classList.toggle('playing',joined&&state.started&&!state.paused&&!game.won);$('hudRole').textContent=joined?(role===0?'▣ 磁力搬运员':'◉ 时间侦察员'):'星港维修队';$('hudRole').style.color=joined?(role===0?'#ffc17f':'#82e0e5'):'';$('hudLevel').textContent=`${String(game.level+1).padStart(2,'0')} / ${l.name}`;$('hudKeys').textContent=`组件 ${game.keys.filter(Boolean).length}/2`;$('hudTime').textContent=$('timer').textContent;$('abilityLabel').textContent=role===1?(game.cooldown>0?`${Math.ceil(game.cooldown/60)}秒`:'脉冲'):game.players[0].carrying>=0?'放下':'磁吸';
 document.querySelector('[data-key="action"]').classList.toggle('cooldown',role===1&&game.cooldown>0);
}
$('join').onclick=()=>{joining=true;if(ws?.readyState===1)send({type:'join',token});else toast('正在连接空间站，请稍候…');tone(500);};$('start').onclick=()=>{send({type:'start'});if(isMobile)enterGameFullscreen(false);};$('restart').onclick=()=>{if(joined)send({type:'restart'});else toast('先接入空间站，再开始关卡。');};$('replay').onclick=()=>send({type:'restart'});$('next').onclick=()=>send({type:'next'});
function leave(){inputTracker.clear();send({type:'leave'});joined=false;joining=false;token='';role=-1;keys={};try{localStorage.removeItem('starport-token');}catch{}update();}$('leave').onclick=leave;$('leavePaused').onclick=leave;
function openMap(){if(!state)return;const unlocked=state.progress.unlocked;$('mapGrid').replaceChildren(...LEVELS.map((l,i)=>{const b=document.createElement('button');b.className='map-card'+(i===game.level?' current':'');b.disabled=i>unlocked;const n=document.createElement('span');n.textContent=String(i+1).padStart(2,'0');const wrap=document.createElement('div'),title=document.createElement('strong'),sub=document.createElement('small');title.textContent=l.name;sub.textContent=i>unlocked?'尚未接通':state.progress.best[i]?'★'.repeat(state.progress.best[i].stars)+' · 已修复':'可挑战';wrap.append(title,sub);b.append(n,wrap);b.onclick=()=>{if(!joined){toast('先进入空间站选择你的角色。');return;}send({type:'select',level:i});$('map').close();};return b;}));$('map').showModal();}
$('levels').onclick=openMap;$('winMap').onclick=openMap;$('help').onclick=()=>$('rules').showModal();document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());document.querySelectorAll('dialog').forEach(d=>d.addEventListener('close',()=>{keys={};}));
$('exitFullscreen').onclick=exitGameFullscreen;
$('sound').onclick=()=>{muted=!muted;$('sound').textContent=muted?'♫ 音效关':'♫ 音效开';$('menuSound').textContent=$('sound').textContent;$('sound').setAttribute('aria-pressed',String(!muted));tone(550);};
$('fullscreen').onclick=()=>{if(document.fullscreenElement||document.webkitFullscreenElement||immersive)exitGameFullscreen();else enterGameFullscreen();};
$('overview').onclick=()=>setOverview(!overview);
$('gameMenuButton').onclick=()=>{releaseInputs();updateDisplayStatus();$('gameMenu').showModal();};
$('menuFullscreen').onclick=()=>{ $('gameMenu').close();if(document.fullscreenElement||document.webkitFullscreenElement)exitGameFullscreen();else enterGameFullscreen();};
$('menuOverview').onclick=()=>{setOverview(!overview);$('gameMenu').close();};
$('menuLevels').onclick=()=>{$('gameMenu').close();openMap();};
$('menuRestart').onclick=()=>{$('gameMenu').close();$('restart').click();};
$('menuHelp').onclick=()=>{$('gameMenu').close();$('rules').showModal();};
$('menuSound').onclick=()=>$('sound').click();
$('menuInstall').onclick=()=>{$('gameMenu').close();$('installHelp').showModal();};
$('menuLeave').onclick=()=>{leave();$('gameMenu').close();};
$('installWelcome').onclick=()=>$('installHelp').showModal();
const keyMap={KeyA:'left',ArrowLeft:'left',KeyD:'right',ArrowRight:'right',KeyW:'jump',ArrowUp:'jump',Space:'action',KeyE:'action'};
function flushInputs(){keys=inputTracker.state();document.querySelectorAll('[data-key]').forEach(b=>b.classList.toggle('pressed',!!keys[b.dataset.key]));send({type:'input',...keys});}
function releaseInputs(){inputTracker.clear();flushInputs();}
window.addEventListener('keydown',e=>{if(e.code==='Escape'&&immersive&&!document.querySelector('dialog[open]'))exitGameFullscreen();if(document.querySelector('dialog[open]'))return;const k=keyMap[e.code];if(k){e.preventDefault();inputTracker.keyDown(k);flushInputs();}});
window.addEventListener('keyup',e=>{const k=keyMap[e.code];if(k){e.preventDefault();inputTracker.keyUp(k);flushInputs();}});
window.addEventListener('blur',releaseInputs);document.addEventListener('visibilitychange',releaseInputs);window.addEventListener('pagehide',releaseInputs);
for(const b of document.querySelectorAll('[data-key]')){const k=b.dataset.key;
 b.addEventListener('pointerdown',e=>{if(!document.body.classList.contains('playing')||document.querySelector('dialog[open]'))return;e.preventDefault();try{b.setPointerCapture(e.pointerId);}catch{}inputTracker.down(e.pointerId,k);flushInputs();});
 for(const ev of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(ev,e=>{inputTracker.up(e.pointerId);flushInputs();});
 b.addEventListener('contextmenu',e=>e.preventDefault());
}
// Safari must never interpret a two-thumb control gesture as scrolling or zooming.
$('touch').addEventListener('touchmove',e=>e.preventDefault(),{passive:false});
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('close',releaseInputs));
setInterval(()=>{if(joined){keys=inputTracker.state();if(document.querySelector('dialog[open]'))keys={};send({type:'input',...keys});}},33);
const C=['#ffc17f','#82e0e5'];
function box(x,y,w,h,c,r=0){ctx.fillStyle=c;if(r){ctx.beginPath();if(ctx.roundRect)ctx.roundRect(x,y,w,h,r);else{const rr=Math.min(r,w/2,h/2);ctx.moveTo(x+rr,y);ctx.arcTo(x+w,y,x+w,y+h,rr);ctx.arcTo(x+w,y+h,x,y+h,rr);ctx.arcTo(x,y+h,x,y,rr);ctx.arcTo(x,y,x+w,y,rr);ctx.closePath();}ctx.fill();}else ctx.fillRect(x,y,w,h);}
function line(x,y,x2,y2,c,width=1){ctx.strokeStyle=c;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x2,y2);ctx.stroke();}
function text(s,x,y,c='#aec8c8',size=11,align='left'){ctx.fillStyle=c;ctx.font=`${size}px system-ui`;ctx.textAlign=align;ctx.fillText(s,x,y);}
function glow(x,y,r,c){const g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,c);g.addColorStop(1,'transparent');ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2);}
function diamond(x,y,r,c){ctx.fillStyle=c;ctx.beginPath();ctx.moveTo(x,y-r);ctx.lineTo(x+r,y);ctx.lineTo(x,y+r);ctx.lineTo(x-r,y);ctx.closePath();ctx.fill();}
function background(t){const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#101b29');g.addColorStop(.6,'#183740');g.addColorStop(1,'#12262c');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
 for(let i=0;i<80;i++){const x=(i*173.93)%W,y=(i*59.37)%480;box(x,y, i%8===0?2:1,1.4,`rgba(190,220,230,${.15+.35*(Math.sin(t/1700+i)+1)/2})`);}
 glow(820,185,290,'#427a8920');ctx.fillStyle='#2e555e';ctx.beginPath();ctx.arc(850,165,90,0,Math.PI*2);ctx.fill();ctx.fillStyle='#24404c';ctx.beginPath();ctx.arc(880,140,90,0,Math.PI*2);ctx.fill();
 for(let x=60;x<1200;x+=220){box(x,0,14,560,'#081b2470');box(x+14,0,4,560,'#49727a25');line(x+20,55,x+200,55,'#93bac01c');line(x+20,420,x+200,420,'#93bac01c');}
 ctx.strokeStyle='#5c8e9b1a';ctx.lineWidth=1;ctx.beginPath();ctx.ellipse(840,175,185,46,-.35,0,Math.PI*2);ctx.stroke();
 for(let i=0;i<5;i++){const x=i*250-80;box(x,465,180,110,'#0a202b');for(let k=0;k<7;k++)box(x+16+k*22,480,9,3,k%3===0?'#6dc7c350':'#51768530');box(x+22,506,135,31,'#14313b');}
 text('ORBITAL SERVICE / DECK '+String(game.level+1).padStart(2,'0'),35,35,'#83a5ad77',11);text('PRESSURE STABLE · LINK '+(state?.seats.every(s=>s?.connected)?'ONLINE':'STANDBY'),1165,35,'#83a5ad77',10,'right');
}
function platform(p,i,moving=false){box(p.x,p.y,p.w,p.h,'#203b43',3);box(p.x,p.y,p.w,4,moving?'#88d1d2':'#718b84');box(p.x+6,p.y+7,p.w-12,2,'#112a32');for(let x=p.x+15;x<p.x+p.w-8;x+=35)box(x,p.y+13,3,3,'#8ea19544');if(moving){glow(p.x+p.w/2,p.y+8,90,'#7fd9d524');for(let x=p.x+8;x<p.x+p.w;x+=16)line(x,p.y+20,x+6,p.y+26,'#7ed5da60',2);}}
function astronaut(p,i,t){const x=p.x,y=p.y,c=C[i],bob=p.ground?Math.sin(t/85)*Math.min(1,Math.abs(p.vx)):0;glow(x+12,y+20,42,c+'18');ctx.save();ctx.translate(x,y+bob);
 if(i===0){box(-5,14,7,17,'#bb8153',2);box(2,10,20,22,'#ecb575',5);box(0,0,24,19,'#edbf8d',7);}else{box(-5,16,7,13,'#5098a6',2);box(2,10,20,22,'#69b6c7',5);box(0,0,24,19,'#a4dbe1',9);}
 box(4,5,17,8,'#173441',4);box(7+(p.facing||1)*2,7,9,2,c,1);box(4,29,6,7,'#94a9a8',1);box(16,29,6,7,'#94a9a8',1);box(-3,20,6,8,c,2);box(22,20,5,8,c,2);line(12,0,12,-5,'#8babad',2);box(10,-7,4,3,c,1);
 if(i===0&&p.carrying>=0){ctx.strokeStyle='#ffc17f88';ctx.setLineDash([3,3]);ctx.strokeRect(-10,-45,44,43);ctx.setLineDash([]);}if(i===1&&!p.ground&&p.jumps===2){for(let k=0;k<3;k++)line(5+k*7,38,5+k*7,45+Math.sin(t/60+k)*4,'#91e7ef77',2);}
 ctx.restore();text(i===role?'你':i===0?'搬运':'侦察',x+12,y-15,c,10,'center');}
function drawNavigation(t){
 if(!isMobile||overview||!joined||!state?.started)return;
 const mw=Math.min(138,view.width*.29),mh=mw*660/1200,x=view.width-mw-14-(view.insets.right||0),y=view.insets.top+62;
 box(x-6,y-6,mw+12,mh+12,'#071b27cc',8);
 for(const [px,py,pw]of LEVELS[game.level].p)box(x+px/1200*mw,y+py/660*mh,Math.max(2,pw/1200*mw),2,'#799b98');
 line(x,y+560/660*mh,x+mw,y+560/660*mh,'#476667');
 LEVELS[game.level].keys.forEach(([kx,ky,r])=>{if(!game.keys[r])diamond(x+kx/1200*mw,y+ky/660*mh,3,C[r]);});
 game.players.forEach((p,i)=>{box(x+(p.x+p.w/2)/1200*mw-2,y+(p.y+p.h/2)/660*mh-2,5,5,C[i],i?2:0);});
 box(x+1050/1200*mw,y+(LEVELS[game.level].exitY-28)/660*mh,12,3,'#b9d5a5');
 ctx.strokeStyle='#b7d3cc77';ctx.lineWidth=1;ctx.strokeRect(x+Math.max(0,camera.x)/1200*mw,y+Math.max(0,camera.y)/660*mh,Math.min(mw,view.width/camera.scale/1200*mw),Math.min(mh,view.height/camera.scale/660*mh));
 text('你与伙伴',x+mw/2,y+mh+18,'#a1b9b7',9,'center');
 const r=Math.max(0,role),me=game.players[r],other=game.players[1-r],l=LEVELS[game.level];
 const target=game.keys[r]?{x:1076+r*64,y:l.exitY-30}: {x:l.keys.find(k=>k[2]===r)[0],y:l.keys.find(k=>k[2]===r)[1]};
 function marker(point,label,color,offset=0){const q=worldToScreen(point,camera);if(q.x>30&&q.x<view.width-30&&q.y>view.insets.top+54&&q.y<view.height-120-view.insets.bottom)return;
 const angle=Math.atan2(q.y-view.height*.45,q.x-view.width/2),cx=view.width/2,cy=view.height*.45;
 const limitX=view.width/2-34,limitY=Math.max(36,(view.height-view.insets.top-view.insets.bottom-174)/2),factor=Math.min(limitX/Math.max(.001,Math.abs(Math.cos(angle))),limitY/Math.max(.001,Math.abs(Math.sin(angle))));
 let sx=Math.max((view.insets.left||0)+26,Math.min(view.width-(view.insets.right||0)-26,cx+Math.cos(angle)*factor)),sy=Math.max(view.insets.top+64,Math.min(view.height-view.insets.bottom-126,cy+Math.sin(angle)*factor+offset));
 if(sx>view.width-mw-34&&sy<y+mh+34)sy=y+mh+38+offset;
 ctx.save();ctx.translate(sx,sy);ctx.rotate(angle);ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(8,0);ctx.lineTo(-3,-5);ctx.lineTo(-3,5);ctx.fill();ctx.restore();
 text(label,sx,sy+18,color,10,'center');}
 marker(target,game.keys[r]?'撤离':'组件',C[r]);marker({x:other.x+12,y:other.y+18},'伙伴',C[1-r],22);
}
function render(t){
 const dt=lastRender?t-lastRender:16;lastRender=t;
 ctx.setTransform(view.dpr,0,0,view.dpr,0,0);ctx.fillStyle='#101e27';ctx.fillRect(0,0,view.width,view.height);
 const target=cameraTarget({width:view.width,height:view.height,mobile:isMobile,overview,player:game.players[Math.max(0,role)],insets:view.insets});camera=smoothCamera(camera,target,dt);
 ctx.save();ctx.scale(camera.scale,camera.scale);ctx.translate(-camera.x,-camera.y);background(t);const l=LEVELS[game.level],ps=geometry(game);box(0,560,W,1200,'#10232b');box(0,560,W,5,'#6b8581');for(let x=10;x<W;x+=64){box(x,580,45,3,'#42606950');line(x,608,x+40,608,'#2c4b55');}text('DOCK '+String(game.level+1).padStart(2,'0')+' / MAINTENANCE ACCESS',35,637,'#54727d',11);
 for(let i=3;i<ps.length;i++){const p=ps[i],moving=i>=3+l.p.length;platform(p,i,moving);if(moving){const b=l.moving[i-3-l.p.length];line(p.x+p.w/2,b[1]+10,p.x+p.w/2,b[1]+b[5]-30,'#6cacb12a',2);}}
 for(const[x,y,w,h,type]of l.haz){const active=type!==0||game.tick%180<100,c=['#f0a467','#7ad1e4','#c29fe4'][type];box(x,y-2,w,h+4,'#14292f');for(let xx=x+4;xx<x+w-4;xx+=12){line(xx,y+1,xx+6,y+9,c+'55',2);if(active){const ht=type===0?22+Math.sin(t/80+xx)*8:12+Math.sin(t/90+xx)*5;line(xx,y,xx+Math.sin(t/120+xx)*4,y-ht,c+'99',2);}}if(active)glow(x+w/2,y,w*.65,c+'22');text(['间歇排气','高压电网','能量泄漏'][type],x+w/2,y+30,c+'bb',9,'center');}
 for(const[x,y,id,mode]of(l.plates||[])){const on=game.active[id]||game.latches[id];box(x,y,50,10,on?'#d3d9a3':'#6c7771',mode==='latch'?5:1);text(mode==='latch'?'接通供电':'持续承重',x+25,y-13,on?'#e4e8b6':'#91a6a1',9,'center');for(const g of(l.gates||[]).filter(g=>g[4]===id)){ctx.setLineDash([3,5]);line(x+25,y+10,g[0]+10,g[1]+g[3],'#bec79933');ctx.setLineDash([]);}}
 for(const[x,y,w,h,id]of(l.gates||[])){const on=game.active[id]||game.latches[id];box(x-3,y-4,w+6,5,'#98ac9b');box(x-3,y+h-1,w+6,5,'#98ac9b');if(!on){box(x,y,w,h,'#c9de9728');for(let yy=y+6;yy<y+h;yy+=10)line(x,yy,x+w,yy,'#e6e7a0a0',2);glow(x+w/2,y+h/2,50,'#dedb7922');}else text('ONLINE',x+w/2,y-13,'#cbdba5',9,'center');}
 for(const[x,y,id]of(l.levers||[])){box(x-8,y-20,20,27,'#314f54',4);box(x-4,y-14,12,12,game.latches[id]?'#b9ddaa':'#e0c888',3);text('解锁',x+2,y-29,'#d8d5ab',9,'center');}
 for(const c of game.crates){box(c.x,c.y,c.w,c.h,'#b18d60',4);box(c.x+4,c.y+4,c.w-8,c.h-8,'#685c49',2);line(c.x+6,c.y+6,c.x+30,c.y+30,'#c3a272',3);line(c.x+30,c.y+6,c.x+6,c.y+30,'#c3a272',3);box(c.x+13,c.y+13,10,10,'#dfc79b',2);}
 for(const[x,y,range,period]of(l.enemies||[])){const ex=x+(1-Math.cos((game.droneTick||0)/period*Math.PI*2))/2*range;line(x,y+14,x+range+27,y+14,'#bb9fe825');glow(ex+13,y+13,45,game.freeze?'#9be5ed30':'#b394dd24');box(ex,y+3,27,20,game.freeze?'#8ac8d4':'#a08bb8',7);box(ex+5,y+9,17,7,'#212e41',3);box(ex+10,y+11,8,3,game.freeze?'#a3f0f0':'#edbbdb');line(ex-4,y+26,ex+31,y+26,'#a7b9c080',2);}
 l.keys.forEach(([x,y,r])=>{if(game.keys[r])return;const yy=y+Math.sin(t/650+r)*3;glow(x,yy,45,C[r]+'30');ctx.save();ctx.translate(x,yy);ctx.rotate(Math.sin(t/1100)*.12);box(-13,-12,26,24,C[r],5);box(-8,-7,16,14,'#203744',2);box(-3,-3,6,6,C[r],1);ctx.restore();text(r===0?'动力组件':'导航芯片',x,yy-24,C[r],10,'center');});
 l.gems.forEach(([x,y,r],i)=>{if(game.gems[i])return;const yy=y+Math.sin(t/700+i)*3;glow(x,yy,20,C[r]+'16');diamond(x,yy,6,C[r]+'bb');diamond(x,yy,2,'#f6ffed');});
 // The shared extraction pad is one shuttle, with two crew positions.
 box(1034,l.exitY-9,137,9,'#718d86',3);for(let i=0;i<2;i++){const x=1055+i*64,y=l.exitY-56,c=C[i];const grad=ctx.createLinearGradient(x,y,x,y+55);grad.addColorStop(0,c+'00');grad.addColorStop(1,c+(game.keys[i]?'44':'14'));ctx.fillStyle=grad;ctx.fillRect(x,y,42,56);line(x,y+52,x+42,y+52,c,3);text(i?'◉':'▣',x+21,y+44,c,18,'center');}text(game.keys.every(Boolean)?'撤离系统已就绪':'等待动力 / 导航组件',1100,l.exitY-70,'#b6d3cc',10,'center');
 game.players.forEach((p,i)=>{let pp=paintPlayers[i]||p;if(Math.hypot(pp.x-p.x,pp.y-p.y)>160)pp={...p};pp={...p,x:pp.x+(p.x-pp.x)*.48,y:pp.y+(p.y-pp.y)*.48};paintPlayers[i]=pp;astronaut(pp,i,t);});
 if(game.freeze){ctx.strokeStyle='#8fe4ec44';ctx.lineWidth=2;ctx.beginPath();ctx.arc(game.players[1].x+12,game.players[1].y+18,30+(180-game.freeze)*3,0,Math.PI*2);ctx.stroke();text('TIME FIELD ACTIVE',W/2,74,'#a0e8ed',12,'center');}
 if(game.flash>0){ctx.fillStyle=`rgba(236,163,146,${game.flash/140})`;ctx.fillRect(0,0,W,H);}if(game.deaths>0)text('维修重试 '+game.deaths+' 次',1165,638,'#789297',10,'right');
 ctx.restore();drawNavigation(t);
 requestAnimationFrame(render);}
requestAnimationFrame(render);
