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
 for(let mode of ['slots','triggers','changes','visibility','episodes']){
  await ev(`document.querySelector('#mode').value='${mode}';document.querySelector('#mode').dispatchEvent(new Event('change'))`);
  assert.ok(await ev("document.querySelector('#content').children.length>0"));checks.push('renders '+mode);
 }
 async function mode(value){await ev(`document.querySelector('#mode').value='${value}';document.querySelector('#mode').dispatchEvent(new Event('change'))`)}
 async function filter(value){await ev(`document.querySelector('#filter').value='${value}';document.querySelector('#filter').dispatchEvent(new Event('change'))`)}
 async function version(value){await ev(`document.querySelector('#version').value='${value}';document.querySelector('#version').dispatchEvent(new Event('change'))`)}
 async function at(t,slot,expected){await ev(`document.querySelector('#time').value=${t};document.querySelector('#time').dispatchEvent(new Event('input'))`);assert.ok(await ev(`document.querySelector('[data-slot="${slot}"]').textContent.includes('${expected}')`))}
 await mode('triggers');assert.equal(await ev("document.querySelectorAll('#content article').length"),55);
 await filter('self');assert.equal(await ev("document.querySelectorAll('#content article').length"),39);checks.push('55 old orange triggers;39 self;filters work');
 await filter('');await mode('changes');assert.equal(await ev("document.querySelectorAll('#content article').length"),await ev('DATA.changes.length'));checks.push('all changed receipts shown');
 await mode('episodes');assert.equal(await ev("document.querySelectorAll('#content article').length"),14);checks.push('14 episodes preserved');
 await mode('slots');assert.equal(await ev("document.querySelectorAll('#slot-cards .card').length"),4);
 await at(519.52,'self:left','supported_active');await at(519.52,'self:left','hud_not_visible');
 await at(375.514,'self:left','supported_active');await at(375.514,'self:left','hud_not_visible');await at(375.514,'self:right','hud_visible_consistent');checks.push('real attack shows only targeted HUD; other identities persist');
 await version('before');await at(519.52,'self:left','last_known_identity_current_evidence_unresolved');
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
 fs.writeFileSync(path.join(out,'before-519.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await version('after');await at(519.52,'self:left','supported_active');
 fs.writeFileSync(path.join(out,'after-519.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await at(500.1,'self:right','vacant');await at(527.1,'opponent:right','vacant');await at(541.6,'opponent:right','烈咬陆鲨');await at(651.6,'opponent:left','vacant');await at(673.6,'opponent:left','炽焰咆哮虎');checks.push('continuity and supported departure/replacement remain distinct');
 await version('before');await filter('unresolved');assert.ok(await ev("document.querySelector('#count').textContent.startsWith('55 ')"));
 await version('after');assert.ok(await ev("document.querySelector('#count').textContent.startsWith('0 ')"));checks.push('orange intervals compared against frozen baseline');
 await filter('');await mode('visibility');await ev("document.querySelector('#more').click()");assert.ok(await ev("document.querySelectorAll('#content article').length>60"));checks.push('visibility pagination');
 const images=await ev(`(async()=>{const urls=[...new Set([...Object.values(DATA.event_evidence).flat().map(p=>p.image),...DATA.visibility.map(p=>p.image)].filter(Boolean))],failed=[];let next=0;await Promise.all(Array.from({length:4},async()=>{while(next<urls.length){const url=urls[next++],im=new Image();im.src=url;try{await im.decode()}catch{failed.push(url)}}}));return{count:urls.length,failed}})()`);
 assert.deepEqual(images.failed,[]);assert.deepEqual(errors,[]);checks.push('all referenced saved PNGs decode offline; no copies');
 const result={status:'passed',html_sha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),browser:(await send('Browser.getVersion')).product,checks,images,network:'offline',existing_images_copied:0,independent_human_review:false};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}),{flag:'wx'});process.exitCode=1}finally{if(ws)ws.close();browser.kill()}})();
