"""Explicit offline fixture generation using the pinned independent Node oracle.

Not invoked by tests or runtime. Writes only new M3.1.1 fixtures and scoped cache.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SELECTED=[('neutral-physical','attack'),('neutral-special','special_attack'),('super-effective','attack'),
 ('stage-2','attack'),('burn','attack'),('weather-rain','special_attack'),('terrain-electric','special_attack'),
 ('reflect-doubles','attack'),('critical-adverse-stages','attack'),('spread','special_attack'),
 ('ability-attacker-Huge Power','attack'),('ability-defender-Fur Coat','attack'),('item-Life Orb','attack'),
 ('body-press','attack'),('psyshock','special_attack'),('fixed-Seismic Toss','attack'),('immune','attack'),
 ('form-Mega Charizard X','attack'),('scenario-LifeOrb-BodySlam','attack')]


def run():
    folder=ROOT/'tests/fixtures/inverse_damage';cache=ROOT/'.cache/m311';cache.mkdir(parents=True,exist_ok=True)
    # Historical fixture checksums are prerequisites, never rewritten.
    old=ROOT/'tests/fixtures/damage'
    oracle_manifest=json.loads((ROOT/'damage/data/manifest.json').read_text())['oracle']
    package=ROOT/'.cache/m31/oracle/node_modules/@smogon/calc'
    for name,digest in oracle_manifest['files'].items():
        assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest,name
    for name,digest in json.loads((old/'manifest.json').read_text())['files'].items():
        assert hashlib.sha256((old/name).read_bytes()).hexdigest()==digest,name
    seeds={r['id']:r for r in json.loads((old/'reference-rolls.json').read_text())['cases']}
    seeds['scenario-LifeOrb-BodySlam']=deepcopy(seeds['neutral-physical'])
    seeds['scenario-LifeOrb-BodySlam']['input']['attacker']['item']='Life Orb'
    cases=[];groups=[]
    for name,stat in SELECTED:
        base=deepcopy(seeds[name]['input']);actual=base['attacker']['stats'][stat]
        domain=list(range(max(1,actual-20),actual+21));groups.append(dict(id=name,stat=stat,input=base,known_stat=actual,candidate_stats=domain))
        for candidate in domain:
            request=deepcopy(base);request['attacker']['stats'][stat]=candidate
            cases.append(dict(id=f'{name}:{candidate}',input=request))
    inputs=cache/'oracle-inputs.json';inputs.write_text(json.dumps(dict(cases=cases)))
    print(f'Enumerating {len(cases)} independent forward requests',flush=True)
    process=subprocess.run(['node','scripts/damage_oracle.cjs',str(inputs)],cwd=ROOT,check=True,capture_output=True,text=True)
    raw=cache/'oracle-rolls.json';raw.write_text(process.stdout)
    oracle=json.loads(process.stdout);rows={r['id']:r['rolls'] for r in oracle['cases']}
    for group in groups:
        group['oracle_rolls']=[dict(candidate=c,rolls=rows[f"{group['id']}:{c}"]) for c in group['candidate_stats']]
        original=rows[f"{group['id']}:{group['known_stat']}"]
        allowed=sorted(set([original[0],original[len(original)//2],original[-1]]))
        group['damage']={'allowed_values':allowed}
        group['expected_feasible']=[r['candidate'] for r in group['oracle_rolls'] if set(r['rolls']) & set(allowed)]
    target=folder/'oracle-enumeration.json';folder.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(dict(schema_version=1,oracle=oracle['oracle'],groups=groups),ensure_ascii=False,separators=(',',':'))+'\n')
    pins=['tests/fixtures/inverse_damage/oracle-enumeration.json','scripts/damage_oracle.cjs',
          'tests/fixtures/damage/manifest.json','tests/fixtures/damage/oracle-package-lock.json','damage/data/manifest.json']
    manifest=dict(schema_version=1,oracle=oracle['oracle'],oracle_evaluations=len(cases),groups=len(groups),
                  description='Expected feasible sets derived exclusively from independently enumerated Node oracle rolls; Python forward/inverse not imported.',
                  files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in pins})
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Pinned {len(groups)} exhaustive domains; historical fixtures unchanged',flush=True)


if __name__=='__main__': run()
