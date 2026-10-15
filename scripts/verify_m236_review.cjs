/* Local Chrome UI check: cached images only, no server or recognition. */
const fs=require('fs'),cp=require('child_process'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,fs.existsSync(path.join(root,'.cache/battles/sample_battle_5/m236u/review-manifest.json'))?'.cache/battles/sample_battle_5/m236u/browser-check':'.cache/battles/sample_battle_5/m236/review-v2-check');
fs.mkdirSync(dir,{recursive:true});
const inputHTML=path.join(root,'reports/M2.3.6-review/review.html');
const inputHash=require('crypto').createHash('sha256').update(fs.readFileSync(inputHTML)).digest('hex');
const profile=fs.mkdtempSync('/tmp/m236-review-v2-chrome-');
const chrome=cp.spawn(process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 ['--headless','--disable-gpu','--no-sandbox','--no-first-run','--user-data-dir='+profile,
  '--remote-debugging-port=0','--allow-file-access-from-files','--window-size=1480,1200',
  'file://'+path.join(root,'reports/M2.3.6-review/review.html')],{stdio:'ignore'});
let ws,id=0,pending=new Map(),errors=[];const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function send(method,params={}){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function waitFor(expression){for(let i=0;i<150;i++){if(await ev(expression))return;await pause(100)}const debug=await ev("({url:location.href,ready:document.readyState,title:document.getElementById('title')?.textContent,item:typeof state==='undefined'?null:state.item?.id})");throw Error('Browser condition timed out: '+expression+' '+JSON.stringify({debug,errors}))}
async function select(expression){await ev('choose('+expression+')');await waitFor("$('frame').complete && $('frame').naturalWidth>0");}
async function field(name,value){await ev(`$('${name}').value=${JSON.stringify(value)};$('${name}').dispatchEvent(new Event('input',{bubbles:true}))`)}
async function screenshot(name){const s=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(dir,name+'.png'),Buffer.from(s.data,'base64'))}
(async()=>{try{
 let port;for(let i=0;i<150;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch(e){await pause(100)}}
 const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(tabs.find(t=>t.type==='page'&&t.url.includes('/M2.3.6-review/review.html')).webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
 await send('Runtime.enable');await waitFor("typeof state!=='undefined' && state.item?.id==='occurrence:coaching'");
 const checks=[];
 assert.equal(await ev('DATA.u?.baseline_frame_count||DATA.frames.length'),120);assert.equal(await ev('DATA.events.filter(e=>e.reviewed_occurrence).length'),11);
 assert.equal(await ev("DATA.events.filter(e=>e.split==='held_out'&&e.kind==='move_execution').length"),2);checks.push('Actual-occurrence denominators remain 11 events / 2 held-out moves; frames are navigation evidence');
 await select("DATA.events.find(e=>e.kind==='background'&&e.frame_ids.some(id=>byFrame.get(id).visibility_review))");
 assert.equal(await ev("$('messageClass').value"),'no_message');assert.match(await ev("$('rawOCR').textContent"),/ype/);assert.match(await ev("$('frameAdmission').textContent"),/No semantic event was admitted/);
 assert.match(await ev("$('frameAssessment').textContent"),/not a missed readable battle message/);
 await field('messageClass','no_message');await field('frameFeedback','White flash: no readable battle message. Noise was correctly rejected.');
 await field('verdict','noise');await field('eventKind','no_message');assert.equal(await ev("annotations.frames[state.frame.id].message_class"),'no_message');
 await screenshot('white-transition');checks.push('No-text Mega animation: visible pixels, rejected ype, no false missed-message classification, actionable noise feedback');
 await select("DATA.events.find(e=>e.id==='occurrence:mega_revelation')");
 assert.match(await ev("$('rawOCR').textContent"),/超级进化/);assert.match(await ev("$('summary').textContent"),/Named unplaced episode/);
 await field('messageClass','readable_correct');await field('visibleMessage','对手的Big Mom超级进化成了超级袋兽！');await field('verdict','correct');await field('eventKind','mega');await field('actor','Big Mom / Kangaskhan');
 checks.push('Readable Mega message: correct recognition and admitted unplaced episode separated from animation frames');
 await select("DATA.events.find(e=>e.id==='occurrence:fake_out')");assert.match(await ev("$('rawOCR').textContent"),/击掌奇袭/);assert.match(await ev("$('summary').textContent"),/target\/effects are not asserted/);
 await field('messageClass','readable_correct');await field('verdict','correct');await field('eventKind','move');await field('actualEvent','Big Mom used Fake Out');await field('actor','Big Mom');await field('target','');
 assert.equal(await ev('annotations.events[state.item.id].target'),'');checks.push('Fake Out: actor editable, target can remain unknown, executed-move-only admission explained');
 await select("DATA.events.find(e=>e.id==='occurrence:coaching')");assert.match(await ev("$('summary').textContent"),/not successfully recognized/);
 await field('messageClass','readable_incorrect');await field('visibleMessage','对手的Invincible使出了指导！');await field('verdict','missing');await field('eventKind','move');await field('actualEvent','Invincible used Coaching');await field('actor','Invincible');await field('feedback','Move name is readable; cached OCR recovered only the prefix. Actor occupancy remains unproven.');
 checks.push('Coaching: failed move distinguished from background noise, visible-message and actor correction saved');
 await select("DATA.events.find(e=>e.id==='nickname:development:Big Nugget')");assert.match(await ev("$('summary').textContent"),/Identity remains unresolved/);assert.match(await ev("$('hudEvidence').textContent"),/Big Nugget/);
 await field('verdict','cannot_determine');await field('eventKind','identity');await field('species','');await field('feedback','Cannot identify the icon independently. Do not infer a species from the nickname.');
 await screenshot('nickname-review');checks.push('Unresolved nickname: same-frame icon evidence, unknown-species option and useful conservative feedback');
 await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:dir});const exported=path.join(dir,'m236-event-review-annotations.json');if(fs.existsSync(exported))fs.unlinkSync(exported);
 await ev("$('export').click()");for(let i=0;i<100&&!fs.existsSync(exported);i++)await pause(100);
 const data=JSON.parse(fs.readFileSync(exported));assert.equal(data.schema,'m236-human-review-v2');assert.equal(data.events['occurrence:coaching'].actor,'Invincible');assert.equal(data.events['occurrence:fake_out'].target,'');
 data.events['occurrence:coaching'].feedback='Imported structured coaching correction';const incoming=path.join(dir,'incoming.json');fs.writeFileSync(incoming,JSON.stringify(data));
 const dom=await send('DOM.getDocument'),node=await send('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#file'});await send('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[incoming]});await ev("$('file').dispatchEvent(new Event('change'))");await waitFor("$('notice').textContent.startsWith('Imported')");assert.equal(await ev("annotations.events['occurrence:coaching'].feedback"),'Imported structured coaching correction');
 await select("DATA.events.find(e=>e.id==='occurrence:coaching')");assert.equal(await ev("$('visibleMessage').value"),'对手的Invincible使出了指导！');
 await ev("location.reload()");await waitFor("typeof state!=='undefined' && state.item?.id==='occurrence:coaching'");assert.equal(await ev("$('feedback').value"),'Imported structured coaching correction');
 checks.push('Structured JSON export/import and browser reload preserve event values and frame visibility; frozen metrics unchanged');
 await field('verdict','incorrect');assert.equal(await ev('priority(state.item)'),1);assert.match(await ev("$('counts').textContent"),/1 flagged incorrect/);await field('verdict','missing');
 await ev("$('timelineView').click()");assert.equal(await ev('state.view'),'timeline');await ev("$('frameView').click()");assert.equal(await ev('listed.length'),await ev('DATA.frames.length'));
 await ev("$('previewView').click()");assert.equal(await ev('listed.length'),24);checks.push('Priority overrides, chronological groups, advanced 120-frame browsing and 24 preview rows work');

 if(await ev('!!DATA.u')){
  await ev("$('regionCategory').value='all';setView('queue')");
  await select("DATA.events.find(e=>e.id==='occurrence:coaching')");
  await field('readingSource','ui_u');assert.match(await ev("$('rawOCR').textContent"),/指导/);assert.match(await ev("$('uEvidence').textContent"),/Temporal occurrence/);
  assert.equal(await ev("DATA.u.replay_executions.filter(r=>r.status==='applied_partial').length"),1);
  assert.equal(await ev("DATA.u.replay_executions.filter(r=>r.reason==='move_actor_not_bound_to_observed_prefix').length"),1);
  for(const category of ['party_overlay','status_overlay','battle_log_overlay']){
   await ev(`$('regionCategory').value='${category}';setView('queue')`);
   assert.ok(await ev('listed.length>0'));await waitFor("$('frame').complete && $('frame').naturalWidth>0");
   assert.equal(await ev("$('messageClass').disabled"),true);
   assert.match(await ev("$('cropLabel').textContent"),/Overlay-specific/);
   if(category==='party_overlay')assert.match(await ev("$('uEvidence').textContent"),/Reserve HP is not active-slot HP/);
   if(category==='status_overlay')assert.match(await ev("$('uEvidence').textContent"),/Unlit stages are not reset/);
   if(category==='battle_log_overlay')assert.match(await ev("$('uEvidence').textContent"),/original event times unknown/);
  }
  await ev("$('regionCategory').value='move_description_overlay';setView('queue')");
  assert.equal(await ev('listed.length'),0);assert.match(await ev("$('title').textContent"),/No verified positive/);assert.equal(await ev("$('visualEvidence').hidden"),true);
  await ev("$('regionCategory').value='all';setView('queue')");
  await select("DATA.events.find(e=>e.u_category==='field_indicator'&&byFrame.get(e.frame_ids[0]).u.ui.regions.some(r=>r.canonical?.literal_counter==='4/5'))");
  assert.match(await ev("$('uEvidence').textContent"),/4\/5/);assert.match(await ev("$('uEvidence').textContent"),/Counter meaning remains unverified/);
  await field('fieldAbility','沙暴状态 — 4/5; duration meaning unknown');await field('errorCategory','none');
  if(fs.existsSync(exported))fs.unlinkSync(exported);await ev("$('export').click()");for(let i=0;i<100&&!fs.existsSync(exported);i++)await pause(100);
  const saved=JSON.parse(fs.readFileSync(exported)),fieldId=await ev('state.item.id');assert.equal(saved.events[fieldId].errorCategory,'none');assert.match(saved.events[fieldId].fieldAbility,/4\/5/);
  await screenshot('u-field-review');
  checks.push('U OCR comparison and prefix-safe actor admission; party/status/log crops and semantics; untested move-description category; field-counter feedback export');
 }
 const white=await ev('DATA.frames.find(f=>f.visibility_review).id');const legacy={schema:'m236-human-review-v1',battle_id:'sample_battle_5',annotations:{[white]:{note:'Preserved legacy note',reviewed:true}}};await ev('importAnnotations('+JSON.stringify(legacy)+')');assert.equal(await ev('annotations.legacy_annotations['+JSON.stringify(white)+'].note'),'Preserved legacy note');
 assert.equal(errors.length,0,JSON.stringify(errors));assert.equal(require('crypto').createHash('sha256').update(fs.readFileSync(inputHTML)).digest('hex'),inputHash);const result={status:'passed',input_html_sha256:inputHash,checks,browser_exceptions:errors,new_ocr:0,video_processing:0,annotations_used_only_in_temporary_browser_profile:true};fs.writeFileSync(path.join(dir,'browser-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{if(ws)ws.close();chrome.kill('SIGTERM')}})().catch(e=>{console.error(e);process.exitCode=1});
