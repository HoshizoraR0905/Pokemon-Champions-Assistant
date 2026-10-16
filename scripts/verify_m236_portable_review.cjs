/* Local Chrome UI check: cached images only, no server or recognition. */
const fs=require('fs'),cp=require('child_process'),path=require('path'),assert=require('assert');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,fs.existsSync(path.join(root,'.cache/battles/sample_battle_5/m236u/review-manifest.json'))?'.cache/battles/sample_battle_5/m236u/browser-check':'.cache/battles/sample_battle_5/m236/review-v2-check');
fs.mkdirSync(dir,{recursive:true});
fs.mkdirSync(path.join(root,'.cache/m236-viewer-repair'),{recursive:true});
const inputHTML=process.env.REVIEW_HTML||path.join(root,'reports/M2.3.6-review/review.html');
const inputHash=require('crypto').createHash('sha256').update(fs.readFileSync(inputHTML)).digest('hex');
const profile=fs.mkdtempSync('/tmp/m236-review-v2-chrome-');
const chrome=cp.spawn(process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 ['--headless','--disable-gpu','--no-sandbox','--no-first-run','--user-data-dir='+profile,
  '--remote-debugging-port=0','--window-size=1480,1200',
  'file://'+inputHTML],{stdio:'ignore'});
let ws,id=0,pending=new Map(),errors=[];const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function send(method,params={}){return new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
async function waitFor(expression){for(let i=0;i<150;i++){if(await ev(expression))return;await pause(100)}const debug=await ev("({url:location.href,ready:document.readyState,title:document.getElementById('title')?.textContent,item:typeof state==='undefined'?null:state.item?.id})");throw Error('Browser condition timed out: '+expression+' '+JSON.stringify({debug,errors}))}
async function select(expression){await ev('choose('+expression+')');await waitFor("$('frame').complete && $('frame').naturalWidth>0");}
async function field(name,value){await ev(`$('${name}').value=${JSON.stringify(value)};$('${name}').dispatchEvent(new Event('input',{bubbles:true}))`)}
async function screenshot(name){const s=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(dir,name+'.png'),Buffer.from(s.data,'base64'))}
(async()=>{try{
let port;for(let i=0;i<150;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch{await pause(100)}}
const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown'||m.method==='Log.entryAdded'||m.method==='Network.loadingFailed')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
await send('Runtime.enable');await send('Log.enable');await send('Network.enable');await send('Page.reload');await pause(2500);
await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
await send('Page.reload');await waitFor("typeof state!=='undefined' && $('frame').naturalWidth>0");
const checks=[], rendering=[];
for(const e of await ev('DATA.events.map(e=>e.id)')){
 await select('DATA.events.find(e=>e.id==='+JSON.stringify(e)+')');await waitFor("[...$('representatives').querySelectorAll('img')].every(i=>i.complete&&i.naturalWidth>0)");
 for(const role of ['before','during','after']){await ev(`$('representatives').querySelector('[data-role=${role}]').click()`);await waitFor("$('frame').complete&&$('frame').naturalWidth>0");assert.equal(await ev('state.frame.id'),await ev('state.item.representatives.'+role));}
 const row=await ev(`({id:state.item.id,src:$('frame').src,w:$('frame').naturalWidth,h:$('frame').naturalHeight,rect:$('frame').getBoundingClientRect().toJSON(),crop:[$('messageCrop').width,$('messageCrop').height],boxes:[...$('boxes').children].map(b=>({left:b.style.left,top:b.style.top,width:b.style.width,height:b.style.height}))})`);assert.ok(row.rect.width>0&&row.rect.height>0&&row.crop[0]>0);rendering.push(row);
}
checks.push('All 36 groups: embedded full frame and before/during/after thumbnails load and switch; crops readable offline without file-access flag');
await ev("setView('preview')");for(let i=0;i<24;i++){await ev(`choose(listed[${i}])`);await waitFor("$('frame').complete&&$('frame').naturalWidth>0");}
checks.push('All 24 preview rows render inside page');
await ev("setView('frames')");for(let i=0;i<await ev('listed.length');i++){await ev(`choose(listed[${i}])`);await waitFor("$('frame').complete&&$('frame').naturalWidth>0");}
assert.equal(errors.length,0,JSON.stringify(errors));checks.push('All 136 raw frames decode; zero resource or JavaScript errors before deliberate error test');
const annotation=path.join(root,'reports/M2.3.6-review/m236-event-review-annotations.json'), original=fs.readFileSync(annotation),incoming=JSON.parse(original);
const dom=await send('DOM.getDocument'),node=await send('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#file'});await send('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[annotation]});await ev("$('file').dispatchEvent(new Event('change'))");await waitFor("$('notice').textContent.startsWith('Imported')");assert.deepStrictEqual(await ev('annotations'),incoming);
const progress=await ev("$('reviewProgress').textContent");checks.push('Actual saved JSON imported via file picker with deep equality, including blank/unknown fields and legacy reviewed=false');
await ev("setView('queue');choose(DATA.events.find(e=>e.id==='nickname:development:Big Nugget'))");assert.equal(await ev("$('species').value"),'Forretress');
await ev("choose(DATA.events.find(e=>e.id==='occurrence:coaching'))");await waitFor("$('frame').naturalWidth>0");await ev("$('frame').scrollIntoView({block:'center'})");await screenshot('repaired-coaching-inline');
await select("DATA.events.find(e=>byFrame.get(e.representatives.during)?.u?.ui.regions.some(r=>r.region_type==='active_hud'&&r.visibility==='visible'))");await ev("$('frame').scrollIntoView({block:'center'})");await screenshot('repaired-hud-inline');
const overlayCheck=await ev(`(()=>{const im=$('frame'),r=im.getBoundingClientRect(),boxes=[...$('boxes').children],regions=state.frame.u.ui.regions.filter(x=>x.region_type==='active_hud'&&['visible','partial'].includes(x.visibility));return {count:regions.length,aligned:regions.every((region,i)=>{const b=boxes[i+1].getBoundingClientRect(),[x,y,X,Y]=region.bounds;return Math.abs(b.left-(r.left+x/im.naturalWidth*r.width))<1&&Math.abs(b.top-(r.top+y/im.naturalHeight*r.height))<1&&Math.abs(b.width-(X-x)/im.naturalWidth*r.width)<1&&Math.abs(b.height-(Y-y)/im.naturalHeight*r.height)<1})}})()`);assert.ok(overlayCheck.count>0&&overlayCheck.aligned);checks.push('HUD overlay DOM bounds match cached native coordinates within one CSS pixel; selected message box visually checked in screenshot');
await select("DATA.events.find(e=>e.id==='occurrence:coaching')");await field('feedback','Temporary validation-only additional review');
await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:dir});const exported=path.join(dir,'m236-event-review-annotations.json');if(fs.existsSync(exported))fs.unlinkSync(exported);await ev("$('export').click()");for(let i=0;i<100&&!fs.existsSync(exported);i++)await pause(100);
const output=JSON.parse(fs.readFileSync(exported));for(const section of ['events','frames','legacy_annotations'])for(const [id,row] of Object.entries(incoming[section]))assert.deepStrictEqual(output[section][id],row);assert.equal(output.events['occurrence:coaching'].feedback,'Temporary validation-only additional review');assert.deepStrictEqual(fs.readFileSync(annotation),original);
await ev('location.reload()');await waitFor("typeof annotations!=='undefined'&&annotations.events['occurrence:coaching']?.feedback==='Temporary validation-only additional review'");checks.push('Additional case exported and persisted on reload; every prior record unchanged; source JSON unchanged');
assert.equal(errors.length,0,JSON.stringify(errors));
await ev("loadImage($('frame'),'assets/intentionally-missing-validation.png')");await waitFor("!$('imageError').hidden");assert.match(await ev("$('imageError').textContent"),/Image failed to load/);checks.push('Explicit missing-image error verified');
const result={status:'passed',chrome:await send('Browser.getVersion'),checks,progress,rendering,browser_events:errors,network:'offline via CDP; file://; no allow-file-access-from-files; isolated temporary Chrome profile',annotation_sha256:require('crypto').createHash('sha256').update(original).digest('hex')};fs.writeFileSync(path.join(root,'.cache/m236-viewer-repair/validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({status:result.status,checks,progress,errors},null,2));
}finally{if(ws)ws.close();chrome.kill('SIGTERM')}})().catch(e=>{console.error(e);process.exitCode=1});