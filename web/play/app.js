// Hall and table shell for the 15 head-to-head games: invite links, seats, reconnection, sound and turn flow.
// Each game family draws its own board in arcade.js, board.js or cards.js via renderers[family].
'use strict';
const $=id=>document.getElementById(id), motion=()=>!matchMedia('(prefers-reduced-motion: reduce)').matches;
const renderers={};
const memoryLevels={1:[8,4,'初识'],2:[10,4,'熟悉'],3:[12,4,'挑战'],4:[15,5,'高手']};
const ROOM_KEY='club-room';
let state=null,socket=null,ready=false,busy=false,browsing=false,selected='connect',pendingJoin='',reconnectTimer,retries=0,intentional=false,toastTimer,flashTimer;
const token=clubId();
const savedName=()=>localStorage.getItem('club-name')||localStorage.getItem('club-unified-name')||'';
const saveName=name=>localStorage.setItem('club-name',name);
function toast(text){clearTimeout(toastTimer);$('toast').textContent=text;$('toast').classList.remove('hidden');toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),3500)}
function sound(kind){window.UnoAudio?.effect(kind)}
function unlock(){window.UnoAudio?.unlock()}

// Sound panel
function updateAudio(){let a=UnoAudio.getSettings();$('fxLevel').value=a.fxLevel*100;$('bgmLevel').value=a.musicLevel*100;$('muteInput').checked=!a.enabled;$('musicButton').textContent=a.musicOn?'开启':'关闭';$('musicButton').setAttribute('aria-pressed',String(a.musicOn));$('soundButton').textContent=a.enabled?'♫':'♪';$('soundButton').setAttribute('aria-label',a.enabled?'声音设置':'声音设置，已静音')}
$('soundButton').onclick=()=>{unlock();let hidden=$('audioPanel').classList.toggle('hidden');$('soundButton').setAttribute('aria-expanded',String(!hidden))};
$('fxLevel').oninput=e=>{unlock();UnoAudio.configure({fxLevel:Number(e.target.value)/100})};$('fxLevel').onchange=()=>sound('tap');
$('bgmLevel').oninput=e=>{unlock();UnoAudio.configure({musicLevel:Number(e.target.value)/100})};
$('musicButton').onclick=()=>{unlock();let a=UnoAudio.getSettings();UnoAudio.configure({musicOn:!a.musicOn,...(!a.musicOn?{enabled:true}:{})});updateAudio()};
$('muteInput').onchange=e=>{unlock();UnoAudio.configure({enabled:!e.target.checked});updateAudio()};updateAudio();
document.addEventListener('click',e=>{if(!e.target.closest('#audioPanel')&&!e.target.closest('#soundButton')){$('audioPanel').classList.add('hidden');$('soundButton').setAttribute('aria-expanded','false')}});

// Hall: every game card comes from catalog.js
function art(kind){if(kind==='connect')return '<div class="art-mini-connect">'+Array(16).fill('<i></i>').join('')+'</div>';if(kind==='memory')return '<div class="art-mini-memory"><i>✿</i><i>☾</i><i>✿</i></div>';if(kind==='dice')return '<div class="art-mini-dice">⚄</div>';if(kind==='rps')return '<div class="art-mini-rps"><span>✌</span><small>vs</small><span>✊</span></div>';if(kind==='number')return '<div class="art-mini-number"><i>37</i><span>?</span><i>68</i></div>';if(kind==='boxes')return '<div class="art-mini-boxes">'+Array(16).fill('<i></i>').join('')+'</div>';return '<div class="extra-art">'+games[kind].icon+'</div>'}
function gameCard(k,g){let b=document.createElement('button');b.className='game-card';b.dataset.game=k;b.setAttribute('aria-label','玩'+g.title);b.innerHTML=`<div class="game-art ${k}" aria-hidden="true">${art(k)}</div><div class="card-content"><div class="card-top"><h3>${g.title}</h3><span class="card-arrow">↗</span></div><p>${g.desc}</p><div class="card-tags">${g.tags.map(t=>`<span>${t}</span>`).join('')}</div></div>`;return b}
const groups={duel:document.createElement('optgroup'),cards:document.createElement('optgroup')};groups.duel.label='对弈小游戏';groups.cards.label='纸牌';
for(let[k,g]of Object.entries(games)){let group=g.family==='cards'?'cards':'duel';$(group==='cards'?'cardGrid':'gameGrid').append(gameCard(k,g));let opt=document.createElement('option');opt.value=k;opt.textContent=g.title;groups[group].append(opt)}
$('gameSelect').append(groups.duel,groups.cards);

