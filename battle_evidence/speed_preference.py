"""User inference preference over existing exact ordering/SP witnesses.

Not an item observation or a probability prior. Recompute from hard domains on
every update: a preferred marginal is never fed back as mechanical evidence.
"""
from copy import deepcopy
from functools import lru_cache

from knowledge.champions_stats import ChampionsStats
from knowledge.stat_feasibility import summary, champions_attainable_stats
from .configuration_domain import DEFAULT_RULE, project_domain

RULE='user-iron-ball-last-resort-v1'
NON_BALL={'none','Choice Scarf','Quick Claw'}


def held_item(context,subject):
    from .inference_integration import value
    p=context.get('pokemon',{}).get(subject,{})
    if value(p.get('item',{}).get('status')) in {'none','consumed','lost','transferred'}:return 'none'
    item=value(p.get('item',{}).get('identity'))
    if isinstance(item,dict):item=item.get('canonical_id')
    if item is None:return None
    from speed_order.core import name
    return name(item,'item')


@lru_cache(maxsize=4096)
def current_stat(form,factor,sp):
    calc=ChampionsStats(form,form='base' if form.startswith('pokeapi:species:') else 'as_named')
    return calc.attainable('speed',adjustments=[factor],point_domain=[sp])['configurations'][0]['actual_stat']


