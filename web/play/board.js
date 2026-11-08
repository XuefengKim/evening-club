// Boards for the six board and logic games.
'use strict';
renderers.board=function(g,mine,fresh){
 const board=$('board'),area=$('actionArea');area.replaceChildren();board.className='board extra-board '+g.kind;board.onclick=null;
 if(g.board){
   const n=g.size,hex=g.kind==='hex';
   let html=g.kind==='reversi'?stats(g,'枚'):'';
   if(hex)html+='<p class="board-hint">● 连接上↕下 · ■ 连接左↔右</p>';
   html+='<div class="extra-grid '+(hex?'hex-grid':'')+'" style="--n:'+n+'">';
   for(let r=0;r<n;r++){
     if(hex)html+='<div class="hex-row" style="--row:'+r+'">';
     for(let c=0;c<n;c++){
       const v=g.board[r][c],legal=g.legal.some(p=>p[0]===r&&p[1]===c),last=g.last?.[0]===r&&g.last?.[1]===c,win=g.line.some(p=>p[0]===r&&p[1]===c);
       html+=`<button class="extra-cell ${v<0?'empty':'p'+v} ${last?'last':''} ${win?'won':''}" data-row="${r}" data-col="${c}" ${mine&&legal?'':'disabled'} aria-label="第 ${r+1} 行第 ${c+1} 列，${v<0?(legal?'可落子':'空位'):v===0?'圆形方':'方形方'}">${v<0?(g.kind==='reversi'&&legal?'·':''):v===0?'●':'■'}</button>`;
     }
     if(hex)html+='</div>';
   }
   board.innerHTML=html+'</div>';
   board.onclick=e=>{let b=e.target.closest('[data-row]');if(b&&!b.disabled)action({act:'place',row:Number(b.dataset.row),col:Number(b.dataset.col)})};
   area.innerHTML='<p class="board-hint">'+(g.kind==='reversi'?'点带小圆点的空位，夹住对方棋子。':g.kind==='hex'?(state.you===0?'你是 ●，从上向下连通。':'你是 ■，从左向右连通。'):'你是 '+(state.you===0?'● 圆形方':'■ 方形方')+'，点空位落子。')+'</p>';
 }else if(g.kind==='nim'){
   board.innerHTML='<div class="pile-list">'+g.piles.map((p,i)=>'<section class="pile"><b>第 '+(i+1)+' 堆 · '+p+' 颗</b><div class="pebbles">'+('● '.repeat(p)||'已取完')+'</div><div class="take-buttons">'+Array.from({length:p},(_,k)=>'<button class="small-button" data-pile="'+i+'" data-count="'+(k+1)+'" '+(mine?'':'disabled')+'>拿 '+(k+1)+'</button>').join('')+'</div></section>').join('')+'</div>';
   board.onclick=e=>{let b=e.target.closest('[data-pile]');if(b&&!b.disabled)action({act:'take',pile:Number(b.dataset.pile),count:Number(b.dataset.count)})};
   area.innerHTML='<p class="board-hint">每回合只拿一堆，拿到最后一颗获胜。</p>';
 }else if(g.kind==='code'){
   board.innerHTML='<div class="code-secret">'+(g.done?g.secret:'? ? ?')+'</div><p class="board-hint">0–5 · 三位不重复数字 · 可用 0 开头</p><div class="code-history">'+(g.history.length?g.history.map(h=>'<div class="code-entry"><span>'+(h.actor===state.you?'你':'对方')+'</span><b>'+h.guess+'</b><span>'+h.exact+' 位正确<br>'+h.near+' 位数字对、位置不同</span></div>').join(''):'<p class="board-hint">还没有线索，从一个组合开始吧。</p>')+'</div>';
   const f=document.createElement('form');f.className='number-form';
   const input=document.createElement('input');input.type='text';input.inputMode='numeric';input.maxLength=3;input.pattern='[0-5]{3}';input.required=true;input.placeholder='例如 024';input.disabled=!mine;input.setAttribute('aria-label','三个互不重复的 0 到 5 数字');
   const b=document.createElement('button');b.className='button coral';b.textContent='猜暗码';b.disabled=!mine;f.append(input,b);
   f.onsubmit=e=>{e.preventDefault();const guess=input.value.trim();if(!/^[0-5]{3}$/.test(guess)||new Set(guess).size!==3){toast('请输入三个互不重复的 0–5 数字');return}action({act:'guess',guess})};area.append(f);
 }
};
