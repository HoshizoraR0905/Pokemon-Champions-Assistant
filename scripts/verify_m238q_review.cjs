/* Offline browser validation for the saved-event audit. Keeps all artifacts. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert'),crypto=require('crypto');
const source=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
if(fs.existsSync(out))throw Error('Validation output exists; choose a new version');
fs.mkdirSync(out,{recursive:true});
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
 await send('Runtime.enable');await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Page.reload');await wait("typeof DATA!=='undefined'&&document.querySelector('#content').children.length>0");
 const checks=[];
 for(const mode of ['timeline','moves','slots','coverage','issues']){
  await ev(`document.querySelector('#mode').value='${mode}';document.querySelector('#mode').dispatchEvent(new Event('change'))`);
  assert.ok(await ev("document.querySelector('#content').children.length>0"));checks.push('renders '+mode);
 }
 await ev("document.querySelector('#mode').value='moves';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content tr').length-1"),23);checks.push('23 move table rows');
 await ev("document.querySelector('#filter').value='partially_applied';document.querySelector('#filter').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content tr').length-1"),9);checks.push('nine partially applied moves');
 await ev("document.querySelector('#filter').value='deferred';document.querySelector('#filter').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content tr').length-1"),14);checks.push('14 deferred moves');
 await ev("document.querySelector('#mode').value='timeline';document.querySelector('#filter').value='';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 for(const filter of ['missing','deferred','ambiguous','duplicate','partially_applied']){
  await ev(`document.querySelector('#filter').value='${filter}';document.querySelector('#filter').dispatchEvent(new Event('change'))`);
  assert.ok(await ev("document.querySelectorAll('#content article').length>0"));checks.push('nonempty '+filter+' filter');
 }
 await ev("document.querySelector('#filter').value='duplicate';document.querySelector('#filter').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),2);checks.push('two suppressed semantic collisions');
 await ev("document.querySelector('#filter').value='';document.querySelector('#search').value='战胜了';document.querySelector('#search').dispatchEvent(new Event('input'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),1);checks.push('observed battle outcome searchable');
 await ev("document.querySelector('#search').value='';document.querySelector('#search').dispatchEvent(new Event('input'));document.querySelector('#observations').checked=true;document.querySelector('#observations').dispatchEvent(new Event('change'))");
 assert.ok(await ev("document.querySelector('#count').textContent.startsWith(String(DATA.counts.inventory_rows))"));checks.push('full inventory count including observations');
 // Decode only existing PNG evidence, never video or recognition models.
 const images=await ev(`(async()=>{const urls=[...new Set(DATA.inventory.flatMap(e=>e.evidence||[]).map(p=>p.href).filter(Boolean))],failed=[];let next=0;await Promise.all(Array.from({length:4},async()=>{while(next<urls.length){const url=urls[next++],im=new Image();im.src=url;try{await im.decode()}catch{failed.push(url)}}}));return {count:urls.length,failed}})()`);
 assert.deepEqual(images.failed,[]);checks.push('existing relative evidence PNGs load offline without copying');
 await ev("document.querySelector('#mode').value='moves';document.querySelector('#observations').checked=false;document.querySelector('#mode').dispatchEvent(new Event('change'))");
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
 const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'moves.png'),Buffer.from(shot.data,'base64'));
 assert.deepEqual(errors,[]);
 const result={status:'passed',browser:(await send('Browser.getVersion')).product,html_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),network:'offline',checks,images,independent_human_review:false,existing_images_copied:0,cleanup:'Browser profile and screenshot preserved'};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}),{flag:'wx'});process.exitCode=1}finally{if(ws)ws.close();browser.kill()}})();
