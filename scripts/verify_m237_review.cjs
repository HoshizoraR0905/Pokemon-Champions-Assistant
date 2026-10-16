/* Offline Chrome validation of the Battle 6 extension, using isolated notes. */
const fs=require('fs'),cp=require('child_process'),path=require('path'),os=require('os'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),cache=process.env.M237_CACHE_DIR||path.join(root,'.cache/battles/sample_battle_6/m237');
const source=process.env.M237_REVIEW_DIR||path.join(root,'reports/battles/sample_battle_6/M2.3.7/review');
const fast=process.env.M237_FAST_REVIEW_CHECK==='1';
const out=path.join(cache,fast?'browser-control-check':'browser-check');fs.mkdirSync(out,{recursive:true});
const portable=fs.mkdtempSync(path.join(os.tmpdir(),'m237-portable-')),profile=fs.mkdtempSync(path.join(os.tmpdir(),'m237-chrome-'));
fs.copyFileSync(path.join(source,'review.html'),path.join(portable,'review.html'));fs.mkdirSync(path.join(portable,'assets'));
for(const file of fs.readdirSync(path.join(source,'assets'))){const from=path.join(source,'assets',file),to=path.join(portable,'assets',file);try{fs.linkSync(from,to)}catch{fs.copyFileSync(from,to)}}
const chrome=cp.spawn(process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 ['--headless','--disable-gpu','--no-sandbox','--no-first-run','--user-data-dir='+profile,'--remote-debugging-port=0','--window-size=1480,1200','file://'+path.join(portable,'review.html')],{stdio:'ignore'});
let ws,id=0,pending=new Map(),errors=[];const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function send(method,params={}){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function waitFor(expression){for(let i=0;i<200;i++){if(await ev(expression))return;await pause(100)}throw Error('Timed out: '+expression)}
async function field(name,value){await ev(`$('${name}').value=${JSON.stringify(value)};$('${name}').dispatchEvent(new Event('input',{bubbles:true}))`)}
async function screenshot(name){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'))}
(async()=>{try{
 let port;for(let i=0;i<150;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch{await pause(100)}}
 const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(['Runtime.exceptionThrown','Network.loadingFailed'].includes(m.method))errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
 await send('Runtime.enable');await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Page.reload');
 await waitFor("typeof state!=='undefined'&&state.frame&&$('frame').complete&&$('frame').naturalWidth>0");
 assert.equal(await ev('DATA.metrics.independently_reviewed_events'),0);assert.equal(await ev('annotations.battle_id'),'sample_battle_6');
 const checks=[];
 // Decode every packaged frame in Chrome with bounded concurrent memory.
 const prior=fast?JSON.parse(fs.readFileSync(path.join(cache,'browser-check/validation.json'),'utf8')):null;if(fast)assert.equal(prior.html_sha256,crypto.createHash('sha256').update(fs.readFileSync(path.join(source,'review.html'))).digest('hex'));
 const decode=fast?{count:0,failed:[]}:await ev(`(async()=>{const paths=[...new Set(DATA.frames.map(f=>f.image))],failed=[];let i=0;async function worker(){while(i<paths.length){const src=paths[i++];await new Promise(resolve=>{const im=new Image();im.onload=()=>{if(!im.naturalWidth)failed.push(src);resolve()};im.onerror=()=>{failed.push(src);resolve()};im.src=src;});}}await Promise.all(Array.from({length:8},worker));return {count:paths.length,failed};})()`);
 assert.deepEqual(decode.failed,[]);checks.push(fast?'Reused matching-HTML full asset/decode receipt from browser-check/validation.json':`All ${decode.count} source-frame assets decoded in offline Chrome outside repository`);
 const selected=await ev(`(()=>{const selected=new Set();const kinds=new Set();for(const e of DATA.events){if(!kinds.has(e.kind)){kinds.add(e.kind);selected.add(e.id)}}for(const t of DATA.turns){const e=DATA.events.find(e=>e.start>=t.start&&e.start<t.end);if(e)selected.add(e.id)}for(let i=0;i<DATA.events.length;i+=Math.max(1,Math.floor(DATA.events.length/40)))selected.add(DATA.events[i].id);return [...selected]})()`);
 for(const key of (fast?selected.slice(0,3):selected)){await ev('choose(DATA.events.find(e=>e.id==='+JSON.stringify(key)+'))');await waitFor("$('frame').complete&&$('frame').naturalWidth>0&&[...$('representatives').querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0)");
  for(const role of ['before','during','after']){await ev(`$('representatives').querySelector('[data-role=${role}]').click()`);await waitFor("$('frame').complete&&$('frame').naturalWidth>0");assert.equal(await ev('state.frame.id'),await ev('state.item.representatives.'+role));}
  const size=await ev("({w:$('frame').getBoundingClientRect().width,h:$('frame').getBoundingClientRect().height,crop:$('messageCrop').width})");assert.ok(size.w>0&&size.h>0&&size.crop>0);
 }
 checks.push(`${fast?Math.min(3,selected.length):selected.length} representative groups across all proposed turns and candidate kinds: embedded full image, crop and before/during/after`);
 const diagnostic=await ev("DATA.events.find(e=>e.diagnostic_note?.kind==='missed_move')?.id||null");
 if(diagnostic){await ev('choose(DATA.events.find(e=>e.id==='+JSON.stringify(diagnostic)+'))');const originalUI=await ev('JSON.stringify(state.frame.u.ui)');assert.equal(await ev("$('messageClass').disabled"),true);await ev("$('overlayReviewOverride').checked=true;$('overlayReviewOverride').dispatchEvent(new Event('change'))");assert.equal(await ev("$('messageClass').disabled||$('visibleMessage').disabled"),false);await field('visibleMessage','Synthetic override validation only');assert.equal(await ev('JSON.stringify(state.frame.u.ui)'),originalUI);checks.push('Human overlay review override enables transcription corrections while frozen UI evidence stays unchanged');}
 await ev("turnPicker.value=DATA.turns.find(t=>t.number!==null)?.id||DATA.turns[0].id;turnPicker.onchange()");
 const chosen=await ev('DATA.turns.find(t=>t.id===turnPicker.value)');assert.ok(await ev('listed.every(e=>e.start>='+chosen.start+'&&e.start<'+chosen.end+')'));
 await ev("document.querySelector('[data-turn-field=verdict]').value='provisional';document.querySelector('[data-turn-field=verdict]').dispatchEvent(new Event('input'))");
 await field('actor','test actor');await field('target','');await field('status','test status');await field('item','test item');await field('turnNumber','99');await field('duplicateOf','test duplicate');
 await ev("$('missingEventText').value='Test omitted event at 123s; synthetic browser validation only';$('addMissingEvent').click()");
 checks.push('Turn filtering/boundary notes; actor, blank target, status, item, turn/order and duplicate corrections; missed-event note');
 const exported=await ev('structuredClone(annotations)');assert.ok(Object.keys(exported.turns).length>0);assert.ok(Object.values(exported.events).some(e=>e.verdict==='missing'));
 // Test actual download and file picker import, not only the in-memory object.
 const downloads=path.join(out,'downloads');fs.mkdirSync(downloads,{recursive:true});await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});await ev("$('export').click()");
 let filename;for(let i=0;i<100;i++){filename=fs.readdirSync(downloads).find(f=>f.endsWith('.json'));if(filename)break;await pause(100)}assert.ok(filename);
 const downloaded=JSON.parse(fs.readFileSync(path.join(downloads,filename),'utf8'));assert.deepEqual(downloaded,exported);
 downloaded.future_field={unknown:'preserved'};const imported=path.join(out,'test-import.json');fs.writeFileSync(imported,JSON.stringify(downloaded));
 await send('DOM.enable');const doc=await send('DOM.getDocument');const node=await send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#file'});await send('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[imported]});await waitFor("$('notice').textContent.startsWith('Imported')");
 assert.deepEqual(await ev('structuredClone(annotations)'),downloaded);
 await send('Page.reload');await waitFor("typeof turnPicker!=='undefined'&&$('frame').naturalWidth>0");assert.deepEqual(await ev('structuredClone(annotations)'),downloaded);
 checks.push('Actual annotation download, file-picker import, blank/unknown-field preservation and reload persistence in isolated profile');
 assert.ok(await ev("(()=>{try{importAnnotations({schema:'m237-human-review-v1',battle_id:'sample_battle_5'});return false}catch{return true}})()"));
 await screenshot('offline-review');assert.deepEqual(errors,[]);
 const result={status:'passed',browser:(await send('Browser.getVersion')).product,html_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(source,'review.html'))).digest('hex'),checks,errors,manual_ground_truth:false,network:'offline',file_access_override:false};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
 }catch(error){fs.writeFileSync(path.join(out,'error.json'),JSON.stringify({error:String(error),errors},null,2));console.error(error);process.exitCode=1;}finally{if(ws)ws.close();const exited=new Promise(resolve=>chrome.once('exit',resolve));chrome.kill();await Promise.race([exited,pause(5000)]);fs.rmSync(portable,{recursive:true,force:true,maxRetries:10,retryDelay:100});fs.rmSync(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});}})();
