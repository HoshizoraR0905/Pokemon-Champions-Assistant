/* Actual Chrome/CDP screenshots of the replay's one-based displayed positions. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),url=process.argv[2],out=path.resolve(process.argv[3]||'');
if(!url||!process.argv[3])throw Error('Usage: node scripts/capture_battle11_report.cjs URL OUTPUT_DIR');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const relative=p=>path.relative(root,p).split(path.sep).join('/');
const pointer=JSON.parse(fs.readFileSync(path.join(root,'.cache/battles/sample_battle_11/m322-reviewed-speed/latest.json')));
const replayPath=pointer.path,replay=JSON.parse(fs.readFileSync(replayPath));assert.equal(replay.frames.length,1008);
const viewport={width:1600,height:1200,deviceScaleFactor:1,mobile:false};
const inputs={url,replay:relative(replayPath),replay_sha256:hash(replayPath),positions:[543,575],viewport,
 code:Object.fromEntries(['scripts/capture_battle11_report.cjs','scripts/templates/speed_replay.html','scripts/templates/speed_replay.js','scripts/templates/speed_replay.css'].map(p=>[p,hash(path.join(root,p))]))};
fs.mkdirSync(out,{recursive:true});const receiptPath=path.join(out,'capture.json');
let receipt=fs.existsSync(receiptPath)?JSON.parse(fs.readFileSync(receiptPath)):null;
if(receipt)assert.deepEqual(receipt.inputs,inputs,'Changed capture inputs; use a new output directory to preserve existing figures');
receipt=receipt||{status:'running',inputs,method:'Chrome DevTools Protocol: dispatch existing slider input at displayed position minus one, await original image decode and two animation frames, capture unedited viewport as JPEG quality 90.',figures:[]};
const save=()=>{const p=receiptPath+'.tmp';fs.writeFileSync(p,JSON.stringify(receipt,null,2)+'\n');fs.renameSync(p,receiptPath);};
const valid=f=>fs.existsSync(path.join(out,f.file))&&hash(path.join(out,f.file))===f.sha256;
if(receipt.status==='complete'&&receipt.figures.length===2&&receipt.figures.every(valid)){console.log('Reused verified report figures:',relative(out));process.exit(0);}
save();
const profile=path.join(root,'.cache/m322/battle11-showcase-v1/chrome-'+Date.now());
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 ['--headless','--disable-gpu','--no-first-run','--user-data-dir='+profile,'--remote-debugging-port=0',url],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let ws,next=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function wait(expression){for(let i=0;i<200;i++){if(await ev(expression))return;await pause(100);}throw Error('Timeout: '+expression);}
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break;}catch{await pause(100);}}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',viewport);
 await wait("typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_11'&&$('frame').naturalWidth>0");
 assert.equal(await ev('DATA.artifact_directory'),relative(path.dirname(replayPath)));
 receipt.browser=(await send('Browser.getVersion')).product;
 for(const position of inputs.positions){
  const existing=receipt.figures.find(f=>f.display_position===position);if(existing&&valid(existing))continue;
  await ev(`$('timeline').value=${position-1};$('timeline').dispatchEvent(new Event('input'));window.scrollTo(0,0);`);
  await wait("$('frame').complete&&$('frame').naturalWidth>0");
  await ev("$('frame').decode().then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))");
  const state=await ev("(()=>{const s=DATA.snapshots[REPLAY_VIEW.snapshotIndex],id='sample_battle_11:opponent:encounter:02d2cc36c1af82e7',p=s.opponents[id],v=DATA.support_catalog[p.support_ref],card=document.querySelector('[data-individual=\\\"'+id+'\\\"]');return {display:$('frameCount').textContent,slider:Number($('timeline').value),time:REPLAY_VIEW.time,source:$('frame').getAttribute('src'),turn:$('turn').textContent,updates:REPLAY_VIEW.updateIds,layers:[...card.querySelectorAll('.support-layer')].map(e=>e.dataset.layer),target:{individual:id,current_form:p.current_form,active:p.active,observed:v.observed,full:v.full},bounds:{frame:$('frame').getBoundingClientRect().toJSON(),timeline:$('timeline').getBoundingClientRect().toJSON(),card:card.getBoundingClientRect().toJSON()}};})()");
  assert.equal(state.slider,position-1);assert.equal(state.display,`${position} / 1008`);assert.equal(state.time,replay.frames[position-1].timestamp);
  assert.equal(state.source,'/'+replay.frames[position-1].image);assert.deepEqual(state.layers,['observed','full']);
  for(const b of Object.values(state.bounds)){assert(b.top>=0);assert(b.bottom<=viewport.height);}
  const shot=await send('Page.captureScreenshot',{format:'jpeg',quality:90,captureBeyondViewport:false});
  const file=`frame-${String(position).padStart(4,'0')}.jpg`;fs.writeFileSync(path.join(out,file),Buffer.from(shot.data,'base64'));
  receipt.figures=receipt.figures.filter(f=>f.display_position!==position);
  const compact={...state,target:{individual:state.target.individual,current_form:state.target.current_form,active:state.target.active,observed:{complete_before:state.target.observed.complete_before,complete_after:state.target.observed.complete_after,incomplete_excluded:state.target.observed.incomplete_excluded,speed:state.target.observed.speed},full:{configuration_count:state.target.full.configuration_count,status:state.target.full.status,speed:state.target.full.speed}}};
  receipt.figures.push({display_position:position,slider_index:position-1,timestamp:state.time,file,sha256:hash(path.join(out,file)),source_frame:replay.frames[position-1],state:compact});
  receipt.status='running';save();console.log('Captured',position,'/ 1008 at',state.time,'seconds:',relative(path.join(out,file)));
 }
 assert.deepEqual(errors,[]);receipt.status='complete';receipt.errors=errors;save();
}catch(e){receipt.status='failed';receipt.error=String(e);receipt.errors=errors;save();console.error(e);process.exitCode=1;}
finally{if(ws)ws.close();browser.kill();}})();
