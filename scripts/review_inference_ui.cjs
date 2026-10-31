/* Browser-only presentation review. Reads sealed replays; never runs a solver. */
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert'),crypto=require('crypto');
const output=path.resolve(process.argv[2]||''),baseline=process.argv.includes('--baseline');
if(!process.argv[2]||fs.existsSync(output))throw Error('Usage: node scripts/review_inference_ui.cjs NEW_OUTPUT_DIR [--baseline]');
fs.mkdirSync(output,{recursive:true});
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const receipt={milestone:process.argv.includes('--m345a')?'M3.4.5a':'M3.4.5',status:'running',stage:'browser_start',human_acceptance:false,inputs:{},packages:[],screenshots:{}};
for(const file of ['scripts/templates/speed_replay.html','scripts/templates/speed_replay.js','scripts/templates/speed_replay.css','scripts/review_inference_ui.cjs','tests/fixtures/replay_ui/m345-support-states.json'])receipt.inputs[file]=hash(fs.readFileSync(path.join(__dirname,'..',file)));
for(const battle of [11,12])for(const profile of ['practical','comprehensive']){const pointer=JSON.parse(fs.readFileSync(path.join(__dirname,`../.cache/battles/sample_battle_${battle}/m342-offensive/latest-${profile}.json`),'utf8'));const manifest=JSON.parse(fs.readFileSync(path.join(path.dirname(pointer.path),'manifest.json'),'utf8'));assert.equal(manifest.status,'complete');receipt.packages.push({battle,profile,path:pointer.path,fingerprint:pointer.fingerprint,replay_sha256:manifest.outputs['replay.json']});}
function checkpoint(stage,status='running'){receipt.stage=stage;receipt.status=status;const temp=path.join(output,'manifest.tmp');fs.writeFileSync(temp,JSON.stringify(receipt,null,2));fs.renameSync(temp,path.join(output,'manifest.json'));}
checkpoint('browser_start');
const browser=cp.spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless','--disable-gpu','--no-first-run','--window-size=1440,1000','--user-data-dir='+path.join(output,'chrome-profile'),'--remote-debugging-port=0','about:blank'],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let ws,serial=0;const pending=new Map(),errors=[],states=[];
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});}
async function ev(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function wait(expression){for(let i=0;i<200;i++){if(await ev(expression))return;await pause(100);}throw Error('Timeout '+expression);}
async function shot(name){await pause(70);const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const bytes=Buffer.from(r.data,'base64');fs.writeFileSync(path.join(output,name+'.png'),bytes);receipt.screenshots[name+'.png']=hash(bytes);checkpoint('captured:'+name);}
const scenarios={11:[['before-moves',159],['after-fakeout',163.03],['speed-order',349.53],['later-moves',502]],12:[['before-psyshock',350],['first-hit',366],['second-hit',449],['additional-moves',652],['before-third',714],['third-hit',715]]};
(async()=>{try{
 let port;for(let i=0;i<100;i++){try{const p=fs.readFileSync(path.join(output,'chrome-profile/DevToolsActivePort'),'utf8').split('\n')[0];if(/^\d+$/.test(p)){port=p;break;}}catch{}await pause(100);}
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params);if(pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
 await send('Runtime.enable');await send('Page.enable');
 for(const battle of [11,12]){
  await send('Page.navigate',{url:`http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=${battle}&damage=1`});
  await wait(`typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_${battle}'&&$('frame').naturalWidth>0`);
  for(const [name,time] of scenarios[battle]){
   await ev(`seek(${time});window.scrollTo(0,0)`);await wait("$('frame').complete&&$('frame').naturalWidth>0");
   const state=await ev(`({time:REPLAY_VIEW.time,damage:REPLAY_VIEW.damageUpdateIds,text:$('opponents').innerText,renderMs:REPLAY_VIEW.renderMs,overflow:document.documentElement.scrollWidth>innerWidth})`);
   states.push({battle,name,...state});await shot(`b${battle}-${name}-desktop`);
  }
  console.log('Captured Battle '+battle);
 }
 if(process.argv.includes('--m345a'))await validateTeamItems({ev,send,shot,wait,states,output});
 else if(!baseline&&typeof validatePresentation==='function')await validatePresentation({ev,send,shot,wait,states,output});
 assert.deepEqual(errors,[]);checkpoint('complete','complete');fs.writeFileSync(path.join(output,'validation.json'),JSON.stringify({status:'passed',phase:baseline?'baseline inspection':'M3.4.5 automated presentation validation',states,errors,human_acceptance:false,recognition_accuracy:'not measured'},null,2));
 }catch(error){receipt.error=String(error);checkpoint('failed','failed');fs.writeFileSync(path.join(output,'error.txt'),error.stack);console.error(error);process.exitCode=1;}finally{if(ws)ws.close();browser.kill();}})();

async function validatePresentation({ev,send,shot,wait,states,output}){
 const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'../tests/fixtures/replay_ui/m345-support-states.json'),'utf8'));
 await ev(`window.__realReplay=DATA;
 window.__renderControlled=(spec,time=0)=>{
  const set=intervals=>{const values=intervals.flatMap(([a,b])=>Array.from({length:b-a+1},(_,i)=>a+i));return {values,intervals,count:values.length,minimum:values[0]??null,maximum:values.at(-1)??null};};
  const full={status:'exact',configuration_count:spec.reference_classes,speed:set(spec.speed),items:['Iron Ball','Quick Claw'],abilities:['fixture ability'],unresolved_reasons:[],item_policy:{profile:spec.profile||'comprehensive',dormant:spec.dormant||[],retained:['Iron Ball','Quick Claw'],inapplicable_stones:[]},offensive_stats:{},training_domain_refs:[]};
  for(const stat of ['attack','special_attack']){const projection={stat,values:set(spec[stat]),speed:full.speed,configuration_classes:spec.reference_classes,direct_constraint:true,evidence_ids:['controlled'],unresolved:[],requirements:{},items:full.items,abilities:full.abilities};
   if(spec.evaluated_classes!==undefined){projection.unresolved=[{reason:'controlled unsupported branch'}];projection.evaluated_support={values:set(spec['evaluated_'+stat]),speed:set(spec.evaluated_speed),configuration_classes:spec.evaluated_classes};}
   full.offensive_stats[stat]=projection;
  }
  const records={},coreCatalog={},weighted=[],cores=[];
  for(let i=0;i<spec.occurrences;i++){const cid='c'+(spec.cores===2&&i===2?1:0);records['o'+i]={core_id:cid,original_record_ids:['team:'+i+':member:0'],template:{moves:['controlled:template:'+i],publications:[{id:'team:'+i}]}};coreCatalog[cid]={nature:'nature:calm',item:'fixture item',ability:'fixture ability',stats:{attack:110,special_attack:165,speed:90},training_points:{hp:1,attack:1,defense:1,special_attack:1,special_defense:1,speed:1}};weighted.push({id:'o'+i,core_id:cid,share:spec.cores?1/spec.occurrences:0,hard_excluded:!spec.cores,matched:[]});}
  for(let i=0;i<spec.cores;i++){const ids=weighted.filter(r=>r.core_id==='c'+i).map(r=>r.id);cores.push({core_id:'c'+i,share:ids.length/spec.occurrences,records:ids,source_records:ids.length,matched_moves:[]});}
  const measure={eligible_records:spec.occurrences,surviving_records:spec.cores?spec.occurrences:0,surviving_cores:spec.cores,status:spec.cores?'conditional_empirical_measure':'empirical_exhausted',moves:[],records:weighted,cores};
  const observed={complete_before:spec.occurrences,complete_after:measure.surviving_records,measure_ref:'controlled',builds:[],speed:set(spec.cores?[[90,90]]:[])};
  const futureTrace={before:{configuration_classes:8,speed:full.speed},after:{configuration_classes:8,speed:full.speed},selector:{offensive_stat:'attack'},before_offensive_stats:full.offensive_stats,after_offensive_stats:full.offensive_stats,numerical_excluded_ids:[],item_evidence_excluded_ids:[]};
  const future={timestamp:20,observation:{id:'controlled:future-damage',timestamp:20,attacker:'controlled:actor',attacker_form:'controlled:form',target_form:'controlled:target',move:'controlled:future-move',damage:10,hp_attribution:{before:{current:100,maximum:100},after:{current:90,maximum:100}},input:{field:{}},sources:[]},full:{updates:[futureTrace]},observed:{updates:[futureTrace]}};
  DATA={...window.__realReplay,names:{'controlled:form':{en:'控制测试个体'},'controlled:future-move':{en:'未来招式'}},support_catalog:{controlled:{full,observed,conditions:[]}},empirical_measures:{controlled:{'0.5':measure}},empirical_core_catalogs:{'controlled:form':{cores:coreCatalog,records}},observed_builds:{},training_domains:{},form_configuration_support:{},reviewed_inference:{review:{identity_links:{}}},offensive_inference:{updates:[future],item_events:[{individual:'controlled:actor',battle_id:'controlled',kind:'held',item:'未来道具',timestamp:20,available_at:20}]},turns:[],action_timeline:[{timestamp:20,kind:'executed_move',side:'opponent',individual:'controlled:actor',move:'controlled:future-move',sources:[]}]};
  renderOpponents({opponents:{'controlled:actor':{active:true,species:'controlled:form',current_form:'controlled:form',support_ref:'controlled'}}},[],time);renderDamage(time);renderActions(time,null);
  return {text:$('opponents').textContent,visible:$('opponents').innerText,state:document.querySelector('[data-individual="controlled:actor"]').dataset.supportState,shares:measure.cores.map(c=>c.share),referenceOpen:document.querySelector('.opponent-card .reference-model').open};
 };`);
 const checks=[];
 for(const spec of fixtures.cases){
  const rendered=await ev(`__renderControlled(${JSON.stringify(spec)})`);
  for(const text of spec.expect)assert(rendered.text.includes(text),spec.id+' missing '+text);
  for(const text of spec.absent||[])assert(!rendered.text.includes(text),spec.id+' unexpected '+text);
  assert(!rendered.referenceOpen,spec.id+' diagnostics should be collapsed');
  if(spec.cores)assert(Math.abs(rendered.shares.reduce((a,b)=>a+b,0)-1)<1e-12);
  if(!spec.cores)assert(await ev("document.querySelector('.fallback-summary')!==null"));
  if(['empty-empirical','disjoint','provisional','both-empty','single-core','no-sample'].includes(spec.id)){
   await ev(`$('frame').closest('.viewer').hidden=true;document.querySelector('header h1').textContent='控制测试 · 非真实战斗证据';document.querySelector('main').style.display='block';document.querySelector('aside').style.maxWidth='720px';window.scrollTo(0,0)`);
   if(spec.id==='provisional')await ev("document.querySelector('.opponent-card .reference-model').open=true");
   await shot('controlled-'+spec.id);
  }
  checks.push(spec.id+': displayed wording and exact projections verified');
 }
 const available=fixtures.cases[0],empty=fixtures.cases[1];
 const earlier=await ev(`__renderControlled(${JSON.stringify(available)},0)`);await ev(`__renderControlled(${JSON.stringify(empty)},0)`);assert.deepEqual(await ev(`__renderControlled(${JSON.stringify(available)},0)`),earlier);checks.push('rewind restores identical sample support, shares and text');
 await ev("window.__originalEvents=EVENTS;EVENTS=[{id:'controlled:future-marker',timestamp:20,kind:'executed_move',text:'未来招式',move:'controlled:future-move'},{id:'controlled:future-hp',timestamp:20,kind:'own_hp_damage',text:'未来伤害 10'}];markers()");
 assert(await ev("[...$('markers').querySelectorAll('button')].every(b=>!b.title.includes('未来招式')&&!b.title.includes('未来伤害'))"));
 await ev('EVENTS=window.__originalEvents;delete window.__originalEvents;markers()');
 assert(!earlier.text.includes('未来道具')&&!earlier.text.includes('未来招式'));assert(await ev("!$('damageEvidence').textContent.includes('100/100')&&!$('actions').textContent.includes('未来招式')"));
 const later=await ev(`__renderControlled(${JSON.stringify(available)},20)`);assert(later.text.includes('未来道具')&&later.text.includes('未来招式'));assert(await ev("$('damageEvidence').textContent.includes('100/100 → 90/100')&&$('actions').textContent.includes('未来招式')"));
 assert.deepEqual(await ev(`__renderControlled(${JSON.stringify(available)},0)`),earlier);checks.push('future item, executed move and HP evidence appear only at availability and disappear on rewind');
 await ev("DATA=window.__realReplay;delete window.__realReplay;delete window.__renderControlled");
 // Restore production view through navigation; controlled tests never edit artifacts.
 for(const battle of [11,12]){
  await send('Page.navigate',{url:`http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=${battle}&damage=1&t=${battle===11?163.03:714.5033333333333}`});
  await wait(`typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_${battle}'&&$('frame').complete&&$('frame').naturalWidth>0`);
  const actor=battle===11?'sample_battle_11:opponent:encounter:3a97ce2b12c2c2fe':'sample_battle_12:opponent:encounter:29f64303ef101514';
  await ev(`window.__sealedData=DATA;window.__beforeDomain=JSON.stringify(DATA.support_catalog);`);
  for(const profile of ['practical','comprehensive']){
   await ev(`$('itemProfile').value='${profile}';$('itemProfile').dispatchEvent(new Event('change'))`);await wait(`DATA?.offensive_inference?.item_profile==='${profile}'&&$('frame').complete`);
   const time=await ev('REPLAY_VIEW.time');
   const text=await ev(`document.querySelector('[data-individual="${actor}"]').innerText`);
   if(battle===11){assert(text.includes('108–118'));assert(text.includes('150–185 ∪ 187–196 ∪ 198–200'));assert(text.includes('16 HP'));}
   else{assert(text.includes('46 HP'));assert(text.includes('特攻阶段 -3'));assert(text.includes('VGC 1/13 次出现'));assert(text.includes('100% 仅指剩余 VGC 样本'));
    assert.equal(await ev(`DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${actor}'].current_form`),'pokeapi:species:858');
    if(profile==='practical')assert(text.includes('160–171 ∪ 175–188 ∪ 193–196 ∪ 198–206'));
    else{assert(text.includes('4158 类机制未决'));assert(text.includes('140–196 ∪ 198–206'));}
   }
   const count=await ev(`document.querySelector('[data-individual="${actor}"] [data-layer=observed]').querySelectorAll('.empirical-core').length`);assert(count>0&&count<=3);
   assert.equal(await ev("$('opponents').firstElementChild.dataset.individual"),actor);
   for(const [width,height,label] of [[1440,1000,'desktop'],[1100,780,'laptop'],[820,900,'narrow']]){
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});await ev('window.scrollTo(0,0)');
    assert(await ev('document.documentElement.scrollWidth<=innerWidth'),`Overflow ${battle} ${width}`);
    assert(await ev(`(()=>{const p=document.querySelector('[data-individual="${actor}"] .stat-summary');return p.scrollWidth<=p.clientWidth})()`));
    await shot(`b${battle}-${profile}-${label}`);states.push({battle,profile,viewport:[width,height],time,text,renderMs:await ev('REPLAY_VIEW.renderMs')});
   }
   await send('Emulation.clearDeviceMetricsOverride');
   // Actual jump controls bracket the exact admission frame, then restore it.
   const timestamp=await ev(`DATA.offensive_inference.updates.at(-1).timestamp`);
   await ev(`$('reviewUpdate').value='${timestamp}';$('reviewBefore').click()`);assert((await ev('REPLAY_VIEW.time'))<timestamp);
   const before=await ev('REPLAY_VIEW.damageUpdateIds');await ev("$('reviewAfter').click()");assert((await ev('REPLAY_VIEW.time'))>=timestamp);assert.equal((await ev('REPLAY_VIEW.damageUpdateIds')).length,before.length+1);
   await ev(`seek(${time})`);
   assert(await ev("DATA.empirical_measure_model.sampling==='all_eligible_vgc_occurrences_no_deduplication'"));
   assert(await ev("DATA.empirical_scope.observations_removed_by_deduplication===0"));
   // Expanding SP/provenance and changing scores use the same DATA object.
   await ev("window.__same=DATA;window.__domain=JSON.stringify(DATA.support_catalog)");
   await ev(`document.querySelector('[data-individual="${actor}"] .empirical-core details').open=true`);
   for(const alpha of ['0','0.25','0.5','0.6','0.75','1'])await ev(`$('empiricalAlpha').value='${alpha}';$('empiricalAlpha').dispatchEvent(new Event('change'))`);
   assert(await ev('DATA===window.__same&&JSON.stringify(DATA.support_catalog)===window.__domain'));
   await ev("$('empiricalAlpha').value='0.5';$('empiricalAlpha').dispatchEvent(new Event('change'))");
  }
  checks.push(`Battle ${battle}: practical/comprehensive numbers, occurrences, evidence navigation, widths and unchanged domains verified`);
 }
 fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({checks,controlled_fixture:fixtures.origin,independent_human_acceptance:false},null,2));
}