function showCreate(kind){selected=kind;let g=games[kind];$('createTitle').textContent=g.title;$('createDescription').textContent=g.desc;$('createIcon').textContent=g.icon;$('playerName').value=savedName();$('createDialog').showModal()}
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=() => $(b.dataset.close).close());
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target!==d)return;let r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}));
function net(text){$('connection').textContent='● '+text}

// Connection: create a table, or join one from an invite link; reloads keep the same seat token.
function forgetRoom(){localStorage.removeItem(ROOM_KEY);history.replaceState(null,'','/')}
function connect(type,payload){if(socket&&socket.readyState<2){intentional=true;socket.close()}clearTimeout(reconnectTimer);intentional=false;ready=false;busy=true;net('连接中');let ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws/table');socket=ws;ws.onopen=()=>{if(socket!==ws)return;ws.send(JSON.stringify({type,token,...payload}))};ws.onmessage=e=>{if(socket!==ws)return;let m;try{m=JSON.parse(e.data)}catch{return}if(m.type==='error'){busy=false;toast(m.message);if(!ready){intentional=true;clearTimeout(reconnectTimer);ws.close();if(type==='join'&&localStorage.getItem(ROOM_KEY)===payload.room)forgetRoom();state=null;showHall();$('joiningCode').textContent=m.message;$('createDescription').textContent=m.message;$('codeNote').textContent=m.message;net('未入座')}return}if(m.type==='left'){state=null;ready=false;busy=false;intentional=true;forgetRoom();ws.close();showHall();return}if(m.type==='state'){let prev=state;state=m;ready=true;busy=false;retries=0;net('已连接');localStorage.setItem(ROOM_KEY,m.room);$('createDialog').close();$('nameDialog').close();render(prev)}};ws.onclose=e=>{if(socket!==ws)return;ready=false;busy=false;net(intentional?'双人联机':'连接断开');if(intentional||e.code===4001){if(e.code===4001)toast('这个座位已在另一个页面接入');return}if(state){render(state);let delay=Math.min(1000*2**retries++,6000);reconnectTimer=setTimeout(()=>connect('join',{room:state.room,name:savedName()}),delay)}else toast('连接失败，请检查网络连接，稍后重新加入')};ws.onerror=()=>net('连接异常')}
function send(msg){if(!ready||socket?.readyState!==1){toast('正在重新连接，请稍等');return false}socket.send(JSON.stringify(msg));return true}
function action(msg){if(busy)return;unlock();if(send({type:'act',...msg})){busy=true;setTimeout(()=>{busy=false},1400)}}
$('createForm').onsubmit=e=>{e.preventDefault();if(busy)return;unlock();saveName($('playerName').value.trim()||'玩家');connect('create',{game:selected,name:savedName()})};
$('nameForm').onsubmit=e=>{e.preventDefault();if(busy)return;unlock();saveName($('joinName').value.trim()||'玩家');connect('join',{room:pendingJoin,name:savedName()})};
function askToJoin(code){pendingJoin=code;$('joiningCode').textContent='房间 '+code+' · 朋友在等你入座。';$('joinName').value=savedName();$('nameDialog').showModal()}
$('codeForm').onsubmit=e=>{e.preventDefault();let code=$('codeInput').value.trim().toUpperCase();if(!/^[0-9A-Z]{4}$/.test(code)){$('codeNote').textContent='房间码是 4 位字母或数字，在朋友的邀请链接末尾。';return}location.href='/r/'+code};
function showInvite(){let link=clubInvite('/',state.room);$('inviteLink').textContent=link;$('inviteCode').textContent=state.room}
$('copyInvite').onclick=async()=>{toast(await clubCopy(clubInvite('/',state.room))?'邀请链接已复制，发给朋友吧':'复制没有成功，请长按链接手动复制')};

// Room controls
$('startButton').onclick=$('againButton').onclick=()=>{unlock();send({type:'start'})};$('botButton').onclick=()=>send({type:'bot',enabled:!state.bot});$('gameSelect').onchange=e=>send({type:'game',game:e.target.value});
$('difficultySelect').onchange=e=>send({type:'difficulty',mode:e.target.value});$('resetProgress').onclick=()=>send({type:'resetProgress'});
function renderDifficulty(){let p=state.progression,visible=state.kind==='memory',active=state.game&&!state.game.done;$('difficultyPanel').classList.toggle('hidden',!visible);if(!visible)return;let level=active?state.game.level:p.nextMemoryLevel,config=memoryLevels[level],auto=p.memoryMode==='progressive';$('difficultySelect').value=p.memoryMode;$('difficultySelect').disabled=!state.host||active||!ready;$('difficultyTitle').textContent=(active?'本局':'下一局')+' · 第 '+level+' 阶 · '+config[2];$('difficultyDescription').textContent=(config[0]*2)+' 张牌 / '+config[0]+' 对 · '+config[1]+' 列排列';$('difficultyProgress').textContent=auto?(active?'本局结束才升级，错配展示固定 1.6 秒。':p.nextMemoryLevel===4?'已到最高第 4 阶，后续保持 15 对。':'完整玩完下一局后自动升一阶；退出不升级。'):'固定难度，后续保持这一阶。';$('resetProgress').classList.toggle('hidden',!state.host||active||!auto||!p.memoryCompleted);$('startButton').textContent='开始第 '+level+' 阶 ↗';$('againButton').textContent='下一局 · 第 '+p.nextMemoryLevel+' 阶 ↗';}
$('switchButton').onclick=()=>{if(!state.host)return;send({type:'game',game:state.kind})};
function leaveNow(){intentional=true;send({type:'leave'});$('leaveDialog').close()}
$('leaveButton').onclick=()=>{if(state?.game&&!state.game.done)$('leaveDialog').showModal();else leaveNow()};$('confirmLeave').onclick=leaveNow;
function showHall(){browsing=false;document.body.classList.remove('in-room');$('roomView').classList.add('hidden');$('hall').classList.remove('hidden');$('homeButton').classList.add('hidden');net('双人联机');window.scrollTo(0,0)}
$('homeButton').onclick=()=>{if(state){browsing=!browsing;$('roomView').classList.toggle('hidden',browsing);$('hall').classList.toggle('hidden',!browsing);$('homeButton').textContent=browsing?'回到牌桌':'游戏厅';window.scrollTo(0,0)}};
// Game cards during a session switch within the room after the current round.
document.querySelectorAll('.game-grid').forEach(grid=>grid.addEventListener('click',e=>{let b=e.target.closest('[data-game]');if(!b)return;if(state){if(!state.host){toast('请发起人切换游戏');return}if(state.game&&!state.game.done){toast('先玩完这局，再切换游戏吧');return}browsing=false;send({type:'game',game:b.dataset.game});$('roomView').classList.remove('hidden');$('hall').classList.add('hidden');$('homeButton').textContent='游戏厅'}else showCreate(b.dataset.game)}));
document.querySelectorAll('[data-away]').forEach(a=>a.addEventListener('click',e=>{if(state?.game&&!state.game.done){e.preventDefault();toast('先玩完这局，再去'+a.dataset.away+'吧')}}));
$('rulesButton').onclick=()=>{if(games[state.kind].family==='cards'){showHelp();return}let g=games[state.kind];$('ruleTitle').textContent=g.title;$('ruleList').replaceChildren(...g.rules.map(t=>{let li=document.createElement('li');li.textContent=t;return li}));$('rulesDialog').showModal()};

// Table rendering
function participant(i){return state.players[i]?.name||'朋友'}
// Names come from other players: escape before putting them into HTML strings.
function esc(text){return String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function canAct(){let g=state?.game;if(!g||g.done||state.paused||!ready)return false;if(g.kind==='memory'&&g.waiting)return false;if(g.kind==='rps')return !g.revealed&&!g.locked[state.you];return g.turn===state.you}
function playerBar(){let nodes=[];for(let i=0;i<2;i++){if(i===1){let score=document.createElement('div');score.className='room-score';score.textContent=state.wins[0]+' : '+state.wins[1];let small=document.createElement('small');small.textContent='今晚胜局';score.append(small);nodes.push(score)}let p=state.players[i],g=state.game,active=g&&!g.done&&!state.paused&&ready&&(g.kind==='rps'?!g.locked[i]:g.turn===i);let card=document.createElement('div');card.className='player-card p'+i+(active?' active':'')+(i===state.you?' is-me':'');let av=document.createElement('div');av.className='player-avatar';av.textContent=i===0?'●':'■';let text=document.createElement('div');text.className='player-text';let name=document.createElement('div');name.className='player-name';name.textContent=(p?.name||'等待朋友')+(p&&i===state.you?' · 你':'');let detail=document.createElement('div');detail.className='player-detail';detail.textContent=p?(p.bot?'人机练习':!p.online?'暂时离线':i===0?'发起人 · 圆形方':'朋友 · 方形方'):'等朋友打开邀请链接';text.append(name,detail);card.append(av,text);nodes.push(card)}$('playerBar').replaceChildren(...nodes)}
function flash(){if(!motion())return;clearTimeout(flashTimer);$('turnFlash').classList.add('hidden');void $('turnFlash').offsetWidth;$('turnFlash').classList.remove('hidden');flashTimer=setTimeout(()=>$('turnFlash').classList.add('hidden'),1300)}
function confetti(){if(!motion())return;for(let i=0;i<45;i++){let e=document.createElement('i');e.className='confetti';e.style.left=Math.random()*100+'vw';e.style.background=['#ef9e7f','#f7d67b','#acd3bc'][i%3];e.style.animationDelay=Math.random()*.5+'s';document.body.append(e);setTimeout(()=>e.remove(),3500)}}
function render(prev){let meta=games[state.kind],cards=meta.family==='cards';document.body.classList.add('in-room');document.body.classList.toggle('card-room',cards);$('hall').classList.toggle('hidden',!browsing);$('roomView').classList.toggle('hidden',browsing);$('homeButton').classList.remove('hidden');$('homeButton').textContent=browsing?'回到牌桌':'游戏厅';history.replaceState(null,'','/?r='+state.room);$('tableLabel').textContent='房间 '+state.room+' · 双人牌桌';$('gameEyebrow').textContent=meta.en;$('gameTitle').textContent=meta.title;$('rulesButton').textContent=cards?'? 帮我一下':'? 玩法';$('rulesNote').textContent=cards?'只需跟着亮起的操作走，牌桌会告诉你下一步。':'本游戏厅采用页面中说明的简化规则，以电脑判定为准。';$('stepGuide').classList.toggle('hidden',!cards);playerBar();$('startButton').textContent='开始这一局 ↗';$('againButton').textContent='再来一局 ↗';renderDifficulty();showInvite();let g=state.game,lobby=!g,waiting=state.players.length<2||state.bot;$('lobby').classList.toggle('hidden',!lobby);$('playArea').classList.toggle('hidden',lobby);$('invitePanel').classList.toggle('hidden',!waiting);$('hostSettings').classList.toggle('hidden',!state.host);$('startButton').classList.toggle('hidden',!state.host);$('startButton').disabled=state.players.length!==2||state.paused||!ready;$('gameSelect').value=state.kind;$('botButton').textContent=state.bot?'关闭人机，等朋友加入':'一个人？开启人机练习';$('botButton').disabled=state.players.length===2&&!state.bot;$('lobbyTitle').textContent=state.players.length===2?'这一桌，准备好了。':'这一局，等你就位。';$('lobbyNote').textContent=state.paused?'对方暂时断线，重新打开原页面就能接回。':state.players.length<2?'把邀请链接发给朋友，打开就能坐下；也可以先和人机练习。':state.host?'开始吧，把这份快乐分成两半。':'发起人准备好后会开始游戏。';if(!prev||prev.kind!==state.kind||(!prev.game&&g)){requestAnimationFrame(()=>window.scrollTo(0,0))}if(!g)return;
let mine=canAct();$('playArea').classList.toggle('my-turn',mine);$('pausedPanel').classList.toggle('hidden',!state.paused&&ready);$('pausedPanel').textContent=ready?'朋友暂时断线，游戏已暂停。重新打开原页面即可接回。':'连接中断，正在自动重新接入，请稍等…';$('turnLabel').textContent=g.done?'这一局，收好。':!ready||state.paused?'稍等，正在等朋友':g.kind==='rps'?(g.revealed?'双方揭晓':mine?'锁定你的选择':'已锁定，等待揭晓'):mine?'● 轮到你了':participant(g.turn)+(state.players[g.turn]?.bot?' 正在思考…':' 的回合');$('turnSub').textContent=g.done?'谢谢你，陪我认真玩这一局。':g.kind==='rps'?'先赢 3 回合 · 选择相互保密':mine?'你的操作区已亮起，慢慢想，不着急。':'留意对方的选择，准备你的下一步。';$('gameNote').textContent=g.note;
let fresh=!prev?.game||g.move!==prev.game.move||g.kind!==prev.game.kind||prev.game.done&&!g.done;
renderers[meta.family](g,mine,fresh);$('resultPanel').classList.toggle('hidden',!g.done);if(g.done){$('resultTitle').textContent=g.winner===-1?'默契平局。':g.winner===state.you?'漂亮，这局属于你。':participant(g.winner)+' 赢了这一局。';$('resultNote').textContent=g.winner===-1?'再来一局，把悬念留到下一次。':g.winner===state.you?'把胜利记在今晚，给对方一个翻盘的机会。':'好局，再试一次？';$('againButton').classList.toggle('hidden',!state.host);$('switchButton').classList.toggle('hidden',!state.host);if(!state.host)$('resultNote').textContent+=' 等发起人开始下一局或切换游戏。'}
if(fresh){if(g.done&&(!prev?.game?.done)){sound(g.winner===state.you?'win':g.winner===-1?'wild':'lose');if(g.winner===state.you)confetti()}else if(g.move>0){let map={drop:'play',flip:'tap',pair:'uno',roll:'draw',bust:'skip',bank:'deal',lock:'tap',reveal:'wild',safe:'turn',explode:'penalty',edge:'play',box:'uno',round:'turn',turn:'turn'};sound(map[g.event.kind]||'tap')}else sound('deal')}
let wasMine=prev?.game&&!prev.game.done&&!prev.paused&&(prev.game.kind==='rps'?!prev.game.locked[prev.you]&&!prev.game.revealed:prev.game.turn===prev.you);if(mine&&!wasMine){flash();sound('turn')}
}
function stats(g,unit){return `<div class="game-stats"><div><b>${g.scores[state.you]}</b><small>你 · ${unit}</small></div><div><b>${g.scores[1-state.you]}</b><small>对方 · ${unit}</small></div></div>`}
function button(text,act,klass='coral',disabled=false){let b=document.createElement('button');b.className='button '+klass;b.textContent=text;b.disabled=disabled;b.onclick=()=>action({act});return b}

// Entry: an invite link joins that table; otherwise reconnect to the last table or open the chosen game.
window.addEventListener('online',()=>{if(state&&!ready){clearTimeout(reconnectTimer);connect('join',{room:state.room,name:savedName()})}});
window.addEventListener('DOMContentLoaded',()=>{
 let params=new URLSearchParams(location.search),invited=clubRoomParam(),lastRoom=localStorage.getItem(ROOM_KEY),missing=(params.get('missing')||'').toUpperCase();
 let entry=location.pathname.match(/^\/play\/([a-z]+)$/)?.[1]||location.hash.slice(1);
 if(missing)$('codeNote').textContent='没有找到房间 '+missing+'，可能已经结束了。请让朋友重新发一次邀请链接。';
 if(invited&&invited!==lastRoom){history.replaceState(null,'','/');askToJoin(invited);return}
 if(lastRoom){connect('join',{room:lastRoom,name:savedName()});return}
 history.replaceState(null,'','/');
 if(games[entry])showCreate(entry);
});
