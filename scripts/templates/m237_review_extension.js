// Extends the preserved M236 event viewer; no recognition or state mutation.
const turnPanel=el('section',null,$('queue').parentNode);turnPanel.className='panel';$('queue').before(turnPanel);
el('h3','Provisional turn navigation',turnPanel);
const turnPicker=el('select',null,turnPanel);turnPicker.id='turnPicker';turnPicker.setAttribute('aria-label','Proposed turn interval');
el('option','Entire recording',turnPicker).value='all';
for(const t of DATA.turns){const o=el('option',`${t.number===null?'Opening':'Baseline cycle '+t.number} · ${t.start.toFixed(1)}–${t.end.toFixed(1)}s · ${t.boundary_status}`,turnPicker);o.value=t.id;}
const turnReview=el('div',null,turnPanel);
annotations.turns=annotations.turns||{};
function renderTurnReview(){turnReview.replaceChildren();const t=DATA.turns.find(t=>t.id===turnPicker.value);if(!t)return;el('p','Automatic command-cycle proposal; no independently confirmed boundary.',turnReview);const saved=annotations.turns[t.id]||{};
 for(const [key,label] of [['verdict','Boundary judgment'],['number','Correct in-game turn number'],['start','Correct start timestamp'],['end','Correct end timestamp'],['event_order','Correct event order / IDs'],['feedback','Boundary evidence / missing actions']]){const l=el('label',label,turnReview);const input=el(key==='feedback'||key==='event_order'?'textarea':'input',null,l);input.value=saved[key]??'';input.dataset.turnField=key;input.oninput=()=>{annotations.turns[t.id]={...annotations.turns[t.id],[key]:input.value};persist();};}}
