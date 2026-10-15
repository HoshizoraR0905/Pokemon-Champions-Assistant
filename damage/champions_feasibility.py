"""Compose numerical inverse damage with exact Champions training feasibility."""
from copy import deepcopy
from knowledge.champions_stats import STATS
from knowledge.stat_feasibility import champions_attainable_stats, summary, allowed
from .inverse_cli import solve as solve_inverse


def infer_champions_attack_stat(*, champions, **inverse_request):
    """Preserve M3.1.1 output and intersect it with one legal training build.

    Supplied non-target actual attacker stats and maximum HP also constrain that
    build. Null unused stats stay unconstrained. Numeric template placeholders
    should be replaced by null if they are not established actual values.
    """
    output=dict(schema_version=1,status='insufficient_information',damage_result=None,
        champions_result=None,joint_result=None,damage_feasible=None,champions_attainable=None,
        stat_intersection=None,final_feasible=None,excluded_by_stat_legality=[],excluded_by_joint_constraints=[],
        per_scenario=[],compatible_configurations=None,witnesses=[],diagnostics=[],assumptions=[
            'Exact only under the selected provisional damage profile and pinned community Champions stat rules.',
            'One canonical form and unchanged underlying training configuration; numerical level is forward context, not a stat-formula multiplier.',
            'Non-target actual attacker stats and maximum HP supplied in forward inputs are known joint constraints; null unused entries remain unknown.'])
    try:
        if not isinstance(champions,dict) or 'identity' not in champions:raise ValueError('champions requires an explicit identity/form constraint')
        stat=inverse_request.get('stat','attack')
        if stat not in ('attack','special_attack'):raise ValueError('Infer attack or special_attack')
        damage=solve_inverse(inverse_request);output['damage_result']=damage
        if damage['feasible'] is None:
            output['status']=damage['status'];output['diagnostics'].append(dict(reason='Numerical damage feasibility is unresolved; no complete filtered set claimed.'));return output
        legal=champions_attainable_stats(stat=stat,**champions);output['champions_result']=legal
        if legal['joint_feasible'] is None:
            output['diagnostics'].extend(legal['diagnostics']);return output
        if damage['attacker']['identities'] != [legal['identity']]:raise ValueError('Champions domain identity/form does not match all damage observations')
        observations=inverse_request['observations']
        if len({o['input']['attacker']['level'] for o in observations})!=1:
            raise ValueError('Composition requires one established level context')
        # An uncertain/changing numerical stat cannot be treated as a fixed known
        # training constraint. Keep this boundary explicit rather than decouple it.
        for variable in inverse_request.get('variables',[]) or []:
            if variable['path'].startswith('attacker.stats.') or variable['path']=='attacker.maximum_hp':
                raise ValueError('Scenario-dependent actual attacker stats/maximum HP require explicit separate composition solves; stages may vary')
        constraints=deepcopy(champions.get('stat_constraints') or {})
        for obs in observations:
            attacker=obs['input']['attacker']
            known=dict(attacker.get('stats',{}));known['hp']=attacker.get('maximum_hp')
            for s,value in known.items():
                if s==stat or value is None:continue
                if s not in STATS or type(value) is not int:raise ValueError('Unresolved/conflicting non-target actual stat prevents joint training verification')
                if s in constraints and not allowed(value,constraints[s]):
                    constraints[s]={'allowed_values':[]}
                else:constraints[s]=value
        joint_args=deepcopy(champions);joint_args['stat_constraints']=constraints
        joint=champions_attainable_stats(stat=stat,**joint_args);output['joint_result']=joint
        if joint['joint_feasible'] is None:output['diagnostics'].extend(joint['diagnostics']);return output
        damage_values=set(damage['feasible']['values']);attainable=set(legal['attainable']['values'])
        intermediate=damage_values & attainable
        final=damage_values & set(joint['joint_feasible']['values'])
        output.update(status='empty' if not final else damage['status'],damage_feasible=deepcopy(damage['feasible']),
            champions_attainable=deepcopy(legal['attainable']),stat_intersection=summary(intermediate),final_feasible=summary(final),
            excluded_by_stat_legality=sorted(damage_values-attainable),excluded_by_joint_constraints=sorted(intermediate-final))
        # Re-run only tiny stat feasibility, not forward damage, to retain exactly
        # the configurations supporting the final intersection.
        existing=constraints.get(stat)
        constraints[stat]={'allowed_values':[v for v in sorted(final) if existing is None or allowed(v,existing)]}
        restricted=champions_attainable_stats(stat=stat,**dict(joint_args,stat_constraints=constraints))
        output['compatible_configurations']=restricted['configurations'];output['witnesses']=restricted['witnesses']
        output['per_scenario']=[dict(id=s['id'],assignment=deepcopy(s['assignment']),
            damage_feasible=deepcopy(s['feasible']),final_feasible=summary(set(s['feasible']['values']) & final)) for s in damage['scenarios']]
        if not final:
            output['diagnostics'].append(dict(reason='Damage constraints are empty.' if not damage_values else
                'Damage-compatible values are unattainable for this form.' if not intermediate else
                'No single training configuration satisfies damage plus known stats, alignment and budget constraints.'))
    except (ValueError,TypeError,KeyError) as exc:
        output.update(status='insufficient_information',final_feasible=None,compatible_configurations=None,witnesses=[])
        output['diagnostics'].append(dict(reason=str(exc)))
    return output
