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
 await send('Runtime.enable');await wait("location.protocol==='file:'&&document.readyState==='complete'&&typeof DATA!=='undefined'");await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Page.reload');await wait("typeof DATA!=='undefined'&&document.querySelector('#content').children.length>0");
 const checks=[];
 for(const mode of ['slots','transitions','changes','failures','episodes','causes']){
  await ev(`document.querySelector('#mode').value='${mode}';document.querySelector('#mode').dispatchEvent(new Event('change'))`);
  assert.ok(await ev("document.querySelector('#content').children.length>0"));checks.push('renders '+mode);
 }
 await ev("document.querySelector('#mode').value='transitions';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),24);checks.push('24 complete switch/send-out/faint comparisons');
 await ev("document.querySelector('#filter').value='faint';document.querySelector('#filter').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),3);checks.push('three distinct faint departures');
 await ev("document.querySelector('#filter').value='recovered';document.querySelector('#filter').dispatchEvent(new Event('change'))");
 assert.ok(await ev("document.querySelectorAll('#content article').length>0"));checks.push('recovered transitions filter');
 await ev("document.querySelector('#filter').value='';document.querySelector('#mode').value='slots';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#slot-cards .card').length"),4);checks.push('four logical slots visible');
 const at=async(t,slot,expected)=>{
  await ev(`document.querySelector('#time').value=${t};document.querySelector('#time').dispatchEvent(new Event('input'))`);
  assert.ok(await ev(`document.querySelector('[data-slot="${slot}"]').textContent.includes('${expected}')`));
 };
 await at(500.1,'self:right','vacant');await at(527.1,'opponent:right','vacant');
 await at(541.6,'opponent:right','烈咬陆鲨');await at(651.6,'opponent:left','vacant');await at(673.6,'opponent:left','炽焰咆哮虎');checks.push('chronological withdrawals, faints and forced replacements');
 await ev("document.querySelector('#version').value='before';document.querySelector('#version').dispatchEvent(new Event('change'))");
 await at(500.1,'self:right','烈咬陆鲨');checks.push('frozen baseline retains its original receipt projection');
 await ev("document.querySelector('#version').value='after';document.querySelector('#version').dispatchEvent(new Event('change'));document.querySelector('#mode').value='episodes';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),14);checks.push('14 entry episodes separate from party size');
 await ev("document.querySelector('#filter').value='unproven';document.querySelector('#filter').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),6);checks.push('six historical individual relations explicitly unproven');
 await ev("document.querySelector('#mode').value='failures';document.querySelector('#filter').value='';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 assert.equal(await ev("document.querySelectorAll('#content article').length"),3);checks.push('three remaining move-binding diagnoses');
 const images=await ev(`(async()=>{const urls=[...new Set(Object.values(DATA.event_evidence).flat().map(p=>p.image).filter(Boolean))],failed=[];let next=0;await Promise.all(Array.from({length:4},async()=>{while(next<urls.length){const url=urls[next++],im=new Image();im.src=url;try{await im.decode()}catch{failed.push(url)}}}));return {count:urls.length,failed}})()`);
 assert.deepEqual(images.failed,[]);checks.push('all existing evidence PNGs load offline; zero images copied');
 await ev("document.querySelector('#mode').value='slots';document.querySelector('#mode').dispatchEvent(new Event('change'))");
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
 const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,'four-slots.png'),Buffer.from(shot.data,'base64'));
 assert.deepEqual(errors,[]);
 const result={status:'passed',browser:(await send('Browser.getVersion')).product,html_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),network:'offline',checks,images,independent_human_review:false,existing_images_copied:0,cleanup:'Browser profile and screenshot preserved'};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}),{flag:'wx'});process.exitCode=1}finally{if(ws)ws.close();browser.kill()}})();
