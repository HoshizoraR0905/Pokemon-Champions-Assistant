"""Scoped offline reference/schema validation with resumable benchmark stages."""
from copy import deepcopy
import argparse,hashlib,json,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from speed_order import effective_speed,infer_speed,compare_speed
from speed_order.__main__ import solve


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


def run(schema_library=None):
    folder=ROOT/'tests/fixtures/speed_order';manifest=json.loads((folder/'manifest.json').read_text())
    for name,digest in manifest['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    files=list((ROOT/'speed_order').rglob('*.py'))+list((ROOT/'speed_order').rglob('*.json'))+[folder/'manifest.json',Path(__file__)]
    files += [ROOT/p for p in ['damage/core.py','knowledge/__init__.py','knowledge/identity.py',
        'knowledge/roster.py','knowledge/champions_stats.py','knowledge/stat_feasibility.py',
        'knowledge/data/manifest.json','knowledge/data/champions_stat_rules.json']]
    fingerprint=hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},sort_keys=True).encode()).hexdigest()
    checkpoint=ROOT/'.cache/m32'/('validation-'+fingerprint[:12]+'.json')
    state=json.loads(checkpoint.read_text()) if checkpoint.exists() else dict(status='running',fingerprint=fingerprint,completed={})
    atomic(checkpoint,state)
    bundle=json.loads((folder/'reference.json').read_text());counts=dict(exact=0,cap_discrepancy_gated=0,schema_pairs=0)
    incoming=outgoing=None
    if schema_library:
        sys.path.append(str(Path(schema_library).resolve()));import jsonschema
        incoming=jsonschema.Draft202012Validator(json.loads((ROOT/'speed_order/schemas/request-v1.json').read_text()))
        outgoing=jsonschema.Draft202012Validator(json.loads((ROOT/'speed_order/schemas/response-v1.json').read_text()))
        for s in [incoming,outgoing]:s.check_schema(s.schema)
    for group in bundle['groups']:
        key='oracle:'+group['id']
        if key not in state['completed'] or incoming and not state['completed'][key].get('schema_checked'):
            exact=gated=0
            for row in group['rows']:
                participant=deepcopy(group['participant']);participant['stage']=row['stage']
                request=dict(operation='effective',input=dict(actual_speed=row['actual_speed'],participant=participant,field=group['field'],profile='showdown-champions-reference-v1'))
                result=solve(request)
                if row['modern_cap_probe']!=row['effective_speed']:
                    assert result['status']=='unsupported';gated+=1
                else:assert result['effective_speed']==row['effective_speed'];exact+=1
                if incoming:incoming.validate(request);outgoing.validate(result)
            state['completed'][key]=dict(exact=exact,gated=gated,schema_checked=bool(incoming));atomic(checkpoint,state);print(key,'complete',flush=True)
        else:print(key,'reused',flush=True)
        counts['exact']+=state['completed'][key]['exact'];counts['cap_discrepancy_gated']+=state['completed'][key]['gated']
        if incoming:counts['schema_pairs']+=len(group['rows'])
    template=json.loads((ROOT/'examples/speed_order/infer.json').read_text())['input'];template['candidate_speeds']=range(50,250)
    b=deepcopy(template['observations'][0]);b['id']='later';b['context']['own']['actual_speed']=180;b['context']['opponent']['stage']=1;b['sequence']=['own','opponent'];b['context']['timing']['turn']=2;b['context']['timing']['decision_id']='turn2:start'
    multi=dict(template,observations=template['observations']+[b])
    scenarios=deepcopy(multi)
    for o in scenarios['observations']:o['context']['opponent']['item']=None
    scenarios['variables']=[dict(id='item',scope='shared',observation_ids=['order1','later'],path='opponent.item',values=['none','Choice Scarf'])]
    for name,request in [('single',template),('multi',multi),('scenarios',scenarios)]:
        key='benchmark:'+name
        if key not in state['completed']:
            start=perf_counter();result=infer_speed(**request);elapsed=perf_counter()-start
            assert result['feasible'] is not None and result['status'] in ('exact','conditional')
            state['completed'][key]=dict(seconds=elapsed,work=result['work']);atomic(checkpoint,state)
        print(key,state['completed'][key],flush=True)
    key='benchmark:repeated_comparison'
    if key not in state['completed']:
        context=template['observations'][0]['context'];start=perf_counter()
        for _ in range(100):result=compare_speed(context=context,opponent_speeds=[99,100,101],profile=template['profile'])
        elapsed=perf_counter()-start;assert result['status']=='speed_tie_possible'
        state['completed'][key]=dict(seconds_total=elapsed,queries=100,seconds_per_query=elapsed/100);atomic(checkpoint,state)
    print(key,state['completed'][key],flush=True)
    if incoming:
        for p in (ROOT/'examples/speed_order').glob('*.json'):
            request=json.loads(p.read_text());incoming.validate(request);outgoing.validate(solve(request));counts['schema_pairs']+=1
        error_cases=[]
        empty=deepcopy(template);empty['candidate_speeds']=[50];error_cases.append(dict(operation='infer',input=empty))
        unknown=deepcopy(template);unknown['candidate_speeds']=[100];unknown['observations'][0]['context']['opponent']['item']=None;error_cases.append(dict(operation='infer',input=unknown))
        unsupported=deepcopy(unknown);unsupported['observations'][0]['context']['opponent']['item']='Quick Claw';error_cases.append(dict(operation='infer',input=unsupported))
        noninformative=deepcopy(unknown);noninformative['observations'][0]['context']['opponent']['item']='none';noninformative['observations'][0]['evidence_kind']='animation_timestamps';error_cases.append(dict(operation='infer',input=noninformative))
        for request in error_cases:
            incoming.validate(request);outgoing.validate(solve(request));counts['schema_pairs']+=1
        assert not incoming.is_valid(dict(operation='compare',input={}))
    state.update(status='complete',counts=counts);atomic(checkpoint,state)
    atomic(ROOT/'.cache/m32/latest-validation.json',dict(path=str(checkpoint.relative_to(ROOT)),fingerprint=fingerprint,status='complete'))
    print(json.dumps(counts))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--schema-library');args=parser.parse_args()
    try:run(args.schema_library)
    except Exception as exc:
        atomic(ROOT/'.cache/m32/last-error.json',dict(status='failed',error=str(exc),resume='Repeat the same validation command; completed checkpoint stages are preserved.'));raise
