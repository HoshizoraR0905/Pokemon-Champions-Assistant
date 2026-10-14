"""Concise human-readable state; expose unknowns instead of filling defaults."""
def show(fact):
    if not fact.known:return fact.knowledge
    return str(fact.value)


def summary(engine):
    s=engine.state
    lines=[f'Battle {s.battle_id}; turn {show(s.turn)}; phase {show(s.phase)}',
           f'Weather: {show(s.weather.kind)} (active {show(s.weather.active)}, remaining {show(s.weather.duration.remaining)}); '
           f'Terrain: {show(s.terrain.kind)} (active {show(s.terrain.active)}, remaining {show(s.terrain.duration.remaining)})',
           f'Trick Room: {show(s.trick_room.active)}']
    for side_id,side in s.sides.items():
        name=side.trainer.get('display_name') or 'unknown'
        lines.append(f'{side_id}: {name}; complete party {show(side.party_complete)}; remaining available {show(side.remaining_available)}')
        for pid in side.party_instance_ids:
            p=s.pokemon[pid];name=p.species.value.get('name',p.species.value.get('canonical_id','unknown')) if p.species.known else 'unknown'
            location=show(p.location)
            if p.hp.unit.known and p.hp.unit.value=='absolute':hp=f'{show(p.hp.current)}/{show(p.hp.maximum)} HP'
            elif p.hp.unit.known and p.hp.unit.value=='displayed_percent':hp=f'{show(p.hp.displayed_percent)}% displayed (absolute HP unknown)'
            else:hp='HP unknown'
            stage_bits=[]
            for stat,stage in p.stages.items():
                if stage.value.known:stage_bits.append(f'{stat}={stage.value.value:+d}')
                elif stage.changes:
                    last=stage.changes[-1];stage_bits.append(f'{stat}: {last["change"]}, magnitude {last["amount"] if last["amount"] is not None else "unknown"}; exact stage unknown')
            lines.append(f'  {pid}: {name}; {location}; {hp}; fainted {show(p.fainted)}; status {show(p.major_status)}')
            if stage_bits:lines.append('    '+ '; '.join(stage_bits))
            if p.item.activations:lines.append(f'    item activation(s): {len(p.item.activations)}; current item status {show(p.item.status)}')
    from collections import Counter
    lines.append('Event applications: '+str(dict(Counter(r.application_status for r in engine.history))))
    if any(r.reason for r in engine.history):
        lines.extend(f'  {r.event["event_id"]}: {r.application_status}: {r.reason}' for r in engine.history if r.reason)
    return '\n'.join(lines)+'\n'
