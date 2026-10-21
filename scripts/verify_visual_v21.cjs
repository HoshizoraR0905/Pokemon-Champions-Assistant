/* Browser validation over localhost without relaxing browser security. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert');
const out=path.resolve(process.argv[2]);if(fs.existsSync(out))throw Error('Choose fresh output');fs.mkdirSync(out,{recursive:true});
const profile=path.join(out,'chrome-profile'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless','--disable-gpu','--no-first-run','--user-data-dir='+profile,'--remote-debugging-port=0','http://127.0.0.1:8766/.cache/m34-visual-v21/review.html'],{stdio:'ignore'});
let ws,id=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});ws.send(JSON.stringify({id:key,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
(async()=>{try{
let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch{await pause(100)}}
const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
await send('Runtime.enable');const counts=[];
for(let n=5;n<=10;n++){
const base='http://127.0.0.1:8766/.cache/battles/sample_battle_'+n+'/m34-visual-v21/';
await send('Page.navigate',{url:base+'review.html'});for(let k=0;k<100;k++){if(await ev("document.querySelectorAll('.boundary').length>0"))break;await pause(100)}
assert(await ev("document.querySelectorAll('.boundary').length>=16"));assert.equal(await ev("document.querySelectorAll('details[open]').length"),0);
assert.equal(await ev("document.querySelectorAll('.status option:checked[value=\"\"]').length===document.querySelectorAll('.boundary').length"),true);
assert(await ev("[...document.querySelectorAll('a[href]')].every(a=>a.protocol==='http:')"));
const exportCheck=await ev("(async()=>{let saved;URL.createObjectURL=b=>{saved=b;return 'blob:review'};URL.revokeObjectURL=()=>{};HTMLAnchorElement.prototype.click=()=>{};document.querySelector('.status').value='human-approved';download();return JSON.parse(await saved.text())})()");assert.equal(exportCheck.decisions.length,1);assert.equal(exportCheck.decisions[0].human_approved,true);assert(!exportCheck.human_approved);
await send('Page.navigate',{url:base+'source.html'});for(let k=0;k<100;k++){if(await ev("document.querySelectorAll('section').length>0"))break;await pause(100)}
const c=await ev("document.querySelectorAll('img').length");assert(c>=200);counts.push({battle:n,grid_frames:c});
const img=await ev("document.querySelector('img').src");assert.equal((await fetch(img)).status,200);
const video=await fetch('http://127.0.0.1:8766/tests/fixtures/sample_battle_'+n+'.mp4',{headers:{Range:'bytes=0-31'}});assert.equal(video.status,206);assert.equal((await video.arrayBuffer()).byteLength,32);
}
assert.deepEqual(errors,[]);await send('Emulation.setDeviceMetricsOverride',{width:1400,height:1000,deviceScaleFactor:1,mobile:false});fs.writeFileSync(path.join(out,'source.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
const result={status:'passed',counts,browser:(await send('Browser.getVersion')).product,security:'Default Chrome security; localhost HTTP only',checks:['six source/review pages','source image HTTP200','video range HTTP206','predictions collapsed','no preselected approvals','single-field human approval export','no JS exceptions']};fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));
}catch(e){console.error(e);process.exitCode=1;fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}),{flag:'wx'})}finally{if(ws)ws.close();browser.kill()}})();
