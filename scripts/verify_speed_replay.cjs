/* Local Chrome/CDP validation. Original frames and videos are never modified. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert');
const url=process.argv[2],out=path.resolve(process.argv[3]);
if(!url||!out)throw Error('Usage: node scripts/verify_speed_replay.cjs URL OUTPUT_DIR');
if(fs.existsSync(out))throw Error('Use a new validation directory');
fs.mkdirSync(out,{recursive:true});const profile=path.join(out,'chrome-profile');
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
 ['--headless','--disable-gpu','--no-first-run','--window-size=1440,1000','--user-data-dir='+profile,'--remote-debugging-port=0',url],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let ws,next=0;const pending=new Map(),errors=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function wait(expression){for(let i=0;i<150;i++){if(await ev(expression))return;await pause(100);}throw Error('Timeout: '+expression);}
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{port=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];break;}catch{await pause(100);}}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 await send('Runtime.enable');await wait("typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_11'&&$('frame').naturalWidth>0");
 const checks=[],latencies=[],imageChecks=[];
 for(const time of [0,141,172.03,174.03,174.53,200,333.03,349.03,418.01,433.53,440.51,494.52,501.02,620]){
  await ev(`seek(${time})`);await wait("$('frame').complete&&$('frame').naturalWidth>0");
  const view=await ev("({view:REPLAY_VIEW,src:$('frame').getAttribute('src'),future:DATA.reviewed_inference.updates.filter(u=>REPLAY_VIEW.updateIds.includes(u.id)&&u.timestamp>REPLAY_VIEW.time).length})");
  assert.equal(view.future,0);assert(view.view.time<=time);latencies.push(view.view.renderMs);imageChecks.push({requested:time,actual:view.view.time,src:view.src});
 }
 await ev('seek(200)');const before=await ev("$('opponents').textContent+'|'+$('deductions').textContent");
 await ev('seek(620);seek(200)');assert.equal(await ev("$('opponents').textContent+'|'+$('deductions').textContent"),before);checks.push('backward/forward candidate and deduction restoration');
 const raichu='sample_battle_11:opponent:encounter:3a97ce2b12c2c2fe';
 await ev('seek(147.03)');assert.equal(await ev(`REPLAY_VIEW.forms['${raichu}']`),null);
 const abilityView=()=>ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${raichu}'],s=DATA.support_catalog[p.support_ref];return {active:p.active_ability||null,observed:s.observed.complete_after,abilities:s.full.branches.map(b=>b.ability),mapped:Object.values(s.observed.ability_mappings||{}).map(m=>m.active_ability)};})()`);
 const preMegaAbility=await abilityView();assert.equal(preMegaAbility.active,null);assert(!preMegaAbility.abilities.includes('No Guard'));assert(!preMegaAbility.mapped.includes('No Guard'));
 const heading=await ev(`document.querySelector('[data-individual="${raichu}"] h2').textContent`);
 assert(heading.startsWith('雷丘'));assert(!heading.includes('阿罗拉'));checks.push('unresolved Raichu uses canonical species heading, possibilities separate');
 const causalBefore=await ev("JSON.stringify({forms:REPLAY_VIEW.forms,occupancy:REPLAY_VIEW.occupancy,opponents:$('opponents').textContent})");
 await ev('seek(158.03)');assert.equal(await ev(`REPLAY_VIEW.forms['${raichu}']`),'pokeapi:form:10530');
 const postMegaAbility=await abilityView();assert.equal(postMegaAbility.active,'No Guard');assert.equal(postMegaAbility.observed,68);assert(postMegaAbility.mapped.every(a=>a==='No Guard'));
 await ev('seek(502);seek(147.03)');assert.equal(await ev("JSON.stringify({forms:REPLAY_VIEW.forms,occupancy:REPLAY_VIEW.occupancy,opponents:$('opponents').textContent})"),causalBefore);
 assert.deepEqual(await abilityView(),preMegaAbility);checks.push('68 published Mega Raichu Y members retain source abilities; active ability switches causally and restores on rewind');
 checks.push('Mega Raichu Y form and backward/forward form/item/occupant/support restoration');
 await ev('seek(210.01)');let tx=await ev("actionRows(REPLAY_VIEW.time,currentTurn(REPLAY_VIEW.time)).find(e=>e.kind==='voluntary_switch')");assert(tx);assert.equal(tx.outgoing.species,'pokeapi:species:637');assert.equal(tx.incoming,null);assert.equal(tx.arrival_time,null);
 await ev('seek(213.51)');tx=await ev("actionRows(REPLAY_VIEW.time,currentTurn(REPLAY_VIEW.time)).find(e=>e.kind==='voluntary_switch')");assert.equal(tx.incoming.species,'pokeapi:species:727');checks.push('Volcarona recall and Incineroar arrival appear at their own evidence times');
 await ev('seek(338.53)');tx=await ev("actionRows(REPLAY_VIEW.time,currentTurn(REPLAY_VIEW.time)).find(e=>e.kind==='pivot_replacement')");assert(tx.pivot_move_id);assert.equal(tx.incoming,null);
 await ev('seek(344.53)');tx=await ev("actionRows(REPLAY_VIEW.time,currentTurn(REPLAY_VIEW.time)).find(e=>e.kind==='pivot_replacement')");assert.equal(tx.incoming.species,'pokeapi:species:637');assert.equal(tx.phase,'move_resolution');checks.push('Parting Shot transaction reveals incoming Volcarona causally, outside voluntary-switch phase');
 await ev('seek(200)');const layers=await ev("(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['sample_battle_11:opponent:encounter:d44d3edfc6ac6181'];const v=DATA.support_catalog[p.support_ref];const c=document.querySelector('[data-individual=\"sample_battle_11:opponent:encounter:d44d3edfc6ac6181\"]');return {order:[...c.querySelectorAll('.support-layer')].map(x=>x.dataset.layer),rendered:c.querySelector('[data-layer=full] .ranges').textContent,expected:intervals(v.full.speed),observed:v.observed.complete_after,full:v.full.speed.values,observedValues:v.observed.speed.values};})()");
 assert.deepEqual(layers.order,['observed','full']);assert.equal(layers.rendered,layers.expected);assert.equal(layers.observed,29);assert(layers.full.length>layers.observedValues.length);checks.push('two-layer ordering and gapped Volcarona values match stored solver projection');
 await ev('seek(174.03)');assert.deepEqual(await ev('REPLAY_VIEW.updateIds'),[]);
 await ev('seek(174.53)');assert((await ev('REPLAY_VIEW.updateIds')).includes('review:b11:initial'));checks.push('constraint available only at second observed action');
 await ev("$('timeline').value=400;$('timeline').dispatchEvent(new Event('input'))");assert.equal(await ev('REPLAY_VIEW.framePosition'),400);
 await ev("$('nextFrame').click()");assert.equal(await ev('REPLAY_VIEW.framePosition'),401);
 await ev("$('prevFrame').click()");assert.equal(await ev('REPLAY_VIEW.framePosition'),400);
 for(const id of ['nextTurn','prevTurn','nextEvent','prevEvent'])await ev(`$('${id}').click()`);checks.push('discrete slider and frame/turn/event navigation');
 const range=await ev("(async()=>{const r=await fetch($('video').src,{headers:{Range:'bytes=0-63'}});return {status:r.status,range:r.headers.get('Content-Range'),bytes:(await r.arrayBuffer()).byteLength};})()");
 assert.equal(range.status,206);assert.equal(range.bytes,64);checks.push('MP4 byte-range seeking');
 await ev("$('seekVideo').click()");await wait("$('video').readyState>=1");
 const seeked=await ev("({video:$('video').currentTime,frame:REPLAY_VIEW.time})");assert(Math.abs(seeked.video-seeked.frame)<.1);checks.push('actual video metadata and timestamp seek');
 for(const number of [10,12,11]){await ev(`$('battle').value='${number}';$('battle').dispatchEvent(new Event('change'))`);await wait(`DATA?.battle_id==='sample_battle_${number}'&&$('frame').naturalWidth>0`);await ev('seek(300)');await wait("$('frame').complete&&$('frame').naturalWidth>0");checks.push('Battle '+number+' loads original screenshot');}
 await ev('seek(440.51)');await wait("$('frame').complete&&$('frame').naturalWidth>0");await send('Page.enable');const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'replay.png'),Buffer.from(shot.data,'base64'));
 assert.deepEqual(errors,[]);latencies.sort((a,b)=>a-b);
 const result={status:'passed',url,browser:(await send('Browser.getVersion')).product,checks,imageChecks,range,seeked,
   render_ms:{samples:latencies.length,median:latencies[Math.floor(latencies.length/2)],maximum:Math.max(...latencies)},
   errors,independent_human_acceptance:false,recognition_accuracy:'not measured'};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(e){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors},null,2));console.error(e);process.exitCode=1;}
finally{if(ws)ws.close();browser.kill();}})();
