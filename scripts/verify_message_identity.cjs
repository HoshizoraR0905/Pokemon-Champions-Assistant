/* Offline browser checks for the frozen message/HUD comparison viewer. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert');
const source=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
if(fs.existsSync(out))throw Error('Choose a fresh browser-check directory');fs.mkdirSync(out,{recursive:true});
const profile=path.join(out,'chrome-profile'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless','--disable-gpu','--no-sandbox','--no-first-run','--user-data-dir='+profile,'--remote-debugging-port=0','file://'+source],{stdio:'ignore'});
let ws,id=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});ws.send(JSON.stringify({id:key,method,params}))})}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value}
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break}catch{await pause(100)}}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}};
 await send('Runtime.enable');await send('Network.enable');await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});await send('Page.reload');
 for(let i=0;i<100;i++){if(await ev("typeof DATA!=='undefined'&&document.querySelectorAll('#entries article').length===8"))break;await pause(100)}
 assert.equal(await ev("document.querySelectorAll('#entries article').length"),8);
 assert.equal(await ev("DATA.comparison.frozen_predictions_sha256.length"),64);
 await ev("document.querySelector('#filter').value='inconclusive';document.querySelector('#filter').dispatchEvent(new Event('change'))");assert.equal(await ev("document.querySelectorAll('#entries article').length"),2);
 await ev("document.querySelector('#filter').value='';document.querySelector('#time').value=104;document.querySelector('#time').dispatchEvent(new Event('input'))");assert.equal(await ev("document.querySelectorAll('#entries article').length"),2);
 await ev("document.querySelector('#time').value=444.25;document.querySelector('#time').dispatchEvent(new Event('input'));document.querySelectorAll('details').forEach(d=>d.open=true)");
 const images=await ev("(async()=>{const imgs=[...document.images];await Promise.all(imgs.map(async i=>{const probe=new Image();probe.src=i.src;await probe.decode()}));return imgs.length})()");assert.equal(images,14);assert.deepEqual(errors,[]);
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});fs.writeFileSync(path.join(out,'comparison.png'),Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 const result={status:'passed',network:'offline',entries:8,inconclusive_filter:2,early_timeline_entries:2,images_decoded:images,browser:(await send('Browser.getVersion')).product};fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result));
}catch(e){console.error(e);process.exitCode=1;fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors}),{flag:'wx'})}finally{if(ws)ws.close();browser.kill()}})();
