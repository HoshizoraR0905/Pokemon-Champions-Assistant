"""Offline M3.1 data/roll validation. Optional JSON Schema check, no recognition."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from damage import calculate,calculate_scenarios
from damage.data import database


def run(schema_library=None):
    folder=ROOT/'tests/fixtures/damage';manifest=json.loads((folder/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('Reference fixture changed: '+name)
    _,_,data_manifest=database();counts=dict(exact_roll_matches=0,explicit_unsupported=0,total=0,schema_pairs=0)
    schema_in=schema_out=None
    if schema_library:
        sys.path.append(str(Path(schema_library).resolve()))
        import jsonschema
        schema_in=jsonschema.Draft202012Validator(json.loads((ROOT/'damage/schemas/request-v1.json').read_text()));schema_out=jsonschema.Draft202012Validator(json.loads((ROOT/'damage/schemas/response-v1.json').read_text()))
        for s in [schema_in,schema_out]:s.check_schema(s.schema)
    for group in ['reference','combo','extra']:
        for row in json.loads((folder/(group+'-rolls.json')).read_text())['cases']:
            result=calculate(row['input']);counts['total']+=1
            if row['id'] in {'ability-attacker-Galvanize','ability-defender-Storm Drain'}:
                assert result['status']=='unsupported' and result['distribution'] is None;counts['explicit_unsupported']+=1
            else:
                assert result['status']=='exact_reference',(row['id'],result)
                assert result['distribution']['rolls']==row['rolls'],row['id'];counts['exact_roll_matches']+=1
            if schema_in:schema_in.validate(row['input']);schema_out.validate(result);counts['schema_pairs']+=1
        print(group,'complete',flush=True)
    example=json.loads((ROOT/'examples/damage/neutral.json').read_text());conditional=dict(scenarios=[dict(id='explicit',input=example)])
    if schema_in:schema_in.validate(conditional);schema_out.validate(calculate_scenarios(conditional))
    code=['damage/core.py','damage/data.py','damage/engine.py','damage/__main__.py','scripts/damage_oracle.cjs','scripts/build_damage_data.py']
    output=dict(status='supported_subset_validated',milestone_complete=False,stages=dict(A='data/contracts/reference fixtures pinned',B='integer core validated',C='bounded modifiers/API complete; broader mechanics and Champions verification remain'),
        counts=counts,data_manifest=data_manifest,code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in code},
        unsupported=['evidence-only numerical formula','unaudited/multihit/variable-power moves','Galvanize and Storm Drain reference discrepancies','grounding overrides/transform/type changes','unimplemented items/abilities/other effects'],schema_validator='jsonschema==4.25.1' if schema_in else 'not invoked')
    target=ROOT/'.cache/m31/validation.json';target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix('.tmp');temp.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');temp.replace(target)
    print(json.dumps(counts));return output
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--schema-library');args=parser.parse_args();run(args.schema_library)
