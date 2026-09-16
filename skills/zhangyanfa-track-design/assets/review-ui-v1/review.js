'use strict';
const $=id=>document.getElementById(id),escapeHTML=s=>String(s).replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
let D,tab='A',index=0,mode='single',playing=false,activeSegment='',seekGeneration=0,frame=0,focusCard=null;
const video=$('video'),voice=$('voice'),qaMode=new URLSearchParams(location.search).get('qa')==='1';let draft={choices:{},seen:[],bgm:null};
try{if(!qaMode)draft=JSON.parse(localStorage.getItem('ep3-stage08-review-v1'))||draft}catch(e){}
const fmt=s=>`${String(Math.floor(s/60)).padStart(2,'0')}:${(s%60).toFixed(2).padStart(5,'0')}`;
const saveLocal=()=>{if(!qaMode)localStorage.setItem('ep3-stage08-review-v1',JSON.stringify(draft))};
function currentCandidate(i=index){const c=D.cues[i];return c.candidates.find(x=>x.candidate_id===(draft.choices[c.cue_id]||'A'))||c.candidates[0]}
function selectedSegment(f){const i=Math.max(0,D.cues.findIndex(c=>c.start_frame<=f&&f<c.end_frame));return currentCandidate(i).segments.find(s=>s.start_frame<=f&&f<s.end_frame)||currentCandidate(i).segments[0]}
function pause(){playing=false;document.querySelectorAll('audio,video').forEach(e=>e.pause());$('play').textContent='播放本條';$('continuous').textContent='連續播放'}
function showAt(s,f){
 const useHook=f<600&&D.cues.filter(c=>c.start_frame<600).every(c=>currentCandidate(c.cue_id-1).candidate_id==='A');
 const id=useHook?'hook':s.segment_id,src=useHook?'/hook.mp4':s.src,target=useHook?f/60:s.source_in+(f-s.start_frame)/60;
 if(activeSegment!==id){activeSegment=id;const gen=++seekGeneration;$('poster').src=s.head_url;$('poster').style.display='block';
  const seek=()=>{if(gen!==seekGeneration)return;video.currentTime=Math.max(0,target);if(playing)video.play().catch(()=>{});};
  video.onseeked=()=>{if(gen===seekGeneration)$('poster').style.display='none'};
  if(video.getAttribute('src')!==src){video.src=src;video.onloadedmetadata=seek;video.load()}else seek();
 }else if(!video.seeking&&Math.abs(video.currentTime-target)>.20){video.currentTime=Math.max(0,target)}
 if(playing&&video.paused&&video.readyState>=2)video.play().catch(()=>{});
}
function overlays(f){
 const b=D.aux.B.find(x=>x.start_frame<=f&&f<x.end_frame),c=D.aux.C.find(x=>x.start_frame<=f&&f<x.end_frame);
 const showB=tab==='B'||(tab==='A'&&$('showB').checked),showC=tab==='C'||(tab==='A'&&$('showC').checked);
 for(const [id,card,show] of [['overlayB',b,showB],['overlayC',c,showC]]){const el=$(id);el.style.display=card&&show?'block':'none';if(card&&show){const src=$('green').checked&&tab!=='A'?card.green_url:card.alpha_url;if(el.getAttribute('src')!==src)el.src=src}}
 const back=tab==='A'||$('showA').checked;video.style.visibility=back?'visible':'hidden';$('poster').style.visibility=back?'visible':'hidden';$('empty').style.display=(!back&&!(tab==='B'?b:c))?'grid':'none';
}
function setFrame(f,seekAudio=true){frame=Math.max(0,Math.min(D.total_frames-1,Math.floor(f)));if(seekAudio)voice.currentTime=frame/60;const i=D.cues.findIndex(c=>c.start_frame<=frame&&frame<c.end_frame);if(i>=0&&i!==index){index=i;renderCurrent(false)};showAt(selectedSegment(frame),frame);overlays(frame);$('scrub').value=frame;$('clock').textContent=fmt(frame/60)+' / '+fmt(D.total_frames/60)}
function go(i){pause();index=Math.max(0,Math.min(346,i));focusCard=null;activeSegment='';renderCurrent(true);setFrame(D.cues[index].start_frame);history.replaceState(null,'',`/tracks/review/${tab}/?cue=${index+1}`)}
function goCard(e){pause();focusCard=e;index=e.cue_first-1;renderCurrent(true);setFrame(e.start_frame);history.replaceState(null,'',`/tracks/review/${tab}/?cue=${index+1}`)}
function renderList(){
 const q=$('search').value.trim().toLowerCase();const list=tab==='A'?D.cues:(D.aux[tab]||[]);$('listtitle').textContent=tab==='A'?'347 條字幕':tab==='B'?'32 張證據與解釋':'10 組關係提示';
 $('list').innerHTML=list.filter(c=>!q||`${c.cue_id||c.id} ${String(c.cue_id||'').padStart(3,'0')} ${c.text||c.title}`.toLowerCase().includes(q)).map(c=>{const i=(c.cue_id||c.cue_first)-1;const active=tab==='A'?i===index:c.start_frame<=frame&&frame<c.end_frame;return `<button class="listrow ${active?'active':''} ${draft.seen.includes(c.cue_id||c.id)?'seen':''}" data-id="${c.cue_id||c.id}"><b>${c.cue_id?String(c.cue_id).padStart(3,'0'):c.id}</b><span>${escapeHTML(c.text||c.title)}</span></button>`}).join('');
 document.querySelectorAll('.listrow').forEach(el=>el.onclick=()=>tab==='A'?go(Number(el.dataset.id)-1):goCard(D.aux[tab].find(e=>e.id===el.dataset.id)));
}
function renderCurrent(scroll){
 const cue=D.cues[index],cand=currentCandidate();$('position').textContent=`${String(index+1).padStart(3,'0')} / 347 · ${fmt(cue.start_frame/60)}–${fmt(cue.end_frame/60)}`;$('caption').textContent=cue.text;
 if(tab==='A'){
  $('choices').style.display='grid';$('choices').innerHTML=cue.candidates.map(c=>`<button class="choice ${c.candidate_id===cand.candidate_id?'selected':''}" data-candidate="${c.candidate_id}"><img src="${c.segments[0].mid_url}" alt="方案 ${c.candidate_id}" loading="lazy"><span class="badge">${c.segments.length} 個鏡頭</span><div class="meta"><strong>方案 ${c.candidate_id}${c.candidate_id===cand.candidate_id?' · 當前選擇':''}</strong>${escapeHTML(c.segments[0].focus)}</div></button>`).join('');
  document.querySelectorAll('.choice').forEach(b=>b.onclick=()=>{pause();draft.choices[cue.cue_id]=b.dataset.candidate;saveLocal();activeSegment='';renderCurrent(false);setFrame(cue.start_frame)});$('reason').textContent=cand.reason;
  $('proofs').innerHTML=cand.segments.map(s=>`<div class="proofrow"><p>${escapeHTML(s.source_id)} · ${s.source_in.toFixed(3)}–${s.source_out.toFixed(3)} 秒 · ${escapeHTML(s.focus)}</p><div>${['head','mid','tail'].map((pos,i)=>`<a target="_blank" href="${s[pos+'_url']}"><img src="${s[pos+'_url']}" loading="lazy" alt="${['頭','中','尾'][i]}幀">${['頭','中','尾'][i]}幀</a>`).join('')}</div></div>`).join('');
 }else{
  $('choices').style.display='none';const e=focusCard||D.aux[tab].find(x=>x.start_frame<=frame&&frame<x.end_frame)||D.aux[tab].find(x=>x.cue_first>=index+1);
  $('reason').textContent=e?`${e.id} · ${e.title} · ${fmt(e.start_frame/60)}–${fmt(e.end_frame/60)} · ${e.source_label}`:'此處不使用本軌畫面。';
  $('proofs').innerHTML=e?`<p>${escapeHTML(e.evidence_kind)} · 閱讀速度 ${e.reading_cps} 字/秒</p><a href="${e.alpha_url}" target="_blank">開啟完整透明預覽 ↗</a>　<a href="${e.green_url}" target="_blank">開啟純綠交付資產 ↗</a>${e.original_url?`　<a href="${e.original_url}" target="_blank">原始來源畫面 ↗</a>`:''}`:'';
 }
 renderList();if(scroll)document.querySelector('.listrow.active')?.scrollIntoView({block:'nearest'});
}
function setTab(t,initial=false){pause();tab=t;document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.dataset.tab===t));$('review').hidden=t==='BGM';$('music').hidden=t!=='BGM';document.querySelector('aside').style.display=t==='BGM'?'none':'flex';
 if(t==='BGM'){renderMusic();if(!initial)history.pushState(null,'','/bgm/');return}
 $('backgroundLabel').style.display=t==='A'?'none':'';$('greenLabel').style.display=t==='A'?'none':'';$('showB').parentElement.style.display=t==='A'?'':'none';$('showC').parentElement.style.display=t==='A'?'':'none';$('green').checked=false;
 $('search').value='';
 if(t!=='A'){const e=initial?(D.aux[t].find(e=>e.cue_first<=index+1&&index+1<=e.cue_last)||D.aux[t].find(e=>e.cue_first>=index+1)||D.aux[t][0]):D.aux[t][0];goCard(e)}else{focusCard=null;renderCurrent(true);setFrame(D.cues[index].start_frame)}
 if(!initial)history.pushState(null,'',`/tracks/review/${t}/?cue=${index+1}`)
}
function renderMusic(){
 $('musicgrid').innerHTML=D.bgm.map(c=>`<article class="musiccard ${draft.bgm===c.candidate_id?'selected':''}" id="music_${c.candidate_id}"><span class="label">方案 ${c.candidate_id.slice(-1)}</span><h2>${escapeHTML(c.direction)}</h2><div>${escapeHTML(c.title)}</div><p>${escapeHTML(c.intent)}</p><audio controls preload="none" src="${c.mix_url}" id="audio_${c.candidate_id}"></audio><div class="checkpoints">${c.checkpoints.map((p,i)=>`<button data-audio="${c.candidate_id}" data-time="${p.audition_start_s}">${['開場','年代矛盾','動機轉折','結尾'][i]}</button>`).join('')}</div><details><summary>配樂單聽</summary><audio controls preload="none" src="${c.music_url}"></audio></details><p>${escapeHTML(c.listening_focus)}</p><button data-bgm="${c.candidate_id}" class="${draft.bgm===c.candidate_id?'selected':''}">${draft.bgm===c.candidate_id?'已記錄偏好':'偏好這一套'}</button></article>`).join('');
 document.querySelectorAll('[data-audio]').forEach(b=>b.onclick=()=>{const a=$('audio_'+b.dataset.audio);a.currentTime=Number(b.dataset.time);a.play()});
 document.querySelectorAll('[data-bgm]').forEach(b=>b.onclick=()=>{draft.bgm=b.dataset.bgm;saveLocal();document.querySelectorAll('.musiccard').forEach(e=>e.classList.toggle('selected',e.id==='music_'+draft.bgm));document.querySelectorAll('[data-bgm]').forEach(x=>{x.textContent=x.dataset.bgm===draft.bgm?'已記錄偏好':'偏好這一套';x.classList.toggle('selected',x.dataset.bgm===draft.bgm)})});
 document.querySelectorAll('#music audio').forEach(a=>a.onplay=()=>document.querySelectorAll('audio').forEach(other=>{if(other!==a)other.pause()}));
}
async function persist(){if(qaMode)return;saveLocal();const r=await fetch('/api/draft-feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(draft)});if(!r.ok)throw new Error('保存失敗');$('saveStatus').textContent='已保存到本期 folder';$('saveMusic').textContent='BGM 偏好已保存'}
function play(which){if(playing){pause();return}mode=which;const end=tab==='A'?D.cues[index].end_frame:focusCard?.end_frame||D.cues[index].end_frame;if(frame>=end-1)setFrame(tab==='A'?D.cues[index].start_frame:focusCard?.start_frame||D.cues[index].start_frame);playing=true;$('play').textContent=which==='single'?'暫停':'播放本條';$('continuous').textContent=which==='continuous'?'暫停連播':'連續播放';voice.play().catch(()=>pause());video.play().catch(()=>{})}
function tick(){if(D&&playing){const f=Math.floor(voice.currentTime*60);const end=tab==='A'?D.cues[index].end_frame:focusCard?.end_frame||D.cues[index].end_frame;if(f>=D.total_frames-1||(mode==='single'&&f>=end-1)){pause();setFrame(Math.min(end-1,D.total_frames-1))}else setFrame(f,false)}requestAnimationFrame(tick)}
fetch('/data.json').then(r=>r.json()).then(data=>{D=data;index=Math.max(0,Math.min(346,(Number(new URLSearchParams(location.search).get('cue'))||1)-1));tab=location.pathname==='/bgm/'?'BGM':location.pathname.match(/review\/(A|B|C)/)?.[1]||'A';$('scrub').max=D.total_frames-1;
 document.querySelectorAll('nav a').forEach(a=>a.onclick=e=>{e.preventDefault();setTab(a.dataset.tab)});$('search').oninput=renderList;$('previous').onclick=()=>tab==='A'?go(index-1):goCard(D.aux[tab][Math.max(0,D.aux[tab].findIndex(e=>e.cue_first-1>=index)-1)]);$('next').onclick=()=>tab==='A'?go(index+1):goCard(D.aux[tab][Math.min(D.aux[tab].length-1,D.aux[tab].findIndex(e=>e.cue_first-1>=index)+1)]);$('play').onclick=()=>play('single');$('continuous').onclick=()=>play('continuous');$('scrub').oninput=e=>{pause();focusCard=null;setFrame(Number(e.target.value))};['showB','showC','showA','green'].forEach(id=>$(id).onchange=()=>overlays(frame));$('mark').onclick=()=>{const key=tab==='A'?index+1:focusCard?.id||D.aux[tab].find(e=>e.start_frame<=frame&&frame<e.end_frame)?.id;if(key&&!draft.seen.includes(key))draft.seen.push(key);saveLocal();renderList();$('saveStatus').textContent='已記錄本條已看'};$('save').onclick=()=>persist().catch(e=>$('saveStatus').textContent=e.message);$('saveMusic').onclick=()=>persist().catch(e=>$('saveMusic').textContent=e.message);setTab(tab,true);tick();
}).catch(err=>{$('caption').textContent='審核資料載入失敗：'+err.message});
