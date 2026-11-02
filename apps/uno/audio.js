/* Local synthesized score and effects. No network assets or microphone access. */
(function(root){
'use strict';
const get=(key,fallback)=>{try{return localStorage.getItem(key)??fallback}catch{return fallback}},save=(key,value)=>{try{localStorage.setItem(key,value)}catch{}};
let ctx,fxBus,musicBus,timer=null,nextBeat=0,beat=0,intense=false,noiseBuffer,hidden=false;
let enabled=get('uno-muted','0')!=='1',musicOn=get('uno-bgm','0')==='1',style=get('uno-music-style','lounge');
let fxLevel=number(get('uno-fx-volume','.65'),.65),musicLevel=number(get('uno-bgm-volume','.3'),.3);
const musicVoices=new Set();
function number(v,f){v=Number(v);return Number.isFinite(v)?Math.max(0,Math.min(1,v)):f}
function available(){return ctx&&ctx.state==='running'&&!hidden&&enabled}
function gains(){if(!ctx)return;fxBus.gain.setTargetAtTime(enabled?fxLevel:0,ctx.currentTime,.04);musicBus.gain.setTargetAtTime(enabled&&musicOn?musicLevel*.32:0,ctx.currentTime,.15)}
function unlock(){try{if(!ctx){ctx=new(root.AudioContext||root.webkitAudioContext)();fxBus=ctx.createGain();musicBus=ctx.createGain();let limiter=ctx.createDynamicsCompressor();limiter.threshold.value=-15;limiter.knee.value=16;limiter.ratio.value=8;fxBus.connect(limiter);musicBus.connect(limiter);limiter.connect(ctx.destination);noiseBuffer=ctx.createBuffer(1,Math.floor(ctx.sampleRate*.3),ctx.sampleRate);let data=noiseBuffer.getChannelData(0);for(let i=0;i<data.length;i++)data[i]=Math.random()*2-1;gains()}if(ctx.state==='suspended')ctx.resume().then(startMusic).catch(()=>{});else startMusic()}catch{}}
function voice(freq,t,duration,volume,type='sine',music=false,endFreq){if(!available())return;let osc=ctx.createOscillator(),gain=ctx.createGain();osc.type=type;osc.frequency.setValueAtTime(freq,t);if(endFreq)osc.frequency.exponentialRampToValueAtTime(Math.max(20,endFreq),t+duration);gain.gain.setValueAtTime(.0001,t);gain.gain.exponentialRampToValueAtTime(Math.max(.0002,volume),t+.008);gain.gain.exponentialRampToValueAtTime(.0001,t+duration);osc.connect(gain);gain.connect(music?musicBus:fxBus);if(music)musicVoices.add(osc);osc.onended=()=>{musicVoices.delete(osc);osc.disconnect();gain.disconnect()};osc.start(t);osc.stop(t+duration+.03)}
function noise(t,duration,volume,frequency=1800,music=false){if(!available())return;let src=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();src.buffer=noiseBuffer;filter.type='highpass';filter.frequency.value=frequency;gain.gain.setValueAtTime(volume,t);gain.gain.exponentialRampToValueAtTime(.0001,t+duration);src.connect(filter);filter.connect(gain);gain.connect(music?musicBus:fxBus);if(music)musicVoices.add(src);src.onended=()=>{musicVoices.delete(src);src.disconnect();filter.disconnect();gain.disconnect()};src.start(t);src.stop(t+duration)}
const midi=n=>440*Math.pow(2,(n-69)/12);
const chords=[[48,55,59,62,64],[45,52,55,59,62],[41,48,52,55,59],[43,50,53,57,62]],melody=[76,null,79,74,71,null,74,72,76,null,79,81,79,76,74,null];
function scheduleBeat(t,i){let chord=chords[Math.floor(i/16)%4],pos=i%16,soft=style==='ambient';if(pos%4===0){voice(midi(chord[0]),t,.65,.18,'sine',true);chord.slice(1).forEach((n,j)=>voice(midi(n+12),t+j*.025,soft?1.7:.9,soft?.045:.06,'sine',true))}if(!soft){if(pos%4===0)voice(100,t,.14,.22,'sine',true,42);if(pos%4===2)noise(t,.07,.045,1400,true);if(pos%2===1)noise(t,.025,.018,6500,true)}let note=melody[i%16];if(note!==null&&(!soft||pos%4===0))voice(midi(note+(intense?12:0)),t,.42,soft?.035:.055,'triangle',true);if(intense&&!soft&&pos%2===0)voice(midi(chord[2]+12),t,.09,.045,'sine',true)}
function tick(){if(!available()||!musicOn){stopMusic();return}let now=ctx.currentTime;if(nextBeat<now-.3)nextBeat=now+.04;let interval=60/(style==='ambient'?66:intense?96:82)/2;while(nextBeat<now+.22){scheduleBeat(nextBeat,beat++);nextBeat+=interval}}
function startMusic(){if(timer!==null||!available()||!musicOn)return;nextBeat=ctx.currentTime+.06;beat=0;tick();timer=root.setInterval(tick,100)}
function stopMusic(){if(timer!==null){root.clearInterval(timer);timer=null}for(let v of musicVoices){try{v.stop()}catch{}}musicVoices.clear()}
function effect(kind){if(!available())return;let t=ctx.currentTime+.005;
if(musicOn){musicBus.gain.cancelScheduledValues(t);musicBus.gain.setTargetAtTime(musicLevel*.12,t,.025);musicBus.gain.setTargetAtTime(musicLevel*.32,t+.35,.18)}
const notes=(ns,gap=.09,d=.2,vol=.13,type='triangle')=>ns.forEach((n,i)=>voice(midi(n),t+i*gap,d,vol,type));
switch(kind){
case 'play':noise(t,.085,.14,900);voice(620,t,.09,.11,'triangle',false,280);break;
case 'draw':noise(t,.12,.1,1900);voice(340,t+.04,.1,.065,'sine',false,460);break;
case 'deal':[0,.09,.18,.27].forEach(d=>noise(t+d,.055,.09,2100));notes([60,64,67],.12,.3,.085);break;
case 'turn':notes([76,79],.11,.27,.11,'sine');break;
case 'skip':voice(760,t,.24,.13,'triangle',false,210);noise(t,.12,.07,1800);break;
case 'reverse':voice(340,t,.13,.1,'sine',false,900);voice(900,t+.14,.15,.1,'sine',false,340);break;
case 'penalty':notes([48,48,55],.12,.2,.14);noise(t+.2,.15,.12,800);break;
case 'wild':notes([72,76,79,83],.065,.3,.1,'sine');break;
case 'uno':notes([81,88,81],.15,.25,.14);break;
case 'win':notes([60,64,67,72,76,79,84],.11,.4,.13);[60,64,67,72].forEach(n=>voice(midi(n),t+.85,.8,.07,'sine'));break;
case 'lose':notes([72,67,64,60],.16,.45,.09,'sine');break;
case 'pass':notes([67,64],.09,.15,.07,'sine');break;
default:voice(880,t,.06,.06,'sine',false,700)
}}
function configure(p){if('enabled'in p){enabled=!!p.enabled;save('uno-muted',enabled?'0':'1')}if('musicOn'in p){musicOn=!!p.musicOn;save('uno-bgm',musicOn?'1':'0')}if('fxLevel'in p){fxLevel=number(p.fxLevel,.65);save('uno-fx-volume',String(fxLevel))}if('musicLevel'in p){musicLevel=number(p.musicLevel,.3);save('uno-bgm-volume',String(musicLevel))}if('style'in p){style=p.style==='ambient'?'ambient':'lounge';save('uno-music-style',style);stopMusic()}gains();if(enabled&&musicOn)startMusic();else stopMusic()}
function setScene(state){intense=!!(state?.started&&!state.winner&&state.players.some(p=>p.count>0&&p.count<=2))}
root.document?.addEventListener('visibilitychange',()=>{hidden=root.document.hidden;if(hidden){stopMusic();if(ctx?.state==='running')ctx.suspend().catch(()=>{})}else if(ctx){unlock()}});
root.addEventListener?.('pagehide',()=>{stopMusic();ctx?.suspend().catch(()=>{})});
root.UnoAudio={unlock,effect,configure,setScene,getSettings:()=>({enabled,musicOn,fxLevel,musicLevel,style})};
})(window);