def infer_saved_speed(orders, *, native, stat_constraints, battle_id, configuration_rule=DEFAULT_RULE,
                      excluded_items=(), team_item_domains=None, team_member=None, item_clause_enabled=False):
    """Intersect SP/alignment/form/ability/item witnesses, then apply preference.

    Each entry is a certified two-action input to the existing M3 adapter. One
    shared current-item/form epoch is required; explicit changes need a richer
    temporal adapter and remain unresolved rather than changing items per pair.
    Team domains, when supplied, describe reviewed original ownership in this
    same epoch; use the existing all-different matching relation.
    """
    from .inference_integration import _order_form_union, forms
    from .team_items import matching, scope
    from speed_order.core import name, knowledge
    configuration_rule=configuration_rule or DEFAULT_RULE
    domain=project_domain(native,stat_constraints,rule=configuration_rule)
    result=dict(status='unresolved',feasible=None,blockers=[],proofs=[o['proof'] for o in orders],
        policy=dict(id=RULE,kind='default inference preference; not observed item absence',
            non_iron_ball_feasible=None,iron_ball_fallback_necessary=False,explicit_iron_ball=False),
        configuration_branches=[],joint_domain=None)
    if not orders:return dict(result,status=domain['status'],feasible=domain['stats']['speed'],joint_domain=domain)
    if domain['status']!='exact':
        result['blockers']=['hard SP/alignment domain is '+domain['status']];return result
    # Validate scope before sharing hidden configurations across observations.
    identities=set()
    for o in orders:
        scope(battle_id,o['subject'])
        aliases=o['context'].get('source_instance_aliases',{})
        identities.add(aliases.get(o['subject'],o['subject']))
        if o['proof'].get('status','certified_local_membership')!='certified_local_membership':
            result['blockers'].append('uncertified action-cycle membership')
    if len(identities)!=1:raise ValueError('Cannot accumulate different Pokémon identities')
    known={held_item(o['context'],o['subject']) for o in orders}-{None}
    if len(known)>1:
        result['blockers'].append('observed item epoch changes require explicit temporal transitions')
    if result['blockers']:return result
    common_forms=set.intersection(*(set(forms(o['context']['pokemon'].get(o['subject'],{}))) for o in orders))
    if not common_forms:
        result['blockers']=['current form epoch changes require explicit temporal transitions'];return result
    known=next(iter(known),None)
    excluded={name(it,'item') for it in excluded_items}
    explicit_ball=known=='Iron Ball';result['policy']['explicit_iron_ball']=explicit_ball
    result['policy']['observed_current_item']=known
    if team_item_domains is not None:
        if not item_clause_enabled:raise ValueError('Team item matching requires verified clause/ownership scope')
        if team_member not in team_item_domains:raise ValueError('Missing team item subject')
        for actor in team_item_domains:scope(battle_id,actor)
    def team_ok(item):
        return team_item_domains is None or matching(team_item_domains,fixed=(team_member,item)) is not None
    def solve(ball):
        # Unknown non-ordering items are a neutral equivalence class, not a
        # claim of absence. Explicit known neutral identities stay in witnesses.
        allowed={'Iron Ball'} if ball else NON_BALL | {f['required_item'] for f in knowledge().facts['pokemon'].values() if f.get('required_item')}
        supports=None;raws=[];blockers=[]
        for o in orders:
            raw=_order_form_union(o['first'],o['second'],o['context'],subject=o['subject'],native=native,
                retained=domain['stats']['speed']['values'],battle_id=battle_id,proof=o['proof'],
                configuration_rule=configuration_rule,allowed_items=allowed)
            raws.append(raw)
            if raw['status'] not in {'exact','contradiction'}:
                blockers.extend(raw.get('blockers',[])+raw.get('diagnostics',[]) or ['ordering engine unresolved']);continue
            branches=raw.get('form_branches') or [dict(form=forms(o['context']['pokemon'][o['subject']])[0],result=raw)]
            local=set()
            for br in branches:
                r=br['result']
                for witness in r.get('compatible_configurations') or []:
                    config=witness['configuration'];item=config['item']
                    actual_item=known if known is not None else item
                    # If another observation established a neutral item, the
                    # unknown neutral class can represent it; order items cannot.
                    if known is not None and item!=known and not (item=='none' and known not in NON_BALL|{'Iron Ball'}):continue
                    if actual_item in excluded or not team_ok(actual_item):continue
                    for index,joint in enumerate(domain['configurations']['branches']):
                        factor=joint['adjustments']['speed']
                        for p in joint['stat_point_domains']['speed']:
                            sp=p['training_points']
                            if ball and not explicit_ball and sp!=0:continue
                            if current_stat(br['form'],factor,sp)!=config['speed']:continue
                            local.add((index,sp,actual_item,config['ability'],br['form']))
            supports=local if supports is None else supports & local
        return supports or set(),sorted(set(blockers)),raws
    non,blocked,raws=solve(False)
    result['policy']['non_iron_ball_feasible']=None if blocked else bool(non)
    chosen=non;fallback=False
    eligible=known is None and 'Iron Ball' not in excluded and team_ok('Iron Ball')
    result['policy'].update(speculative_iron_ball_eligible=eligible,
        iron_ball_fallback_needed_by_order=not non if not blocked else None)
    if explicit_ball or (not non and not blocked and eligible):
        chosen,blocked,raws=solve(True);fallback=not explicit_ball
    result['policy'].update(iron_ball_fallback_necessary=fallback,
        selected='observed Iron Ball' if explicit_ball else 'Iron Ball fallback' if fallback else 'non-Iron-Ball',
        speed_sp_zero_required=fallback)
    if blocked:
        result['blockers']=blocked;return result
    # Reuse exact joint branch rows; restrict Speed rows without flattening SP
    # budgets or the single shared alignment into independent stat assumptions.
    selected=[];witnesses=[]
    for index,original in enumerate(domain['configurations']['branches']):
        points={key[1] for key in chosen if key[0]==index}
        if not points:continue
        br=deepcopy(original)
        br['stat_point_domains']['speed']=[p for p in br['stat_point_domains']['speed'] if p['training_points'] in points]
        checked=champions_attainable_stats(identity=native,
            form='base' if native.startswith('pokeapi:species:') else 'as_named',stat='speed',
            alignments=[br['alignment']],point_domains={s:[p['training_points'] for p in ps] for s,ps in br['stat_point_domains'].items()},
            retain_witnesses=False)
        if checked['status']!='exact':continue
        br=checked['configurations']['branches'][0]
        selected.append(br)
        for key in sorted(k for k in chosen if k[0]==index):
            _,sp,item,ability,form=key
            witnesses.append(dict(alignment=br['alignment'],speed_factor=br['adjustments']['speed'],speed_sp=sp,
                intrinsic_speed=next(p['actual_stat'] for p in br['stat_point_domains']['speed'] if p['training_points']==sp),
                item=item,ability=ability,current_form=form))
    joint=deepcopy(domain);joint['configurations']['branches']=selected
    for stat in joint['stats']:
        joint['stats'][stat]=summary(p['actual_stat'] for b in selected for p in b['stat_point_domains'][stat])
        joint['stat_points'][stat]=summary(p['training_points'] for b in selected for p in b['stat_point_domains'][stat])
        joint['alignment_modifiers'][stat]=sorted({b['adjustments'][stat] for b in selected})
    joint['status']='exact' if selected else 'contradiction'
    result.update(status=joint['status'],feasible=joint['stats']['speed'],joint_domain=joint,
        configuration_branches=witnesses,source_constraints=[dict(event_ids=[o['first']['event']['event_id'],o['second']['event']['event_id']],
            command_source=o['proof']['command_source']) for o in orders],
        tie_compatible=any(r.get('tie_compatible') for r in raws),
        form_branches=raws[-1].get('form_branches',[]) if raws else [],
        blockers=[] if selected else ['no shared item/form/ability/SP/alignment configuration satisfies accumulated evidence'],
        item_semantics='unknown none branch denotes neutral ordering equivalence, not proof of absence',
        reference_scope='existing provisional Champions reference; one shared item/form epoch; no unseen transfers/suppression')
    if not selected:result['policy']['iron_ball_fallback_satisfies_evidence']=False
    elif fallback:result['policy']['iron_ball_fallback_satisfies_evidence']=True
    return result


class SavedSpeedInference:
    """Chronological ledger retaining hard domains rather than preferred outputs."""
    def __init__(self, *, native, stat_constraints, battle_id, configuration_rule=DEFAULT_RULE, **item_rules):
        self.args=dict(native=native,stat_constraints=deepcopy(stat_constraints),battle_id=battle_id,
            configuration_rule=configuration_rule,**item_rules)
        self.orders=[];self.results=[]

    def add(self,first,second,context,*,subject,proof,stat_constraints=None):
        key=(first['event']['event_id'],second['event']['event_id'])
        if any((o['first']['event']['event_id'],o['second']['event']['event_id'])==key for o in self.orders):
            return deepcopy(self.results[-1])
        if stat_constraints is not None:self.args['stat_constraints']=deepcopy(stat_constraints)
        self.orders.append(deepcopy(dict(first=first,second=second,context=context,subject=subject,proof=proof)))
        result=infer_saved_speed(self.orders,**self.args);self.results.append(deepcopy(result));return result
