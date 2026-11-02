import assert from 'node:assert/strict';
import{cameraTarget,smoothCamera,worldToScreen,createPointerTracker,tryNativeFullscreen}from'./view.mjs';
for(const[width,height]of[[320,568],[375,667],[390,844],[430,932],[568,320],[667,375],[844,390],[932,430]]){
 for(const insets of[{top:0,bottom:0},{top:47,bottom:34}])for(const p of[{x:60,y:524,w:24,h:36},{x:540,y:324,w:24,h:36},{x:1130,y:140,w:24,h:36},{x:1100,y:-160,w:24,h:36}]){
 const c=cameraTarget({width,height,mobile:true,player:p,insets}),q=worldToScreen({x:p.x+12,y:p.y+18},c);
 assert.ok(c.scale*36>=45,`readable actor at ${width}x${height}`);assert.ok(q.x>=0&&q.x<=width);assert.ok(q.y>=insets.top+45&&q.y<=height-insets.bottom-100,`actor outside HUD/thumb controls at ${width}x${height}`);
 const wide=cameraTarget({width,height,mobile:true,overview:true,player:p});assert.ok(1200*wide.scale<=width+.001);assert.ok(660*wide.scale<=height+.001);
 }
}
console.log('PASS readable follow camera and full-map fit across 8 mobile sizes, portrait/landscape, safe-area insets');
const c=smoothCamera({x:0,y:0,scale:1.4},{x:500,y:200,scale:1.4},16);assert.ok(c.x>0&&c.x<500);assert.deepEqual(smoothCamera(c,{x:250,y:100,scale:1.4},16,true),{x:250,y:100,scale:1.4});
const input=createPointerTracker();input.down(1,'right');input.down(2,'jump');assert.deepEqual(input.state(),{left:false,right:true,jump:true,action:false});input.up(2);assert.equal(input.state().right,true);assert.equal(input.state().jump,false);input.down(3,'action');input.up(1);assert.equal(input.state().action,true);assert.equal(input.state().right,false);input.keyDown('jump');input.down(4,'jump');input.up(4);assert.equal(input.state().jump,true);input.clear();assert.deepEqual(input.state(),{left:false,right:false,jump:false,action:false});
console.log('PASS simultaneous move/jump/action, independent finger release, keyboard coexistence and canceled input cleanup');
let called=0;assert.deepEqual(await tryNativeFullscreen({},{}),{native:false,reason:'unsupported'});assert.deepEqual(await tryNativeFullscreen({requestFullscreen(){called++;return Promise.reject(Error('denied'));}},{fullscreenEnabled:true}),{native:false,reason:'denied'});assert.equal((await tryNativeFullscreen({requestFullscreen(){called++;return Promise.resolve();}},{fullscreenEnabled:true})).native,true);assert.equal((await tryNativeFullscreen({webkitRequestFullscreen(){called++;}},{webkitFullscreenEnabled:true,fullscreenEnabled:false})).native,true);assert.equal(called,3);
console.log('PASS unsupported iPhone-style API, denied request, standard and prefixed fullscreen paths');
