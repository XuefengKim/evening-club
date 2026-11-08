import{spawn}from'node:child_process';import{tmpdir}from'node:os';import path from'node:path';import fs from'node:fs';import assert from'node:assert/strict';import{WebSocket}from'ws';
const port=18902,progress=path.join(tmpdir(),`starport-test-${process.pid}.json`);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ids={a:'a'.repeat(32),b:'b'.repeat(32),c:'c'.repeat(32)};
let all=[],child;
function boot(){child=spawn(process.execPath,['server.mjs'],{cwd:import.meta.dirname,env:{...process.env,PORT:String(port),PROGRESS_FILE:progress},stdio:['ignore','pipe','pipe']});return new Promise((r,j)=>{child.stdout.once('data',r);child.once('error',j);child.once('exit',c=>j(Error('server exited '+c)));});}
async function client(){let ws=new WebSocket(`ws://127.0.0.1:${port}`),messages=[];ws.on('message',x=>messages.push(JSON.parse(x)));await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});const c={ws,messages,send:x=>ws.send(JSON.stringify(x)),wait:async(pred)=>{for(let i=0;i<150;i++){const m=messages.find(pred);if(m)return m;await sleep(20);}throw Error('message timeout');},state:()=>messages.filter(m=>m.type==='state').at(-1)};all.push(c);return c;}
try{await boot();
// Two separate crews never share a room.
const a=await client(),b=await client(),x=await client(),y=await client();
a.send({type:'create',player:ids.a});const aa=await a.wait(m=>m.type==='joined');assert.equal(aa.role,0);assert.match(aa.room,/^S[0-9A-Z]{3}$/);
x.send({type:'create',player:ids.c});const xx=await x.wait(m=>m.type==='joined');assert.notEqual(xx.room,aa.room);
b.send({type:'join',room:aa.room.toLowerCase(),player:ids.b});const bb=await b.wait(m=>m.type==='joined');assert.equal(bb.role,1);assert.equal(bb.room,aa.room);assert.notEqual(aa.token,bb.token);
y.send({type:'join',room:'SZZZ',player:ids.c});assert.equal((await y.wait(m=>m.type==='error')).code,'missing');
await sleep(100);a.send({type:'start'});await sleep(180);assert.equal(a.state().started,true);assert.equal(a.state().paused,false);assert.equal(x.state().seats[1],null);
const old=a.state().game.players.map(p=>p.x);a.send({type:'input',right:true});await sleep(180);assert.ok(a.state().game.players[0].x>old[0]+10);assert.equal(a.state().game.players[1].x,old[1]);assert.equal(JSON.stringify(a.state()).includes(aa.token),false);assert.equal(JSON.stringify(a.state()).includes(ids.a),false);
const stranger=await client();stranger.send({type:'join',room:aa.room});await stranger.wait(m=>m.type==='error');stranger.send({type:'restart'});stranger.ws.close();
// Disconnect pauses only that room; the seat token reclaims the same role.
a.send({type:'input'});b.ws.close();await sleep(100);assert.equal(a.state().paused,true);let clock=a.state().game.time;await sleep(150);assert.equal(a.state().game.time,clock);
const reconnect=await client();reconnect.send({type:'join',room:aa.room,token:bb.token,player:ids.b});assert.equal((await reconnect.wait(m=>m.type==='joined')).role,1);await sleep(150);assert.equal(a.state().paused,false);assert.ok(a.state().game.time>clock);
a.send({type:'select',level:7});await sleep(100);assert.equal(a.state().game.level,0);a.send({type:'restart'});await sleep(100);assert.ok(a.state().game.time<.2);
assert.equal((await fetch(`http://127.0.0.1:${port}/server.mjs`)).status,404);
for(const c of[a,reconnect,x])c.send({type:'leave'});await sleep(100);assert.equal((await(await fetch(`http://127.0.0.1:${port}/health`)).json()).rooms,0);
console.log('PASS separate rooms, invite join, unknown code, independent input, spectator denial, token and player-id privacy, disconnect pause, reconnect, stage locks, restart, leave');
// Progress is stored per player on the server and survives a restart.
fs.writeFileSync(progress,JSON.stringify({players:{[ids.a]:{unlocked:3,best:{0:{stars:2,time:40,deaths:1}}}}}));
for(const c of all)c.ws.terminate();all=[];child.kill();await sleep(150);await boot();
const p=await client(),q=await client();p.send({type:'create',player:ids.a});const pp=await p.wait(m=>m.type==='joined');q.send({type:'join',room:pp.room,player:ids.b});await q.wait(m=>m.type==='joined');await sleep(80);
assert.equal(q.state().progress.unlocked,3);q.send({type:'select',level:3});await sleep(100);assert.equal(q.state().game.level,3);
q.send({type:'select',level:4});await sleep(100);assert.equal(q.state().game.level,3);
const saved=JSON.parse(fs.readFileSync(progress));assert.equal(saved.players[ids.b],undefined);
console.log('PASS per-player server progress: partner inherits higher unlock in the room, file survives restart, locked stages refused');
}finally{for(const c of all)c.ws.terminate();child?.kill();try{fs.unlinkSync(progress);}catch{}try{fs.unlinkSync(progress+'.tmp');}catch{}}
