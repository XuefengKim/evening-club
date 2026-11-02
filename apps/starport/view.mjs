// View calculations are independent of the shared game simulation.
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
export function cameraTarget({width,height,mobile=false,overview=false,player,insets={top:0,bottom:0}}){
 if(!mobile||overview){const scale=Math.min(width/1200,height/660);return {scale,x:(1200-width/scale)/2,y:(660-height/scale)/2};}
 const scale=height>width?1.38:clamp(height/265,1.25,1.65);
 const top=insets.top+60,bottom=insets.bottom+(height>width?142:116);
 const usable=Math.max(90,height-top-bottom),anchor=top+usable*.65;
 const p=player||{x:60,y:524,w:24,h:36,vx:0,vy:0};
 const look=clamp((p.vx||0)*14,-52,52);
 const viewWidth=width/scale;
 return {scale,x:clamp(p.x+p.w/2+look-viewWidth/2,0,Math.max(0,1200-viewWidth)),y:clamp(p.y+p.h*.6+clamp((p.vy||0)*3,-32,20)-anchor/scale,-420,570)};
}
export function smoothCamera(previous,target,delta=16,snap=false){
 if(!previous||snap||Math.abs(previous.scale-target.scale)>.01)return {...target};
 const a=1-Math.exp(-Math.min(100,delta)/85);
 const ay=1-Math.exp(-Math.min(100,delta)/(target.y<previous.y?55:90));
 return {scale:target.scale,x:previous.x+(target.x-previous.x)*a,y:previous.y+(target.y-previous.y)*ay};
}
export function worldToScreen(point,camera){return {x:(point.x-camera.x)*camera.scale,y:(point.y-camera.y)*camera.scale};}
export function createPointerTracker(){
 const pointers=new Map(),keyboard=new Set();
 return {down:(id,key)=>pointers.set(id,key),up:id=>pointers.delete(id),keyDown:key=>keyboard.add(key),keyUp:key=>keyboard.delete(key),clear:()=>{pointers.clear();keyboard.clear();},state:()=>Object.fromEntries(['left','right','jump','action'].map(key=>[key,keyboard.has(key)||[...pointers.values()].includes(key)]))};
}
export async function tryNativeFullscreen(element,documentLike){
 // Call synchronously from a real tap. Unsupported iPhone Safari keeps the
 // already-enabled immersive layout; this never removes touch controls.
 const request=element.requestFullscreen||element.webkitRequestFullscreen;
 if(!request||documentLike.fullscreenEnabled===false&&!documentLike.webkitFullscreenEnabled)return {native:false,reason:'unsupported'};
 try{await request.call(element,{navigationUI:'hide'});return {native:true};}catch{return {native:false,reason:'denied'};}
}
