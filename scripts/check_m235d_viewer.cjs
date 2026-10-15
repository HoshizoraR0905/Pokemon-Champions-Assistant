/* Offline browser checks only; no recognition or battle-state execution. */
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const viewer=path.resolve(process.argv[2]||'');if(!fs.existsSync(viewer))throw new Error('Pass the generated review.html path');
const out=path.dirname(viewer),profile=path.join(out,'browser-smoke-profile');
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const child=spawn(chrome,['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-extensions','--disable-sync','--metrics-recording-only','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:['ignore','ignore','pipe']});
let errorText='';child.stderr.on('data',d=>errorText+=d.toString());
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let ws,id=0,session,pending=new Map(),runtimeErrors=[];
function command(method,params={},sessionId=session){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params,...(sessionId?{sessionId}:{})}));setTimeout(()=>{if(pending.has(n)){pending.delete(n);reject(new Error(`CDP timeout: ${method}`))}},15000).unref()})}
async function evaluate(expression){const r=await command('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value}
function assert(value,message){if(!value)throw new Error(message)}
(async()=>{
 let endpoint;for(let i=0;i<100;i++){endpoint=errorText.match(/DevTools listening on (ws:\/\/[^\s]+)/)?.[1];if(endpoint)break;await pause(100)}assert(endpoint,'Chrome debugging endpoint missing');
 ws=new WebSocket(endpoint);await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true})});
 ws.addEventListener('message',({data})=>{const m=JSON.parse(data);if(m.method==='Runtime.exceptionThrown')runtimeErrors.push(m.params);const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result)}});
 const target=await command('Target.createTarget',{url:'about:blank'},null);session=(await command('Target.attachToTarget',{targetId:target.targetId,flatten:true},null)).sessionId;
 await command('Runtime.enable');await command('Page.enable');await command('Emulation.setDeviceMetricsOverride',{width:1550,height:1250,deviceScaleFactor:1,mobile:false});await command('Page.navigate',{url:pathToFileURL(viewer).href});
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('original')?.complete && document.getElementById('original')?.naturalWidth>0"))break;await pause(100)}
 assert(await evaluate("$('original').naturalWidth===1311"),'Full cached frame did not load');
 assert(await evaluate("DATA.frames.length===10"),'Expected seven snapshots plus missing reviewed HUD checkpoints');
 await evaluate("$('filter').value='snapshots';filter()");assert(await evaluate('frames.length===7'),'Snapshot filter');
 await evaluate("$('filter').value='held';filter()");assert(await evaluate('frames.length===5'),'All held-out positive checkpoints filter');
 await evaluate("$('frame').value=frames.findIndex(f=>Math.abs(f.timestamp-300.01666666666665)<1e-6);show()");await pause(250);
 assert(await evaluate("$('cards').children.length===4"),'Four HUD evidence cards missing');
 assert(await evaluate("selected.slots[0].final.admission_reason==='identity_not_independently_supported'"),'Held-out admission diagnostic missing');
 assert(await evaluate("$('overlay').querySelectorAll('.hudbox').length===12"),'HUD name/icon/HP regions missing');
 await evaluate("$('proximity').checked=true;$('proximity').onchange()");assert(await evaluate("$('proximityFlag').textContent.includes('UNSUPPORTED')"),'Proximity warning missing');
 await evaluate("$('question').value='no';$('question').onchange();note().scene_regions.push([100,100,180,190]);overlays()");assert(await evaluate("$('overlay').querySelectorAll('.scenebox').length===1"),'Separate manual 3D marking missing');
 const shot=await command('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'viewer-heldout-300.png'),Buffer.from(shot.data,'base64'));
 await evaluate("$('frame').value=frames.findIndex(f=>Math.abs(f.timestamp-456.01)<1e-6);show()");await pause(250);
 assert(await evaluate("selected.slots.length===0 && $('overlay').querySelectorAll('.hudbox').length===0"),'Missing predictions must not invent overlay boxes');
 assert(await evaluate("$('empty').textContent.includes('4 visible HUD slots')"),'Visible-but-unrecognized HUD distinction missing');
 assert(await evaluate("$('neighbors').querySelectorAll('img').length===4"),'Nearby cached full frames missing');
 const loaded=await evaluate("Array.from($('neighbors').querySelectorAll('img')).map(i=>i.src)");assert(loaded.every(x=>x.startsWith('file:')),'Viewer should use local cached images only');
 assert(runtimeErrors.length===0,JSON.stringify(runtimeErrors));
 fs.writeFileSync(path.join(out,'viewer-validation.json'),JSON.stringify({status:'passed',browser:'local Chrome headless',checks:['full uncropped cached frame loaded','ten diagnostic frames','seven snapshot filter','five held-out positive checkpoint filter','four slot cards and twelve source regions','color admission diagnostic','proximity-only unsupported warning','separate manual scene mark','missing observation has no fabricated regions','four nearby cached full frames','local image URLs','no runtime exceptions'],ocr_predictions:0,video_processing:false},null,2)+'\n');
 process.stdout.write('Viewer browser checks passed; no OCR or video processing.\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1}).finally(async()=>{if(ws){try{await command('Browser.close',{},null)}catch{}ws.close()}child.kill()});
