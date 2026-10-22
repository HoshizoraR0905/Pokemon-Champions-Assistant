/* Offline data only. Rendering never calls a solver or consults future state. */
'use strict';
let DATA=null, framePosition=0, loadGeneration=0, EVENTS=[], lastRenderMs=0;
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const json=x=>JSON.stringify(x,null,2);
const localPath=p=>{const root=DATA?.source_stage_a?.split('/.cache/')[0];return '/'+(root&&p.startsWith(root+'/')?p.slice(root.length+1):p.replace(/^\//,''));};
const label=k=>DATA?.names[k]?.['zh-hans']||DATA?.names[k]?.zh||DATA?.names[k]?.en||k||'未知';
const intervals=s=>s?.count===0?'空集（无兼容配置）':s?.intervals?.map(([a,b])=>a===b?String(a):`${a}–${b}`).join('，')||'未确定';
const hull=s=>s?.count?`${s.minimum}–${s.maximum}`:'未确定';
function floorIndex(rows,time){let lo=0,hi=rows.length;while(lo<hi){const m=(lo+hi)>>1;if(rows[m].timestamp<=time)lo=m+1;else hi=m;}return lo-1;}
function details(parent,title,data){const d=el('details'),pre=el('pre');let filled=false;d.append(el('summary',title),pre);d.addEventListener('toggle',()=>{if(d.open&&!filled){pre.textContent=json(data);filled=true;}});parent.append(d);return d;}
function sourceLinks(parent,events){for(const e of events)for(const s of e.sources||[]){if(!s.image)continue;const a=el('a',`${Number(s.timestamp??e.timestamp).toFixed(3)}s 原帧`,'sourceLink');a.href=localPath(s.image);a.target='_blank';a.rel='noopener';parent.append(a);}}
function table(parent,headers,rows){const t=el('table'),head=el('tr');for(const h of headers)head.append(el('th',h));t.append(head);for(const row of rows){const tr=el('tr');for(const cell of row)tr.append(el('td',cell));t.append(tr);}parent.append(t);}
function phaseText(event,snapshot){const kinds={pivot_replacement:'招式引发替换 · 行动结算',forced_replacement:'倒下后替补',initial_send_out:'开场派出',item_revelation:'Mega 道具反应',unresolved_transition:'替换阶段未定',voluntary_switch:'主动换人阶段',mega_evolution:'Mega 阶段',transformation:'形态变化',executed_move:'普通行动阶段',prevented_action:'普通行动阶段 · 被阻止',move_execution:'招式执行阶段',selected_action:'指令选择',normal_command_entry:'指令输入',switch_out:'替换事件 · 类别未审查',speed_constraint:'速度约束更新'};return kinds[event?.kind]||snapshot?.last_observed_phase?.phase||'未知';}
function currentTurn(time){return DATA.turns.filter(t=>t.command_interval[1]<=time&&time<t.next_command_interval[1]).at(-1);}
function visibleTransition(e,time){const copy={...e};copy.sources=(e.sources||[]).filter(s=>(s.timestamp??e.timestamp)<=time);if(e.arrival_time>time){copy.incoming=null;copy.arrival_time=null;copy.interval=[e.timestamp,null];copy.source_event_ids=(e.source_event_ids||[]).filter(id=>id!==e.arrival_source_event_id);copy.arrival_source_event_id=null;}if(e.pivot_transaction_id&&DATA.action_timeline.find(t=>t.id===e.pivot_transaction_id)?.timestamp>time)delete copy.pivot_transaction_id;return copy;}
function actorText(p){return p?(label(p.current_form||p.species)+(p.current_form?'':' · 形态未定')):'个体未定';}
function actionRows(time,turn){const lower=turn?.command_interval[1]??Math.max(0,...DATA.turns.filter(t=>t.next_command_interval[1]<=time).map(t=>t.next_command_interval[1]));
 return (DATA.action_timeline||[]).filter(e=>e.timestamp<=time&&(turn?e.segment_id===turn.turn_id:e.timestamp>=lower)).map(e=>visibleTransition(e,time));}
function renderActions(time,turn){const box=$('actions');box.replaceChildren();const rows=[];
 for(const e of actionRows(time,turn)){
  const kinds={executed_move:'普通行动',prevented_action:'被阻止 / 畏缩',selected_action:'已选择',voluntary_switch:'主动换人阶段',mega_evolution:'Mega 阶段',pivot_replacement:'招式引发替换',forced_replacement:'倒下后替补',initial_send_out:'开场派出',unresolved_transition:'替换类别未定',unresolved_transformation:'形态变化未定',item_revelation:'道具揭示'};
  let actor=label(e.individual),text=e.text||label(e.move);
  if('outgoing' in e){actor=(e.side==='opponent'?'对方 ':'我方 ')+actorText(e.outgoing);text=`${actorText(e.outgoing)} → ${e.incoming?actorText(e.incoming):'入场宝可梦未定'}`;}
  if(e.kind==='mega_evolution'){actor=label(e.original_form);text=`${label(e.original_form)} → ${label(e.resulting_form)}`;}
  const sources=(e.sources||[]).map(s=>`${(s.timestamp??e.timestamp).toFixed(3)}s`).join(' / ');
  rows.push([e.timestamp.toFixed(3),actor,text,kinds[e.kind]||e.kind,e.phase==='move'&&e.priority?`基础 ${e.priority.base_priority??'未知'} / 有效 ${e.priority.effective_priorities?.join(',')||'未知'}`:`${e.phase} · ${sources}`]);
  const detail=details(box,`${e.timestamp.toFixed(3)}s 来源 / 出入场个体 / 阶段`,e);sourceLinks(detail,[e]);
 }
 if(rows.length)table(box,['秒','行动者','行动 / 出入场','类别','优先度 / 阶段'],rows);else box.append(el('p','当前尚无可用的行动证据','empty'));
}
function speedLayer(card,title,layer,cls){const section=el('section',undefined,'support-layer '+cls);section.dataset.layer=cls;section.append(el('h3',title),el('div',layer?.speed?.count?hull(layer.speed):layer?.speed?.count===0?'空集':'未确定','range'),el('p',intervals(layer?.speed),'ranges'));card.append(section);return section;}
function renderOpponents(snapshot,updates,time){const box=$('opponents');box.replaceChildren();
 for(const [id,p] of Object.entries(snapshot?.opponents||{})){
  const support=DATA.support_catalog?.[p.support_ref];const card=el('article');card.dataset.individual=id;
  card.append(el('h2',label(p.current_form||p.species)+(p.current_form?'':' · 当前形态未定')),el('small',id,'muted'));
  card.append(el('p',p.active?'当前在场':'已观察个体 · 当前离场','muted'));
  if(!p.current_form)card.append(el('p',`可能形态：${(p.possible_forms||[]).map(label).join('、')||'未知'}`,'muted'));
  if(!support){card.append(el('p','参考支持未完成 · '+(p.unresolved_reasons||[]).join('；'),'empty'));box.append(card);continue;}
  const observed=speedLayer(card,'1. 经验配置支持',support.observed,'observed');
  observed.append(el('p',`完整配置 ${support.observed.complete_before} → ${support.observed.complete_after}；字段不全排除 ${support.observed.incomplete_excluded}`,'muted'),el('p',`${DATA.empirical_scope.source} · ${DATA.empirical_scope.population} · ${DATA.empirical_scope.regulation} · ${DATA.empirical_scope.format}`,'muted'),el('p','数据集中未出现的配置仍可能合法。','muted'));
  const full=speedLayer(card,'2. 完整参考模型',support.full,'full');
  full.append(el('p',`配置类 ${support.full.configuration_count} · ${support.full.status==='unresolved'?'未决：支持范围或行动时状态仍有限制':'固定参考模型投影'}`,'muted'),el('p','保留讲究围巾、黑色铁球、先制之爪等受支持分支。非独立 Champions 机制认证。','muted'));
  details(full,'道具、特性、形态分支与未决原因',support.full);
  details(full,'数值倾向 / 速度 SP / 联合训练域',Object.fromEntries((support.full.training_domain_refs||[]).map(id=>[id,DATA.training_domains[id]])));
  if(p.form_evidence)details(full,'原始形态与 Mega 训练 / 道具关联',DATA.form_configuration_support[p.form_evidence.id]);
  details(observed,'联合配置：原始特性 / 当前特性 / 数值倾向 / 速度 SP / 来源构筑',support.observed.builds.map(id=>({source:DATA.observed_builds[id],current:support.observed.ability_mappings?.[id]})));
  details(card,'继承的计算条件',support.conditions);
  details(card,'观察值与形态证据',{item:p.observed_item,observed_ability:p.observed_ability,active_ability:p.active_ability,active_ability_basis:p.active_ability_basis,status:p.observed_status,speed_stage:p.observed_speed_stage,current_form:p.current_form,possible_forms:p.possible_forms,form_evidence:p.form_evidence});
  box.append(card);
 }
 if(!box.children.length)box.append(el('p','此时还没有对方个体的可用证据。','empty'));
}
function renderDeductions(updates){const box=$('deductions');box.replaceChildren();for(const u of [...updates].reverse()){
 const card=el('article');card.dataset.constraint=u.id;card.append(el('span',u.scope==='source_reviewed_order'?'来源审查约束':'带条件计算','badge '+(u.scope==='source_reviewed_order'?'direct':'conditional')),el('strong',`${u.timestamp.toFixed(3)}s · ${u.id}`));
 card.append(el('p',u.actions.map(a=>`${a.individual}: ${a.kind==='move'?label(a.move):a.kind}${a.outcome==='flinched'?'（畏缩）':''}`).join(' → ')));
 for(const [id,after] of Object.entries(u.after)){const before=u.before[id];card.append(el('p',`${id}：${intervals(before.speed)} → ${intervals(after.speed)}；配置类 ${before.configuration_count} → ${after.configuration_count}`));}
 card.append(el('p',u.assumptions.join('；'),'muted'));sourceLinks(card,u.evidence);
 details(card,'优先度、状态与自方速度',{actions:u.actions,state:u.state,own_speed:u.own_speed});
 details(card,'淘汰配置、同速候选与联合关系',u.solver);details(card,'经验支持前后（保持完整配置相关性）',{before:u.empirical_before,after:u.empirical_after,solver:u.empirical_solver});box.append(card);
 }if(!updates.length)box.append(el('p','此时间点尚无已审查的速度约束。','empty'));
}
function render(){if(!DATA)return;const start=performance.now();const frame=DATA.frames[framePosition],time=frame.timestamp;
 const si=floorIndex(DATA.snapshots,time),snapshot=DATA.snapshots[si];const ei=floorIndex(EVENTS,time),event=EVENTS[ei];
 const turn=currentTurn(time);const updates=DATA.reviewed_inference.updates.filter(u=>u.timestamp<=time);
 $('frame').src=localPath(frame.image);$('source').href=localPath(frame.image);$('clock').textContent=`${time.toFixed(3)} s`;
 $('turn').textContent=turn?`本地回合 ${turn.local_index}`:'回合未知';$('phase').textContent=`最近观察：${phaseText(event,snapshot)}`;
 $('frameCount').textContent=`${framePosition+1} / ${DATA.frames.length}`;$('timeline').value=framePosition;
 $('provenance').textContent=json(frame);$('field').textContent=json(snapshot?.field??{status:'未知'});
 const ownStates=DATA.reviewed_inference.own_states?.filter(s=>s.timestamp<=time)||[];
 const own=ownStates.reduce((all,s)=>{all[s.individual]=s;return all;},{});$('individualState').replaceChildren();
 for(const s of Object.values(own)){$('individualState').append(el('p',`我方 ${label(s.current_form)} · 未修正速度 ${s.unmodified_speed}（${s.timestamp.toFixed(3)}s 来源）`));sourceLinks($('individualState'),[s]);}
 $('eventDetails').textContent=json({event,snapshot_time:snapshot?.timestamp,comparisons:DATA.comparisons.filter(c=>c.timestamp<=time&&c.timestamp>=(turn?.command_interval[1]??0)).map(c=>({id:c.id,status:c.status,blockers:c.blockers}))});
 $('occupants').textContent=Object.entries(snapshot?.occupancy||{}).map(([side,rows])=>(side==='self'?'我方':'对方')+'：'+Object.values(rows).map(p=>actorText(p)).join('、')).join('；');
 renderActions(time,turn);renderOpponents(snapshot,updates,time);renderDeductions(updates);
 lastRenderMs=performance.now()-start;window.REPLAY_VIEW={time,framePosition,snapshotIndex:si,updateIds:updates.map(u=>u.id),renderMs:lastRenderMs,occupancy:snapshot?.occupancy,forms:Object.fromEntries(Object.entries(snapshot?.opponents||{}).map(([id,p])=>[id,p.current_form])),actionIds:actionRows(time,turn).map(e=>e.id)};
}
function seek(time){framePosition=Math.max(0,floorIndex(DATA.frames,time));render();}
function step(kind,direction){if(!DATA)return;const time=DATA.frames[framePosition].timestamp;
 if(kind==='frame'){framePosition=Math.max(0,Math.min(DATA.frames.length-1,framePosition+direction));render();return;}
 const times=kind==='turn'?DATA.turns.map(t=>t.command_interval[1]):EVENTS.map(e=>e.timestamp);
 const target=direction>0?times.find(t=>t>time+0.0001):times.filter(t=>t<time-0.0001).at(-1);
 if(target!==undefined){ // Navigation targets the first available frame that can show the event.
  const index=floorIndex(DATA.frames,target);framePosition=Math.min(DATA.frames.length-1,index>=0&&DATA.frames[index].timestamp===target?index:index+1);render();}
}
function markers(){const box=$('markers');box.replaceChildren();const max=DATA.frames.at(-1).timestamp;
 for(const e of EVENTS){if(e.kind==='visual_phase')continue;const symbols={normal_command_entry:'●',voluntary_switch:'◆',switch_out:'◆',mega_evolution:'◇',transformation:'◇',move_execution:'▲',executed_move:'▲',prevented_action:'▲',speed_constraint:'★'};const b=el('button',symbols[e.kind]||'■');b.style.left=`${e.timestamp/max*100}%`;b.title=`${e.timestamp.toFixed(3)}s ${e.kind} ${e.text||e.move||''}`;b.setAttribute('aria-label',b.title);b.onclick=()=>{const i=floorIndex(DATA.frames,e.timestamp);framePosition=DATA.frames[i]?.timestamp===e.timestamp?i:Math.min(i+1,DATA.frames.length-1);render();};box.append(b);}
}
async function loadBattle(){const generation=++loadGeneration;DATA=null;document.querySelector('main').classList.add('loading');$('status').textContent='加载预计算证据…';
 try{const response=await fetch(`/.cache/battles/sample_battle_${$('battle').value}/m322-reviewed-speed/latest.json`,{cache:'no-store'});if(!response.ok)throw Error('尚未生成此录像的回放');const pointer=await response.json();const relative=pointer.path.split('/.cache/')[1];if(!relative)throw Error('Invalid local artifact pointer');const r=await fetch('/.cache/'+relative);if(!r.ok)throw Error('Replay data missing');const data=await r.json();if(generation!==loadGeneration)return;DATA=data;framePosition=0;
 EVENTS=[...new Map([...DATA.timeline.filter(e=>!['switch_out','send_out','transformation'].includes(e.kind)),...(DATA.action_timeline||[]),...DATA.reviewed_inference.updates.map(u=>({id:u.id,timestamp:u.timestamp,kind:'speed_constraint'}))].map(e=>[e.id,e])).values()].sort((a,b)=>a.timestamp-b.timestamp||a.id.localeCompare(b.id));
 $('timeline').max=DATA.frames.length-1;markers();$('video').src=localPath(DATA.duration_coverage.source_video);$('empiricalFile').href=localPath(DATA.empirical_artifact);$('status').textContent=`${DATA.frames.length} 原帧 · ${DATA.reviewed_metrics.deterministic} 来源审查约束 · ${DATA.reviewed_metrics.conditional} 带条件约束`;
 const url=new URL(location.href);url.searchParams.set('battle',$('battle').value);history.replaceState(null,'',url);render();
 }catch(e){if(generation===loadGeneration)$('status').textContent=e.message;}finally{if(generation===loadGeneration)document.querySelector('main').classList.remove('loading');}
}
$('battle').value=new URLSearchParams(location.search).get('battle')||'11';$('battle').onchange=loadBattle;
$('timeline').oninput=()=>{framePosition=Number($('timeline').value);render();};
for(const [id,kind,direction] of [['prevFrame','frame',-1],['nextFrame','frame',1],['prevTurn','turn',-1],['nextTurn','turn',1],['prevEvent','event',-1],['nextEvent','event',1]])$(id).onclick=()=>step(kind,direction);
$('seekVideo').onclick=()=>{if(!DATA)return;$('videoPanel').open=true;const video=$('video'),time=DATA.frames[framePosition].timestamp;
 if(video.readyState===0){video.addEventListener('loadedmetadata',()=>{video.currentTime=time;},{once:true});video.preload='metadata';video.load();}else video.currentTime=time;};
document.addEventListener('keydown',e=>{if(e.target.matches('input,select,button'))return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();step('frame',e.key==='ArrowLeft'?-1:1);}});
loadBattle();
