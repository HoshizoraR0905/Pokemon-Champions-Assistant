"""Opt-in neutral initialization with reviewed opening evidence.

No constructor defaults: partial recordings retain unknown facts. Ordinary
switch resets use the declared reference profile; Baton Pass remains unresolved.
"""
from .battle_state import Fact, fact


def quantified_stage_event(event):
    """Opt-in Chinese announcement magnitude; source receipt remains immutable.

    52Poké documents plain one-stage and 大幅 two-stage announcements. This is
    explicitly a reference-language interpretation, not an OCR accuracy claim.
    """
    from copy import deepcopy
    import re
    text=''.join(event.original_text.split())
    stat=r'(?:攻击|防御|特攻|特防|速度|命中率|闪避率)'
    match=re.fullmatch(r'.+的'+stat+r'(?:、'+stat+r')*(大幅)?(?:提高了|降低了)[！!。.]?',text)
    if not match:return event
    event=deepcopy(event)
    event.attributes['stages']=2 if match[1] else 1
    event.attributes['stage_magnitude_reference']='52poke-zh-stat-announcement-v1; generic reference corroboration, not independent Champions UI validation'
    return event


def opening(engine, state, event):
    proof = state.knowledge.get('battle_start_review')
    if not proof or event.event_id != proof.get('event_id'):
        return
    if not (proof.get('covers_start') is True and proof.get('sources')
            and proof.get('reviewer') and not state.pokemon):
        return
    from .state_engine import evidence_link
    provenance = dict(rule='reviewed_battle_start', review=proof, **evidence_link(event))
    for effect in (state.weather, state.terrain):
        effect.kind = fact('none', provenance, 'derived')
        effect.active = fact(False, provenance, 'derived')
    state.trick_room.active = fact(False, provenance, 'derived')
    for side in state.sides.values():
        for effect in side.conditions.values():
            effect.active = fact(False, provenance, 'derived')
    state.knowledge['neutral_opening_established'] = provenance


def entering(engine, state, pokemon, event, *, fresh, continuity=False):
    if not state.knowledge.get('neutral_opening_established') and not continuity:
        return
    from .state_engine import evidence_link
    proof = dict(rule='ordinary_entry_zero_stages', **evidence_link(event),
                 verification='showdown_champions_reference; 52Poke switch corroboration')
    # The caller must explicitly mark special inherited-stage entries. Never
    # fill these using an ordinary-entry rule.
    transfer=state.knowledge.get('pending_stage_transfer',{})
    inherited = event.attributes.get('stage_transfer_possible') is True or transfer.get('side')==pokemon.side_id
    for stage in pokemon.stages.values():
        stage.value = Fact(provenance=[proof]) if inherited else fact(0, proof, 'derived')
        stage.interval = Fact(provenance=[proof]) if inherited else fact([0, 0], proof, 'derived')
    if transfer.get('side')==pokemon.side_id:state.knowledge.pop('pending_stage_transfer',None)
    if fresh:
        sid=(pokemon.original_identity.value or {}).get('species_id')
        prior=[p for p in state.pokemon.values() if p is not pokemon and p.side_id==pokemon.side_id
               and (p.original_identity.value or {}).get('species_id')==sid]
        # New encounter IDs can be unresolved returns. A previous status must
        # not be cured just because the identity adapter created another ID.
        if not prior:
            pokemon.major_status = fact('none', dict(proof, rule='fresh_battle_entry_status'), 'derived')
        elif all(p.major_status.known for p in prior) and len({p.major_status.value for p in prior})==1:
            pokemon.major_status = fact(prior[0].major_status.value,dict(proof,rule='all_prior_identity_alternatives_agree'), 'derived')


def coverage_gap(state, event):
    if not state.knowledge.get('neutral_opening_established'):return
    from .state_engine import evidence_link
    proof=dict(rule='genuine_coverage_gap',**evidence_link(event))
    for effect in (state.weather,state.terrain,state.trick_room):
        effect.active=Fact(provenance=[proof]);effect.kind=Fact(provenance=[proof])
    for side in state.sides.values():
        for effect in side.conditions.values():effect.active=Fact(provenance=[proof])
    for p in state.pokemon.values():
        p.major_status=Fact(provenance=[proof])
        for stage in p.stages.values():
            stage.value=Fact(provenance=[proof]);stage.interval=Fact(provenance=[proof])
    state.knowledge['inference_coverage_gap']=proof


def initialize_full_hp(state,pokemon,event,*,fresh):
    """An explicitly verified initial full baseline, never a HUD observation."""
    rule=state.knowledge.get('initial_full_hp_rule',{})
    sid=(pokemon.original_identity.value or {}).get('species_id')
    if not fresh or pokemon.side_id!='self' or not rule.get('verified') or sid not in rule.get('species_ids',[]):return
    if any((p.original_identity.value or {}).get('species_id')==sid for p in state.pokemon.values() if p is not pokemon and p.side_id==pokemon.side_id):return
    configured=state.knowledge.get('team',{}).get('instances',{}).get(pokemon.pokemon_instance_id)
    maximum=(configured or {}).get('fields',{}).get('hp',{}).get('value')
    if maximum is None:return
    from .state_engine import evidence_link
    proof=dict(rule='verified_initial_full_hp',confirmation=rule,**evidence_link(event))
    if not pokemon.hp.current.known:pokemon.hp.current=fact(maximum,proof,'derived')
    if not pokemon.hp.maximum.known:pokemon.hp.maximum=fact(maximum,proof,'derived')
    if not pokemon.hp.unit.known:pokemon.hp.unit=fact('absolute',proof,'derived')


def activated_field(engine,state,event,record):
    """Opt-in documented activation deduction; no fabricated weather message."""
    from copy import deepcopy
    from .state_engine import evidence_link
    ability=(event.canonical_references.get('ability') or {}).get('canonical_id')
    rule=state.knowledge.get('ability_field_reference',{}).get(ability)
    if not rule or not rule.get('sources') or ability!='pokeapi:ability:45':return
    if rule.get('weather')!='sandstorm':return
    derived=deepcopy(event);derived.event_type='weather_change'
    derived.attributes=dict(event.attributes,weather='sandstorm',change='start')
    engine._field_event(state,derived)
    proof=dict(rule=deepcopy(rule),deduction='observed Sand Stream activation establishes sandstorm',**evidence_link(event))
    for name in ('active','kind','initiated_by'):
        previous=getattr(state.weather,name)
        setattr(state.weather,name,fact(previous.value,proof,'derived'))
    record.bindings['derived_field_transition']=dict(weather='sandstorm',knowledge='derived',source_event_id=event.event_id,rule=rule)
