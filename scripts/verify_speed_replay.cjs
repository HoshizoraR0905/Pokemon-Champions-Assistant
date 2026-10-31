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
 let port;for(let i=0;i<100;i++){try{const candidate=fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0].trim();if(/^\d+$/.test(candidate)){port=candidate;break;}}catch{}await pause(100);}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 await send('Runtime.enable');
 const selectedBattle=new URL(url).searchParams.get('battle');
 if(new URL(url).searchParams.get('damage')==='1'&&['11','12'].includes(selectedBattle)){
  await wait(`typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_${selectedBattle}'&&DATA.offensive_inference&&$('frame').naturalWidth>0`);
  if(await ev("DATA.empirical_measure_model?.version==='M3.4.4'")){
   assert(await ev("DATA.empirical_measure_model.sampling==='all_eligible_vgc_occurrences_no_deduplication'&&DATA.empirical_scope.source==='vgcmulticalc'&&DATA.empirical_scope.observations_removed_by_deduplication===0&&!DATA.empirical_scope.publication_family_audit"));
   const checks=[],latencies=[],n=Number(selectedBattle),actor=n===12?'sample_battle_12:opponent:encounter:29f64303ef101514':'sample_battle_11:opponent:encounter:3a97ce2b12c2c2fe';
   const state=()=>ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${actor}'],s=DATA.support_catalog[p.support_ref],m=DATA.empirical_measures[s.observed.measure_ref]?.[$('empiricalAlpha').value];return {time:REPLAY_VIEW.time,damage:REPLAY_VIEW.damageUpdateIds,records:s.observed.complete_after,cores:m?.surviving_cores,moves:m?.moves,scores:m?.records.map(r=>[r.id,r.share,r.log_tilt]),attack:s.full.offensive_stats?.attack.values.values,special:s.full.offensive_stats?.special_attack.values.values,speed:s.full.speed.values,layers:[...document.querySelector('[data-individual="${actor}"]').querySelectorAll('.support-layer')].map(e=>e.dataset.layer)};})()`);
   if(n===12){
    await ev('seek(350)');const early=await state();assert(!early.moves.includes('pokeapi:move:473'));
    await ev('seek(360)');const announced=await state();assert(announced.moves.includes('pokeapi:move:473'));assert.equal(announced.records,13);assert.equal(announced.damage.length,0);
    const f=await ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${actor}'],m=DATA.empirical_measures[DATA.support_catalog[p.support_ref].observed.measure_ref]['0.5'];return m.frequencies['pokeapi:move:473'];})()`);assert.equal(f.positive,0);assert(Number.isFinite(f.effective_weight));
    await ev('seek(366)');const first=await state();assert.equal(first.records,1);assert.equal(first.cores,1);assert.equal(first.damage.length,1);
    await ev('seek(449)');const second=await state();assert.equal(second.records,1);assert.equal(second.damage.length,2);
    await ev('seek(714)');assert.equal((await state()).damage.length,2);
    await ev('seek(715)');const third=await state();assert.equal(third.records,1);assert.equal(third.damage.length,3);assert.equal(third.cores,1);
    assert(await ev("$('damageEvidence').textContent.includes('50/164 → 4/164')&&$('damageEvidence').textContent.includes('特攻阶段 -3')"));
    const u=await ev("(()=>{const u=DATA.offensive_inference.updates.at(-1);return {hp:u.observation.damage,stage:u.observation.stage_audit.stage,moveExclusions:u.observed.updates.reduce((n,v)=>n+v.move_membership_excluded_ids.length,0),items:u.full.updates.at(-1).item_evidence_excluded_ids.length,unknown:u.full.updates.at(-1).unresolved_after.configuration_classes,coreExclusions:u.observed.updates.map(v=>v.numerical_excluded_ids.length)};})()");
    assert.equal(u.hp,46);assert.equal(u.stage,-3);assert.equal(u.moveExclusions,0);assert.deepEqual(u.coreExclusions,[12,0,0]);assert.equal(u.items,1683);assert.equal(u.unknown,(await ev('DATA.offensive_inference.item_profile'))==='practical'?0:4158);
    await ev('seek(350)');assert.deepEqual(await state(),early);await ev('seek(715)');assert.deepEqual(await state(),third);
    checks.push('zero-count Psyshock is finite soft evidence; 13 occurrences tested, 12 occurrences numerically excluded, one original joint core survives three exact hits; source stage -3 and separate White Herb evidence exclusions; no future third-hit admission');
   }else{
    await ev('seek(162.53)');assert.equal((await state()).damage.length,0);await ev('seek(163.03)');const hit=await state();assert.deepEqual(hit.attack,Array.from({length:11},(_,i)=>108+i));assert.equal(hit.speed[0],150);assert.equal(hit.damage.length,1);assert(await ev("$('damageEvidence').textContent.includes('184/184 → 168/184')"));
    const aggregation=await ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${actor}'],m=DATA.empirical_measures[DATA.support_catalog[p.support_ref].observed.measure_ref]['0.5'],c=m.cores.find(c=>c.source_records>1),cat=DATA.empirical_core_catalogs[p.current_form];return {count:c.source_records,templates:new Set(c.records.map(id=>JSON.stringify(cat.records[id].template.moves))).size,share:c.share,sum:m.records.filter(r=>r.core_id===c.core_id).reduce((a,r)=>a+r.share,0),text:document.querySelector('[data-individual="${actor}"] .empirical-core').textContent};})()`);
    assert(aggregation.count>=2);assert(aggregation.templates>=2);assert(Math.abs(aggregation.share-aggregation.sum)<1e-12);assert(/\d+ 条来源记录/.test(aggregation.text));
    checks.push('Battle 11 source Fake Out 16 HP and full Attack 108–118 / Speed minimum 150 unchanged; distinct move templates on one core retain original occurrence counts and their summed UI mass');
   }
   assert.deepEqual((await state()).layers,['observed','full']);assert.deepEqual(await ev("[...$('battle').options].map(o=>o.value)"),['10','11','12']);
   assert(await ev(`document.querySelector('[data-individual="${actor}"] [data-layer=observed]').textContent.includes('不是对手持有该配置的概率')`));
   assert(await ev(`document.querySelector('[data-individual="${actor}"] .empirical-core')!==null`));
   await ev('window.__m344Data=DATA');const time=await ev('REPLAY_VIEW.time');
   for(const alpha of ['0','0.25','0.5','0.6','0.75','1']){await ev(`$('empiricalAlpha').value='${alpha}';$('empiricalAlpha').dispatchEvent(new Event('change'))`);assert(await ev('window.__m344Data===DATA'));assert.equal(await ev('REPLAY_VIEW.time'),time);latencies.push(await ev('REPLAY_VIEW.renderMs'));}
   await ev("$('empiricalAlpha').value='0.5';$('empiricalAlpha').dispatchEvent(new Event('change'))");
   const originalProfile=await ev('DATA.offensive_inference.item_profile'),saved=await state(),other=originalProfile==='practical'?'comprehensive':'practical';
   await ev(`$('itemProfile').value='${other}';$('itemProfile').dispatchEvent(new Event('change'))`);await wait(`DATA?.empirical_measure_model?.version==='M3.4.4'&&DATA.offensive_inference.item_profile==='${other}'`);assert.equal(await ev('REPLAY_VIEW.time'),time);assert.deepEqual((await state()).layers,['observed','full']);
   await ev(`$('itemProfile').value='${originalProfile}';$('itemProfile').dispatchEvent(new Event('change'))`);await wait(`DATA?.offensive_inference?.item_profile==='${originalProfile}'`);assert.deepEqual(await state(),saved);
   const reference=await ev(`(()=>{const p=document.querySelector('[data-individual="${actor}"] .reference-model');p.open=true;document.querySelector('[data-individual="${actor}"]').scrollIntoView({block:'start'});return p.open;})()`);assert(reference);
   await send('Page.enable');const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'m344-ranked-cores.png'),Buffer.from(shot.data,'base64'));
   checks.push('exactly two layers; compact joint-core shortlist with collapsed SP/provenance; six precomputed alpha scores change without domain rebuild; profile switch preserves timestamp and rewind; three-battle navigation intact');
   const range=await ev("(async()=>{const r=await fetch($('video').src,{headers:{Range:'bytes=0-63'}});return {status:r.status,bytes:(await r.arrayBuffer()).byteLength};})()");assert.equal(range.status,206);assert.equal(range.bytes,64);assert.deepEqual(errors,[]);
   const result={status:'passed',milestone:'M3.4.4',url,checks,state:await state(),render_ms:{maximum:Math.max(...latencies),samples:latencies.length},errors,recognition_accuracy:'not measured',independent_human_acceptance:false};fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));return;
  }
 }

 if(new URL(url).searchParams.get('battle')==='12'&&new URL(url).searchParams.get('damage')==='1'){
  await wait("typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_12'&&DATA.offensive_inference&&$('frame').naturalWidth>0");
  const actor='sample_battle_12:opponent:encounter:29f64303ef101514',checks=[],latencies=[];
  const state=()=>ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${actor}'],s=DATA.support_catalog[p.support_ref];return {ids:REPLAY_VIEW.damageUpdateIds,observed:s.observed.complete_after,exhaustion:s.observed.exhaustion_reason,full:s.full.offensive_stats?.special_attack.values.values,evaluated:s.full.offensive_stats?.special_attack.evaluated_support?.values.values,layers:[...document.querySelector('[data-individual="${actor}"]').querySelectorAll('.support-layer')].map(e=>e.dataset.layer)};})()`);
  await ev('seek(365)');const before=await state();assert.deepEqual(before.ids,[]);assert.equal(before.observed,13);
  await ev('seek(366)');const first=await state();assert.deepEqual(first.ids,['review:b12:received-4']);assert.equal(first.observed,0);assert.equal(first.exhaustion,'revealed_move_membership');assert.deepEqual(first.layers,['observed','full']);
  assert(await ev("$('damageEvidence').textContent.includes('184/184 → 58/184')"));
  assert(await ev(`document.querySelector('[data-individual="${actor}"] .empirical-exhaustion').textContent.includes('不表示原特攻数值')`));
  checks.push('first hit 126 HP; empty empirical support explicitly attributed to move membership; exactly two layers');
  await ev('seek(449)');const second=await state();assert.equal(second.ids.length,2);assert.deepEqual(second.evaluated,[...Array.from({length:49},(_,i)=>148+i),...Array.from({length:9},(_,i)=>198+i)]);
  assert(await ev("$('damageEvidence').textContent.includes('119/164 → 19/164')"));
  const results=await ev("DATA.offensive_inference.updates.map(u=>({hp:u.observation.damage,classes:u.full.updates.at(-1).after.configuration_classes,items:u.full.requirements.supported_items,unknown:u.full.updates.at(-1).unresolved_after.configuration_classes}))");
  assert.deepEqual(results.map(r=>r.hp),[126,100]);assert(results[0].items.includes('Life Orb'));assert(!results[1].items.includes('Life Orb'));assert(results[1].items.includes('Twisted Spoon'));assert(results[1].classes<results[0].classes);const initialProfile=await ev('DATA.offensive_inference.item_profile');assert.equal(results[1].unknown,initialProfile==='practical'?0:4158);
  checks.push('cumulative Special Attack support keeps integer gap at 197; Life Orb excluded in supported branches; unresolved branches preserved');
  assert(await ev(`!document.querySelector('[data-individual="${actor}"] .reference-model').open`));
  await ev(`document.querySelector('[data-individual="${actor}"] .reference-model summary').click()`);
  assert(await ev(`document.querySelector('[data-individual="${actor}"] [data-layer=full]').checkVisibility()`));
  if(initialProfile==='comprehensive')assert(await ev(`document.querySelector('[data-individual="${actor}"] .evaluated-support').textContent.includes('已计算分支')`));
  assert(await ev("$('itemPolicyNote').textContent.includes('休眠不等于证据排除')"));
  const otherProfile=initialProfile==='practical'?'comprehensive':'practical';
  const savedTime=await ev('REPLAY_VIEW.time');
  await ev(`$('itemProfile').value='${otherProfile}';$('itemProfile').dispatchEvent(new Event('change'))`);
  await wait(`DATA?.offensive_inference?.item_profile==='${otherProfile}'`);
  assert.equal(await ev('REPLAY_VIEW.time'),savedTime);const other=await state();assert.equal(other.ids.length,2);
  assert.equal(other.full.includes(140),otherProfile==='comprehensive');
  await ev(`$('itemProfile').value='${initialProfile}';$('itemProfile').dispatchEvent(new Event('change'))`);
  await wait(`DATA?.offensive_inference?.item_profile==='${initialProfile}'`);assert.deepEqual(await state(),second);
  await ev('seek(365)');assert.deepEqual((await state()).ids,[]);await ev('seek(449)');
  await ev(`(()=>{const p=document.querySelector('[data-individual="${actor}"] .reference-model');if(!p.open)p.querySelector('summary').click();})()`);
  checks.push('profile switching reads precomputed artifacts, preserves timestamp and two layers; policy dormancy distinguished from numerical exclusion; rewind remains causal');
  await wait("$('frame').complete&&$('frame').naturalWidth>0");await send('Page.enable');
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'battle12-after.png'),Buffer.from(shot.data,'base64'));
  await ev(`document.querySelector('[data-individual="${actor}"] [data-layer=full] [data-stat=special_attack]').scrollIntoView({block:'start'})`);
  const supportShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'hatterene-support.png'),Buffer.from(supportShot.data,'base64'));
  for(const t of [365,366,449,700,365,449]){await ev(`seek(${t})`);latencies.push(await ev('REPLAY_VIEW.renderMs'));}
  assert.deepEqual(await state(),second);await ev('seek(365)');assert.deepEqual(await state(),before);await ev('seek(366)');assert.deepEqual(await state(),first);await ev('seek(449)');
  checks.push('rewind removes both future hits; forward seeking restores exact earlier/final supports without solver execution');
  const range=await ev("(async()=>{const r=await fetch($('video').src,{headers:{Range:'bytes=0-63'}});return {status:r.status,bytes:(await r.arrayBuffer()).byteLength};})()");assert.equal(range.status,206);assert.equal(range.bytes,64);
  await ev("$('damageMode').checked=false;$('damageMode').dispatchEvent(new Event('change'))");await wait("DATA?.battle_id==='sample_battle_12'&&!DATA.offensive_inference");
  checks.push('original Speed mode and cached media byte ranges remain available');assert.deepEqual(errors,[]);
  const result={status:'passed',url,checks,results,render_ms:{samples:latencies.length,maximum:Math.max(...latencies)},errors,independent_human_acceptance:false,recognition_accuracy:'not measured'};
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));return;
 }
 await wait("typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_11'&&$('frame').naturalWidth>0");
 const initialArtifact=await ev("({battle:DATA.battle_id,directory:DATA.offensive_artifact_directory||DATA.artifact_directory,sourceSpeedHash:DATA.offensive_inference?.source_speed_sha256||null})");
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
 if(new URL(url).searchParams.get('damage')==='1'){
  await ev('seek(162.53)');assert.deepEqual(await ev('REPLAY_VIEW.damageUpdateIds'),[]);
  assert.equal(await ev("document.querySelectorAll('.offensive-stat[data-direct-constraint=true]').length"),0);
  const beforeDamage=await ev("$('opponents').textContent+'|'+$('damageEvidence').textContent");
  await ev('seek(163.03)');assert.deepEqual(await ev('REPLAY_VIEW.damageUpdateIds'),['review:b11:fakeout-hp']);
  const damage=await ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${raichu}'],s=DATA.support_catalog[p.support_ref];return {attack:s.full.offensive.values.values,speed:s.full.speed.minimum,observed:s.observed.complete_after,layers:[...document.querySelector('[data-individual="${raichu}"]').querySelectorAll('.support-layer')].map(e=>e.dataset.layer),hp:$('damageEvidence').textContent};})()`);
  assert.deepEqual(damage.attack,[108,109,110,111,112,113,114,115,116,117,118]);assert.equal(damage.speed,150);assert.equal(damage.observed,52);assert.deepEqual(damage.layers,['observed','full']);assert(damage.hp.includes('184/184 → 168/184'));
  const offense=await ev(`(()=>{const card=document.querySelector('[data-individual="${raichu}"]'),stats=card.querySelectorAll('[data-layer=observed] .offensive-stat'),panel=card.querySelector('.reference-model');return {stats:[...stats].map(e=>e.dataset.stat),special:card.querySelector('[data-layer=observed] [data-stat=special_attack]').textContent,closed:!panel.open,hidden:!card.querySelector('[data-layer=full]').checkVisibility(),damageClosed:[...$('damageEvidence').querySelectorAll('.reference-model')].every(e=>!e.open)};})()`);
  assert.deepEqual(offense.stats,['attack','special_attack']);assert(offense.special.includes('尚无该数值的承伤直接约束'));assert(offense.closed&&offense.hidden&&offense.damageClosed,JSON.stringify(offense));
  await ev(`document.querySelector('[data-individual="${raichu}"] .reference-model summary').click()`);
  assert(await ev(`document.querySelector('[data-individual="${raichu}"] [data-layer=full]').checkVisibility()`));
  checks.push('observed Attack and Special Attack share survivors; no claimed special-damage evidence; full model collapsed by default and expandable in cards and damage evidence');
  const afterDamage=await ev("$('opponents').textContent+'|'+$('damageEvidence').textContent");
  await ev('seek(502);seek(162.53)');assert.equal(await ev("$('opponents').textContent+'|'+$('damageEvidence').textContent"),beforeDamage);
  await ev('seek(163.03)');assert.equal(await ev("$('opponents').textContent+'|'+$('damageEvidence').textContent"),afterDamage);
  checks.push('own HP 184→168; Attack 108–118 and joint Speed minimum 150; 52 move-compatible observed members; causal backward/forward damage restoration with two layers');
  await wait("$('frame').complete&&$('frame').naturalWidth>0");await send('Page.enable');const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'damage-after.png'),Buffer.from(shot.data,'base64'));
 }
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
 if(new URL(url).searchParams.get('damage')==='1'){await ev("$('damageMode').checked=false;$('damageMode').dispatchEvent(new Event('change'))");await wait("DATA?.battle_id==='sample_battle_11'&&!DATA.offensive_inference");checks.push('original Speed replay mode remains available');}
 for(const number of [10,12,11]){await ev(`$('battle').value='${number}';$('battle').dispatchEvent(new Event('change'))`);await wait(`DATA?.battle_id==='sample_battle_${number}'&&$('frame').naturalWidth>0`);await ev('seek(300)');await wait("$('frame').complete&&$('frame').naturalWidth>0");checks.push('Battle '+number+' loads original screenshot');}
 await ev('seek(440.51)');await wait("$('frame').complete&&$('frame').naturalWidth>0");await send('Page.enable');const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(out,'replay.png'),Buffer.from(shot.data,'base64'));
 assert.deepEqual(errors,[]);latencies.sort((a,b)=>a-b);
 const result={status:'passed',url,initialArtifact,browser:(await send('Browser.getVersion')).product,checks,imageChecks,range,seeked,
   render_ms:{samples:latencies.length,median:latencies[Math.floor(latencies.length/2)],maximum:Math.max(...latencies)},
   errors,independent_human_acceptance:false,recognition_accuracy:'not measured'};
 fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}catch(e){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors},null,2));console.error(e);process.exitCode=1;}
finally{if(ws)ws.close();browser.kill();}})();
