// Starport Crew rooms. Runs privately on the loopback interface behind the Python app,
// which serves the browser files and relays /ws/starport here.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes,randomInt} from 'node:crypto';
import {WebSocketServer,WebSocket} from 'ws';
import {createGame,step,LEVELS,stars} from '../web/starport/engine.mjs';

const root=path.dirname(fileURLToPath(import.meta.url)),port=Number(process.env.PORT||8900);
const progressPath=process.env.PROGRESS_FILE||path.join(root,'..','.data','starport-progress.json');
// A crew that played keeps a dropped seat for 5 minutes; a room nobody started is reclaimed after 2.
const ALPHABET='23456789ABCDEFGHJKLMNPQRSTUVWXYZ',MAX_ROOMS=2000,SEAT_GRACE=300000,UNSTARTED_GRACE=120000;
const ROLE_NAMES=['搬运员','侦察员'];

// Progress belongs to each player's anonymous browser id, so both partners keep what they unlock.
// Installs from the LAN version kept one shared {unlocked,best}; it stays as a floor for every crew on that install.
let saved={players:{}};
try{const p=JSON.parse(fs.readFileSync(progressPath));if(p&&typeof p.players==='object')saved={players:p.players,legacy:p.legacy||null};else if(p&&Number.isInteger(p.unlocked))saved={players:{},legacy:{unlocked:p.unlocked,best:p.best||{}}};}catch{}
let saveTimer=null;
function save(){clearTimeout(saveTimer);saveTimer=setTimeout(()=>{fs.mkdirSync(path.dirname(progressPath),{recursive:true});fs.writeFileSync(progressPath+'.tmp',JSON.stringify(saved));fs.renameSync(progressPath+'.tmp',progressPath);},300);}
const validPlayer=id=>typeof id==='string'&&/^[0-9a-f]{16,64}$/.test(id)?id:null;
function record(id){return saved.players[id]||{unlocked:0,best:{}};}
const better=(a,b)=>!b||a.stars>b.stars||a.stars===b.stars&&a.time<b.time;
function merged(room){
 const out={unlocked:0,best:{}};
 for(const r of[saved.legacy,...room.seats.map(s=>s?.player?record(s.player):null)]){if(!r)continue;out.unlocked=Math.max(out.unlocked,Math.min(LEVELS.length-1,r.unlocked|0));for(const[k,v]of Object.entries(r.best||{}))if(better(v,out.best[k]))out.best[k]=v;}
 return out;
}
function credit(room){
 const game=room.game,rank=stars(game),entry={stars:rank,time:game.time,deaths:game.deaths};
 for(const s of room.seats){if(!s?.player)continue;const r=record(s.player);r.unlocked=Math.max(r.unlocked|0,Math.min(LEVELS.length-1,game.level+1));r.best={...(r.best||{})};if(better(entry,r.best[game.level]))r.best[game.level]=entry;saved.players[s.player]=r;}
 save();
}

const rooms=new Map();
function newCode(){let code;do code='S'+Array.from({length:3},()=>ALPHABET[randomInt(ALPHABET.length)]).join('');while(rooms.has(code));return code;}
function makeRoom(){const room={code:newCode(),game:createGame(),seats:[null,null],started:false,played:false,inputs:[{},{}],lastSeen:[0,0],version:0,tick:0};rooms.set(room.code,room);return room;}
function preview(player){const id=validPlayer(player);return{type:'hello',room:null,game:createGame(),progress:merged({seats:[id?{player:id}:null]}),seats:[null,null],started:false,paused:false,version:0};}
const publicSeat=s=>s?{connected:!!s.ws,name:s.name}:null;
const snapshot=room=>({type:'state',room:room.code,game:room.game,progress:merged(room),seats:room.seats.map(publicSeat),started:room.started,paused:!room.seats.every(s=>s?.ws),version:room.version});
const send=(ws,data)=>{if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(data));};
function broadcast(room){const d=JSON.stringify(snapshot(room));for(const s of room.seats)if(s?.ws?.readyState===WebSocket.OPEN&&s.ws.bufferedAmount<150000)s.ws.send(d);}
function dropIfEmpty(room){if(room.seats.every(s=>!s))rooms.delete(room.code);}

