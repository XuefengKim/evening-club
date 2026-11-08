// Three guided card games: crazy eights, palace, six-card golf.
'use strict';
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
function renderCards(g,mine,fresh){
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
   if(card&&!card.disabled){const c=Number(card.dataset.card);if(g.kind==='eights'){if(cardRank(c)===8){wildCard=c;$('suitDialog').showModal()}else action({act:'play',card:c})}else if(g.phase==='setup'){swapHand=swapHand===c?null:c;renderCards(g,mine,false)}else{selectCard(c);renderCards(g,mine,false)}}
   if(slot&&!slot.disabled){const c=Number(slot.dataset.up);if(g.phase==='setup'){if(swapHand===null){toast('先点下方一张手牌，再选要交换的明牌');return}action({act:'swap',hand:g.hand.indexOf(swapHand),slot:g.up[you].indexOf(c)})}else{selectCard(c);renderCards(g,mine,false)}}
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
   const b=document.createElement('button');b.className='button outline';b.textContent=discardMode?'改成：用这张牌替换':'这张不要：弃牌并翻一张暗牌';b.disabled=!mine;b.onclick=()=>{discardMode=!discardMode;renderCards(g,mine,false)};area.append(b)
 }
 if(g.closer!==null&&!g.done){const p=document.createElement('p');p.className='last-turn-note';p.textContent=g.closer===you?'对方走完最后一回合，就会自动结算。':'你的最后一回合，选好再替换。';area.append(p)}
}
for(const s of Object.keys(suitMarks)){const b=document.createElement('button');b.className='suit-choice '+s;b.textContent=suitMarks[s]+' '+suitNames[s];b.onclick=()=>{$('suitDialog').close();action({act:'play',card:wildCard,suit:s})};$('suitChoices').append(b)}
renderers.cards=renderCards;
