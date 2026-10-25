"""Fingerprint-scoped, checkpointed offline experiment; no existing-system writes."""
import argparse
import fcntl
import json
from pathlib import Path
import platform
import traceback
import numpy as np
from metagame.common import atomic_json, encode, sha, now
from experiments.no_sp_archetypes.frozen import file_hash
from experiments.moveset_diagnostics.run import protected_snapshot
from .features import DESIGN
from .data import prepare
from .evaluate import evaluate_fold,summarize

ROOT=Path(__file__).resolve().parents[2]


def protected_files(m351,m353):
    result=protected_snapshot(m351)
    paths=[Path(m353)/'frozen.json',Path(m353)/'manifest.json']
    for directory in ('damage','speed_order','speed_inference','battle_evidence','tracking','knowledge'):
        paths+=sorted((ROOT/directory).glob('*.py'))
        paths+=sorted((ROOT/directory).glob('*.json'))
        paths+=sorted((ROOT/directory/'data').glob('*.json'))
    result.update({str(p):file_hash(p) for p in paths if p.is_file()})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m353',type=Path,default=ROOT/'.cache/research/m353/cd20fc295b0e5cb16e15')
    parser.add_argument('--m351',type=Path,default=ROOT/'.cache/research/m351/7933afbb341cdbeddbe3')
    parser.add_argument('--output',type=Path,default=ROOT/'.cache/research/m354')
    parser.add_argument('--report',type=Path,default=ROOT/'milestone_reports/M3.5.4_Team_Speed_Control_and_SP_Prediction.md')
    args=parser.parse_args()
    if any(args.output.resolve().is_relative_to(p.resolve()) for p in (args.m351,args.m353,ROOT/'.cache/research/m353')):
        raise ValueError('Outputs must remain outside source and human-review namespaces')
    protected=protected_files(args.m351,args.m353)
    sources={str(p):file_hash(p) for p in [args.m353/'frozen.json',args.m351/'population.json',ROOT/'knowledge/data/champions_facts.json',ROOT/'knowledge/data/entities.json',ROOT/'knowledge/data/champions_priority_corrections.json',ROOT/'speed_order/data/sources-v2.json',ROOT/'battle_evidence/order-mechanics-v1.json']}
    dependencies=sorted((ROOT/'knowledge').glob('*.py'))+[ROOT/'speed_order/forms.py',ROOT/'speed_order/core.py',ROOT/'metagame/published/speed_support.py',ROOT/'metagame/common.py',ROOT/'knowledge/data/champions_stat_rules.json',ROOT/'knowledge/data/identity.json',ROOT/'knowledge/data/manifest.json']
    sources.update({str(p):file_hash(p) for p in dependencies})
    # The local pinned executable is evidence, never downloaded or required by
    # feature extraction at runtime. Verify it against existing source metadata.
    speed_sources=json.loads((ROOT/'speed_order/data/sources-v2.json').read_text())
    evidence=[]
    for entry in speed_sources['sources']:
        if entry.get('path','').endswith(('ps-data-abilities.ts','ps-data-mods-champions-abilities.ts')):
            p=ROOT/entry['path']
            if not p.exists() or file_hash(p)!=entry['sha256']:raise ValueError('Pinned local ability reference missing or changed')
            evidence.append(entry);sources[str(p)]=file_hash(p)
    code={p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py') if p.name!='report.py'}
    identity=dict(version='M3.5.4-v1',design=DESIGN,design_sha256=file_hash(Path(__file__).with_name('preregistered.json')),
                  sources=sources,code=code,numpy=np.__version__,python=platform.python_version(),
                  mechanics_evidence=evidence,mechanics_scope='Existing Champions pinned reference; not official or independent activation certification')
    fingerprint=sha(encode(identity).encode())[:20]
    run=args.output/fingerprint;run.mkdir(parents=True,exist_ok=True)
    with (run/'study.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest_path=run/'manifest.json'
        manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(fingerprint=fingerprint,identity=identity,stages={},created_at=now())
        manifest.update(status='running',resume_command=f'.venv/bin/python -m experiments.team_speed_context.run --m353 {args.m353} --m351 {args.m351} --output {args.output} --report {args.report}')
        atomic_json(manifest_path,manifest)
        def stage(name,fn,implementation=None):
            path=run/(name+'.json');old=manifest['stages'].get(name,{})
            reuse=old.get('status')=='complete' and old.get('implementation')==implementation and path.exists() and file_hash(path)==old.get('sha256')
            if reuse and name=='report':reuse=all(Path(p).is_file() and file_hash(p)==h for p,h in json.loads(path.read_text())['files'].items())
            if reuse:
                print('Reuse '+name,flush=True);return json.loads(path.read_text())
            manifest['stages'][name]=dict(status='running',started_at=now(),implementation=implementation,
                invalidation_reason='Missing stage or mismatched output/implementation; other completed stages retained')
            atomic_json(manifest_path,manifest);print('Run '+name,flush=True)
            try:
                result=fn();atomic_json(path,result)
                manifest['stages'][name].update(status='complete',completed_at=now(),sha256=file_hash(path),output=str(path));atomic_json(manifest_path,manifest)
                return result
            except Exception as exc:
                manifest['stages'][name].update(status='failed',error=str(exc),traceback=traceback.format_exc());manifest['status']='failed';atomic_json(manifest_path,manifest);raise
        data=stage('population-features',lambda:prepare(args.m353,args.m351))
        print(f"Audit: {data['n']} occurrences; {data['groups']} stronger groups; {data['m351_groups']} original groups",flush=True)
        folds=[]
        for seed in DESIGN['outer_seeds']:
            for fold in range(DESIGN['outer_folds']):
                folds.append(stage(f'evaluation-{seed}-{fold}',lambda seed=seed,fold=fold:evaluate_fold(data['rows'],data['targets'],seed,fold)))
        result=stage('evaluation-summary',lambda:summarize(data['rows'],data['targets'],folds))
        from .report import write_report
        stage('report',lambda:write_report(args.report,data,result,identity,fingerprint,run),implementation=file_hash(Path(__file__).with_name('report.py')))
        after=protected_files(args.m351,args.m353)
        if protected!=after:
            manifest.update(status='protected_files_changed',error='Protected file changed concurrently; no experiment code writes these paths.')
            atomic_json(manifest_path,manifest);raise RuntimeError(manifest['error'])
        manifest.update(status='complete',completed_at=now(),protected_files_unchanged=True,protected_file_hashes=protected)
        atomic_json(manifest_path,manifest);atomic_json(args.output/'latest.json',dict(fingerprint=fingerprint,path=str(run.resolve())))
        for name in ('A_median','B_own','C_context'):print(name,result['pooled'][name]['mae'],flush=True)
        print(f'Complete {fingerprint}; protected files unchanged\n{args.report}',flush=True)


if __name__=='__main__':main()
