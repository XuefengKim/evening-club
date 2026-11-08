import assert from 'node:assert/strict';
import {createGame,step,LEVELS,geometry,hit,stars}from '../web/starport/engine.mjs';
let cases=0;function test(name,fn){fn();cases++;console.log('PASS',name);}
const tick=(s,n,inputs=[{},{}])=>{for(let i=0;i<n;i++)step(s,inputs);};
test('Each player moves independently; held jump does not auto-repeat',()=>{let s=createGame();tick(s,20);let x=s.players[1].x;tick(s,10,[{right:true},{}]);assert.equal(s.players[1].x,x);assert.ok(s.players[0].x>60);tick(s,100,[{jump:true},{}]);assert.equal(s.players[0].y,524);});
test('Scout has a second jump; engineer does not',()=>{let s=createGame();tick(s,10);step(s,[{jump:true},{jump:true}]);tick(s,15);const a=s.players[0].vy;step(s,[{jump:true},{jump:true}]);assert.ok(s.players[0].vy>a);assert.ok(s.players[1].vy<-10);});
test('Scout pulse freezes drones and has a cooldown',()=>{let s=createGame(5);tick(s,10);step(s,[{},{action:true}]);let frame=s.droneTick;tick(s,50);assert.equal(s.droneTick,frame);assert.ok(s.cooldown>400);step(s,[{},{action:true}]);assert.ok(s.freeze<180);tick(s,181);assert.ok(s.droneTick>frame);});
test('Magnet can lift and release cargo; held cargo does not activate plate',()=>{let s=createGame(3);tick(s,10);Object.assign(s.players[0],{x:210,y:524});step(s,[{action:true},{}]);assert.equal(s.players[0].carrying,0);assert.equal(s.crates[0].carried,true);step(s);step(s,[{action:true},{}]);assert.equal(s.players[0].carrying,-1);assert.equal(s.crates[0].carried,false);Object.assign(s.crates[0],{x:375,y:524});step(s);assert.ok(s.active.a);});
test('Permanent power switch and far-side unlock persist',()=>{let s=createGame(2);Object.assign(s.players[0],{x:660,y:524});step(s);assert.ok(s.latches.a);Object.assign(s.players[0],{x:50});step(s);assert.ok(s.active.a);s=createGame(3);Object.assign(s.players[1],{x:897,y:230});step(s);assert.ok(s.latches.a);});
test('Pressure plate has a grace window and then closes',()=>{let s=createGame(3);Object.assign(s.crates[0],{x:378,y:524});step(s);assert.ok(s.active.a);s.crates[0].x=200;tick(s,149);assert.ok(s.active.a);tick(s,3);assert.equal(s.active.a,false);});
test('Damage resets stage items but preserves elapsed time and mistakes',()=>{let s=createGame(1);s.keys=[true,true];s.gems=[true,true,true,true];s.time=12;Object.assign(s.players[1],{x:750,y:524});step(s);assert.equal(s.deaths,1);assert.ok(s.time>12);assert.equal(s.keys[0],false);assert.equal(s.gems[0],false);});
test('Both roles are vulnerable to permanent electrical hazards',()=>{for(const role of[0,1]){let s=createGame(1);Object.assign(s.players[role],{x:530,y:524});step(s);assert.equal(s.deaths,1);}});
test('Victory requires both components and both crew at extraction',()=>{let s=createGame();Object.assign(s.players[0],{x:1060,y:144});Object.assign(s.players[1],{x:1124,y:144});step(s);assert.equal(s.won,false);s.keys=[true,true];step(s);assert.equal(s.won,true);assert.equal(stars(s),2);s.gems=s.gems.map(()=>true);assert.equal(stars(s),3);});
test('Moving cargo lift carries a standing crew member',()=>{let s=createGame(4);step(s);const lift=s.platforms.at(-1);Object.assign(s.players[0],{x:lift.x+20,y:lift.y-36,vy:0,ground:true});let y=s.players[0].y;tick(s,60);assert.ok(s.players[0].y<y-40);});
// Physics trajectory checks run the real controller for every stair connection.
// Open barriers in fixtures; switch/plate behavior is verified independently above.
test('Every engineer stair jump is reachable with real physics',()=>{for(let li=0;li<LEVELS.length;li++){
 const l=LEVELS[li];let targets=l.p.map(p=>({x:p[0],y:p[1],w:p[2],h:20}));if(l.moving)targets.splice(1,0,{x:405+(li===7?20:0),y:330,w:120,h:18});
 for(let i=0;i<targets.length-1;i++){const a=targets[i],b=targets[i+1];let found=false;
 for(const offset of[24,32,48,64]){let s=createGame(li);s.latches={a:true,b:true};s.freeze=10000;s.droneTick=0;s.players[1].x=40;s.players[1].y=524;
 // Geometry path test uses a static lift at its intermediate elevation.
 const original=LEVELS[li];const fixture={...original,haz:[],enemies:[],moving:[],p:[...original.p]};if(l.moving)fixture.p.push([targets[1].x,targets[1].y,120]);LEVELS[li]=fixture;
 const p=s.players[0];Object.assign(p,{x:a.x+a.w-offset,y:a.y-36,ground:true,vy:0});
 for(let f=0;f<85;f++){step(s,[{jump:f===0,right:p.x<b.x+Math.min(35,b.w/3)},{}]);if(p.ground&&Math.abs(p.y+36-b.y)<2&&p.x+p.w>b.x&&p.x<b.x+b.w){found=true;break;}}
 LEVELS[li]=original;if(found)break;}
 assert.ok(found,`level ${li+1} stair ${i+1} => ${i+2}`);
 }
}});

test('Complete first stage from spawn using only both players movement and jumps',()=>{const s=createGame();const phases=[{x:160},{x:310,y:455,jump:true},{x:392},{x:565,y:360,jump:true},{x:642},{x:810,y:265,jump:true},{x:912},{x:1030,y:180,jump:true},{x:1065}];const phasesByRole=[phases,phases.map((v,i)=>i===8?{x:1125}:v)];let ids=[0,0],jumpStarted=[false,false];for(let f=0;f<2500&&!s.won;f++){const inputs=s.players.map((p,r)=>{let task=phasesByRole[r][ids[r]];if(!task)return {};if(task.jump){if(jumpStarted[r]&&p.ground&&Math.abs(p.y+p.h-task.y)<2){ids[r]++;jumpStarted[r]=false;return {};}const j=!jumpStarted[r]&&p.ground;jumpStarted[r]||=j;return {right:p.x<task.x-3,left:p.x>task.x+3,jump:j};}if(Math.abs(p.x-task.x)<4){ids[r]++;return {};}return {right:p.x<task.x,left:p.x>task.x};});step(s,inputs);}assert.equal(s.won,true);assert.deepEqual(s.keys,[true,true]);assert.equal(s.deaths,0);console.log('First stage complete in',s.time.toFixed(1),'seconds');});

console.log(`${cases} engine checks passed`);
