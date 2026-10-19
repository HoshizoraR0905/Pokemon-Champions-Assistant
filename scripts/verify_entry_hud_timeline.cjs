/* Offline timeline checks; preserves browser evidence in a fresh directory. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert'),crypto=require('crypto');
const source=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
if(fs.existsSync(out))throw Error('Use a fresh validation directory');fs.mkdirSync(out,{recursive:true});
const profile=path.join(out,'chrome-profile');
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless','--disable-gpu','--no-sandbox','--no-first-run','--user-data-dir='+profile,'--remote-debugging-port=0','file://'+source],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let ws,next=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function wait(expression){for(let i=0;i<100;i++){if(await ev(expression))return;await pause(100)}throw Error('Timeout '+expression)}
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch{await pause(100)}}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown'||m.method==='Network.loadingFailed')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
 await send('Runtime.enable');await wait("document.readyState==='complete'&&typeof DATA!=='undefined'&&document.querySelectorAll('.card').length===4");
 await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Page.reload');await wait("typeof DATA!=='undefined'&&document.querySelectorAll('.card').length===4");
 const checks=[];
 async function select(predicate){await ev(`(()=>{const i=DATA.timeline.findIndex(${predicate});if(i<0)throw Error('Timeline point absent');document.querySelector('#time').value=i;document.querySelector('#time').dispatchEvent(new Event('input'));return i})()`)}
 const battle=await ev("DATA.summary.battle_id");
 assert.ok(await ev("document.querySelector('#audit')!==null"));
 assert.ok(await ev("DATA.summary.recognition_calls===0&&DATA.summary.video_decoding===0&&DATA.summary.model_probes.length===0"));
 checks.push('Saved-only timeline; no scene inference');
 if(battle==='sample_battle_5'&&await ev("DATA.summary.provisional_episodes.some(e=>e.hud_display_name)")){
 await select("r=>r.timestamp===133.02166666666668&&r.slots['opponent:right'].display_name==='Big Nugget'&&r.slots['opponent:left'].display_name==='Invincible'");
 const pair=await ev("DATA.timeline[Number(document.querySelector('#time').value)].slots");
 assert.equal(pair['opponent:right'].display_reference,'级别对战大师Big Nugget');
 assert.equal(pair['opponent:left'].display_reference,'喜欢宝可梦的Invincible');
 assert.equal(pair['opponent:right'].display_name_evidence.possible_title_segment,'级别对战大师');
 assert.equal(pair['opponent:left'].display_name_evidence.possible_title_segment,'喜欢宝可梦的');
 assert.ok((await ev("document.querySelector('#content').innerText")).includes('Message reference:'));
 checks.push('Battle 5 authoritative HUD names and original references stay separate');
 }
 if(battle==='sample_battle_7'){
 await select("r=>r.timestamp===499.51666666666665&&r.type==='send_out'");
 const early=await ev("DATA.timeline[Number(document.querySelector('#time').value)].slots['opponent:right']");
 assert.equal(early.species_id,null);assert.equal(early.occupancy,'occupied_unidentified');
 await select("r=>r.timestamp===503.0183333333333&&r.type==='move_execution'");
 assert.equal(await ev("DATA.timeline[Number(document.querySelector('#time').value)].slots['opponent:right'].species_id"),null);
 await select("r=>r.timestamp===521.0216666666666&&r.slots['opponent:right'].species_id===279");
 const resolved=await ev("DATA.timeline[Number(document.querySelector('#time').value)].slots['opponent:right']");
 assert.equal(resolved.instance_id,early.instance_id);assert.equal(resolved.arrival,early.arrival);
 assert.equal(resolved.identity_resolution,521.0216666666666);
 assert.equal(resolved.hud_binding.first_candidate_time,520.0216666666666);
 assert.equal(resolved.hud_binding.first_eligible_time,520.0216666666666);
 assert.ok((await ev("document.querySelector('#audit').innerText")).includes('first_eligible_time'));
 checks.push('Papudo same episode, causal resolution and first-HUD provenance');
 await select("r=>r.timestamp===133.02166666666668&&r.slots['opponent:left'].species_id===1018");
 const torto=await ev("DATA.timeline[Number(document.querySelector('#time').value)].slots['opponent:left']");
 assert.equal(torto.hud_binding.first_eligible_time,132.02166666666668);
 assert.ok(torto.hud_binding.candidates.some(c=>c.reasons.includes('reused_identity')));
 checks.push('Torto first HUD and inconclusive reused frame remain audited');
 }
 const first=await ev("DATA.timeline.findIndex(r=>Object.values(r.slots).some(s=>s.hud_binding))");
 assert.ok(first>=0);await ev("document.querySelector('#time').value="+first+";document.querySelector('#time').dispatchEvent(new Event('input'))");
 const images=await ev("(async()=>{const urls=[...new Set([...document.querySelectorAll('img')].map(i=>i.src))],failed=[];for(const url of urls){const im=new Image();im.src=url;try{await im.decode()}catch{failed.push(url)}}return {count:urls.length,failed}})()");assert.deepEqual(images.failed,[]);checks.push('Local saved images decode offline');
 await send('Emulation.setDeviceMetricsOverride',{width:1500,height:1000,deviceScaleFactor:1,mobile:false});await ev("document.querySelector('#time').value="+first+";document.querySelector('#time').dispatchEvent(new Event('input'))");
 fs.writeFileSync(path.join(out,'provisional-arrival.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 assert.deepEqual(errors,[]);const result={status:'passed',html_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),checks,images,network:'offline',browser:(await send('Browser.getVersion')).product,independent_human_review:false};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}));process.exitCode=1}finally{if(ws)ws.close();browser.kill()}})();
