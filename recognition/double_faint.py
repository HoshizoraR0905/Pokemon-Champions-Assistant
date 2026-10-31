"""Acquire independent HUD evidence only for a supported double-faint pair."""
from recognition.regions import hud_roi
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import time
from tracking.double_faint import POLICY, pending_pair


class DoubleFaintVerifier:
    def __init__(self, battle_id):
        self.battle_id = battle_id
        self.pending = {}
        self.last_attempt = {}
        self.rows_seen = 0
        self.faints = {side: {} for side in ('self', 'opponent')}
        self.entries = {side: [] for side in self.faints}
        self.checked = set()
        self.counts = Counter()
        self.trainers = {}

    def _candidates(self, rows):
        """Scheduling hints only. StateEngine alone admits a replacement pair.

        Scan only appended evidence, including on resume. Trainer consensus and
        the existing parser can route announcements; no roster/slot guesses.
        Unknown routing is permissive and can only cause extra verification.
        """
        from recognition.trainers import aggregate_trainer
        from recognition.event_schedule import ordered_entries
        from battle_events.parser import BattleContext, EventParser
        candidates = set()
        for row in rows[self.rows_seen:]:
            for observation in row.get('trainer_observations', []):
                if (observation.get('evidence') and
                        observation['evidence'][0]['timestamp'] <= row['timestamp']):
                    side = observation['side']
                    self.trainers[side] = aggregate_trainer(self.trainers.get(side), observation)
            for event in row['occurrence_decision']['events']:
                kind = event['event_type']
                if kind not in {'faint', 'send_out', 'switch_out', 'position_change'}:
                    continue
                side = event['side']
                if side not in self.faints:
                    context = BattleContext()
                    for team, trainer in self.trainers.items():
                        if trainer.get('status') == 'accepted':
                            context.participants[team].display_name = trainer['display_name']
                    if not hasattr(self, 'parser'):
                        self.parser = EventParser()
                    side = self.parser.parse(dict(entry_id=event['event_id'],
                        raw_text=event['original_text'], ocr_confidence=event.get('ocr_confidence')),
                        context, self.battle_id).side
                sides = [side] if side in self.faints else list(self.faints)
                # Other-side activity cannot expire this side's valid pair.
                # Unknown routing is only a permissive scheduling hint; the
                # authoritative engine rechecks every submitted HUD proof.
                if side in self.faints:
                    self.pending.pop(side, None)
                for team in sides:
                    if kind == 'faint':
                        # A replacement between two faints is not a double faint.
                        if self.entries[team]:
                            self.faints[team] = {}; self.entries[team] = []
                        actor = event.get('actor') or {}
                        key = actor.get('canonical_id') or event['original_text']
                        self.faints[team][key] = event['event_id']
                    elif kind == 'send_out':
                        if len(self.faints[team]) < 2:
                            if side in self.faints:
                                self.faints[team] = {}; self.entries[team] = []
                            continue
                        self.entries[team].extend([event['event_id'] + ':' + str(i)
                            for i, _ in enumerate(ordered_entries(event['original_text']))])
                        if len(self.entries[team]) == 2:
                            candidates.add((team, tuple(self.faints[team].values()), tuple(self.entries[team])))
                    elif side in self.faints:
                        self.faints[team] = {}; self.entries[team] = []
        self.rows_seen = len(rows)
        return candidates - self.checked

    def observe_prefix(self, rows, roster):
        candidates = self._candidates(rows)
        self.counts['prefix_observations'] += 1
        if not candidates:
            self.counts['prefix_replays_avoided'] += 1
            return
        self.checked.update(candidates)
        started = time.perf_counter()
        from recognition.event_report import video_events
        from tracking.battle_state import BattleState
        from tracking.state_engine import StateEngine, EventRecord, event_from_dict, ordering
        engine = StateEngine(BattleState(self.battle_id, knowledge=dict(message_identity_v1=True,
            reliability_v1=True, reliability_v2=True, identity_v1=True, active_continuity_v1=True,
            active_persistence_v1=True, command_reconciliation_v1=True)))
        events = video_events(rows, roster, self.battle_id)
        for i, event in enumerate(events, 1):
            event['attributes']['sequence'] = i
        engine.history = [EventRecord(e, i, ordering(event_from_dict(e))) for i,e in enumerate(events,1)]
        engine.replay()
        self.counts['candidate_prefix_replays'] += 1
        self.counts['candidate_replay_events'] += len(events)
        self.counts['candidate_replay_seconds'] += time.perf_counter() - started
        self.pending = {side:pair for side in engine.state.sides
                        if (pair := pending_pair(engine.state, side))}

    def verify(self, recognizer, frame, cards, counts, row):
        if not self.pending:
            return
        from recognition.command_checkpoint import strict_single_ui
        if not strict_single_ui(row.get('command_inspection') or {}):return
        from recognition import box
        from recognition.entities import EntityResolver
        from tracking.evidence_fusion import identity_evidence
        resolver = EntityResolver()  # No active-state, party or pending-message hints.
        for side, pair in list(self.pending.items()):
            if frame.timestamp <= max(e['start'] for e in pair):
                continue
            key = tuple(e['episode_id'] for e in pair)
            if frame.timestamp - self.last_attempt.get(key, float('-inf')) < 2:
                continue
            selected = [c for c in cards if ('self' if c[0]=='own' else 'opponent') == side]
            if {c[1] for c in selected} != {0,1} or len(selected) != 2:
                continue
            self.last_attempt[key] = frame.timestamp
            slots = {}
            for screen_side, i, offset, name_roi in selected:
                name = recognizer.ocr.read(frame.image, box(frame.image,name_roi), italic=True, independent=True)
                counts['double_faint_hud_name_reads'] += 1
                name = resolver.resolve(name, 'species', region_kind='species')
                roi = (hud_roi('own',offset,'icon') if screen_side=='own'
                       else hud_roi('opponent',offset,'icon'))
                icon = recognizer.icons.identify(frame.image, box(frame.image,roi))
                counts['double_faint_hud_icon_reads'] += 1
                from recognition.identity import combine_identity
                name = combine_identity(name, icon, resolver.knowledge)
                slots['left' if i==0 else 'right'] = dict(species=asdict(name), icon=asdict(icon), independent=True)
            proof = dict(policy=POLICY, timestamp=frame.timestamp, source_id=frame.source, slots=slots)
            # Both per-slot candidates carry the same frame-local pair. Placement
            # is checked atomically in StateEngine before either slot gets HP.
            mons = row.setdefault('snapshot', {}).setdefault('pokemon', [])
            for screen_side, i, _, _ in selected:
                slot = f'{screen_side}_active_{i+1}'
                mon = next((m for m in mons if m['slot']==slot), None)
                if mon is None:
                    mon = dict(slot=slot, species={}, icon=None, hp={})
                    mons.append(mon)
                mon['double_faint_hud'] = deepcopy(proof)
            # Scheduling may stop only on a supported, bijective match. The
            # authoritative placement still belongs exclusively to StateEngine.
            refs = [identity_evidence(r['species'],r['icon'])[0] for r in slots.values()]
            from tracking.double_faint import independent_candidate_support
            candidates_confirmed=all(not e.get('candidate_only') or any(ref and ref['species_id']==e['species_id']
                and independent_candidate_support(reading,ref) for ref,reading in zip(refs,slots.values())) for e in pair)
            if all(refs) and len({r['species_id'] for r in refs}) == 2 and Counter(
                    r['species_id'] for r in refs) == Counter(e['species_id'] for e in pair) and candidates_confirmed:
                self.pending.pop(side)