const server=http.createServer((req,res)=>{
 if(new URL(req.url,'http://localhost').pathname==='/health'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({ok:true,rooms:rooms.size}));return;}
 res.writeHead(404);res.end('Not found');
});
const wss=new WebSocketServer({server,maxPayload:4096});
wss.on('connection',(ws,req)=>{
 if(req.headers.origin){try{if(new URL(req.headers.origin).host!==req.headers.host){ws.close(1008,'Origin mismatch');return;}}catch{ws.close();return;}}
 let room=null,role=-1,count=0,windowStart=Date.now(),misses=0;
 const seat=()=>room&&role>=0?room.seats[role]:null;
 function take(target,index,m){
  const old=target.seats[index];
  if(old?.ws&&old.ws!==ws)old.ws.close(4001,'Connected elsewhere');
  target.seats[index]={token:old?.token||randomBytes(24).toString('hex'),ws,name:String(m.name||old?.name||ROLE_NAMES[index]).slice(0,12),player:validPlayer(m.player)||old?.player||null};
  room=target;role=index;room.inputs[role]={};
  send(ws,{type:'joined',role,token:room.seats[role].token,room:room.code});broadcast(room);
 }
 ws.on('message',raw=>{try{
  if(Date.now()-windowStart>1000){count=0;windowStart=Date.now();}if(++count>100)return;
  const m=JSON.parse(raw);
  // Before taking a seat, a page may ask for this browser's own progress (stage map on the welcome screen).
  if(m.type==='hello'){if(!seat())send(ws,preview(m.player));return;}
  if(m.type==='create'){
   if(seat())return;
   if(rooms.size>=MAX_ROOMS){send(ws,{type:'error',message:'现在开着的维修舱太多了，请稍后再试。'});return;}
   take(makeRoom(),0,m);return;
  }
  if(m.type==='join'){
   if(seat())return;
   const target=rooms.get(String(m.room||'').trim().toUpperCase());
   if(!target){if(++misses>12){ws.close(4008,'Too many attempts');return;}send(ws,{type:'error',code:'missing',message:'没有找到这个维修舱，可能已经结束了。请让伙伴重新发一次邀请链接。'});return;}
   let index=typeof m.token==='string'?target.seats.findIndex(s=>s&&s.token===m.token):-1;
   if(index<0)index=target.seats.findIndex(s=>!s);
   if(index<0){send(ws,{type:'error',message:'两位伙伴已入座。若是断线，请使用原来的浏览器页面重连。'});return;}
   take(target,index,m);return;
  }
  const mine=seat();if(!mine||mine.ws!==ws)return;
  const r=room;
  if(m.type==='input'){r.inputs[role]={left:m.left===true,right:m.right===true,jump:m.jump===true,action:m.action===true};r.lastSeen[role]=Date.now();}
  if(m.type==='start'&&r.seats.every(s=>s?.ws)){r.started=true;r.played=true;broadcast(r);}
  if(m.type==='restart'){r.game=createGame(r.game.level);r.inputs=[{},{}];r.version++;broadcast(r);}
  if(m.type==='select'&&Number.isInteger(m.level)&&m.level>=0&&m.level<=merged(r).unlocked&&m.level<LEVELS.length){r.game=createGame(m.level);r.started=r.seats.every(s=>s?.ws);r.version++;broadcast(r);}
  if(m.type==='next'&&r.game.won&&r.game.level<LEVELS.length-1){r.game=createGame(r.game.level+1);r.inputs=[{},{}];r.version++;broadcast(r);}
  if(m.type==='leave'){r.seats[role]=null;r.inputs[role]={};room=null;role=-1;r.started=false;if(r.seats.every(s=>!s))rooms.delete(r.code);else broadcast(r);}
 }catch{send(ws,{type:'error',message:'操作没有生效，请重试。'});}});
 ws.on('close',()=>{const s=seat();if(s?.ws===ws){s.ws=null;room.inputs[role]={};s.disconnectedAt=Date.now();broadcast(room);}});
});

setInterval(()=>{
 const now=Date.now();
 for(const room of rooms.values()){
  for(let i=0;i<2;i++){const s=room.seats[i];if(now-room.lastSeen[i]>750)room.inputs[i]={};if(s&&!s.ws&&now-s.disconnectedAt>(room.played?SEAT_GRACE:UNSTARTED_GRACE)){room.seats[i]=null;room.started=false;}}
  if(room.seats.every(s=>!s)){rooms.delete(room.code);continue;}
  if(room.started&&room.seats.every(s=>s?.ws)&&!room.game.won){step(room.game,room.inputs);if(room.game.won){credit(room);room.version++;}}
  if(++room.tick%3===0)broadcast(room);
 }
},1000/60).unref();

server.listen(port,process.env.GAME_BIND||'127.0.0.1',()=>console.log(`Starport Crew rooms on 127.0.0.1:${port}`));
