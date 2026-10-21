"""Verified build inputs and read-only combat projections using maintained calculators."""
from copy import deepcopy
from knowledge.champions_stats import ChampionsStats,STATS
from speed_order.core import effective_speed,identity_key
from damage.core import stage_stat


class KnownBuilds:
    def __init__(self):self.records={}

    def register(self,*,battle_id,instance_id,record):
        key=(battle_id,instance_id)
        if key in self.records:raise ValueError('Build binding already exists; explicit reconstruction required')
        r=deepcopy(record)
        if r.get('verified') is not True or not r.get('evidence'):raise ValueError('Verified source and instance binding evidence required')
        identity=identity_key(r['identity'],r['form']);stats={s:None for s in STATS};provenance=[]
        if r.get('training_points') is not None and r.get('alignment') is not None:
            calc=ChampionsStats(r['identity'],form=r['form']).calculate(r['training_points'],r['alignment'])
            stats.update(calc['stats']);provenance.append(calc['provenance'])
        for stat,v in r.get('observed_stats',{}).items():
            if stat not in stats or type(v) is not int or v<1:raise ValueError('Invalid verified actual stat')
            if stats[stat] is not None and stats[stat]!=v:raise ValueError('Observed and calculated configured stats conflict')
            stats[stat]=v
        r.update(canonical_identity=identity,stats=stats,stat_provenance=provenance)
        self.records[key]=r

    def import_team(self,team,*,battle_id,bindings,binding_evidence):
        """Consume existing TeamConfiguration without changing it or assuming SP displays."""
        if not binding_evidence:raise ValueError('Battle instance/slot binding evidence required')
        def reviewed(field):
            return field['status']=='manual_verified' and not any(not c.get('resolved',False) for c in field.get('conflicts',[]))
        for member in team.data['members']:
            pid=bindings.get(member['instance_id'])
            if not pid:continue
            fields=member['fields'];identity=fields['identity']
            if not reviewed(identity):continue
            observed={s:fields[s]['value'] for s in STATS if reviewed(fields[s])}
            optional={k:fields[f]['canonical_id'] or fields[f]['value'] for k,f in [('ability','ability'),('item','held_item')] if reviewed(fields[f])}
            self.register(battle_id=battle_id,instance_id=pid,record=dict(identity=identity['canonical_id'] or identity['value'],form='as_named',
                verified=True,evidence=deepcopy(binding_evidence)+[dict(team_id=team.data['team_id'],fields=deepcopy(fields))],
                observed_stats=observed,**optional))

    def projection(self,battle_id,pid,participant,field,*,profile):
        r=self.records.get((battle_id,pid))
        if not r:return dict(status='unknown',stats={s:None for s in STATS},effective_speed=None,reasons=['verified_own_build_missing'])
        result=dict(status='configured',stats=deepcopy(r['stats']),record=deepcopy(r),effective_speed=None,
            stage_adjusted={},combat_stats={s:None for s in STATS if s not in ('hp','speed')},
            reasons=['Full offensive/defensive item, ability and field modifiers require a damage-calculator action context'])
        try:
            if identity_key(participant['identity'],participant['form'])!=r['canonical_identity']:
                result.update(status='current_form_differs_from_configured_build',stats={s:None for s in STATS});return result
            for stat,stage in participant.get('stages',{}).items():
                if stat in r['stats'] and stat!='hp' and r['stats'][stat] is not None and type(stage) is int and -6<=stage<=6:
                    result['stage_adjusted'][stat]=stage_stat(r['stats'][stat],stage)
            # Items/abilities are taken from the contemporaneous actor, not the configured build.
            if r['stats']['speed'] is not None:
                context=deepcopy(participant);context.pop('stages',None)
                context['actual_speed']=r['stats']['speed']
                value=effective_speed(actual_speed=r['stats']['speed'],participant=context,field=field,profile=profile)
                result['speed_evaluation']=value
                if value['status']=='exact_reference':result['effective_speed']=value['effective_speed']
        except (ValueError,KeyError,TypeError) as exc:result['reasons'].append(str(exc))
        return result
