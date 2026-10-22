"""Offline M3.2.1 schema/source/performance checks with atomic scoped checkpoints."""
from copy import deepcopy
from pathlib import Path
from time import perf_counter
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speed_order import infer_speed
from speed_order.__main__ import solve
from speed_order.core import identity_key


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def run(schema_library):
    files = sorted((ROOT/'speed_order').rglob('*.py')) + sorted((ROOT/'speed_order').rglob('*.json'))
    files += sorted((ROOT/'examples/speed_order/v2').glob('*.json')) + [Path(__file__)]
    files += [ROOT/p for p in ['knowledge/champions_stats.py','knowledge/stat_feasibility.py',
        'knowledge/identity.py','knowledge/__init__.py','knowledge/data/manifest.json',
        'knowledge/data/champions_facts.json','knowledge/data/champions_stat_rules.json','damage/core.py',
        'tests/fixtures/speed_order/manifest.json','tests/fixtures/speed_order/reference.json',
        'tests/test_dynamic_action_order.py']]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    # A modified local reference snapshot invalidates source validation only by
    # producing a new checkpoint; prior successful checkpoints remain preserved.
    for source in json.loads((ROOT/'speed_order/data/sources-v2.json').read_text())['sources']:
        if 'path' in source:
            snapshot = ROOT/source['path']
            hashes[source['path']] = hashlib.sha256(snapshot.read_bytes()).hexdigest() if snapshot.exists() else None
    fingerprint = hashlib.sha256(json.dumps([hashes, schema_library], sort_keys=True).encode()).hexdigest()
    path = ROOT/'.cache/m321'/f'validation-{fingerprint[:12]}.json'
    state = json.loads(path.read_text()) if path.exists() else dict(status='running',fingerprint=fingerprint,inputs=hashes,completed={})
    atomic(path,state)
    stage = 'initializing'

    def save(key, value):
        state['completed'][key] = value
        atomic(path,state)
        print(key, value, flush=True)

    try:
        stage = 'sources'
        if stage not in state['completed']:
            checked = []; unavailable = []
            for source in json.loads((ROOT/'speed_order/data/sources-v2.json').read_text())['sources']:
                if 'path' not in source:
                    continue
                snapshot = ROOT/source['path']
                if not snapshot.exists():
                    unavailable.append(source['path']); continue
                assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source['sha256'], source['path']
                checked.append(source['path'])
            original = json.loads((ROOT/'tests/fixtures/speed_order/manifest.json').read_text())
            for name,digest in original['files'].items():
                assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
            save(stage,dict(checked_snapshots=len(checked),unavailable_snapshots=unavailable,
                            original_fixture_hashes='unchanged'))
        else:
            print(stage,'reused',flush=True)
        stage = 'schemas'
        if stage not in state['completed']:
            if schema_library:
                sys.path.append(str(Path(schema_library).resolve()))
            import jsonschema
            incoming = jsonschema.Draft202012Validator(json.loads((ROOT/'speed_order/schemas/request-v2.json').read_text()))
            outgoing = jsonschema.Draft202012Validator(json.loads((ROOT/'speed_order/schemas/response-v2.json').read_text()))
            for validator in [incoming,outgoing]:
                validator.check_schema(validator.schema)
            count = 0
            for file in sorted((ROOT/'examples/speed_order/v2').glob('*.json')):
                request = json.loads(file.read_text()); incoming.validate(request)
                result = solve(request); outgoing.validate(result)
                assert result['status'] == 'exact', (file,result['diagnostics'])
                count += 1
                strict = deepcopy(request); strict['input']['profile']='champions-evidence-only-v1'
                incoming.validate(strict); result=solve(strict);outgoing.validate(result)
                assert result['status']=='unresolved'
                count += 1
            ordinary=json.loads((ROOT/'examples/speed_order/v2/ordinary.json').read_text())
            empty=deepcopy(ordinary);empty['input']['configurations']=empty['input']['configurations'][:1]
            incoming.validate(empty);result=solve(empty);outgoing.validate(result);assert result['status']=='empty';count+=1
            unsupported=deepcopy(ordinary);unsupported['input']['configurations'][0]['ability']='Quick Draw'
            incoming.validate(unsupported);result=solve(unsupported);outgoing.validate(result);assert result['status']=='unresolved';count+=1
            invalid=deepcopy(ordinary);invalid['input']['observations'][0]['actions'][0]['activation']['state']='missing_message'
            assert not incoming.is_valid(invalid)
            invalid=deepcopy(ordinary);invalid['input']['configurations'][0]['speed']=True
            assert not incoming.is_valid(invalid)
            save(stage,dict(request_response_pairs=count,invalid_requests_rejected=2))
        else:
            print(stage,'reused',flush=True)
        ordinary=json.loads((ROOT/'examples/speed_order/v2/ordinary.json').read_text())['input']
        for size,turns,actions in [(66,1,2),(666,3,4)]:
            stage=f'benchmark:{size}-configurations-{turns}-turns-{actions}-actions'
            if stage in state['completed']:
                print(stage,'reused',state['completed'][stage],flush=True);continue
            request=deepcopy(ordinary)
            request['configurations']=[dict(id=f'{s}:{ability}:{item}',speed=s,ability=ability,item=item,training=None)
                for s in range(90,201) for ability in ['Overgrow','Chlorophyll']
                for item in ['none','Choice Scarf','Quick Claw']][:size]
            request['observations']=[]
            for turn in range(turns):
                obs=deepcopy(ordinary['observations'][0]);obs.update(id=f'turn:{turn}',decision_id=f'turn:{turn}')
                obs['state']['participants']['opp'].update(identity=identity_key('Venusaur','base'),form='base')
                obs['actions'][1]['move']='pokeapi:move:89' # Venusaur Earthquake, Champions learnset checked.
                obs['state']['field']['weather']='sun' if turn!=1 else 'none'
                obs['state']['field']['trick_room']=turn==2
                obs['state']['participants']['own']['actual_speed']=100 if turn==1 else 180
                obs['sequence']=['opp:move'] # Explicit observed prefix, complete pending set.
                for j in range(actions-2):
                    iid=f'other:{j}';p=deepcopy(obs['state']['participants']['own'])
                    p.update(instance_id=iid,actual_speed=50+j)
                    obs['state']['participants'][iid]=p
                    a=deepcopy(obs['actions'][0]);a.update(id=iid+':move',individual=iid)
                    obs['actions'].append(a)
                request['observations'].append(obs)
            start=perf_counter();result=infer_speed(**request);elapsed=perf_counter()-start
            assert result['status']=='exact',result['diagnostics']
            save(stage,dict(seconds=elapsed,configurations=size,turns=turns,actions=actions,
                            compatible_configurations=len(result['compatible_configurations']),work=result['work']))
        state.update(status='complete');state.pop('error',None);atomic(path,state)
        atomic(ROOT/'.cache/m321/latest-validation.json',dict(path=str(path.relative_to(ROOT)),fingerprint=fingerprint,status='complete'))
        print('complete',str(path.relative_to(ROOT)),flush=True)
    except Exception as exc:
        state.update(status='failed',error=dict(stage=stage,reason=str(exc)),
                     resume='Repeat the identical command; completed fingerprinted stages are reused.')
        atomic(path,state)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema-library',help='Optional existing local jsonschema library path')
    args=parser.parse_args();run(args.schema_library)
