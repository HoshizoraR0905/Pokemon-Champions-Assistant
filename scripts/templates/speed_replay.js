/* Offline data only. Rendering never calls a solver or consults future state. */
'use strict';
let DATA=null, framePosition=0, loadGeneration=0, EVENTS=[], lastRenderMs=0;
const $=id=>document.getElementById(id);
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const json=x=>JSON.stringify(x,null,2);
const localPath=p=>{const root=DATA?.source_stage_a?.split('/.cache/')[0];return '/'+(root&&p.startsWith(root+'/')?p.slice(root.length+1):p.replace(/^\//,''));};
const label=k=>DATA?.names[k]?.['zh-hans']||DATA?.names[k]?.zh||DATA?.names[k]?.en||k||'未知';
const intervals=s=>s?.count===0?'空集（无兼容配置）':s?.intervals?.map(([a,b])=>a===b?String(a):`${a}–${b}`).join(' ∪ ')||'未确定';
const itemText=items=>items.length>8?`${items.length} 种（${['none','Twisted Spoon','Wise Glasses','Life Orb'].filter(i=>items.includes(i)).concat(items.slice(0,2)).join(' / ')} 等；完整列表见下方）`:items.join(' / ');
function floorIndex(rows,time){let lo=0,hi=rows.length;while(lo<hi){const m=(lo+hi)>>1;if(rows[m].timestamp<=time)lo=m+1;else hi=m;}return lo-1;}
function details(parent,title,data){const d=el('details'),pre=el('pre');let filled=false;d.append(el('summary',title),pre);d.addEventListener('toggle',()=>{if(d.open&&!filled){pre.textContent=json(data);filled=true;}});parent.append(d);return d;}
function sourceLinks(parent,events){for(const e of events)for(const s of e.sources||[]){if(!s.image)continue;const a=el('a',`${Number(s.timestamp??e.timestamp).toFixed(3)}s 原帧`,'sourceLink');a.href=localPath(s.image);a.target='_blank';a.rel='noopener';parent.append(a);}}
function table(parent,headers,rows){const t=el('table'),head=el('tr');for(const h of headers)head.append(el('th',h));t.append(head);for(const row of rows){const tr=el('tr');for(const cell of row)tr.append(el('td',cell));t.append(tr);}parent.append(t);}
function phaseText(event,snapshot){const kinds={pivot_replacement:'招式引发替换 · 行动结算',forced_replacement:'倒下后替补',initial_send_out:'开场派出',item_revelation:'Mega 道具反应',unresolved_transition:'替换阶段未定',voluntary_switch:'主动换人阶段',mega_evolution:'Mega 阶段',transformation:'形态变化',executed_move:'普通行动阶段',prevented_action:'普通行动阶段 · 被阻止',move_execution:'招式执行阶段',selected_action:'指令选择',normal_command_entry:'指令输入',switch_out:'替换事件 · 类别未审查',speed_constraint:'速度约束更新',own_hp_damage:'我方承伤约束'};return kinds[event?.kind]||snapshot?.last_observed_phase?.phase||'未知';}
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
function speedLayer(card,title,layer,cls){const section=el('section',undefined,'support-layer '+cls);section.dataset.layer=cls;section.append(el('h3',title),el('p',intervals(layer?.speed),'ranges'));card.append(section);return section;}
function referencePanel(parent){const d=el('details',undefined,'reference-model');d.append(el('summary','完整参考模型（展开查看）'));parent.append(d);return d;}
function renderDamage(time){
 const updates=(DATA.offensive_inference?.updates||[]).filter(u=>u.timestamp<=time);$('damagePanel').hidden=!DATA.offensive_inference;$('damageEvidence').replaceChildren();
 if(!updates.length){$('damageEvidence').append(el('p','当前尚无已准入的我方承伤观察。','empty'));return;}
 for(const u of updates){
  const o=u.observation,h=o.hp_attribution,card=el('div',undefined,'damage-entry');card.dataset.damageObservation=o.id;
  const detail=el('details');detail.append(el('summary',`${o.timestamp.toFixed(3)}s · ${label(o.move)} · HP ${h.before.current}/${h.before.maximum} → ${h.after.current}/${h.after.maximum}（${o.damage}）`));
  if(o.stage_audit)detail.append(el('p',`特攻阶段 ${o.stage_audit.stage} · ${o.stage_audit.transitions.length} 次已审查变化；白色香草：用户复核触发提示缺失，单列物品证据排除。`));
  for(const [key,title] of [['observed','VGC 样本'],['full','参考模型']]){const r=u[key].updates.at(-1);detail.append(el('p',`${title}：${r.before.configuration_classes} → ${r.after.configuration_classes}；伤害数值排除 ${r.numerical_excluded_ids?.length||0}；物品证据排除 ${r.item_evidence_excluded_ids?.length||0}。`));}
  detail.append(el('p',`行动时：${label(o.attacker_form)} → ${label(o.target_form)}；${o.input.field?.weather||'天气未知'} / ${o.input.field?.terrain||'场地未知'}。`));
  details(detail,'行动时条件、原始 HP 归因与全部来源',o);const full=referencePanel(detail);details(full,'精确投影、道具、特性与独立随机数',u.full.updates.at(-1));card.append(detail);changeLinks(card,{timestamp:o.timestamp,sources:o.sources});$('damageEvidence').append(card);
 }
}
// Presentation of existing exact sets only; no candidate generation or weights.
function supportView(support,measure){
 const full=support.full||{},observed=support.observed||{},stats=Object.values(full.offensive_stats||{});
 const total=full.configuration_count??stats[0]?.configuration_classes??null;
 const possible=total!==null?total>0:full.speed?.count>0;
 const unknown=Math.max(0,...stats.map(s=>s.evaluated_support?Math.max(0,s.configuration_classes-s.evaluated_support.configuration_classes):s.unresolved?.length?s.configuration_classes:0));
 const policy=full.item_policy,omitted=policy?.profile==='practical'?(policy.dormant||[]).length:0;
 const available=measure?measure.surviving_cores>0:observed.complete_after>0;
 const noSample=measure?measure.eligible_records===0:observed.complete_before===0;
 let state=available?'available':possible?(noSample?'no_sample':'fallback'):unknown?'provisional':'contradiction';
 if(available&&unknown)state='provisional';
 const qualified=Boolean(omitted||unknown||full.unresolved_reasons?.length||full.status==='unresolved');
 return {state,available,noSample,possible,total,unknown,omitted,qualified};
}
function statSummary(parent,full,view){
 const strip=el('div',undefined,'stat-summary');strip.append(el('p','参考可行范围 · '+(full.item_policy?.profile||'固定机制条件'),'scope-label'));
 const rows=el('div',undefined,'stat-grid'),stats=full.offensive_stats||{},informative=Object.values(stats).some(s=>s.direct_constraint||s.evidence_ids?.length);
 const entries=[['speed','速度',full.speed],...Object.entries(stats).filter(([stat])=>['attack','special_attack'].includes(stat)).filter(()=>informative||!view.available).map(([stat,s])=>[stat,stat==='attack'?'物攻':'特攻',s.values])];
 for(const [stat,title,values] of entries){const cell=el('div');cell.dataset.stat=stat;cell.append(el('span',title,'muted'),el('strong',intervals(values),'ranges'));if(stats[stat])cell.append(el('small',stats[stat].direct_constraint?'承伤直接约束':'联合支持','muted'));rows.append(cell);}
 strip.append(rows);if(!view.available)strip.classList.add('fallback-summary');parent.append(strip);
}
function itemExplanations(parent,explanation){
 if(!explanation)return;
 const panel=el('details',undefined,'item-explanations');panel.append(el('summary',`道具条件下的${explanation.stat==='attack'?'物攻':'特攻'}支持与复算见证`));let built=false;
 panel.addEventListener('toggle',()=>{if(!panel.open||built)return;built=true;
  panel.append(el('p',`总体：${intervals(explanation.overall)}；已计算分支并集：${intervals(explanation.evaluated_union)}`,'item-union'));
  if(explanation.unresolved_union.count)panel.append(el('p',`机制未决支持：${intervals(explanation.unresolved_union)}（不计入已计算并集）`,'uncertainty'));
  const evidence=el('p',undefined,'muted');evidence.textContent='累计证据：'+explanation.observations.map(id=>{const u=DATA.offensive_inference.updates.find(u=>u.id===id);return u?`${u.timestamp.toFixed(3)}s / ${u.observation.damage} HP`:id;}).join('；');panel.append(evidence);
  const labels={supported:'已计算兼容',unresolved:'机制未决',policy_dormant:'Practical 策略休眠',rescue_hypothesis:'救援假设（非确认）',source_confirmed:'来源确认',excluded_by_damage:'伤害数值排除',excluded_by_item_evidence:'直接物品证据排除',excluded_by_team_uniqueness:'同队初始道具唯一性证据排除',not_in_active_domain:'不在当前启用域'};
  const draw=(where,groups)=>{
   const t=el('table',undefined,'item-support-table'),head=el('tr');for(const h of ['道具假设','已计算支持','未决支持 / 状态'])head.append(el('th',h));t.append(head);
   for(const g of groups){
    const tr=el('tr');tr.dataset.items=g.items.join('|');const first=el('td'),detail=el('details');
    detail.append(el('summary',g.label==='No held item / audited direct-hit-neutral items'?`无直接增伤（${g.items.length} 种，含无道具）`:g.label));
    detail.append(el('p',`原始道具：${g.items.join(' / ')}；${g.configuration_classes} 配置类。`));
    for(const hit of g.critical){const u=DATA.offensive_inference.updates.find(u=>u.id===hit.observation);detail.append(el('p',`${u?u.observation.damage+' HP':hit.observation}：${hit.states.map(s=>(s.critical?'会心':'非会心')+' '+intervals(s.values)).join('；')||'无已计算分支'}`));}
    detail.append(el('p','会心支持均与当前累计存活的同道具配置相交；不得把各边际任意拼接。','muted'));first.append(detail);tr.append(first,el('td',intervals(g.evaluated)));
    const status=el('td');if(g.unresolved.count)status.append(el('p',intervals(g.unresolved),'uncertainty'));status.append(el('p',g.states.map(s=>labels[s]||s).join('；')));
    if(g.states.includes('policy_dormant'))status.append(el('small','未参与本次过滤，不等于伤害排除。'));
    if(g.states.includes('rescue_hypothesis')&&!g.states.includes('source_confirmed'))status.append(el('small','由可行性失败触发，未确认携带。'));
    tr.append(status);t.append(tr);
   }where.append(t);
  };
  const important=explanation.groups.filter(g=>g.evaluated.count||g.unresolved.count||g.items.includes('Life Orb'));
  const others=explanation.groups.filter(g=>!important.includes(g));draw(panel,important);
  if(others.length){const hidden=el('details');hidden.append(el('summary',`其他休眠 / 已排除道具（${others.reduce((n,g)=>n+g.items.length,0)} 种）`));let drawn=false;hidden.ontoggle=()=>{if(hidden.open&&!drawn){drawn=true;draw(hidden,others);}};panel.append(hidden);}
  const witnesses=el('details',undefined,'feasibility-witnesses');witnesses.append(el('summary','完整 SP 见证与前向复算输入'));
  for(const w of explanation.witnesses){const d=el('details');d.dataset.witnessValue=w.value;
   const status={evaluated_witness:'可复算',unresolved_only:'仅未决分支暂留，无数值见证',not_supported:'无支持',evaluated_witness_unavailable:'当前投影有支持，但未构造完整见证'}[w.status];d.append(el('summary',`${explanation.stat==='attack'?'物攻':'特攻'} ${w.value} · ${status}`));
   if(w.witness){const proof=w.witness;d.append(el('p',`${proof.initial_item} / ${proof.ability}；速度 ${proof.stats.speed}；总 SP ${proof.total_sp} ≤ 66。`),el('p',`倾向 ${proof.alignment.increase||'中性'} ↑ / ${proof.alignment.decrease||'中性'} ↓；六项 SP：${Object.entries(proof.training_points).map(([s,v])=>s+' '+v).join(' / ')}`));
    for(const hit of proof.hits){d.append(el('p',`${hit.observation}：${hit.critical?'会心':'非会心'}，随机数 ${hit.roll}，预测伤害 ${hit.predicted_damage}。`));details(d,'前向输入与实际修正项',hit);}details(d,'完整联合配置见证',proof);
   }witnesses.append(d);
  }panel.append(witnesses);
 });parent.append(panel);
}
function compactReference(section,full,view){
 itemExplanations(section,full.item_explanations);
 section.append(el('p',`${view.total??'未知'} 个参考配置类${view.unknown?`，其中 ${view.unknown} 个机制未决`:'（在所列参考条件下）'}`,'muted'));
 const stats=Object.values(full.offensive_stats||{}),evaluated=stats.find(s=>s.evaluated_support);
 if(view.unknown){
  section.append(el('p','总支持含未决分支，不能将已计算分支当作穷尽结论。','uncertainty'));
  if(evaluated?.evaluated_support.speed)section.append(el('p',`已计算速度：${intervals(evaluated.evaluated_support.speed)}`,'evaluated-support'));
  if(evaluated)for(const s of stats)if(s.evaluated_support)section.append(el('p',`已计算${s.stat==='attack'?'物攻':'特攻'}：${intervals(s.evaluated_support.values)}`,'evaluated-support'));
 }
 const alternatives=el('details');alternatives.append(el('summary','道具 / 特性备选与策略范围'));
 const items=full.items||stats[0]?.items||[],abilities=full.abilities||stats[0]?.abilities||[];
 alternatives.append(el('p',`道具备选：${itemText(items)}`),el('p',`特性备选：${abilities.join(' / ')||'未确定'}`));
 if(full.item_policy)alternatives.append(el('p',`${full.item_policy.profile}：休眠 ${view.omitted} 种；休眠是策略省略，不是数值排除。`),el('p',`休眠道具：${full.item_policy.dormant?.join(' / ')||'无'}`));
 details(alternatives,'完整备选与策略记录',{items,abilities,policy:full.item_policy});section.append(alternatives);
 details(section,'精确可行值、联合 SP 域与未决原因',full);
}
function damageChange(u){
 const o=u.observation,r=u.full.updates.at(-1),stat=r.selector?.offensive_stat;
 let text=`${label(o.move)}造成 ${o.damage} HP；`;
 if(o.stage_audit)text+=`特攻阶段 ${o.stage_audit.stage}；`;
 if(r.after_offensive_stats&&r.before_offensive_stats){const beforeStat=r.before_offensive_stats[stat],afterStat=r.after_offensive_stats[stat],before=beforeStat?.evaluated_support?.values||beforeStat?.values,after=afterStat?.evaluated_support?.values||afterStat?.values;
  text+=before&&after&&json(before.values)!==json(after.values)?`${afterStat?.unresolved?.length?'已计算分支的':''}${stat==='attack'?'物攻':'特攻'}支持收窄。`:r.numerical_excluded_ids?.length?'排除额外参考配置，数值投影未变。':'当前数值支持保留。';
 }else text+='承伤约束已更新。';
 if(r.before?.speed?.minimum!==undefined&&r.after?.speed?.minimum>r.before.speed.minimum)text+=`联合速度下界由 ${r.before.speed.minimum} 提高至 ${r.after.speed.minimum}。`;
 if(r.item_evidence_excluded_ids?.length)text+=`另有 ${r.item_evidence_excluded_ids.length} 类因物品证据排除${o.stage_audit?'（白色香草提示复核）':''}。`;
 return text;
}
function latestChange(id,updates,time){
 const damage=(DATA.offensive_inference?.updates||[]).filter(u=>u.timestamp<=time&&u.observation.attacker===id).at(-1);
 const links=DATA.reviewed_inference?.review?.identity_links||{},keys=Object.keys(links).filter(k=>links[k].includes(id));
 const speed=updates.filter(u=>u.timestamp<=time&&keys.some(k=>u.after?.[k])).at(-1);
 if(speed&&(!damage||speed.timestamp>damage.timestamp)){const key=keys.find(k=>speed.after[k]),before=speed.before[key].speed,after=speed.after[key].speed;
  return {timestamp:speed.timestamp,text:json(before.values)!==json(after.values)?`行动顺序证据将速度支持收窄至 ${intervals(after)}。`:'行动顺序校验保留当前速度支持。',sources:speed.evidence?.flatMap(e=>e.sources||[])||[]};
 }
 return damage?{timestamp:damage.timestamp,text:damageChange(damage),sources:damage.observation.sources||[]}:null;
}
function jumpEvidence(timestamp,before=false){
 const i=floorIndex(DATA.frames,timestamp);framePosition=Math.max(0,Math.min(DATA.frames.length-1,before?(DATA.frames[i]?.timestamp===timestamp?i-1:i):(DATA.frames[i]?.timestamp===timestamp?i:i+1)));render();
}
function changeLinks(parent,event){
 const controls=el('div',undefined,'evidence-links');for(const [title,before] of [['证据前',true],['证据后',false]]){const b=el('button',title);b.onclick=()=>jumpEvidence(event.timestamp,before);controls.append(b);}
 const latest=(event.sources||[]).filter(s=>s.image&&(s.timestamp??event.timestamp)<=event.timestamp).sort((a,b)=>(b.timestamp??event.timestamp)-(a.timestamp??event.timestamp))[0];
 if(latest)sourceLinks(controls,[{timestamp:event.timestamp,sources:[latest]}]);parent.append(controls);
}
function empiricalShortlist(section,layer,form){
 const key=layer.measure_ref,alpha=$('empiricalAlpha').value,measure=DATA.empirical_measures?.[key]?.[alpha],cat=DATA.empirical_core_catalogs?.[form];
 if(!measure||!cat)return false;
 section.dataset.measureRef=key;section.dataset.alpha=alpha;
 section.append(el('p',`VGC ${measure.surviving_records}/${measure.eligible_records} 次出现 · ${measure.surviving_cores} 个核心`,'sample-count'));
 if(!measure.surviving_cores)return true;
 section.append(el('p','条件重加权样本份额；不是对手持有该配置的概率。','sample-scope'));
 if(measure.cores.length===1&&measure.cores[0].share===1)section.append(el('p','100% 仅指剩余 VGC 样本，不代表实际对手的配置已确定。','sample-certainty'));
 if(measure.moves.length&&measure.records.some(r=>!r.hard_excluded&&r.matched.length<measure.moves.length))section.append(el('p','部分 VGC 模板未记录已见招式；训练核心仍按软匹配保留。','soft-move-note'));
 if(measure.status==='retained_with_unresolved_mechanics')section.append(el('p','部分样本因机制未决暂留。','uncertainty'));
 const draw=(parent,row)=>{const core=cat.cores[row.core_id],card=el('div',undefined,'empirical-core');card.dataset.coreId=row.core_id;
  const title=el('div',undefined,'core-title');title.append(el('strong',`${(100*row.share).toFixed(1)}%`),el('span',`${label(core.nature).replace('nature:','')} · ${core.item} / ${core.ability}${row.provisional?' · 未决':''}`));
  card.append(title,el('p',`物攻 ${core.stats.attack} · 特攻 ${core.stats.special_attack} · 速度 ${core.stats.speed}`),el('p',`${row.source_records} 条来源记录 · ${row.matched_moves.length} 种已揭示招式匹配`,'muted'));
  const extra=el('details');extra.append(el('summary','SP、原始招式与 VGC 来源'));
  details(extra,'六项 SP / 数值倾向 / 完整核心',core);
  details(extra,'原始招式模板、来源与记录分数',row.records.map(id=>({id,source:cat.records[id],score:measure.records.find(r=>r.id===id)})));card.append(extra);parent.append(card);};
 measure.cores.slice(0,3).forEach(r=>draw(section,r));
 if(measure.cores.length>3){const more=el('details');more.append(el('summary',`更多 ${measure.cores.length-3} 个核心`));let built=false;more.ontoggle=()=>{if(more.open&&!built){built=true;measure.cores.slice(3).forEach(r=>draw(more,r));}};section.append(more);}
 const diagnostics=el('details');diagnostics.append(el('summary','招式匹配与评分说明'));
 diagnostics.append(el('p',`已揭示：${measure.moves.map(label).join(' / ')||'无'}。模板未记录的招式不会排除训练核心；只有所列硬证据能淘汰配置。`));
 details(diagnostics,'平滑频率、α、逐次出现分数与硬证据排除',measure);section.append(diagnostics);return true;
}
function renderOpponents(snapshot,updates,time){
 const box=$('opponents');box.replaceChildren();
 const entries=Object.entries(snapshot?.opponents||{}),changes=Object.fromEntries(entries.map(([id])=>[id,latestChange(id,updates,time)]));
 entries.sort(([a,p],[b,q])=>Number(q.active)-Number(p.active)||(changes[b]?.timestamp??-1)-(changes[a]?.timestamp??-1));
 for(const [id,p] of entries){
  const support=DATA.support_catalog?.[p.support_ref],card=el('article',undefined,'opponent-card');card.dataset.individual=id;
  const heading=el('div',undefined,'opponent-heading');heading.append(el('h2',label(p.current_form||p.species)+(p.current_form?'':' · 形态未定')),el('span',p.active?'在场':'离场','badge '+(p.active?'direct':'inactive')));card.append(heading);
  const body=p.active?card:el('details',undefined,'inactive-details');if(body!==card){body.append(el('summary','查看已观察个体的支持'));card.append(body);}
  if(!support){body.append(el('p','参考支持未完成；状态保持未知。','uncertainty'));box.append(card);continue;}
  const measure=DATA.empirical_measures?.[support.observed.measure_ref]?.[$('empiricalAlpha').value],view=supportView(support,measure);card.dataset.supportState=view.state;
  const ledger=(DATA.offensive_inference?.item_events||[]).filter(e=>e.individual===id&&e.available_at<=time&&e.timestamp<=time&&e.kind!=='reviewed_negative');
  const lastItem=ledger.filter(e=>e.kind!=='initial_held').at(-1),item=lastItem?(['consumed','transferred_out','removed'].includes(lastItem.kind)?`${lastItem.item}（已消耗 / 移出）`:lastItem.kind==='unresolved_transfer'?'未知（转移未决）':lastItem.item):p.observed_item;
  const ability=p.observed_ability?label(p.observed_ability):p.active_ability;
  body.append(el('p',`已知道具：${item||'未知'} · ${p.observed_ability?'已观察特性':'当前特性'}：${ability||'未知'}${!p.observed_ability&&p.active_ability?'（形态推得）':''}`,'confirmed-facts'));
  const team=support.full.team_item_constraint;
  const ownerReview=ledger.find(e=>e.kind==='initial_owner_options');
  if(ownerReview)body.append(el('p','初始所有者未决（同队二选一）：本个体原始 Life Orb，或消耗 Normal Gem 后由智挥猩 Symbiosis 转入。当前持有已确认，转移未确认。','uncertainty'));
  if(team?.excluded_items?.length)body.append(el('p',`同队初始道具唯一性证据排除：${team.excluded_items.join(' / ')}。消费或转移不释放原始配装占用。`,'team-item-evidence'));
  if(ledger.length){const history=el('details');history.append(el('summary','道具来源与持有历史'));
   for(const e of ledger){history.append(el('p',`${e.timestamp.toFixed(3)}s · ${e.item} · ${{initial_held:'初始持有（连续性复核推得）',initial_owner_options:'初始所有者未决（同队关系）',activated:'触发并确认当时持有',held:'当时持有',consumed:'消耗',removed:'移除',transferred_in:'转入',transferred_out:'转出',replaced:'替换',restored:'恢复',unresolved_transfer:'转移未决'}[e.kind]||e.kind}；${e.available_at.toFixed(3)}s 准入。`));
    if(e.exact_wording)history.append(el('p',e.exact_wording));
    details(history,'来源记录',e);
   }history.append(el('p','“受到了反作用力造成的伤害”是一般反作用力；“的生命被少量削减了”是本次复核的生命宝珠相关措辞。一般反作用力本身不确认生命宝珠。','muted'));body.append(history);
  }
  const change=changes[id];if(change){const latest=el('div',undefined,'latest-change');latest.append(el('p',`${change.timestamp.toFixed(3)}s · ${change.text}`));changeLinks(latest,change);body.append(latest);}
  statSummary(body,support.full,view);
  if(view.unknown)body.append(el('p',`${view.unknown} 类机制未决；总支持可能宽于已计算分支。`,'uncertainty'));
  if(view.omitted)body.append(el('p',`Practical 休眠 ${view.omitted} 种道具：策略省略，不是数值排除。`,'policy-note'));
  if(!view.unknown&&view.qualified)body.append(el('p','依赖列明的参考机制与状态假设，尚非全局穷尽结论。','muted'));
  const observed=el('section',undefined,'support-layer observed');observed.dataset.layer='observed';observed.append(el('h3',view.available?'VGC 样本 · 前三核心':'VGC 样本'));
  if(!view.available){
   observed.append(el('p',view.noSample?'该形态没有合格的完整 VGC 观察；不表示训练配置不合法。':'没有记录中的 VGC 训练配置与当前证据兼容。','empirical-exhaustion'));
   if(view.possible)observed.append(el('p','样本外的参考合法配置仍然可能；上方自动显示完整参考模型的可行范围。','fallback-message'));
   else observed.append(el('p',view.qualified?'两层支持在当前范围内为空；需检查证据归因、状态假设、机制覆盖与道具策略，不能据此断言全局矛盾。':'两层支持均为空：证据或模型矛盾。请检查归因、状态假设与机制覆盖。','contradiction'));
  }
  body.append(observed);const ranked=empiricalShortlist(observed,support.observed,p.current_form);
  if(!ranked&&view.available)observed.append(el('p',`经验配置 ${support.observed.complete_after}；速度 ${intervals(support.observed.speed)}`));
  const full=speedLayer(referencePanel(body),'完整参考模型 · 诊断',support.full,'full');compactReference(full,support.full,view);
  const exact=el('details');exact.append(el('summary','联合训练域与计算条件'));details(exact,'SP、形态分支、个体身份与观察来源',{id,participant:p,conditions:support.conditions,training:Object.fromEntries((support.full.training_domain_refs||[]).map(ref=>[ref,DATA.training_domains[ref]])),form:p.form_evidence?DATA.form_configuration_support[p.form_evidence.id]:null});full.append(exact);
  details(observed,'经验联合数值与全部来源',{stats:support.observed.offensive_stats,builds:support.observed.builds.map(id=>({source:DATA.observed_builds[id],current:support.observed.ability_mappings?.[id]}))});box.append(card);
 }
 if(!box.children.length)box.append(el('p','此时还没有对方个体的可用证据。','empty'));
}
function renderDeductions(updates){const box=$('deductions');box.replaceChildren();for(const u of [...updates].reverse()){
 const card=el('article');card.dataset.constraint=u.id;card.append(el('span',u.scope==='source_reviewed_order'?'来源审查约束':'带条件计算','badge '+(u.scope==='source_reviewed_order'?'direct':'conditional')),el('strong',`${u.timestamp.toFixed(3)}s · ${u.id}`));
 card.append(el('p',u.actions.map(a=>`${a.individual}: ${a.kind==='move'?label(a.move):a.kind}${a.outcome==='flinched'?'（畏缩）':''}`).join(' → ')));
 for(const [id,after] of Object.entries(u.empirical_after||{})){const before=u.empirical_before[id];card.append(el('p',`经验配置 ${id}：${intervals(before.speed)} → ${intervals(after.speed)}；配置类 ${before.configuration_count} → ${after.configuration_count}`));}
 const full=referencePanel(card);
 for(const [id,after] of Object.entries(u.after)){const before=u.before[id];full.append(el('p',`${id}：${intervals(before.speed)} → ${intervals(after.speed)}；配置类 ${before.configuration_count} → ${after.configuration_count}`));}
 card.append(el('p',u.assumptions.join('；'),'muted'));sourceLinks(card,u.evidence);
 details(card,'优先度、状态与自方速度',{actions:u.actions,state:u.state,own_speed:u.own_speed});
 details(full,'淘汰配置、同速候选与联合关系',u.solver);details(card,'经验支持前后（保持完整配置相关性）',{before:u.empirical_before,after:u.empirical_after,solver:u.empirical_solver});box.append(card);
 }if(!updates.length)box.append(el('p','此时间点尚无已审查的速度约束。','empty'));
}
function render(){if(!DATA)return;const start=performance.now();const frame=DATA.frames[framePosition],time=frame.timestamp;
 const si=floorIndex(DATA.snapshots,time),snapshot=DATA.snapshots[si];const ei=floorIndex(EVENTS,time),event=EVENTS[ei];
 const turn=currentTurn(time);const updates=DATA.reviewed_inference.updates.filter(u=>u.timestamp<=time);
 $('status').textContent=`已准入承伤 ${(DATA.offensive_inference?.updates||[]).filter(u=>u.timestamp<=time).length} · 行动顺序约束 ${updates.length}`;
 $('frame').src=localPath(frame.image);$('source').href=localPath(frame.image);$('clock').textContent=`${time.toFixed(3)} s`;
 $('turn').textContent=turn?`本地回合 ${turn.local_index}`:'回合未知';$('phase').textContent=`最近观察：${phaseText(event,snapshot)}`;
 $('frameCount').textContent=`${framePosition+1} / ${DATA.frames.length}`;$('timeline').value=framePosition;
 $('provenance').textContent=json(frame);$('field').textContent=json(snapshot?.field??{status:'未知'});
 const ownStates=DATA.reviewed_inference.own_states?.filter(s=>s.timestamp<=time)||[];
 const own=ownStates.reduce((all,s)=>{all[s.individual]=s;return all;},{});$('individualState').replaceChildren();
 for(const s of Object.values(own)){$('individualState').append(el('p',`我方 ${label(s.current_form)} · 未修正速度 ${s.unmodified_speed}（${s.timestamp.toFixed(3)}s 来源）`));sourceLinks($('individualState'),[s]);}
 $('eventDetails').textContent=json({event,snapshot_time:snapshot?.timestamp,comparisons:DATA.comparisons.filter(c=>c.timestamp<=time&&c.timestamp>=(turn?.command_interval[1]??0)).map(c=>({id:c.id,status:c.status,blockers:c.blockers}))});
 $('occupants').textContent=Object.entries(snapshot?.occupancy||{}).map(([side,rows])=>(side==='self'?'我方':'对方')+'：'+Object.values(rows).map(p=>actorText(p)).join('、')).join('；');
 renderActions(time,turn);renderOpponents(snapshot,updates,time);renderDeductions(updates);renderDamage(time);
 const address=new URL(location.href);address.searchParams.set('t',String(time));history.replaceState(null,'',address);
 lastRenderMs=performance.now()-start;window.REPLAY_VIEW={time,framePosition,snapshotIndex:si,updateIds:updates.map(u=>u.id),damageUpdateIds:(DATA.offensive_inference?.updates||[]).filter(u=>u.timestamp<=time).map(u=>u.id),renderMs:lastRenderMs,occupancy:snapshot?.occupancy,forms:Object.fromEntries(Object.entries(snapshot?.opponents||{}).map(([id,p])=>[id,p.current_form])),actionIds:actionRows(time,turn).map(e=>e.id)};
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
 for(const e of EVENTS){if(e.kind==='visual_phase')continue;const symbols={normal_command_entry:'●',voluntary_switch:'◆',switch_out:'◆',mega_evolution:'◇',transformation:'◇',move_execution:'▲',executed_move:'▲',prevented_action:'▲',speed_constraint:'★',own_hp_damage:'▼'};const b=el('button',symbols[e.kind]||'■');b.style.left=`${e.timestamp/max*100}%`;b.title=`${e.timestamp.toFixed(3)}s ${phaseText(e)}`;b.setAttribute('aria-label',b.title);b.onclick=()=>{const i=floorIndex(DATA.frames,e.timestamp);framePosition=DATA.frames[i]?.timestamp===e.timestamp?i:Math.min(i+1,DATA.frames.length-1);render();};box.append(b);}
}
async function loadBattle(preserveTime=false){const initialTime=loadGeneration===0?Number(new URLSearchParams(location.search).get('t')||0):0;const savedTime=preserveTime===true&&DATA?DATA.frames[framePosition].timestamp:Number.isFinite(initialTime)?Math.max(0,initialTime):0;const generation=++loadGeneration;DATA=null;document.querySelector('main').classList.add('loading');$('status').textContent='加载预计算证据…';
 try{const stage=$('damageMode').checked?'m342-offensive':'m322-reviewed-speed';const response=await fetch(`/.cache/battles/sample_battle_${$('battle').value}/${stage}/${stage==='m342-offensive'?'latest-'+$('itemProfile').value:'latest'}.json`,{cache:'no-store'});if(!response.ok)throw Error('尚未生成此录像的所选证据回放；可切换速度回放');const pointer=await response.json();const relative=pointer.path.split('/.cache/')[1];if(!relative)throw Error('Invalid local artifact pointer');const r=await fetch('/.cache/'+relative);if(!r.ok)throw Error('Replay data missing');const data=await r.json();if(generation!==loadGeneration)return;DATA=data;if(!new URLSearchParams(location.search).has('alpha')&&DATA.empirical_measure_model)$('empiricalAlpha').value=String(DATA.empirical_measure_model.default_alpha);framePosition=Math.max(0,floorIndex(DATA.frames,savedTime));if(initialTime&&DATA.frames[framePosition].timestamp<savedTime&&framePosition<DATA.frames.length-1)framePosition++;
 if(stage==='m342-offensive'){const base=await(await fetch(`/.cache/battles/sample_battle_${$('battle').value}/m322-reviewed-speed/latest.json`,{cache:'no-store'})).json();const parent=base.path.split('/.cache/')[1];const seal=await(await fetch('/.cache/'+parent.replace(/replay\.json$/,'manifest.json'))).json();if(seal.status!=='complete'||seal.outputs['replay.json']!==DATA.offensive_inference.source_speed_sha256)throw Error('速度证据已更新，请重新生成承伤约束回放');if(generation!==loadGeneration)return;}
 EVENTS=[...new Map([...DATA.timeline.filter(e=>!['switch_out','send_out','transformation'].includes(e.kind)),...(DATA.action_timeline||[]),...DATA.reviewed_inference.updates.map(u=>({id:u.id,timestamp:u.timestamp,kind:'speed_constraint'})),...(DATA.offensive_inference?.updates||[]).map(u=>({id:u.id,timestamp:u.timestamp,kind:'own_hp_damage',text:`我方承伤 ${u.observation.damage}`,sources:u.observation.sources}))].map(e=>[e.id,e])).values()].sort((a,b)=>a.timestamp-b.timestamp||a.id.localeCompare(b.id));
 $('timeline').max=DATA.frames.length-1;markers();reviewNavigation();$('video').src=localPath(DATA.duration_coverage.source_video);$('empiricalFile').href=localPath(DATA.empirical_artifact);$('status').textContent=`${DATA.frames.length} 原帧 · ${DATA.reviewed_metrics.deterministic} 来源审查约束 · ${DATA.reviewed_metrics.conditional} 带条件约束`;
 $('itemPolicyNote').textContent=DATA.offensive_inference?`Full Reference Model · ${DATA.offensive_inference.item_profile||'historical'}。Practical 的缩减包含显式建模假设，不代表穷尽合法道具；休眠不等于证据排除。切换读取预计算结果。`:'';
 document.querySelector('header small').textContent=DATA.empirical_measure_model?(DATA.offensive_inference?.milestone==='M3.4.5a'?'POKÉMON CHAMPIONS ASSISTANT · M3.4.5a':'POKÉMON CHAMPIONS ASSISTANT · M3.4.5'):'POKÉMON CHAMPIONS ASSISTANT · M3.2.2';
 document.querySelector('header h1').textContent=$('damageMode').checked?'速度与承伤证据回放':'速度证据回放';
 const url=new URL(location.href);url.searchParams.set('battle',$('battle').value);if($('damageMode').checked)url.searchParams.set('damage','1');else url.searchParams.delete('damage');url.searchParams.set('items',$('itemProfile').value);history.replaceState(null,'',url);render();
 }catch(e){if(generation===loadGeneration)$('status').textContent=e.message;}finally{if(generation===loadGeneration)document.querySelector('main').classList.remove('loading');}
}
function reviewNavigation(){const picker=$('reviewUpdate');picker.replaceChildren();const updates=[...(DATA.offensive_inference?.updates||[]).map(u=>({timestamp:u.timestamp,kind:'承伤'})),...DATA.reviewed_inference.updates.map(u=>({timestamp:u.timestamp,kind:'速度支持'}))].sort((a,b)=>a.timestamp-b.timestamp);for(const u of updates){const option=el('option',`${u.timestamp.toFixed(3)}s · ${u.kind}`);option.value=u.timestamp;picker.append(option);}picker.disabled=!updates.length;for(const id of ['reviewBefore','reviewAfter'])$(id).disabled=!updates.length;}
$('reviewBefore').onclick=()=>jumpEvidence(Number($('reviewUpdate').value),true);$('reviewAfter').onclick=()=>jumpEvidence(Number($('reviewUpdate').value));
$('empiricalAlpha').value=new URLSearchParams(location.search).get('alpha')||'0.5';$('empiricalAlpha').onchange=()=>{const url=new URL(location.href);url.searchParams.set('alpha',$('empiricalAlpha').value);history.replaceState(null,'',url);if(DATA)render();};
$('itemProfile').value=new URLSearchParams(location.search).get('items')||'practical';$('itemProfile').onchange=()=>loadBattle(true);
$('battle').value=new URLSearchParams(location.search).get('battle')||'11';$('battle').onchange=loadBattle;
$('damageMode').checked=new URLSearchParams(location.search).get('damage')==='1';$('damageMode').onchange=loadBattle;
$('timeline').oninput=()=>{framePosition=Number($('timeline').value);render();};
for(const [id,kind,direction] of [['prevFrame','frame',-1],['nextFrame','frame',1],['prevTurn','turn',-1],['nextTurn','turn',1],['prevEvent','event',-1],['nextEvent','event',1]])$(id).onclick=()=>step(kind,direction);
$('seekVideo').onclick=()=>{if(!DATA)return;$('videoPanel').open=true;const video=$('video'),time=DATA.frames[framePosition].timestamp;
 if(video.readyState===0){video.addEventListener('loadedmetadata',()=>{video.currentTime=time;},{once:true});video.preload='metadata';video.load();}else video.currentTime=time;};
document.addEventListener('keydown',e=>{if(e.target.matches('input,select,button'))return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();step('frame',e.key==='ArrowLeft'?-1:1);}});
loadBattle();
