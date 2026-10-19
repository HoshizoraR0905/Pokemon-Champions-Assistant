/* Offline saved-data HTML verification. Keeps profiles, screenshots and results. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert'),crypto=require('crypto');
const source=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
if(fs.existsSync(out))throw Error('Use a fresh validation output');fs.mkdirSync(out,{recursive:true});
const profile=path.join(out,'chrome-profile');
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless','--disable-gpu','--no-sandbox','--no-first-run','--user-data-dir='+profile,'--remote-debugging-port=0','file://'+source],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let ws,next=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function wait(expression){for(let i=0;i<100;i++){if(await ev(expression))return;await pause(100)}throw Error('Timeout '+expression)}
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch{await pause(100)}}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown'||m.method==='Network.loadingFailed')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
 await send('Runtime.enable');await wait("location.protocol==='file:'&&document.readyState==='complete'&&typeof DATA!=='undefined'");await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Page.reload');await wait("typeof DATA!=='undefined'&&document.querySelector('#content').children.length>0");
 const checks=[];
 async function select(id,value){await ev(`document.querySelector('#${id}').value=${JSON.stringify(value)};document.querySelector('#${id}').dispatchEvent(new Event('change'))`)}
 for(let mode of ['slots','events','transitions','deferred','baseline','references','frames']){
  await select('mode',mode);assert.ok(await ev("document.querySelector('#content').children.length>0"));checks.push('renders '+mode);
 }
 await select('mode','slots');assert.equal(await ev("document.querySelectorAll('#slot-cards .card').length"),4);
 for(let version of ['before','after']){await select('version',version);await ev("document.querySelector('#time').value=200;document.querySelector('#time').dispatchEvent(new Event('input'))");assert.equal(await ev("document.querySelectorAll('#slot-cards .card').length"),4)}
 checks.push('both four-slot timelines and video-time slider');
 await select('mode','transitions');assert.equal(await ev("document.querySelectorAll('#content article').length"),await ev('Math.min(40,DATA.transitions.length)'));
 await select('mode','deferred');await select('status','deferred');assert.ok(await ev("document.querySelector('#count').textContent.startsWith(String(DATA.deferred.filter(r=>r.after.status==='deferred').length)+' ')"));checks.push('deferred filter count');
 await select('status','');await select('mode','events');await select('side','opponent');await select('kind','move_execution');
 assert.ok(await ev("document.querySelector('#count').textContent.startsWith(String(DATA.events.filter(r=>r.after.side==='opponent'&&r.after.kind==='move_execution').length)+' ')"));checks.push('side and event type filters');
 await select('side','');await select('kind','');await select('mode','frames');await ev("document.querySelector('#more').click()");assert.ok(await ev("document.querySelectorAll('#content article').length>40"));checks.push('frame pagination');
 await ev("document.querySelector('#search').value='nonexistent-marker-rc';document.querySelector('#search').dispatchEvent(new Event('input'))");assert.equal(await ev("document.querySelectorAll('#content article').length"),0);checks.push('text search');
 await ev("document.querySelector('#search').value='';document.querySelector('#search').dispatchEvent(new Event('input'))");await select('mode','slots');
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
 fs.writeFileSync(path.join(out,'four-slots.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await select('mode','transitions');fs.writeFileSync(path.join(out,'transitions.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 const images=await ev(`(async()=>{const urls=[...new Set([...Object.values(DATA.event_evidence).flat().map(p=>p.image),...DATA.frames.map(p=>p.image),...DATA.reference_review.cases.flatMap(p=>p.evidence.map(q=>q.image))].filter(Boolean))],failed=[];let next=0;await Promise.all(Array.from({length:4},async()=>{while(next<urls.length){const url=urls[next++],im=new Image();im.src=url;try{await im.decode()}catch{failed.push(url)}}}));return{count:urls.length,failed}})()`);
 assert.deepEqual(images.failed,[]);assert.deepEqual(errors,[]);checks.push('all referenced saved PNGs decode offline; no copies');
 const result={status:'passed',html_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),browser:(await send('Browser.getVersion')).product,checks,images,network:'offline',existing_images_copied:0,independent_human_review:false};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}),{flag:'wx'});process.exitCode=1}finally{if(ws)ws.close();browser.kill()}})();
