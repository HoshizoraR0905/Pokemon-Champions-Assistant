"""Resume the B24 Speed audit from sealed receipts and completed contexts only.

Never acquires images, invokes StateEngine.replay, or republishes old inference.
Outputs a new versioned audit; use --output to preserve an earlier experiment.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_evidence.inference_integration import value, forms
from battle_evidence.speed_preference import SavedSpeedInference, RULE, held_item
from battle_evidence.configuration_domain import project_domain, DEFAULT_RULE
from battle_evidence.constraint_trace import resolved_event, event_time
from speed_order.core import knowledge, name
from speed_order.mechanics import effective_priority, mega_stones
from battle_evidence.team_items import matching

BASE=ROOT/'.cache/battles/sample_battle_24'
SOURCE=BASE/'event-driven/fresh-b24-20261101-v1'
DIAG=BASE/'diagnosis/b24-reviewed-context-20261101-v1'
TRACE=DIAG/'traces/7c3ffb267920ed10/trace.json'
CONTEXT=DIAG/'contexts-119376ea8122799a-attempt-1.jsonl'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def intervals(v):return ', '.join(str(a) if a==b else f'{a}–{b}' for a,b in v['intervals'])

def priorities(rec,context):
    pid=rec['bindings']['actor']['pokemon_instance_id'];p=context['pokemon'].get(pid,{})
    ability=value(p.get('ability',{}).get('identity'))
    ability=ability.get('canonical_id') if isinstance(ability,dict) else ability
    abilities=[name(ability,'ability')] if ability else sorted({ab for form in forms(p) for ab in knowledge().facts['pokemon'][form]['ability_names']})
    found=set();errors=[]
    for ab in abilities:
        try:
            found.add(effective_priority(dict(move=rec['event']['canonical_references']['move']['canonical_id']),
                dict(ability=ab,ability_active=True),dict(terrain=value(context.get('field',{}).get('terrain',{}).get('kind'))))['effective'])
        except ValueError as exc:errors.append(str(exc))
    # Report catalog priority even where callback execution lacks an M3 contract.
    # These B24 native abilities are handled above; never use this as solver admission.
    if not found and abilities and not set(abilities)&{'Prankster','Gale Wings','Triage'}:
        fact=knowledge().facts['moves'][rec['event']['canonical_references']['move']['canonical_id']]
        if type(fact.get('priority')) is int:found.add(fact['priority'])
    return dict(values=sorted(found),errors=errors,scope='native ability options; no unobserved suppression/transfer')

def run(output):
    paths=[TRACE,CONTEXT,SOURCE/'replay.json',SOURCE/'video-only.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    trace=read(TRACE);records=read(SOURCE/'replay.json')['history'];rmap={r['event']['event_id']:r for r in records}
    contexts={}
    for raw in CONTEXT.open():
        row=json.loads(raw);contexts[row['event_id']]=row['context']
    members={m['roster_id']:deepcopy(m) for m in trace['roster']}
    seen=set();rows=[];ledgers={}
    team_domains={rid:({'none','Choice Scarf','Quick Claw'}|mega_stones())-
        set(m['original_item_exclusions']) for rid,m in members.items()}
    for u in trace['updates']:
        if u['kind']!='speed_order_candidate':continue
        o=u['observation'];key=o['joint_relation_id']
        if key in seen:continue
        seen.add(key);c=u['new_constraint'];first=rmap[o['first_event_id']];second=rmap[o['second_event_id']]
        row=dict(id=key,cycle=o['command_cycle'],first=first,second=second,
            certification=c['certification'],original_admissibility=c['admissibility_reasons'],
            original_numerical=c.get('numerical_inference'),outcome=None,numerical=None,
            source_update_ids=[x['update_id'] for x in trace['updates'] if x['kind']=='speed_order_candidate' and x['observation']['joint_relation_id']==key])
        reasons=c['admissibility_reasons']
        row['effective_priorities']=[priorities(x,contexts[x['event']['event_id']]) for x in (first,second)]
        ps=[set(x['values']) for x in row['effective_priorities']]
        if any('priorit' in x for x in reasons) or not ps[0]&ps[1]:row['outcome']='different or uncertain priority'
        elif reasons:row['outcome']='uncertified action-cycle membership'
        else:
            pid=u['pokemon_instance_id'];other=c['first'] if c['second']==pid else c['second']
            if ':opponent:' in other:row['outcome']='opponent joint relation; known comparator unavailable'
            else:
                member=members[u['opponent_roster_id']]
                rid=member['roster_id']
                if rid not in ledgers:
                    hard=deepcopy(member['final_stats']);hard['speed']=deepcopy(member['initial']['speed'])
                    ledgers[rid]=SavedSpeedInference(native=member['initial_form'],stat_constraints=hard,
                        battle_id=trace['battle_id'],configuration_rule=DEFAULT_RULE)
                if held_item(contexts[first['event']['event_id']],pid) is None:
                    candidates=deepcopy(team_domains)
                    if 'Iron Ball' not in member['original_item_exclusions']:candidates[rid].add('Iron Ball')
                    ledgers[rid].args.update(team_member=rid,item_clause_enabled=True,team_item_domains=candidates)
                result=ledgers[rid].add(first,second,contexts[first['event']['event_id']],subject=pid,proof=c['certification'])
                row['numerical']=result
                if result['status']=='exact':
                    before=member['final_stats']['speed'];after=result['feasible']
                    row['outcome']='valid and numerically informative' if before['values']!=after['values'] else 'valid but not narrowing'
                    member['final_stats']['speed']=after
                    if result['policy']['observed_current_item'] is None:
                        team_domains[rid]={w['item'] for w in result['configuration_branches']}
                else:row['outcome']='missing comparator configuration or execution semantics'
        rows.append(row)
    roster=[]
    for original in trace['roster']:
        member=members[original['roster_id']];ledger=ledgers.get(member['roster_id'])
        policy_result=ledger.results[-1] if ledger else None
        domain=policy_result['joint_domain'] if policy_result and policy_result['status']=='exact' else project_domain(member['initial_form'],member['final_stats'])
        roster.append(dict(name=member['name'],roster_id=member['roster_id'],native=member['initial_form'],
            before=member['initial']['speed'],after=domain['stats']['speed'],
            joint_domain=domain,policy_result=policy_result,
            policy=policy_result['policy'] if policy_result else dict(id=RULE,non_iron_ball_feasible=True,
                iron_ball_fallback_necessary=False,selected='non-Iron-Ball; no admissible Speed comparisons',
                kind='inference preference; not proof of item absence'),
            chronological_constraints=[r['id'] for r in rows
                if any(x.get('bindings',{}).get('actor',{}).get('pokemon_instance_id') in member['lineage_ids']
                       or x.get('bindings',{}).get('actor',{}).get('pokemon_instance_id') in
                       [s for l in member['lineages'] for s in l.get('source_instance_ids',[])] for x in [r['first'],r['second']])]))
    previous=BASE/'diagnosis/speed-order-audit-v1/audit-v4.json'
    result=dict(schema_version=2,scope='saved evidence only; no state replay or production mutation',
        speed_preference=RULE,previous_audit=dict(path=str(previous.relative_to(ROOT)),sha256=sha(previous)),
        item_clause=dict(rule_verified=True,scope='hypothetical loadout compatibility; current possession does not reserve original ownership',
            domains={k:sorted(v) for k,v in team_domains.items()},matching=matching(team_domains),
            inferred_iron_ball_holders=[rid for rid,ledger in ledgers.items() if ledger.results[-1]['policy']['iron_ball_fallback_necessary']]),
        sources=hashes,configuration_rule=DEFAULT_RULE,candidates=rows,roster=roster,
        outcomes=dict(Counter(r['outcome'] for r in rows)),unique_candidates=len(rows),
        prior_updates=36,source_code={str(p.relative_to(ROOT)):sha(p) for p in
            [Path(__file__),ROOT/'battle_evidence/inference_integration.py',ROOT/'battle_evidence/speed_preference.py',
             ROOT/'battle_evidence/configuration_domain.py',ROOT/'battle_evidence/team_items.py',
             ROOT/'battle_evidence/constraint_trace.py',ROOT/'speed_order/mechanics.py']})
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    assert len(rows)==30
    output.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if output.exists() and output.read_text()!=encoded:raise ValueError('Preserve previous diagnostic: select a new --output')
    if not output.exists():output.write_text(encoded)
    print(json.dumps(dict(outcomes=result['outcomes'],roster=[dict(name=r['name'],before=intervals(r['before']),after=intervals(r['after'])) for r in roster]),ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=BASE/'diagnosis/speed-order-audit-v1/audit-iron-ball-last-resort-v4.json')
    run(parser.parse_args().output)
