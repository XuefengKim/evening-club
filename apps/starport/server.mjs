import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes} from 'node:crypto';
import {WebSocketServer,WebSocket} from 'ws';
import {createGame,step,LEVELS,stars} from './engine.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),port=Number(process.env.PORT||8900);
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.webmanifest':'application/manifest+json'};
const progressPath=process.env.PROGRESS_FILE||path.join(root,'progress.json');
let networkTick=0;
let progress={unlocked:0,best:{}};try{const p=JSON.parse(fs.readFileSync(progressPath));if(Number.isInteger(p.unlocked)&&p.unlocked>=0&&p.unlocked<LEVELS.length)progress=p;}catch{}
const save=()=>{fs.writeFileSync(progressPath+'.tmp',JSON.stringify(progress));fs.renameSync(progressPath+'.tmp',progressPath);};
let game=createGame(),seats=[null,null],started=false,inputs=[{},{}],lastSeen=[0,0],version=0;
const publicSeat=s=>s?{connected:!!s.ws,name:s.name}:null;
const snapshot=()=>({type:'state',game,progress,seats:seats.map(publicSeat),started,paused:!seats.every(s=>s?.ws),version});
const send=(ws,data)=>{if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(data));};
const broadcast=()=>{const d=JSON.stringify(snapshot());for(const s of seats)if(s?.ws?.readyState===WebSocket.OPEN&&s.ws.bufferedAmount<150000)s.ws.send(d);};
const server=http.createServer((req,res)=>{const url=new URL(req.url,'http://localhost');if(url.pathname==='/health'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({ok:true,players:seats.filter(s=>s?.ws).length,level:game.level,started}));return;}let file=decodeURIComponent(url.pathname);if(file==='/'||file==='/index.html')file='/index.html';if(!['/index.html','/style.css','/client.mjs','/engine.mjs','/view.mjs','/manifest.webmanifest','/icon-192.png','/icon-512.png','/favicon.svg'].includes(file)){res.writeHead(404);res.end('Not found');return;}try{res.writeHead(200,{'Content-Type':types[path.extname(file)]||'text/plain','Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});res.end(fs.readFileSync(path.join(root,file)));}catch{res.writeHead(404);res.end('Not found');}});
const wss=new WebSocketServer({server,maxPayload:4096});
wss.on('connection',(ws,req)=>{if(req.headers.origin){try{if(new URL(req.headers.origin).host!==req.headers.host){ws.close(1008,'Origin mismatch');return;}}catch{ws.close();return;}}
let role=-1,count=0,windowStart=Date.now();send(ws,{type:'hello',...snapshot(),type:'hello'});
ws.on('message',raw=>{try{if(Date.now()-windowStart>1000){count=0;windowStart=Date.now();}if(++count>100)return;const m=JSON.parse(raw);if(m.type==='join'){
 if(role>=0)return;role=seats.findIndex(s=>s&&s.token===m.token);if(role<0)role=seats.findIndex(s=>!s);if(role<0){send(ws,{type:'error',message:'两位伙伴已入座。若是断线，请使用原来的浏览器页面重连。'});return;}
 if(seats[role]?.ws&&seats[role].ws!==ws)seats[role].ws.close(4001,'Connected elsewhere');const token=seats[role]?.token||randomBytes(24).toString('hex');seats[role]={token,ws,name:String(m.name||['搬运员','侦察员'][role]).slice(0,12)};inputs[role]={};send(ws,{type:'joined',role,token});broadcast();return;}
 if(role<0||seats[role]?.ws!==ws)return;
 if(m.type==='input'){inputs[role]={left:m.left===true,right:m.right===true,jump:m.jump===true,action:m.action===true};lastSeen[role]=Date.now();}
 if(m.type==='start'&&seats.every(s=>s?.ws)){started=true;broadcast();}
 if(m.type==='restart'){game=createGame(game.level);inputs=[{},{}];version++;broadcast();}
 if(m.type==='select'&&Number.isInteger(m.level)&&m.level>=0&&m.level<=progress.unlocked&&m.level<LEVELS.length){game=createGame(m.level);started=seats.every(s=>s?.ws);version++;broadcast();}
 if(m.type==='next'&&game.won&&game.level<LEVELS.length-1){game=createGame(game.level+1);inputs=[{},{}];version++;broadcast();}
 if(m.type==='leave'){seats[role]=null;inputs[role]={};role=-1;started=false;if(seats.every(s=>!s)){game=createGame();version++;}broadcast();}
 }catch{send(ws,{type:'error',message:'操作没有生效，请重试。'});}});
 ws.on('close',()=>{if(role>=0&&seats[role]?.ws===ws){seats[role].ws=null;inputs[role]={};seats[role].disconnectedAt=Date.now();broadcast();}});
});
setInterval(()=>{for(let i=0;i<2;i++){if(Date.now()-lastSeen[i]>750)inputs[i]={};if(seats[i]&&!seats[i].ws&&Date.now()-seats[i].disconnectedAt>300000){seats[i]=null;started=false;}}
 if(started&&seats.every(s=>s?.ws)&&!game.won){step(game,inputs);if(game.won){const prev=progress.best[game.level],rank=stars(game);progress.unlocked=Math.max(progress.unlocked,Math.min(LEVELS.length-1,game.level+1));if(!prev||rank>prev.stars||rank===prev.stars&&game.time<prev.time)progress.best[game.level]={stars:rank,time:game.time,deaths:game.deaths};save();version++;}}
 if(++networkTick%3===0)broadcast();
},1000/60).unref();
server.listen(port,process.env.GAME_BIND||'127.0.0.1',()=>console.log(`Starport Crew running on http://0.0.0.0:${port}`));
