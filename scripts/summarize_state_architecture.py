"""Verify saved architecture experiments and publish a compact measured summary.

Reads saved outputs only. Does not replay events or acquire recognition data.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tracking.evidence_history import expand_compact
from battle_artifacts import BattleArtifacts


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize():
    results = []
    identities = {}
    hardware = None
    for battle in range(20, 25):
        experiment = 'state-architecture-20261101-b21-v2' if battle == 21 else 'state-architecture-20261101-v1'
        artifacts = BattleArtifacts(f'sample_battle_{battle}', root=ROOT)
        folder = artifacts.cache(Path('diagnosis') / experiment)
        baseline, refactor = [read(folder / stage / 'manifest.json') for stage in ('baseline', 'refactor')]
        comparison = read(folder / 'comparison.json')
        if baseline['status'] != 'complete' or refactor['status'] != 'complete' or comparison['status'] != 'passed':
            raise ValueError(f'Incomplete or failed B{battle} comparison')
        if baseline['identity']['input_sha256'] != refactor['identity']['input_sha256']:
            raise ValueError(f'B{battle} inputs differ')
        for stage, manifest in (('baseline', baseline), ('refactor', refactor)):
            if hardware is not None and hardware != manifest['hardware']:
                raise ValueError(f'B{battle} {stage} recorded platform/Python differs')
            hardware = manifest['hardware']
            for name, expected in manifest['outputs'].items():
                if sha(folder / stage / name) != expected:
                    raise ValueError(f'B{battle} {stage} output changed: {name}')
            identity = {k: manifest['identity'][k] for k in ('sources', 'script_sha256')}
            if stage in identities and identities[stage] != identity:
                raise ValueError(f'B{battle} {stage} code differs from the other battles')
            identities[stage] = identity
        a, b = [read(folder / stage / 'replay.json') for stage in ('baseline', 'refactor')]
        if a != b:
            raise ValueError(f'B{battle} full legacy replay differs, including receipt hashes')
        packet = read(folder / 'refactor' / 'compact-state.json')
        if expand_compact(packet) != b['state']:
            raise ValueError(f'B{battle} compact state failed round trip')
        if (folder / 'baseline' / 'prefixes.jsonl').read_bytes() != (folder / 'refactor' / 'prefixes.jsonl').read_bytes():
            raise ValueError(f'B{battle} decision/checkpoint prefixes differ')
        if sha(ROOT / baseline['input']) != baseline['identity']['input_sha256']:
            raise ValueError(f'B{battle} source packet changed')
        metrics = ('replay_wall', 'replay_cpu', 'callback_wall', 'callback_cpu', 'core_wall', 'core_cpu',
                   'peak_process_rss_bytes', 'spans', 'intervals')
        results.append(dict(
            battle=battle, experiment=experiment, folder=str(folder.relative_to(ROOT)),
            input_sha256=baseline['identity']['input_sha256'],
            receipts=baseline['completed_receipts'], exact_full_replay=True, exact_prefixes=True,
            receipt_statuses=dict(Counter(r['application_status'] for r in a['history'])),
            deferred_rejected_reasons=dict(Counter(r['reason'] for r in a['history']
                if r['application_status'] in {'deferred', 'rejected'})),
            compact_round_trip=True, source_input_unchanged=True,
            baseline={k: baseline[k] for k in metrics}, refactor={k: refactor[k] for k in metrics},
            core_wall_speedup=baseline['core_wall'] / refactor['core_wall'],
            core_cpu_speedup=baseline['core_cpu'] / refactor['core_cpu'],
            legacy_state_bytes=refactor['legacy_state_bytes'], compact_current_bytes=refactor['compact_current_bytes'],
            compact_evidence_bytes=len(json.dumps(packet['evidence'], ensure_ascii=False, separators=(',', ':')).encode()),
            compact_total_bytes=len(json.dumps(packet, ensure_ascii=False, separators=(',', ':')).encode()),
            compact_evidence_nodes=len(packet['evidence']),
            manifests={stage: sha(folder / stage / 'manifest.json') for stage in ('baseline', 'refactor')},
        ))
    for stage, identity in identities.items():
        source = ROOT if stage == 'refactor' else ROOT / '.cache/baselines/pre-state-engine-refactor-20261101/source'
        for name, expected in identity['sources'].items():
            if sha(source / name) != expected:
                raise ValueError(f'{stage} implementation changed since measurement: {name}')
        if sha(ROOT / 'scripts/benchmark_state_architecture.py') != identity['script_sha256']:
            raise ValueError('Benchmark script changed since measurement')
    return dict(
        schema_version=1, status='passed', date='2026-11-02',
        baseline_commit='cb8bc7c1ecb49eae316fd9535e294aebd0eee10a',
        scope='One bulk saved-production-event replay per battle/implementation; no recognition or production PTR measurement',
        validation='Exact full schema-2 replay including every receipt hash, every decision prefix, checkpoint states, HP projections, and compact/full round trip',
        limits=[
            'RSS high-water is sampled at replay completion: includes input loading/initialization and callbacks, excludes subsequent final artifact exports; not a replay-only memory delta.',
            'Core wall/CPU exclude measured callbacks; progress manifest bookkeeping remains included.',
            'state_export spans include diagnostic full-state checkpoints in refactor runs; do not interpret them as core replay shares.',
            'Early B21/B22 baseline intervals overlapped short focused tests; these are shared-workstation observations, not controlled isolated wall-time trials.',
            'Production raw-event inputs differ from later reviewed/promoted diagnostic contexts; fixture regressions cover reviewed inference policies separately.',
            'Compact-current size excludes the retained evidence table; this is state/history separation, not a claim of smaller total disk artifacts or uniformly lower RSS.',
            'This does not measure recognition accuracy, complete semantic coverage, or production video PTR.',
        ],
        hardware=hardware, code_identities=identities, battles=results,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/refactor/state-engine-architecture-20261102-measurements.json')
    args = parser.parse_args()
    result = summarize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(args.output)
    for row in result['battles']:
        print(f"B{row['battle']}: {row['receipts']} exact receipts; core wall {row['baseline']['core_wall']:.3f} -> {row['refactor']['core_wall']:.3f}s ({row['core_wall_speedup']:.2f}x)")