turnPicker.onchange=()=>{renderTurnReview();setView(state.view);};
const correctionFields=[['turnNumber','Correct turn number'],['eventTimestamp','Correct event timestamp / ordering'],['status','Status correction'],['ability','Ability revelation'],['item','Item revelation'],['faintSwitch','Faint / switch / replacement correction'],['duplicateOf','Duplicate of event ID'],['insertAfter','Insert / order after event ID']];
const fieldGrid=el('div',null,$('eventCorrection'));fieldGrid.className='grid';
for(const [key,label] of correctionFields){const l=el('label',label,fieldGrid),input=el('input',null,l);input.id=key;eventFields.push(key);input.addEventListener('input',saveEvent);}
const missLabel=el('label','Add a missed event anywhere in the recording',$('eventCorrection'));
const miss=el('textarea',null,missLabel);miss.id='missingEventText';miss.placeholder='Timestamp, turn, visible action, actor/target if known, source frames';
const addMissing=el('button','Save missed-event review note',$('eventCorrection'));addMissing.id='addMissingEvent';
addMissing.onclick=()=>{if(!miss.value.trim())return;const key='manual:'+Date.now();annotations.events[key]={verdict:'missing',feedback:miss.value,source_event_id:state.item?.id||null};miss.value='';persist();$('saved').textContent='Missed-event note saved separately; export annotations to preserve it.';};
const originalChoose=choose;
choose=function(e){originalChoose(e);const t=DATA.turns.find(t=>e.start>=t.start&&e.start<t.end);if(!t)return;const box=el('section',null,$('decisions'));box.className='panel';el('h3','Chronological state and turn uncertainty',box);el('p',`${t.number===null?'Opening':'Baseline cycle '+t.number}; ${t.boundary_status}. ${t.basis}`,box);
const before=DATA.prefixes[e.state_before_ref]||t.starting_state,after=DATA.prefixes[e.state_after_ref]||t.ending_state;
el('p',e.state_before_ref!=null?'States are engine prefixes immediately before the candidate and through its last observed frame.':'These are interval boundary states; no separate event-state transition was established for this UI card.',box);
detail('State before / prefix provenance',before,box);detail('State after / prefix provenance',after,box);detail('Full automatic event evidence',e,box);};
const originalRenderHUD=renderHUD;
renderHUD=function(f){originalRenderHUD(f);detail('All frozen frame predictions, interface OCR and region evidence',DATA.raw[f.id],$('hudEvidence'));};
const originalImport=importAnnotations;
importAnnotations=function(d){if(d.schema!=='m237-human-review-v1'||d.battle_id!=='sample_battle_6')throw Error('Expected Battle 6 M237 annotations.');const msg=originalImport(d);annotations.turns=annotations.turns||{};renderTurnReview();return msg;};
const originalProgress=reviewProgress;
reviewProgress=function(){originalProgress();const judged=Object.values(annotations.turns||{}).filter(v=>v.verdict?.trim()).length;$('reviewProgress').textContent+=` · ${judged} turn-boundary review records (independent status must be established separately).`;};
$('split').hidden=true;
$('actualEvent').placeholder='Literal visible message / proposed event';
$('notice').textContent='Independent baseline. No human verdicts are prefilled. Export notes to keep partial progress.';
setView('timeline');reviewProgress();
if(location.hash){const item=DATA.events.find(e=>e.id===decodeURIComponent(location.hash.slice(1)));if(item)choose(item);}
const missedPanel=el('section',null,$('eventCorrection'));missedPanel.className='panel';
function renderMissingNotes(){missedPanel.replaceChildren();el('h3','Saved missed-event notes',missedPanel);const notes=Object.entries(annotations.events).filter(([id])=>id.startsWith('manual:'));if(!notes.length)el('p','No missed-event notes saved.',missedPanel);for(const [id,note] of notes){const block=el('div',null,missedPanel);el('small',id,block);const edit=el('textarea',null,block);edit.value=note.feedback||'';edit.oninput=()=>{annotations.events[id]={...annotations.events[id],feedback:edit.value};originalPersist();};const remove=el('button','Remove this note',block);remove.onclick=()=>{delete annotations.events[id];persist();};}}
const originalPersist=persist;
persist=function(){originalPersist();renderMissingNotes();};
renderMissingNotes();
if(DATA.agent_diagnostics){const root=$('uSummary');root.hidden=false;el('h2','Post-baseline agent diagnostics — not independent ground truth',root);el('p',`Baseline: ${DATA.metrics.proposed_turns} provisional cycles and ${DATA.metrics.raw_message_occurrences} message candidates. A separate visual scan proposes ${(DATA.agent_diagnostics.turn_proposals||[]).length} action groups. No diagnostic fact is admitted to state or counted as a human judgment.`,root);
for(const t of DATA.agent_diagnostics.turn_proposals||[]){const d=el('details',null,root);el('summary',`Diagnostic provisional turn ${t.number} · ${t.start.toFixed(2)}–${t.end.toFixed(2)}s`,d);el('p','Start: '+t.starting_context,d);el('p',t.actions,d);el('p','End: '+t.ending_context,d);el('p','Audit: '+t.audit,d);const jump=el('button','Inspect this interval in the baseline timeline',d);jump.onclick=()=>{turnPicker.value='all';renderTurnReview();setView('timeline');const e=DATA.events.find(e=>e.start>=t.start&&e.start<t.end);if(e)choose(e);};}
const outcome=(DATA.agent_diagnostics.notes||[]).find(n=>n.kind==='result_screen');if(outcome)el('p',`${outcome.timestamp.toFixed(3)}s: ${outcome.literal_or_panel_reading}. Agent visual reading; baseline winner remains unestablished.`,root);}

// A detector's false overlay label must not prevent a human from reviewing text.
const overrideLabel=el('label',null,$('visibilityHint').parentNode);overrideLabel.className='inline';
const overrideOverlay=el('input',null,overrideLabel);overrideOverlay.type='checkbox';overrideOverlay.id='overlayReviewOverride';
overrideLabel.append(document.createTextNode(' Override predicted overlay for this frame review (notes only)'));
function applyOverlayReviewOverride(){const f=state.frame;if(!f)return;overrideOverlay.checked=!!annotations.frames[f.id]?.overlay_review_override;if(overrideOverlay.checked){$('messageClass').disabled=false;$('visibleMessage').disabled=false;$('visibilityHint').textContent='Human review override: judge actual pixels even if the frozen detector claimed an overlay. Baseline predictions and state are unchanged.';}}
overrideOverlay.onchange=()=>{if(!state.frame)return;annotations.frames[state.frame.id]={...annotations.frames[state.frame.id],overlay_review_override:overrideOverlay.checked};persist();if(overrideOverlay.checked)applyOverlayReviewOverride();else selectFrame(state.frame.id);};
const originalSelectFrame=selectFrame;
selectFrame=function(id){originalSelectFrame(id);applyOverlayReviewOverride();};
applyOverlayReviewOverride();
