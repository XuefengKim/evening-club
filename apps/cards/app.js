'use strict';
const entryGame=location.hash.slice(1);
const $=id=>document.getElementById(id), motion=()=>!matchMedia('(prefers-reduced-motion: reduce)').matches;
const games={"eights": {"title": "疯狂八点", "en": "CRAZY EIGHTS", "icon": "8", "desc": "接花色，换方向感。把好牌留到最后？", "tags": ["接牌攻防", "接近 UNO"], "rules": ["这桌使用双人功能牌版：每人 7 张；同花色或同点数可接，8 随时换花色。", "Q 跳过对方；2 让对方摸两张并跳过，不叠加。摸一张即结束回合。", "剩一张自动提醒；功能牌可以收尾。起手为普通牌，牌库空时保留堆顶、重洗弃牌；无牌可摸且双方连续跳过时，剩余罚分低者胜（8=50、JQK=10、A=1）。"], "source": "https://www.pagat.com/eights/crazy8s.html"}, "palace": {"title": "宫殿牌", "en": "PALACE", "icon": "♜", "desc": "清手牌，出明牌，最后一张盲翻定胜负。", "tags": ["清堆反击", "三段闯关"], "rules": ["准备阶段可反复交换手牌和三张明牌，双方准备后开始。先手随机；先出手牌，牌库有牌时补到 3 张，再出明牌，最后盲翻底牌。", "点数接相同或更大；A 最大，2 万能重置，10 随时清堆，连续四张同点数也清堆并连走。可同时出多张同点数。", "手牌接不上可收整堆；明牌阶段先选一张加入整堆再收回，底牌盲翻接不上也连堆收回。三处的牌全出完者获胜。"], "source": "https://www.pagat.com/beating/shithead.html"}, "golf": {"title": "六张高尔夫", "en": "SIX CARD GOLF", "icon": "6", "desc": "分数越低越好。凑成一列，轻轻归零。", "tags": ["换牌取舍", "配对抵消"], "rules": ["单局快玩版：每人 2×3 六张暗牌，先各翻两张。每回合从牌库或弃牌堆拿一张，再替换自己任意一张。", "牌库摸来的牌可不要，但必须选一张暗牌亮出；拿来的弃牌必须替换。有人全部亮牌后，对方再走一个完整回合结算。", "同列两张同点数计 0；A=1、2=-2、3–10 按点数、JQ=10、K=0。总分低者胜，同分平局；一局结束，不打九轮。"], "source": "https://www.pagat.com/draw/golf.html"}};
const shapes=['✿','☾','✦','☂','♥','♧','☀','♫','♞','♜','⚓','✈','⌂','☕','⌛'], shapeNames=['花朵','月亮','星星','雨伞','爱心','叶片','太阳','音符','小马','城堡','船锚','飞机','房屋','咖啡','沙漏'];
const memoryLevels={1:[8,4,'初识'],2:[10,4,'熟悉'],3:[12,4,'挑战'],4:[15,5,'高手']};
const hands={rock:['✊','石头'],paper:['✋','布'],scissors:['✌','剪刀']};
let state=null,socket=null,ready=false,busy=false,browsing=false,selected='eights',pendingJoin='',reconnectTimer,retries=0,intentional=false,toastTimer,flashTimer;
let token=localStorage.getItem('club-unified-cards-token');if(!token){token=(crypto.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2))+Math.random().toString(36).slice(2);localStorage.setItem('club-unified-cards-token',token)}
const savedName=()=>localStorage.getItem('club-unified-cards-name')||'';
function toast(text){clearTimeout(toastTimer);$('toast').textContent=text;$('toast').classList.remove('hidden');toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),3500)}
function sound(kind){window.UnoAudio?.effect(kind)}
function unlock(){window.UnoAudio?.unlock()}
function updateAudio(){let a=UnoAudio.getSettings();$('fxLevel').value=a.fxLevel*100;$('bgmLevel').value=a.musicLevel*100;$('muteInput').checked=!a.enabled;$('musicButton').textContent=a.musicOn?'开启':'关闭';$('musicButton').setAttribute('aria-pressed',String(a.musicOn));$('soundButton').textContent=a.enabled?'♫':'♪';$('soundButton').setAttribute('aria-label',a.enabled?'声音设置':'声音设置，已静音')}
$('soundButton').onclick=()=>{unlock();let hidden=$('audioPanel').classList.toggle('hidden');$('soundButton').setAttribute('aria-expanded',String(!hidden))};
$('fxLevel').oninput=e=>{unlock();UnoAudio.configure({fxLevel:Number(e.target.value)/100})};$('fxLevel').onchange=()=>sound('tap');
$('bgmLevel').oninput=e=>{unlock();UnoAudio.configure({musicLevel:Number(e.target.value)/100})};
$('musicButton').onclick=()=>{unlock();let a=UnoAudio.getSettings();UnoAudio.configure({musicOn:!a.musicOn,...(!a.musicOn?{enabled:true}:{})});updateAudio()};
$('muteInput').onchange=e=>{unlock();UnoAudio.configure({enabled:!e.target.checked});updateAudio()};updateAudio();
document.addEventListener('click',e=>{if(!e.target.closest('#audioPanel')&&!e.target.closest('#soundButton')){$('audioPanel').classList.add('hidden');$('soundButton').setAttribute('aria-expanded','false')}});
function art(kind){return '<div class="extra-art">'+games[kind].icon+'</div>'}
for(let[k,g]of Object.entries(games)){let b=document.createElement('button');b.className='game-card';b.dataset.game=k;b.setAttribute('aria-label','玩'+g.title);b.innerHTML=`<div class="game-art ${k}" aria-hidden="true">${art(k)}</div><div class="card-content"><div class="card-top"><h3>${g.title}</h3><span class="card-arrow">↗</span></div><p>${g.desc}</p><div class="card-tags">${g.tags.map(t=>`<span>${t}</span>`).join('')}</div></div>`;$('gameGrid').append(b);let opt=document.createElement('option');opt.value=k;opt.textContent=g.title;$('gameSelect').append(opt)}
$('unoLink').href='/';
function showCreate(kind){selected=kind;let g=games[kind];$('createTitle').textContent=g.title;$('createDescription').textContent=g.desc;$('createIcon').textContent=g.icon;$('playerName').value=savedName();$('createDialog').showModal()}
$('gameGrid').onclick=e=>{let b=e.target.closest('[data-game]');if(b)showCreate(b.dataset.game)};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=() => $(b.dataset.close).close());
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target!==d)return;let r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}));
function net(text){$('connection').textContent='● '+text}
function connect(type,payload){if(socket&&socket.readyState<2){intentional=true;socket.close()}clearTimeout(reconnectTimer);intentional=false;ready=false;busy=true;net('连接中');let ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws/cards');socket=ws;ws.onopen=()=>{if(socket!==ws)return;ws.send(JSON.stringify({type,token,...payload}))};ws.onmessage=e=>{if(socket!==ws)return;let m;try{m=JSON.parse(e.data)}catch{return}if(m.type==='error'){busy=false;toast(m.message);if(!ready){intentional=true;clearTimeout(reconnectTimer);ws.close();if(type==='join'&&localStorage.getItem('club-unified-cards-room')===payload.room)localStorage.removeItem('club-unified-cards-room');state=null;showHall();$('joiningCode').textContent=m.message;$('createDescription').textContent=m.message;net('未入座')}return}if(m.type==='left'){state=null;ready=false;busy=false;intentional=true;localStorage.removeItem('club-unified-cards-room');ws.close();showHall();return}if(m.type==='state'){let prev=state;state=m;ready=true;busy=false;retries=0;net('已连接');localStorage.setItem('club-unified-cards-room',m.room);$('createDialog').close();$('nameDialog').close();render(prev)}};ws.onclose=e=>{if(socket!==ws)return;ready=false;busy=false;net(intentional?'双人联机':'连接断开');if(intentional||e.code===4001){if(e.code===4001)toast('这个座位已在另一个页面接入');return}if(state){render(state);let delay=Math.min(1000*2**retries++,6000);reconnectTimer=setTimeout(()=>connect('join',{room:state.room,name:savedName()}),delay)}else toast('连接失败，请检查网络连接，稍后重新加入')};ws.onerror=()=>net('连接异常')}
function send(msg){if(!ready||socket?.readyState!==1){toast('正在重新连接，请稍等');return false}socket.send(JSON.stringify(msg));return true}
function action(msg){if(busy)return;unlock();if(send({type:'act',...msg})){busy=true;setTimeout(()=>{busy=false},1400)}}
$('createForm').onsubmit=e=>{e.preventDefault();if(busy)return;unlock();localStorage.setItem('club-unified-cards-name',$('playerName').value.trim()||'玩家');connect('create',{game:selected,name:savedName()})};
let discoveryState=null;
async function refreshDiscovery(){if(state)return;try{let r=await fetch('api/table',{cache:'no-store'});if(!r.ok)throw Error();discoveryState=await r.json();let d=discoveryState;$('joinButton').disabled=!d.available||!d.canJoin;$('joinButton').textContent=d.available&&!d.canJoin?'稍等这一局':'加入';$('discoveryTitle').textContent=d.available?d.host+' 已经选了「'+games[d.game].title+'」':'还没人开局，选个喜欢的游戏吧。';$('discoveryNote').textContent=d.available?(d.canJoin?'点一下加入，马上坐到对方面前。':d.playing?'对方正在对局，结束后这里就能加入。':'两个人已经入座，回到原页面即可继续。'):'选下面任意一个游戏，对方就能在这里直接加入。'}catch{$('discoveryTitle').textContent='正在寻找对方的牌桌…';$('discoveryNote').textContent='请检查网络连接；服务唤醒可能需要约一分钟。';$('joinButton').disabled=true}}
$('joinButton').onclick=()=>{if(state){toast('你已经在这桌了，点击「回到牌桌」继续');return}unlock();let name=savedName()||'朋友';localStorage.setItem('club-unified-cards-name',name);connect('joinCurrent',{name})};
setInterval(refreshDiscovery,1500);refreshDiscovery();
$('nameForm').onsubmit=e=>{e.preventDefault();if(busy)return;unlock();localStorage.setItem('club-unified-cards-name',$('joinName').value.trim()||'玩家');connect('join',{room:pendingJoin,name:savedName()})};
$('startButton').onclick=$('againButton').onclick=()=>{unlock();send({type:'start'})};$('botButton').onclick=()=>send({type:'bot',enabled:!state.bot});$('gameSelect').onchange=e=>send({type:'game',game:e.target.value});
$('difficultySelect').onchange=e=>send({type:'difficulty',mode:e.target.value});$('resetProgress').onclick=()=>send({type:'resetProgress'});
function renderDifficulty(){let p=state.progression,visible=state.kind==='memory',active=state.game&&!state.game.done;$('difficultyPanel').classList.toggle('hidden',!visible);if(!visible)return;let level=active?state.game.level:p.nextMemoryLevel,config=memoryLevels[level],auto=p.memoryMode==='progressive';$('difficultySelect').value=p.memoryMode;$('difficultySelect').disabled=!state.host||active||!ready;$('difficultyTitle').textContent=(active?'本局':'下一局')+' · 第 '+level+' 阶 · '+config[2];$('difficultyDescription').textContent=(config[0]*2)+' 张牌 / '+config[0]+' 对 · '+config[1]+' 列排列';$('difficultyProgress').textContent=auto?(active?'本局结束才升级，错配展示固定 1.6 秒。':p.nextMemoryLevel===4?'已到最高第 4 阶，后续保持 15 对。':'完整玩完下一局后自动升一阶；退出不升级。'):'固定难度，后续保持这一阶。';$('resetProgress').classList.toggle('hidden',!state.host||active||!auto||!p.memoryCompleted);$('startButton').textContent='开始第 '+level+' 阶 ↗';$('againButton').textContent='下一局 · 第 '+p.nextMemoryLevel+' 阶 ↗';}

$('switchButton').onclick=()=>{if(!state.host)return;send({type:'game',game:state.kind})};
function leaveNow(){intentional=true;send({type:'leave'});$('leaveDialog').close()}
$('leaveButton').onclick=()=>{if(state?.game&&!state.game.done)$('leaveDialog').showModal();else leaveNow()};$('confirmLeave').onclick=leaveNow;
function showHall(){browsing=false;setTimeout(refreshDiscovery,0);document.body.classList.remove('in-room');$('roomView').classList.add('hidden');$('hall').classList.remove('hidden');$('homeButton').classList.add('hidden');history.replaceState(null,'',location.pathname);net('双人联机');window.scrollTo(0,0)}
$('homeButton').onclick=()=>{if(state){browsing=!browsing;$('roomView').classList.toggle('hidden',browsing);$('hall').classList.toggle('hidden',!browsing);$('homeButton').textContent=browsing?'回到牌桌':'游戏厅';window.scrollTo(0,0)}};
// Game cards during a session switch within the room after the current round.
$('gameGrid').onclick=e=>{let b=e.target.closest('[data-game]');if(!b)return;if(state){if(!state.host){toast('请发起人切换游戏');return}if(state.game&&!state.game.done){toast('先玩完这局，再切换游戏吧');return}browsing=false;send({type:'game',game:b.dataset.game});$('roomView').classList.remove('hidden');$('hall').classList.add('hidden');$('homeButton').textContent='游戏厅'}else showCreate(b.dataset.game)};
$('rulesButton').onclick=showHelp;

function participant(i){return state.players[i]?.name||'朋友'}
function canAct(){let g=state?.game;if(!g||g.done||state.paused||!ready)return false;if(g.kind==='memory'&&g.waiting)return false;if(g.kind==='rps')return !g.revealed&&!g.locked[state.you];return g.turn===state.you}
function playerBar(){let nodes=[];for(let i=0;i<2;i++){if(i===1){let score=document.createElement('div');score.className='room-score';score.textContent=state.wins[0]+' : '+state.wins[1];let small=document.createElement('small');small.textContent='今晚胜局';score.append(small);nodes.push(score)}let p=state.players[i],g=state.game,active=g&&!g.done&&!state.paused&&ready&&(g.kind==='rps'?!g.locked[i]:g.turn===i);let card=document.createElement('div');card.className='player-card p'+i+(active?' active':'')+(i===state.you?' is-me':'');let av=document.createElement('div');av.className='player-avatar';av.textContent=i===0?'●':'■';let text=document.createElement('div');text.className='player-text';let name=document.createElement('div');name.className='player-name';name.textContent=(p?.name||'等待朋友')+(p&&i===state.you?' · 你':'');let detail=document.createElement('div');detail.className='player-detail';detail.textContent=p?(p.bot?'人机练习':!p.online?'暂时离线':i===0?'发起人 · 圆形方':'朋友 · 方形方'):'等对方点「加入」';text.append(name,detail);card.append(av,text);nodes.push(card)}$('playerBar').replaceChildren(...nodes)}
function flash(){if(!motion())return;clearTimeout(flashTimer);$('turnFlash').classList.add('hidden');void $('turnFlash').offsetWidth;$('turnFlash').classList.remove('hidden');flashTimer=setTimeout(()=>$('turnFlash').classList.add('hidden'),1300)}
function confetti(){if(!motion())return;for(let i=0;i<45;i++){let e=document.createElement('i');e.className='confetti';e.style.left=Math.random()*100+'vw';e.style.background=['#ef9e7f','#f7d67b','#acd3bc'][i%3];e.style.animationDelay=Math.random()*.5+'s';document.body.append(e);setTimeout(()=>e.remove(),3500)}}
function render(prev){document.body.classList.add('in-room');$('hall').classList.toggle('hidden',!browsing);$('roomView').classList.toggle('hidden',browsing);$('homeButton').classList.remove('hidden');$('homeButton').textContent=browsing?'回到牌桌':'游戏厅';history.replaceState(null,'',location.pathname);let meta=games[state.kind];$('gameEyebrow').textContent=meta.en;$('gameTitle').textContent=meta.title;playerBar();$('startButton').textContent='开始这一局 ↗';$('againButton').textContent='再来一局 ↗';renderDifficulty();let g=state.game,lobby=!g;$('lobby').classList.toggle('hidden',!lobby);$('playArea').classList.toggle('hidden',lobby);$('hostSettings').classList.toggle('hidden',!state.host);$('startButton').classList.toggle('hidden',!state.host);$('startButton').disabled=state.players.length!==2||state.paused||!ready;$('gameSelect').value=state.kind;$('botButton').textContent=state.bot?'关闭人机，等朋友加入':'一个人？开启人机练习';$('botButton').disabled=state.players.length===2&&!state.bot;$('lobbyTitle').textContent=state.players.length===2?'这一桌，准备好了。':'这一局，等你就位。';$('lobbyNote').textContent=state.paused?'对方暂时断线，重新打开原页面就能接回。':state.players.length<2?'对方打开游戏厅，点「加入」就能坐下；也可以先和人机练习。':state.host?'开始吧，把这份快乐分成两半。':'发起人准备好后会开始游戏。';if(!prev||prev.kind!==state.kind||(!prev.game&&g)){requestAnimationFrame(()=>window.scrollTo(0,0))}if(!g)return;
let mine=canAct();$('playArea').classList.toggle('my-turn',mine);$('pausedPanel').classList.toggle('hidden',!state.paused&&ready);$('pausedPanel').textContent=ready?'朋友暂时断线，游戏已暂停。重新打开原页面即可接回。':'连接中断，正在自动重新接入，请稍等…';$('turnLabel').textContent=g.done?'这一局，收好。':!ready||state.paused?'稍等，正在等朋友':g.kind==='rps'?(g.revealed?'双方揭晓':mine?'锁定你的选择':'已锁定，等待揭晓'):mine?'● 轮到你了':participant(g.turn)+(state.players[g.turn]?.bot?' 正在思考…':' 的回合');$('turnSub').textContent=g.done?'谢谢你，陪我认真玩这一局。':g.kind==='rps'?'先赢 3 回合 · 选择相互保密':mine?'你的操作区已亮起，慢慢想，不着急。':'留意对方的选择，准备你的下一步。';$('gameNote').textContent=g.note;
let fresh=!prev?.game||g.move!==prev.game.move||g.kind!==prev.game.kind||prev.game.done&&!g.done;
renderBoard(g,mine,fresh);$('resultPanel').classList.toggle('hidden',!g.done);if(g.done){$('resultTitle').textContent=g.winner===-1?'默契平局。':g.winner===state.you?'漂亮，这局属于你。':participant(g.winner)+' 赢了这一局。';$('resultNote').textContent=g.winner===-1?'再来一局，把悬念留到下一次。':g.winner===state.you?'把胜利记在今晚，给对方一个翻盘的机会。':'好局，再试一次？';$('againButton').classList.toggle('hidden',!state.host);$('switchButton').classList.toggle('hidden',!state.host);if(!state.host)$('resultNote').textContent+=' 等发起人开始下一局或切换游戏。'}
if(fresh){if(g.done&&(!prev?.game?.done)){sound(g.winner===state.you?'win':g.winner===-1?'wild':'lose');if(g.winner===state.you)confetti()}else if(g.move>0){let map={drop:'play',flip:'tap',pair:'uno',roll:'draw',bust:'skip',bank:'deal',lock:'tap',reveal:'wild',safe:'turn',explode:'penalty',edge:'play',box:'uno',round:'turn',turn:'turn'};sound(map[g.event.kind]||'tap')}else sound('deal')}
let wasMine=prev?.game&&!prev.game.done&&!prev.paused&&(prev.game.kind==='rps'?!prev.game.locked[prev.you]&&!prev.game.revealed:prev.game.turn===prev.you);if(mine&&!wasMine){flash();sound('turn')}
}
function stats(g,unit){return `<div class="game-stats"><div><b>${g.scores[state.you]}</b><small>你 · ${unit}</small></div><div><b>${g.scores[1-state.you]}</b><small>对方 · ${unit}</small></div></div>`}
function button(text,act,klass='coral',disabled=false){let b=document.createElement('button');b.className='button '+klass;b.textContent=text;b.disabled=disabled;b.onclick=()=>action({act});return b}
let selectedCards=[],swapHand=null,discardMode=false,wildCard=null;
const suitMarks={spades:'♠',hearts:'♥',clubs:'♣',diamonds:'♦'}, suitNames={spades:'黑桃',hearts:'红桃',clubs:'梅花',diamonds:'方块'};
function cardRank(c){return c%13+1}
function cardSuit(c){return ['spades','hearts','clubs','diamonds'][Math.floor(c/13)]}
function cardLabel(c){return c===null?'暗牌':suitNames[cardSuit(c)]+({1:'A',11:'J',12:'Q',13:'K'}[cardRank(c)]||cardRank(c))}
function cardHTML(c,attrs='',extra='',badge=''){
 const hidden=c===null,mark=hidden?'✳':suitMarks[cardSuit(c)],rank=hidden?'':({1:'A',11:'J',12:'Q',13:'K'}[cardRank(c)]||cardRank(c));
 return `<button class="playing-card ${hidden?'card-back':cardSuit(c)} ${extra}" ${attrs} aria-label="${cardLabel(c)}${badge?'，'+badge:''}"><span class="card-corner">${rank}<small>${hidden?'':mark}</small></span><b>${mark}</b>${badge?`<span class="card-badge">${badge}</span>`:''}</button>`;
}
function guide(g,mine){
 if(g.done)return {title:'这一局，收好。',body:g.kind==='golf'?'已经全部亮牌。同列同点数已经归零，比较两个人的总分。':'你的手牌旅程结束了。可以再来一局，也可以换个游戏。',steps:[]};
 if(!mine)return {title:state.paused?'等朋友回来，牌桌已经暂停':'看看对方怎么出招',body:'轮到你时，可操作的牌和按钮会亮起来。',steps:[]};
 if(g.kind==='eights')return {title:g.legal.length?'点一张亮起的牌，接到中间':'这次接不上，摸一张牌',body:g.legal.length?'牌下方会告诉你为什么能出。打出 8 后，再选一个花色。':'点击「摸一张」。摸到的牌会放进手中，轮到对方。',steps:['看中间的牌','点亮起的手牌','8 可换花色']};
 if(g.kind==='palace'){
   if(g.phase==='setup')return {title:swapHand===null?'先点一张手牌，再换到明牌区':'现在点上面一张明牌，交换它们',body:'明牌会留到手牌出完后才使用。满意后点击「准备好了」。不想换也能直接准备。',steps:['选手牌','点明牌交换','准备好了']};
   const zone=g.zones[state.you];
   if(zone==='down')return {title:'最后一关：点一张底牌盲翻',body:'能接就打出去；接不上会连同整堆收回手中。牌没翻开前，谁都不知道是什么。',steps:['手牌已清空','明牌已清空','盲翻底牌']};
   if(zone==='up')return {title:'现在从明牌里出牌',body:'点相同点数可以一起出。暗掉的牌接不上，但仍可选：它会连同整堆收回手中。',steps:['手牌已清空','出明牌','再盲翻']};
   return {title:selectedCards.length?'选好了，点「打出所选」':g.legal.length?'选一张或多张同点数的亮牌':'接不上了，点击「收走整堆」',body:'接相同或更大的牌。2 能重置，10 能清堆再出一手。牌库有牌时，出完自动补到三张。',steps:['选亮牌','打出所选','看效果']};
 }
 if(g.phase==='setup')return {title:'先翻开自己的两张牌',body:'点你下方带亮边的暗牌。未知的牌不会提前显示，翻开前不用猜哪张更好。',steps:['翻第一张','再翻一张','开始换牌']};
 if(g.pending===null)return {title:g.closer!==null?'这是你的最后一个回合，选一张牌':'先选一张：摸牌库，或拿弃牌',body:'尽量让自己的分数变小。同一列凑成相同点数，整列就变成 0 分。',steps:['拿一张牌','选位置替换','低分获胜']};
 return {title:discardMode?'点一张暗牌亮出，摸来的牌会被弃掉':'点下方一张牌，用新牌替换它',body:discardMode?'只亮出，不替换。翻开后才知道它的分数。':'可以替换明牌，也可以替换暗牌；被换下的牌会交到中间。',steps:['已拿到新牌','点自己的牌','结束回合']};
}
function showHelp(){if(!state?.game)return;const hint=guide(state.game,canAct());$('ruleTitle').textContent=hint.title;$('ruleList').replaceChildren();const li=document.createElement('li');li.textContent=hint.body;$('ruleList').append(li);$('rulesDialog').showModal()}
function renderBoard(g,mine,fresh){
 if(fresh){selectedCards=[];swapHand=null;discardMode=false}
 const board=$('board'),area=$('actionArea');area.replaceChildren();board.className='board card-table '+g.kind;board.onclick=null;
 const hint=guide(g,mine);$('stepGuide').innerHTML='<div class="guide-heading"><span class="guide-dot">'+(mine?'↘':'◌')+'</span><div><b>'+hint.title+'</b><p>'+hint.body+'</p></div></div>'+(hint.steps.length?'<div class="guide-steps">'+hint.steps.map((s,i)=>'<span><i>'+(i+1)+'</i>'+s+'</span>').join('')+'</div>':'');
 if(g.phase==='setup'){$('turnSub').textContent='跟着亮边操作，不需要先背规则。';$('turnLabel').textContent=mine?'先做开局准备':'对方正在准备'}
 if(g.event.kind==='burn'&&fresh)sound('wild');
 if(g.kind==='golf'){renderGolf(g,mine,board,area);if(fresh)explainEffect(g);return}
 const you=state.you,other=1-you;
 const badge=c=>g.kind==='eights'?(cardRank(c)===8?'换花色':cardRank(c)===2?'对方摸 2':cardRank(c)===12?'跳过对方':cardSuit(c)===g.activeSuit?'同花色':'同点数'):(cardRank(c)===2?'重置':cardRank(c)===10?'清堆':cardRank(c)===1?'A 最大':'');
 let html='<div class="opponent-hand"><span>'+participant(other)+' · '+g.handCounts[other]+' 张手牌</span><div class="mini-backs">'+Array(Math.min(g.handCounts[other],12)).fill('<i>✳</i>').join('')+(g.handCounts[other]>12?'<small>+'+(g.handCounts[other]-12)+'</small>':'')+'</div></div>';
 if(g.kind==='palace')html+=palaceRows(g,other,false,mine);
 html+='<div class="table-center"><div class="stock-stack"><b>'+g.deckCount+'</b><small>牌库剩余</small></div><div class="discard-pile">'+(g.top===null?'<div class="empty-pile">空堆<br>任意起牌</div>':cardHTML(g.top,'disabled','top-card'))+'<small>桌面 '+g.pileCount+' 张</small></div>'+(g.kind==='eights'?'<div class="suit-status '+g.activeSuit+'"><b>'+suitMarks[g.activeSuit]+'</b><small>现在接'+suitNames[g.activeSuit]+'</small></div>':'<div class="stock-stack"><b>'+g.burnedCount+'</b><small>已清除</small></div>')+'</div>';
 if(g.kind==='palace')html+=palaceRows(g,you,true,mine);
 html+='<div class="your-hand-label">你的手牌 · '+g.hand.length+' 张'+(g.kind==='eights'&&g.hand.length===1?' · 最后一张！':'')+'</div><div class="card-hand">';
 for(const c of g.hand){const setup=g.kind==='palace'&&g.phase==='setup',enabled=mine&&(setup||g.legal.includes(c));html+=cardHTML(c,`data-card="${c}" ${enabled?'':'disabled'}`,((enabled?'can-play ':'')+(selectedCards.includes(c)||swapHand===c?'selected ':'')),setup?'点选交换':g.legal.includes(c)?badge(c):'接不上')}
 html+='</div>';board.innerHTML=html;
 board.onclick=e=>{
   const card=e.target.closest('[data-card]'),slot=e.target.closest('[data-up]'),blind=e.target.closest('[data-down]');
   if(card&&!card.disabled){const c=Number(card.dataset.card);if(g.kind==='eights'){if(cardRank(c)===8){wildCard=c;$('suitDialog').showModal()}else action({act:'play',card:c})}else if(g.phase==='setup'){swapHand=swapHand===c?null:c;renderBoard(g,mine,false)}else{selectCard(c);renderBoard(g,mine,false)}}
   if(slot&&!slot.disabled){const c=Number(slot.dataset.up);if(g.phase==='setup'){if(swapHand===null){toast('先点下方一张手牌，再选要交换的明牌');return}action({act:'swap',hand:g.hand.indexOf(swapHand),slot:g.up[you].indexOf(c)})}else{selectCard(c);renderBoard(g,mine,false)}}
   if(blind&&!blind.disabled)action({act:'play',slot:Number(blind.dataset.down)})
 };
 if(g.kind==='eights')area.append(button('摸一张 · 结束回合','draw',g.legal.length?'outline':'coral pulse-target',!mine));
 else if(g.phase==='setup')area.append(button('准备好了 ↗','ready','coral',!mine));
 else {
   const play=button('打出所选'+(selectedCards.length?' · '+selectedCards.length+' 张':''),'play','coral',!mine||!selectedCards.length);play.onclick=()=>action({act:'play',cards:selectedCards.slice()});area.append(play);
   if(g.zones[you]==='hand')area.append(button('收走整堆 · '+g.pileCount+' 张','pickup',g.legal.length?'outline':'coral pulse-target',!mine||!g.pileCount));
 }
 if(fresh)explainEffect(g);
 function selectCard(c){if(selectedCards.includes(c))selectedCards=selectedCards.filter(v=>v!==c);else{if(selectedCards.length&&cardRank(selectedCards[0])!==cardRank(c))selectedCards=[];selectedCards.push(c)}}
}
function explainEffect(g){
 if(!g.move||g.done)return;
 let text='',actor=g.event.actor;
 if(g.kind==='eights'&&g.event.kind==='play'){
   const rank=cardRank(g.event.card);
   if(rank===2)text=actor===state.you?'对方 +2 张 · 你继续':'你 +2 张 · 对方继续';
   if(rank===12)text=actor===state.you?'⊘ 跳过对方 · 你继续':'⊘ 跳过你 · 对方继续';
   if(rank===8)text='现在接 '+suitMarks[g.activeSuit]+' '+suitNames[g.activeSuit];
   if(rank===2&&motion()){
     const from=document.querySelector('.discard-pile')?.getBoundingClientRect(),target=document.querySelector(actor===state.you?'.opponent-hand':'.card-hand')?.getBoundingClientRect();
     if(from&&target)for(let i=0;i<2;i++){const c=document.createElement('i');c.className='effect-flying-card';c.textContent='✳';Object.assign(c.style,{left:from.left+'px',top:from.top+'px'});document.body.append(c);const a=c.animate([{transform:'translate(0,0)',opacity:1},{transform:`translate(${target.left+target.width/2-from.left}px,${target.top-from.top}px)`,opacity:0}],{duration:750,delay:i*180,easing:'ease-in-out'});a.onfinish=()=>c.remove()}
   }
 }
 if(g.kind==='palace'&&g.event.kind==='burn')text='✦ 清掉整堆 → 0 张 · 继续出牌';
 if(g.kind==='palace'&&g.event.kind==='penalty')text=actor===state.you?'收走整堆 → 回到手牌阶段':'对方收走整堆 → 由你起牌';
 if(g.kind==='golf'&&g.closer!==null)text='最后一回合 · 即将亮牌结算';
 if(!text)return;
 document.querySelector('.card-effect')?.remove();const node=document.createElement('div');node.className='card-effect';node.setAttribute('role','status');node.textContent=text;document.body.append(node);setTimeout(()=>node.remove(),2100);
}
function palaceRows(g,p,own,mine){
 const upActive=own&&mine&&(g.phase==='setup'?swapHand!==null:g.zones[p]==='up'),downActive=own&&mine&&g.phase==='play'&&g.zones[p]==='down';
 return '<div class="palace-zones '+(own?'own-zones':'')+'"><div class="zone-row"><small>'+(own?'你的':'对方')+'明牌</small><div class="three-cards">'+g.up[p].map(c=>c===null?'<div class="card-slot">✓</div>':cardHTML(c,`data-up="${c}" ${upActive?'':'disabled'}`,upActive?'can-play'+(selectedCards.includes(c)?' selected':''):'',own&&g.phase==='play'&&g.zones[p]==='up'&&!g.legal.includes(c)?'接不上会收堆':'')).join('')+'</div></div><div class="zone-row"><small>最后盲翻</small><div class="three-cards">'+g.down[p].map((exists,i)=>exists?cardHTML(null,`data-down="${i}" ${downActive?'':'disabled'}`,downActive?'can-play':''): '<div class="card-slot">✓</div>').join('')+'</div></div></div>';
}
function golfPoints(c){const r=cardRank(c);return r===2?-2:r===13?0:Math.min(r,10)}
function renderGolf(g,mine,board,area){
 const you=state.you,other=1-you;
 function layout(p,own){
   const cards=g.layouts[p],pairs=[0,1,2].filter(i=>cards[i]!==null&&cards[i+3]!==null&&cardRank(cards[i])===cardRank(cards[i+3]));
   return '<section class="golf-layout"><div class="layout-label">'+(own?'你':participant(other))+' · '+(g.done?'总分 ':'已亮牌小计 ')+g.scores[p]+'<small>'+(g.done?'':' 暗牌尚未计分')+'</small></div><div class="golf-grid">'+cards.map((c,i)=>{const enabled=own&&mine&&!g.done&&(g.phase==='setup'?c===null:g.pending!==null&&(!discardMode||c===null));return cardHTML(c,`data-slot="${i}" ${enabled?'':'disabled'}`,enabled?'can-play':'',pairs.includes(i%3)?'配对 0 分':c===null?(enabled?'点这里':''):golfPoints(c)+' 分')}).join('')+'</div></section>';
 }
 let html=layout(other,false)+'<div class="table-center"><div class="draw-zone"><button class="draw-stack '+(mine&&g.phase==='play'&&g.pending===null?'can-play':'')+'" data-source="deck" '+(mine&&g.phase==='play'&&g.pending===null?'':'disabled')+'>✳<small>摸牌库 · '+g.deckCount+'</small></button></div><div class="draw-zone">'+(g.top===null?'<div class="empty-pile">暂无弃牌</div>':cardHTML(g.top,`data-source="pile" ${mine&&g.phase==='play'&&g.pending===null?'':'disabled'}`,mine&&g.phase==='play'&&g.pending===null?'can-play':'','拿弃牌'))+'</div></div>';
 if(g.pending!==null)html+='<div class="pending-card"><span>你刚拿到</span>'+cardHTML(g.pending,'disabled','',golfPoints(g.pending)+' 分')+'<span>↓ 点下方选择位置</span></div>';
 html+=layout(you,true);board.innerHTML=html;
 board.onclick=e=>{const source=e.target.closest('[data-source]'),slot=e.target.closest('[data-slot]');if(source&&!source.disabled)action({act:'draw',source:source.dataset.source});if(slot&&!slot.disabled)action({act:g.phase==='setup'?'reveal':discardMode?'discard':'replace',slot:Number(slot.dataset.slot)})};
 if(g.pending!==null&&g.pendingSource==='deck'&&g.layouts[you].includes(null)){
   const b=document.createElement('button');b.className='button outline';b.textContent=discardMode?'改成：用这张牌替换':'这张不要：弃牌并翻一张暗牌';b.disabled=!mine;b.onclick=()=>{discardMode=!discardMode;renderBoard(g,mine,false)};area.append(b)
 }
 if(g.closer!==null&&!g.done){const p=document.createElement('p');p.className='last-turn-note';p.textContent=g.closer===you?'对方走完最后一回合，就会自动结算。':'你的最后一回合，选好再替换。';area.append(p)}
}
for(const s of Object.keys(suitMarks)){const b=document.createElement('button');b.className='suit-choice '+s;b.textContent=suitMarks[s]+' '+suitNames[s];b.onclick=()=>{$('suitDialog').close();action({act:'play',card:wildCard,suit:s})};$('suitChoices').append(b)}

// Reloads and brief Wi-Fi interruptions keep the same room and seat token.
history.replaceState(null,'',location.pathname);
let lastRoom=localStorage.getItem('club-unified-cards-room');if(lastRoom)connect('join',{room:lastRoom,name:savedName()});
window.addEventListener('online',()=>{if(state&&!ready){clearTimeout(reconnectTimer);connect('join',{room:state.room,name:savedName()})}});

if(games[entryGame]&&!lastRoom)showCreate(entryGame);
