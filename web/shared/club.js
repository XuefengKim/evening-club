// Small helpers shared by every page: an anonymous browser id, invite links and copying.
'use strict';
function clubId(){
 let id='';try{id=localStorage.getItem('club-id')||''}catch{}
 if(!/^[0-9a-f]{32}$/.test(id)){id=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');try{localStorage.setItem('club-id',id)}catch{}}
 return id;
}
function clubInvite(page,code){return location.origin+page+'?r='+code}
function clubRoomParam(){return (new URLSearchParams(location.search).get('r')||'').trim().toUpperCase()}
async function clubCopy(text){
 try{await navigator.clipboard.writeText(text);return true}catch{}
 const t=document.createElement('textarea');t.value=text;t.setAttribute('readonly','');t.style.cssText='position:fixed;top:0;left:0;opacity:0';document.body.append(t);t.select();
 let ok=false;try{ok=document.execCommand('copy')}catch{}t.remove();return ok;
}
