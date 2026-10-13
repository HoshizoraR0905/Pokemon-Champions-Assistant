"""Visible changes only: no move or causal inference from HP changes."""
import re
from models import Recognition, BattleEvent, Observation


class Tracker:
    def __init__(self):
        self.last: dict[str, object] = {}
        self.team: dict[str, dict[str, Observation]] = {}
        self.events: list[BattleEvent] = []

    def update(self, result: Recognition) -> list[BattleEvent]:
        events: list[BattleEvent] = []
        def observe(kind: str, subject: str, obs: Observation) -> None:
            if obs.value is None:
                return
            key = f'{kind}:{subject}'
            old = self.last.get(key)
            if key in self.last and old != obs.value:
                events.append(BattleEvent(result.timestamp,result.frame_index,kind,
                                          subject,old,obs.value,obs.confidence,evidence=obs))
            elif kind == 'battle_message' and key not in self.last:
                events.append(BattleEvent(result.timestamp,result.frame_index,kind,
                                          subject,None,obs.value,obs.confidence,evidence=obs))
            self.last[key] = obs.value

        for p in result.pokemon:
            # Species change resets slot HP baseline: do not attribute a switch to damage.
            key = f'species_change:{p.slot}'
            if p.species.value is not None and key in self.last and self.last[key] != p.species.value:
                self.last.pop(f'hp_change:{p.slot}', None)
            observe('species_change',p.slot,p.species)
            observe('hp_change',p.slot,p.hp)
            if (p.team_instance_id or p.slot.startswith('own_team_')) and p.species.value:
                config = self.team.setdefault(p.team_instance_id or p.slot, {})
                prior_species = config.get('species')
                if prior_species:
                    prior_id = prior_species.resolution.canonical_id if prior_species.resolution else prior_species.value
                    new_id = p.species.resolution.canonical_id if p.species.resolution else p.species.value
                    if prior_id != new_id and not (prior_species.resolution and prior_species.resolution.verification_status=='verified'):
                        config.clear()
                for name, observation in {'species':p.species,**p.configuration}.items():
                    if observation.value is None:
                        continue
                    old = config.get(name)
                    if old and old.resolution and old.resolution.verification_status=='verified':
                        if not observation.resolution or observation.resolution.verification_status!='verified':
                            continue
                    config[name] = observation
        for name, obs in result.conditions.items():
            observe('condition_text_change',name,obs)
        if result.screen in ('battle_screen','move_selection','team_preview') and result.message.value is None:
            self.last.pop('battle_message:message',None)
        observe('battle_message','message',result.message)
        if any(e.kind == 'battle_message' for e in events):
            text = str(result.message.value)
            match = re.fullmatch(r'(对手的)?(.+?)使出了\s*(.+?)[!！。]',text)
            if match:
                side, name, move = match.groups()
                events.append(BattleEvent(result.timestamp,result.frame_index,'move_execution',
                    name.strip(),None,{'move':move.strip(),'side':'opponent' if side else 'unspecified'},
                    result.message.confidence,'visible_message_parse',result.message))
        self.events.extend(events)
        return events
