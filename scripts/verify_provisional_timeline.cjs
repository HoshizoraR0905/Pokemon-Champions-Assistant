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
 await select("r=>r.timestamp===499.51666666666665&&r.type==='send_out'");
 assert.ok((await ev("document.querySelector('#content').innerText")).includes('occupied_unidentified'));checks.push('Papudo occupied_unidentified at send-out');
 const early=await ev("DATA.timeline.find(r=>r.timestamp===499.51666666666665&&r.type==='send_out').slots['opponent:right']");
 assert.equal(early.species_id,null);assert.equal(early.arrival,499.51666666666665);
 await select("r=>r.timestamp===503.0183333333333&&r.type==='move_execution'");assert.ok((await ev("document.querySelector('#content').innerText")).includes('occupied_unidentified'));checks.push('Gameplay interval keeps unidentified occupancy');
 await select("r=>r.timestamp===521.0216666666666&&r.slots['opponent:right'].species_id===279");
 const resolved=await ev("DATA.timeline[Number(document.querySelector('#time').value)].slots['opponent:right']");
 assert.equal(resolved.instance_id,early.instance_id);assert.equal(resolved.arrival,early.arrival);assert.equal(resolved.identity_resolution,521.0216666666666);checks.push('HUD resolution preserves instance and arrival');
 await select("r=>r.timestamp===123.00333333333333&&r.slots['opponent:left'].display_reference==='Torto'");assert.ok((await ev("document.querySelector('#content').innerText")).includes('occupied_unidentified'));checks.push('Torto opening provisional occupancy');
 assert.ok(await ev("DATA.summary.model_probes.every(p=>p.status==='abstained'&&p.species_id===null&&p.candidate_scores.every(c=>c.score===null))"));checks.push('Model probe abstentions remain distinct from human reference');
 const images=await ev("(async()=>{const urls=[...new Set([...document.querySelectorAll('img')].map(i=>i.src))],failed=[];for(const url of urls){const im=new Image();im.src=url;try{await im.decode()}catch{failed.push(url)}}return {count:urls.length,failed}})()");assert.deepEqual(images.failed,[]);checks.push('Local saved images decode offline');
 await send('Emulation.setDeviceMetricsOverride',{width:1500,height:1000,deviceScaleFactor:1,mobile:false});await select("r=>r.timestamp===499.51666666666665&&r.type==='send_out'");
 fs.writeFileSync(path.join(out,'provisional-arrival.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 assert.deepEqual(errors,[]);const result={status:'passed',html_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),checks,images,network:'offline',browser:(await send('Browser.getVersion')).product,independent_human_review:false};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}));process.exitCode=1}finally{if(ws)ws.close();browser.kill()}})();
