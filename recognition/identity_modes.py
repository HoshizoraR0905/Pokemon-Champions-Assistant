"""Message-only production identity and bounded, observational HUD verification."""
from copy import deepcopy
from dataclasses import asdict
from knowledge.message_names import MessageNames


def message_identity(event, names=None):
    from recognition.event_schedule import ordered_entries
    names = names or MessageNames()
    refs = ordered_entries(event.original_text)
    literal = event.attributes.get('display_reference') or (refs[0] if len(refs) == 1 else '')
    match = names.resolve(literal)
    complete = event.original_text.rstrip().endswith(('！', '!'))
    event.actor = deepcopy(match['identity']) if complete and (event.ocr_confidence or 0) >= .95 else None
    event.attributes['message_identity'] = deepcopy(match)
    event.attributes.pop('display_alias_evidence', None)
    event.uncertainty = [u for u in event.uncertainty if u not in {'actor_unresolved', 'actor_variant_unresolved'}]
    if not event.actor: event.uncertainty.append('actor_unresolved')
    elif not event.actor.get('canonical_identity'): event.uncertainty.append('actor_variant_unresolved')
    return event


def read_hp(recognizer, frame, cards, counts):
    from recognition import box
    from recognition.parsers import ratio, percentage
    from models import Observation
    result = dict(pokemon=[])
    for side, i, offset, _ in cards:
        if side == 'own':
            a = recognizer.ocr.read(frame.image, box(frame.image, (.177+offset,.915,.213+offset,.955)), numeric=True, italic=True)
            b = recognizer.ocr.read(frame.image, box(frame.image, (.220+offset,.925,.243+offset,.955)), numeric=True, italic=True)
            hp = ratio(Observation(f'{a.value or ""}/{b.value or ""}', min(a.confidence,b.confidence),
                                   (a.region[0],a.region[1],b.region[2],b.region[3]), f'{a.raw_text}/{b.raw_text}'))
        else:
            hp = percentage(recognizer.ocr.read(frame.image, box(frame.image, (.681+offset,.113,.727+offset,.154)), numeric=True))
        result['pokemon'].append(dict(slot=f'{side}_active_{i+1}', species={}, icon=None, hp=asdict(hp)))
        counts['hud_hp_reading_invocations'] += 1
    return result


class EntryVerifier:
    """One first eligible frame, no retry loop; no prediction enters classification."""
    def __init__(self, battle_id):
        self.battle_id = battle_id
        self.predictions = {}

    def observe_prefix(self, rows):
        from recognition.event_report import video_events
        from tracking.battle_state import BattleState
        from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
        engine = StateEngine(BattleState(self.battle_id, knowledge=dict(reliability_v1=True, reliability_v2=True,
            identity_v1=True, active_continuity_v1=True, active_persistence_v1=True, message_identity_v1=True)))
        events = [e for e in video_events(rows, [], self.battle_id) if e['event_type'] != 'hud_observation']
        for i,e in enumerate(events,1):e['attributes']['sequence']=i
        engine.history = [EventRecord(e,i,ordering(event_from_dict(e))) for i,e in enumerate(events,1)]
        engine.replay()
        eventmap = {r.event['event_id']: r.bindings.get('resolved_event') or r.event for r in engine.history}
        for ep in engine.state.knowledge.get('active_entry_episodes', []):
            event = eventmap.get(ep['entry_event_id'], {})
            if event.get('event_type') != 'send_out': continue
            # Ordered children retain immutable pre-policy raw actors. Freeze
            # the same strict message prediction actually applied by StateEngine.
            event=message_identity(event_from_dict(event)).to_dict()
            key = ep['episode_id']
            if key not in self.predictions:
                self.predictions[key] = dict(episode_id=key, event_id=ep['entry_event_id'], timestamp=ep['start'],
                    side=ep['side'], slot=ep['slot'], identity=deepcopy(event.get('actor')), text=event['original_text'],
                    evidence=deepcopy(event['evidence']), title=event['attributes'].get('message_identity'),
                    outcome='pending', attempts=[])
            p = self.predictions[key]
            p['departure'] = (ep.get('departure') or {}).get('timestamp')
            if p['departure'] is not None and p['outcome'] == 'pending': p['outcome'] = 'not_observed'

    def verify(self, recognizer, frame, cards, counts):
        from recognition import box
        from tracking.evidence_fusion import identity_evidence
        from recognition.entities import EntityResolver
        # A fresh resolver and independent=True bypass all contextual nickname/roster hints.
        if not any(p['outcome']=='pending' and p.get('slot') for p in self.predictions.values()):return
        resolver = EntityResolver()
        for p in self.predictions.values():
            if p['outcome'] != 'pending' or frame.timestamp <= p['timestamp']: continue
            card = next((c for c in cards if ('self' if c[0]=='own' else 'opponent') == p['side']
                         and ('left' if c[1]==0 else 'right') == p['slot']), None)
            if card is None: continue
            side, _, o, name_roi = card
            name = recognizer.ocr.read(frame.image, box(frame.image,name_roi), italic=True, independent=True)
            counts['verification_hud_name_reads'] += 1
            name = resolver.resolve(name, 'species', region_kind='species')
            roi = (.080+o,.825,.137+o,.961) if side=='own' else (.563+o,.030,.623+o,.157)
            icon = recognizer.icons.identify(frame.image,box(frame.image,roi))
            counts['verification_hud_icon_reads'] += 1
            species = asdict(name); icon = asdict(icon)
            ref, status, reason = identity_evidence(species, icon, reliability=True)
            p['attempts'].append(dict(timestamp=frame.timestamp, source_id=frame.source,
                capture_metadata=deepcopy(frame.metadata), species=species, icon=icon, status=status, reason=reason))
            a = p['identity']
            p['outcome'] = 'inconclusive' if not a or not ref else 'match' if a['species_id']==ref['species_id'] else 'mismatch'

    def finish(self):
        for p in self.predictions.values():
            if p['outcome']=='pending': p['outcome']='not_observed'
        return dict(policy='first_eligible_post_entry_HUD_single_attempt_v1', entries=list(self.predictions.values()))