async function validateTeamItems({ev,send,shot,wait,states,output}){
 const actor='sample_battle_12:opponent:encounter:29f64303ef101514',incineroar='sample_battle_12:opponent:encounter:13602f7dde98f1c5',checks=[];
 await send('Page.navigate',{url:'http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=12&damage=1&t=166'});
 await wait("typeof DATA!=='undefined'&&DATA?.battle_id==='sample_battle_12'&&$('frame').naturalWidth>0");
 for(const profile of ['practical','comprehensive']){
  await ev(`$('itemProfile').value='${profile}';$('itemProfile').dispatchEvent(new Event('change'))`);
  await wait(`DATA?.offensive_inference?.item_profile==='${profile}'&&$('frame').complete`);
  const state=()=>ev(`(()=>{const s=DATA.snapshots[REPLAY_VIEW.snapshotIndex],p=s.opponents['${incineroar}'];return {text:$('opponents').textContent,items:DATA.support_catalog[p.support_ref].full.items};})()`);
  await ev('seek(166)');const before=await state();assert(!before.text.includes('初始所有者未决（同队二选一）'));
  await ev('seek(167.01166666666666)');const after=await state();assert.deepEqual(after.items,['Life Orb','Normal Gem']);assert(after.text.includes('初始所有者未决（同队二选一）'));
  await ev(`document.querySelector('[data-individual="${incineroar}"]').scrollIntoView({block:'start'})`);await shot('b12-'+profile+'-life-orb-reveal');
  await ev('seek(166)');assert.deepEqual(await state(),before);
  for(const [name,time] of [['first',365.51166666666666],['second',448.0083333333333],['third',714.5033333333333]]){
   await ev(`seek(${time})`);
   const support=await ev(`(()=>{const p=DATA.snapshots[REPLAY_VIEW.snapshotIndex].opponents['${actor}'];const s=DATA.support_catalog[p.support_ref];return {items:s.full.items,explanation:s.full.item_explanations,observed:s.observed.complete_after,text:document.querySelector('[data-individual="${actor}"]').textContent};})()`);
   assert(!support.items.includes('Life Orb'));assert(support.text.includes('同队初始道具唯一性证据排除'));
   const orb=support.explanation.items.find(i=>i.item==='Life Orb');assert.deepEqual(orb.states,['excluded_by_team_uniqueness']);assert.equal(orb.evaluated.values.count,0);
   await ev(`(()=>{const c=document.querySelector('[data-individual="${actor}"]');for(const d of c.querySelectorAll('.reference-model,.item-explanations'))d.open=true;})()`);
   await wait(`document.querySelector('[data-individual="${actor}"] .item-support-table')!==null`);
   await ev(`document.querySelector('[data-individual="${actor}"] .item-support-table').scrollIntoView({block:'start'})`);
   await shot('b12-'+profile+'-'+name+'-item-support');
   states.push({profile,name,time,items:support.items,observed:support.observed,overall:support.explanation.overall,orb:orb.states});
  }
  assert(await ev("DATA.empirical_measure_model.sampling==='all_eligible_vgc_occurrences_no_deduplication'&&DATA.empirical_scope.observations_removed_by_deduplication===0&&DATA.empirical_measure_model.default_alpha===0.5"));
  checks.push(profile+': causal reveal and rewind; all three exact item supports; team exclusion wording; VGC no dedup and alpha 0.5');
 }
 fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({milestone:'M3.4.5a',checks,human_acceptance:false},null,2));
}
