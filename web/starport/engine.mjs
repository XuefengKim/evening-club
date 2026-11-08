export const W=1200,H=660;
const rect=(x,y,w,h)=>({x,y,w,h});
const levels=[
 {name:'失联的泊位',chapter:'01 / 外环泊位',tip:'寻找橙色动力组件和蓝色导航芯片，然后一起登上顶部撤离平台。蓝色侦察员可以二段跳。',p:[[240,455,180],[490,360,180],[750,265,190],[965,180,205]],haz:[],keys:[[310,430,0],[570,335,1]],gems:[[110,520,0],[205,520,1],[800,240,0],[870,240,1]],exitY:180},
 {name:'高压走廊',chapter:'01 / 外环泊位',tip:'橙色排气口间歇喷发；蓝色电网和紫色泄漏持续危险。观察时机，所有危险对两位队员都有效。',p:[[200,455,170],[420,365,180],[670,275,185],[930,185,240]],haz:[[300,548,105,12,0],[500,548,105,12,1],[730,548,75,12,2]],keys:[[460,340,0],[735,250,1]],gems:[[345,530,0],[550,530,1],[975,160,0],[1030,160,1]],exitY:185},
 {name:'远端供电',chapter:'02 / 货运中枢',tip:'踩下地面的圆形供电钮，永久关闭上层安保屏障。连线指向对应屏障。',p:[[210,460,190],[450,365,190],[710,270,190],[960,180,210]],haz:[[480,548,100,12,1]],keys:[[290,435,1],[790,245,0]],gems:[[535,525,1],[500,340,0],[1010,155,0],[1070,155,1]],plates:[[650,550,'a','latch']],gates:[[850,80,24,190,'a']],exitY:180},
 {name:'磁力搬运',chapter:'02 / 货运中枢',tip:'橙色搬运员按 E / 空格吸起货箱，再按一次放到方形压板上。蓝色队员先过屏障，触碰远端解锁钮。',p:[[230,455,185],[480,360,185],[740,265,180],[965,180,205]],haz:[[750,548,100,12,2]],keys:[[305,430,0],[545,335,1]],gems:[[800,240,1],[1010,155,0],[1080,155,1],[150,520,0]],plates:[[370,550,'a','hold']],gates:[[850,75,25,190,'a']],crates:[[280,520]],levers:[[905,245,'a']],exitY:180},
 {name:'失重货梯',chapter:'03 / 反应堆区',tip:'搭乘自动货梯向上。蓝色队员可在空中再跳一次；橙色队员需要等待货梯抵达。',p:[[210,460,150],[610,340,170],[835,250,150],[1000,165,170]],moving:[[405,450,120,18,0,-175,240]],haz:[[400,548,165,12,2]],keys:[[270,435,0],[680,315,1]],gems:[[460,420,0],[880,225,1],[1040,140,0],[1100,140,1]],exitY:165},
 {name:'巡检失控',chapter:'03 / 反应堆区',tip:'巡检无人机已失控。蓝色侦察员按 E / 空格释放时间脉冲，冻结无人机 3 秒；冷却 8 秒。',p:[[220,455,200],[475,360,200],[735,265,190],[980,180,190]],haz:[[260,548,100,12,0],[520,548,100,12,1]],enemies:[[490,332,150,180],[750,237,145,200]],keys:[[320,430,1],[815,240,0]],gems:[[305,525,0],[570,525,1],[1020,155,0],[1090,155,1]],exitY:180},
 {name:'双路重启',chapter:'04 / 核心控制室',tip:'分头接通左右供电钮，再通过两道安保屏障。侦察员用时间脉冲掩护搬运员。',p:[[210,460,175],[440,365,180],[695,270,190],[950,180,220]],haz:[[340,548,110,12,0],[635,548,105,12,1]],plates:[[170,550,'a','latch'],[900,550,'b','latch']],gates:[[565,175,25,190,'a'],[825,80,25,190,'b']],enemies:[[720,242,130,195]],keys:[[495,340,1],[765,245,0]],gems:[[390,525,0],[690,525,1],[1000,155,0],[1070,155,1]],exitY:180},
 {name:'最后的撤离',chapter:'04 / 核心控制室',tip:'综合维修：磁吸货箱压住供电板，搭货梯取回组件，冻结无人机，然后一起登上撤离平台。',p:[[205,460,160],[625,355,160],[840,265,145],[1010,175,160]],moving:[[425,455,120,18,0,-175,250]],haz:[[400,548,170,12,2],[740,548,95,12,0]],plates:[[325,550,'a','hold']],crates:[[235,520]],gates:[[920,65,22,200,'a']],levers:[[980,245,'a']],enemies:[[640,327,115,170]],keys:[[280,435,0],[700,330,1]],gems:[[790,525,0],[875,240,1],[1040,150,0],[1110,150,1]],exitY:175}
];
export const LEVELS=levels;
export const hit=(a,b)=>a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;
export function createGame(index=0){const l=levels[index];return {level:index,tick:0,time:0,deaths:0,won:false,freeze:0,cooldown:0,players:[0,1].map((role)=>({...rect(60+role*65,510,24,36),vx:0,vy:0,role,ground:false,coyote:0,jumpWas:false,actionWas:false,jumps:0,carrying:-1,facing:1,trail:[]})),keys:[false,false],gems:l.gems.map(()=>false),latches:{},active:{},gateGrace:{},crates:(l.crates||[]).map(([x,y])=>({...rect(x,y,36,36),vy:0})),platforms:[],flash:0};}
export function geometry(s){let l=levels[s.level];return [rect(0,560,W,100),rect(-30,0,30,H),rect(W,0,30,H),...l.p.map(([x,y,w])=>rect(x,y,w,20)),...(l.moving||[]).map(([x,y,w,h,dx,dy,period])=>{const t=(1-Math.cos(s.tick/period*Math.PI*2))/2;return rect(x+dx*t,y+dy*t,w,h)})];}
function die(s){const d=s.deaths+1,t=s.time;Object.assign(s,createGame(s.level));s.deaths=d;s.time=t;s.flash=35;}
function horizontal(p,dx,solids){p.x+=dx;for(const b of solids)if(hit(p,b)){if(dx>0)p.x=b.x-p.w;else if(dx<0)p.x=b.x+b.w;}}
function vertical(p,solids){p.y+=p.vy;p.ground=false;for(const b of solids)if(hit(p,b)){if(p.vy>0){p.y=b.y-p.h;p.ground=true;}else if(p.vy<0)p.y=b.y+b.h;p.vy=0;}}
export function step(s,inputs=[{},{}]){if(s.won)return;s.tick++;s.time+=1/60;if(s.freeze>0)s.freeze--;if(s.cooldown>0)s.cooldown--;if(s.flash)s.flash--;if(!s.freeze)s.droneTick=(s.droneTick||0)+1;const l=levels[s.level],old=s.platforms,solids=geometry(s);s.platforms=solids;
 for(let i=3+l.p.length;i<solids.length;i++){const p=solids[i],prev=old[i];if(prev)for(const a of [...s.players,...s.crates])if(Math.abs(a.y+a.h-prev.y)<3&&a.x+a.w>prev.x&&a.x<prev.x+prev.w){a.x+=p.x-prev.x;a.y+=p.y-prev.y;}}
 for(const [x,y,id,mode]of(l.plates||[])){const on=[...s.players,...s.crates.filter(c=>!c.carried)].some(a=>hit(a,rect(x,y-3,50,15)));if(on&&mode==='latch')s.latches[id]=true;if(on)s.gateGrace[id]=150;else s.gateGrace[id]=Math.max(0,(s.gateGrace[id]||0)-1);s.active[id]=!!(s.latches[id]||s.gateGrace[id]);}
 for(const[x,y,id]of(l.levers||[]))if(s.players.some(p=>hit(p,rect(x-12,y-22,30,40))))s.latches[id]=true;
 const gates=(l.gates||[]).filter(g=>!s.active[g[4]]&&!s.latches[g[4]]).map(g=>rect(...g));
 for(const c of s.crates){if(c.carried)continue;c.vy=Math.min(12,c.vy+.48);vertical(c,[...solids,...gates]);}
 for(let role=0;role<2;role++){const p=s.players[role],input=inputs[role]||{},dx=((input.right?1:0)-(input.left?1:0))*3.6;
 p.coyote=p.ground?7:Math.max(0,p.coyote-1);if(p.ground)p.jumps=0;if(input.jump&&!p.jumpWas&&(p.coyote>0||(role===1&&p.jumps<2))){p.vy=-11.8;p.jumps++;p.coyote=0;p.ground=false;}p.jumpWas=!!input.jump;p.vx=dx;if(dx)p.facing=Math.sign(dx);
 if(input.action&&!p.actionWas){if(role===0){if(p.carrying>=0){const c=s.crates[p.carrying];const drop={...c,x:p.x+p.facing*39,y:p.y+p.h-36};if(![...solids,...gates].some(b=>hit(drop,b))){Object.assign(c,drop,{carried:false});p.carrying=-1;}}else{const ci=s.crates.findIndex(c=>Math.hypot(c.x-p.x,c.y-p.y)<120);if(ci>=0){p.carrying=ci;s.crates[ci].carried=true;}}}else if(s.cooldown===0){s.freeze=180;s.cooldown=480;}}p.actionWas=!!input.action;
 for(const c of s.crates)if(!c.carried&&hit({...p,x:p.x+dx},c)){const before=c.x;horizontal(c,dx,[...solids,...gates,...s.crates.filter(o=>o!==c)]);if(Math.abs(c.x-before-dx)>.01)p.vx=0;}
 horizontal(p,p.vx,[...solids,...gates,...s.crates.filter(c=>!c.carried)]);p.vy=Math.min(13,p.vy+.48);vertical(p,[...solids,...gates,...s.crates.filter(c=>!c.carried)]);if(p.carrying>=0){const c=s.crates[p.carrying];c.x=p.x-6;c.y=p.y-39;}
 for(const[x,y,w,h,type]of l.haz)if((type!==0||s.tick%180<100)&&hit(p,rect(x,y,w,h))){die(s);return;}
 for(const[x,y,range,period]of(l.enemies||[])){const ex=x+(1-Math.cos((s.droneTick||0)/period*Math.PI*2))/2*range;if(hit(p,rect(ex,y,27,27))){die(s);return;}}
 if(p.y>H+40){die(s);return;}
 for(const[x,y,r]of l.keys)if(r===role&&hit(p,rect(x-12,y-12,24,24)))s.keys[role]=true;
 l.gems.forEach(([x,y,r],i)=>{if(r===role&&hit(p,rect(x-9,y-9,18,18)))s.gems[i]=true;});
 }
 s.won=s.keys.every(Boolean)&&s.players.every((p,i)=>hit(p,rect(1055+i*64,l.exitY-56,42,56)));
}
export const stars=s=>1+(s.gems.every(Boolean)?1:0)+(s.deaths===0?1:0);
