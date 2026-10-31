"""Independent full-recording M2.3.7 orchestration; existing recognizers stay frozen.

One recording, content-addressed predictions, atomic stages, separate review notes.
"""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import SamplingConfig, acquire, atomic_json, fingerprint
from recognition.context import context_dump, context_restore

BID = 'sample_battle_6'


class ScopedArtifacts(BattleArtifacts):
    def cache(self, name):
        name = str(name)
        for old, new in [('m233b1/', 'm237/acquisition/'), ('m235/', 'm237/')]:
            if name.startswith(old):
                name = new + name[len(old):]
                break
        return super().cache(name)


PATHS = ScopedArtifacts(BID, ROOT)
P = PATHS.cache('m237')
R = PATHS.report('M2.3.7')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load(name):
    return json.loads((P / name).read_text())


def frozen_sources():
    files = [f for folder in ['recognition', 'tracking', 'battle_events', 'models', 'knowledge', 'capture']
             for f in (ROOT / folder).rglob('*') if f.suffix in {'.py', '.json', '.yaml', '.yml'} and '__pycache__' not in f.parts]
    files += [ROOT / p for p in ['battle_artifacts.py', 'scripts/process_m235.py', 'scripts/process_m236.py',
                                'scripts/process_m236u.py', 'scripts/replay_m233a.py', 'scripts/m232_replay.py']]
    files += list((ROOT / 'rules').glob('*.json'))
    return {str(f.relative_to(ROOT)): sha(f) for f in sorted(set(files))}


def verify_sources():
    for f, digest in load('baseline-freeze.json')['sources'].items():
        if sha(ROOT / f) != digest:
            raise ValueError('Frozen baseline dependency changed: ' + f)


def freeze():
    from scripts.validate_m232 import video_identity
    import imageio_ffmpeg
    PATHS.prepare()
    if (P / 'baseline-freeze.json').exists():
        verify_sources()
        assert sha(PATHS.video()) == load('baseline-freeze.json')['video_sha256']
        print('Reused immutable baseline source freeze', flush=True)
        return
    media = video_identity(PATHS.video())
    reader = imageio_ffmpeg.read_frames(str(PATHS.video()))
    ffmetadata = next(reader)
    reader.close()
    media['metadata']['count_based_duration_seconds'] = media['metadata']['duration_seconds']
    media['metadata']['duration_seconds'] = ffmetadata['duration']
    duration = ffmetadata['duration']
    # Declared without looking at Battle 6 species, messages, or answers.
    protocol = dict(sample_fps=2.0, survey_width=328, recognition_width=1311,
                    targeted_fps=3.0, targeted_policy='one second on either side of survey phase/overlay transitions; at most 20% of duration',
                    hud_interval_seconds=2.0, interface_interval_seconds=2.0,
                    ocr_budget=math.ceil(duration) * 24, icon_budget=math.ceil(duration) * 12,
                    first_cost_probe_seconds=30, raw_prediction_policy='all selected live-message rows; 2s HUD/menu anchors; all detected banner transitions',
                    evaluation='independent baseline; human reviewed denominator initially zero',
                    unobserved_policy='sampling alone does not establish absence; unknowns retained',
                    turn_policy='provisional command-cycle boundaries; explicit OCR turn headers recorded separately')
    old_roots = [ROOT / '.cache/battles/sample_battle_5', ROOT / 'reports/battles/sample_battle_5', ROOT / 'reports/M2.3.6-review']
    preserved = {str(f.relative_to(ROOT)): dict(size=f.stat().st_size, mtime_ns=f.stat().st_mtime_ns)
                 for base in old_roots for f in base.rglob('*') if f.is_file() and not f.is_symlink()}
    sensitive = [ROOT / 'reports/M2.3.6-review/m236-event-review-annotations.json']
    sensitive += [f for f in old_roots[0].rglob('*.json') if 'seal' in f.name]
    seal = dict(status='frozen_before_battle_6_pixels_or_predictions', battle_id=BID,
                git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                git_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
                sources=frozen_sources(), video=media, ffmpeg_metadata=ffmetadata,
                video_sha256=sha(PATHS.video()), protocol=protocol,
                historical_sensitive={str(f.relative_to(ROOT)): sha(f) for f in sensitive})
    for f in seal['sources']:
        target = P / 'baseline-code' / f
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / f).read_bytes())
    atomic_json(P / 'historical-preservation.json', preserved)
    atomic_json(P / 'baseline-freeze.json', seal)
    atomic_json(P / 'protocol.json', protocol)
    print(json.dumps(dict(duration=duration, protocol=protocol), indent=2), flush=True)


def survey():
    import cv2
    import numpy as np
    from recognition.phases import classify_phase
    from recognition.ui_regions import inspect_ui
    seal = load('baseline-freeze.json')
    rows = acquire(PATHS, seal['video'], SamplingConfig(seal['protocol']['sample_fps'], 328), 0,
                   seal['video']['metadata']['duration_seconds'])
    out = []
    previous = None
    for i, row in enumerate(rows):
        image = cv2.imread(str(ROOT / row['image']))
        # Inspect expected UI at the established display scale; no OCR or identity.
        native = cv2.resize(image, (1311, 603))
        phase, confidence, components, warnings = classify_phase(native)
        ui = inspect_ui(native)
        small = cv2.resize(image, (64, 30)).astype('float32')
        change = None if previous is None else float(np.abs(small - previous).mean())
        previous = small
        out.append(dict(**row, phase=phase, confidence=confidence, overlay=ui['overlay'],
                        components=components, warnings=warnings, scene_change=change,
                        visible_regions=[r['region_type'] for r in ui['regions'] if r['visibility'] == 'visible']))
        if i % 100 == 0:
            atomic_json(P / 'survey-progress.json', dict(status='partial', complete=i + 1, total=len(rows)))
            print('Survey UI', i + 1, '/', len(rows), flush=True)
    transitions = [r['target_timestamp'] for a, r in zip(out, out[1:])
                   if (a['phase'], a['overlay']) != (r['phase'], r['overlay'])]
    cap = seal['video']['metadata']['duration_seconds'] * .2
    targets = set()
    for t in transitions:
        extra = set(SamplingConfig(3).targets(max(0, t-1), min(seal['video']['metadata']['duration_seconds'], t+1)))
        if len(targets | extra) / 3 <= cap:
            targets |= extra
    atomic_json(P / 'survey.json', dict(status='complete', frames=out, transitions=transitions,
                                      targeted_times=sorted(targets), ocr_calls=0,
                                      phase_counts=dict(Counter(r['phase'] for r in out))))
    print('Survey complete', len(out), 'frames', len(transitions), 'transitions', flush=True)


def acquisition():
    seal = load('baseline-freeze.json')
    duration = seal['video']['metadata']['duration_seconds']
    rows = acquire(PATHS, seal['video'], SamplingConfig(seal['protocol']['sample_fps']), 0, duration)
    # Extra samples at the next finer grid around source-independent UI transitions.
    times = load('survey.json')['targeted_times']
    intervals = []
    for t in times:
        if intervals and t <= intervals[-1][1] + 1e-7:
            intervals[-1][1] = min(duration, t + 1/3)
        else:
            intervals.append([t, min(duration, t + 1/3)])
    for left, right in intervals:
        # Integer seek boundaries avoid a known sampler rounding failure for
        # fractional 3-FPS seeks. Keep only the predeclared target cells.
        decoded = acquire(PATHS, seal['video'], SamplingConfig(3), math.floor(left), min(duration, math.ceil(right)))
        rows += [r for r in decoded if any(abs(r['target_timestamp']-t)<1e-7 for t in times)]
    # Preserve first source observation once when two grids select the same PTS.
    unique = {}
    for row in sorted(rows, key=lambda r: r['timestamp']):
        unique.setdefault(row['source_id'], row)
    atomic_json(P / 'acquisition.json', dict(status='complete', frames=list(unique.values()),
        base_grid_count=len(SamplingConfig().targets(0, duration)), targeted_intervals=intervals,
        total_grid_observations=len(rows), video=seal['video'], protocol=seal['protocol']))
    print('Acquired', len(unique), 'distinct PTS frames', flush=True)


class CachedIcons:
    def __init__(self, limit):
        from recognition.icons import IconRecognizer
        self.base = IconRecognizer()
        self.source = self.base.source
        self.limit = limit
        self.hits = 0
        self.ledger_path = P / 'icon-ledger.json'
        if not self.ledger_path.exists():
            atomic_json(self.ledger_path, dict(total=0, limit=limit, reservations=[]))

    def identify(self, image, region):
        from models import IconEvidence, IconCandidate
        from recognition.sprite_shape import identify_shape
        results = []
        x, y, X, Y = region
        for profile in ['default', 'silhouette']:
            key = fingerprint(dict(pixels=hashlib.sha256(image[y:Y, x:X].tobytes()).hexdigest(),
                                   shape=image[y:Y, x:X].shape, source=self.source, profile=profile))
            target = P / 'icons' / (key + '.json')
            if target.exists():
                data = json.loads(target.read_text()); self.hits += 1
            else:
                ledger = load('icon-ledger.json')
                if ledger['total'] >= self.limit:
                    raise RuntimeError('Battle 6 icon budget exhausted')
                ledger['total'] += 1
                ledger['reservations'].append(dict(key=key, status='reserved'))
                atomic_json(self.ledger_path, ledger)
                result = self.base.identify(image, region) if profile == 'default' else identify_shape(self.base, image, region)
                data = asdict(result)
                atomic_json(target, data)
                ledger['reservations'][-1]['status'] = 'complete'
                atomic_json(self.ledger_path, ledger)
            data['region'] = region
            data['candidates'] = [IconCandidate(**c) for c in data['candidates']]
            results.append(IconEvidence(**data))
        a, b = results
        result = (IconEvidence(region=region, status='ambiguous', reason='independent_profiles_disagree', candidates=a.candidates)
                  if a.status == b.status == 'resolved' and a.species_id != b.species_id
                  else a if a.status == 'resolved' or b.status != 'resolved' else b)
        result.independent_profiles = [asdict(v) for v in results]
        return result


def bounded_ocr(limit):
    from scripts.process_m235 import CropCache
    cache = CropCache(PATHS, limit, cache_only=False)
    backend = cache.load()
    predict = backend.predict
    ledger_path = P / 'ocr-ledger.json'
    if not ledger_path.exists():
        atomic_json(ledger_path, dict(total=0, limit=limit, reservations=[]))
    def bounded(crops):
        results = []
        for crop in crops:
            key = fingerprint(dict(shape=list(crop.shape), pixels=hashlib.sha256(crop.tobytes()).hexdigest(), **cache.identity))
            target = PATHS.cache('m235/reads/' + key + '.json')
            if target.exists():
                results += predict([crop]); continue
            ledger = load('ocr-ledger.json')
            if ledger['total'] >= limit:
                raise RuntimeError('Battle 6 OCR budget exhausted; completed predictions preserved')
            ledger['total'] += 1
            ledger['reservations'].append(dict(key=key, status='reserved'))
            atomic_json(ledger_path, ledger)
            try:
                results += predict([crop])
            except Exception as exc:
                ledger['reservations'][-1].update(status='error', error=repr(exc))
                atomic_json(ledger_path, ledger)
                raise
            ledger['reservations'][-1]['status'] = 'complete'
            atomic_json(ledger_path, ledger)
        return results
    backend.predict = bounded
    return cache


def recognize(through_seconds=None):
    import cv2
    from capture import Frame
    from recognition import Recognizer, box
    from recognition.identity_flow import recognize_hud, preview_rows, hud_cards
    from recognition.ui_regions import inspect_ui, read_message
    from recognition.message_occurrences import MessageOccurrences
    from recognition.visual_evidence import variants, parse_popup, parse_detail, DETAIL_ROIS, normalized_box, stage_arrows
    from recognition.party_panel import layout as party_layout, parse as parse_party
    from recognition.visual_adapter import selected_panel_side
    from recognition.battle_log import extract_view
    seal = load('baseline-freeze.json')
    protocol = seal['protocol']
    code = {k: sha(ROOT/k) for k in seal['sources']}
    runseal_path = P / 'recognition-runner-seal.json'
    # Freeze orchestration before its first prediction as well as all recognizers.
    runner = dict(runner=sha(__file__), frozen_sources=code, protocol=protocol,
                  ocr_manifest=sha(ROOT/'.cache/m15-onnx-medium/local-manifest.json'))
    if runseal_path.exists():
        assert json.loads(runseal_path.read_text()) == runner, 'Baseline runner changed after predictions started'
    else:
        atomic_json(runseal_path, runner)
        (P/'baseline-code/scripts/process_m237.py').write_bytes(Path(__file__).read_bytes())
    rows = load('acquisition.json')['frames']
    if through_seconds is not None:
        rows = [r for r in rows if r['timestamp'] < through_seconds]
    cache = bounded_ocr(protocol['ocr_budget'])
    icons = CachedIcons(protocol['icon_budget'])
    recognizer = Recognizer(cache, icons=icons)
    groups = MessageOccurrences(BID)
    output, decisions, emitted = [], [], []
    last_anchor = -math.inf
    previous_signature = None
    started = time.monotonic()
    for i, raw in enumerate(rows):
        target = P/'observations'/(fingerprint(dict(runner=runner, source_id=raw['source_id'], sha256=raw['sha256']))+'.json')
        if target.exists():
            row = json.loads(target.read_text())
            context_restore(recognizer.context, row['context_after'])
        else:
            image = cv2.imread(str(ROOT/raw['image']))
            assert sha(ROOT/raw['image']) == raw['sha256']
            ui = inspect_ui(image)
            message_region = next(r for r in ui['regions'] if r['region_type']=='battle_message')
            message = read_message(image, cache, message_region)
            signature = (ui['phase'], ui['overlay'], tuple((r['region_id'],r['visibility']) for r in ui['regions']))
            anchor = raw['timestamp']-last_anchor >= protocol['interface_interval_seconds'] or signature != previous_signature
            snapshot = None
            cards = hud_cards(image)
            frame = Frame(image, raw['source_id'], i, raw['timestamp'], raw)
            if anchor:
                if ui['phase'] in {'team_preview','team_configuration','move_selection','move_target_selection','pokemon_selection','switch_selection'}:
                    snapshot = recognizer.recognize(frame)
                    recognizer.context.preview_observations += preview_rows(snapshot, BID)
                elif cards and not ui['overlay']:
                    snapshot = recognize_hud(recognizer, frame)
            row = dict(**raw, ui=ui, message=message, snapshot=snapshot.to_dict() if snapshot else {},
                       scheduling=dict(anchor=anchor,candidate_cards=len(cards)), visual=dict(readings={},parsed=[]),
                       window=[0, seal['video']['metadata']['duration_seconds']])
            if anchor:
                for r in ui['regions']:
                    if r['region_type']=='field_indicator' and r['visibility']=='partial':
                        r['ocr']={k:asdict(cache.read(image,box(image,roi))) for k,roi in
                                  [('label',(.205,.045,.30,.095)),('counter',(.39,.045,.424,.095))]}
                        r['selected_for_ocr']=True
                        label=r['ocr']['label']['raw_text'].strip()
                        if label in {'沙暴状态','晴天','雨天','下雪','精神场地','青草场地','戏法空间'} and r['ocr']['label']['confidence']>=.9:
                            r['canonical']=dict(literal_label=label,literal_counter=r['ocr']['counter']['raw_text'].strip(),
                                                observed_at=raw['timestamp'],counter_meaning='unverified',trigger_time=None)
                def multi_read(bounds, label):
                    return [dict(**cache.predict([crop])[0],box=bounds,config_id=label+':'+name,
                                 source_sha256=raw['sha256']) for name,crop in variants(image,bounds)]
                for r in ui['regions']:
                    if r['region_type']=='ability_banner' and r['visibility']=='visible':
                        readings={k:multi_read(bounds,k) for k,bounds in zip(['species','ability'],r['fields']['lines'])}
                        parsed=parse_popup(readings)
                        r['ocr']=readings;r['fields']['cached_extraction']=parsed;r['selected_for_ocr']=True
                        row['visual']['readings'].update({r['region_id']+':'+k:v for k,v in readings.items()})
                        row['visual']['parsed'].append(dict(kind='popup',screen_edge=r['screen_edge'],battle_side=None,**parsed))
                        r['admission']=dict(status='unresolved',reason='Screen edge does not independently establish side or biological instance')
                if ui['overlay']=='status_overlay':
                    readings={k:multi_read(normalized_box(image,roi),k) for k,roi in DETAIL_ROIS.items()}
                    row['visual'].update(readings=readings,parsed=[dict(kind='detail',**parse_detail(readings,stage_arrows(image)))],selection=selected_panel_side(image))
                if ui['overlay']=='party_overlay':
                    selection=party_layout(image)
                    if selection:
                        readings={k:multi_read(normalized_box(image,roi),k) for k,roi in selection['rois'].items()}
                        row['party_panel']=dict(readings=readings,selection=selection,parsed=parse_party(readings,selection))
                if ui['overlay']=='battle_log_overlay':
                    row['log']=extract_view(image,cache,raw['source_id'],raw['timestamp'],raw['sha256'])
            row['context_after']=context_dump(recognizer.context)
            atomic_json(target,row)
        if row['scheduling']['anchor']:
            last_anchor=row['timestamp']
        previous_signature=(row['ui']['phase'],row['ui']['overlay'],tuple((r['region_id'],r['visibility']) for r in row['ui']['regions']))
        decision=groups.observe(row)
        decisions.append(dict(timestamp=row['timestamp'],source_id=row['source_id'],reason=decision['reason'],
                              occurrence_id=(decision['occurrence'] or {}).get('id'),events=[e['event_id'] for e in decision['events']]))
        emitted += decision['events']
        # Context remains checkpointed per frame, not repeated in the aggregate.
        output.append({k:v for k,v in row.items() if k!='context_after'})
        if i%20==0 or i+1==len(rows):
            atomic_json(P/'recognition-progress.json',dict(status='partial',complete=i+1,total=len(rows),
                last_timestamp=row['timestamp'],seconds=time.monotonic()-started,ocr_attempts=load('ocr-ledger.json')['total'],ocr_hits=cache.hits))
            print('Recognition',i+1,'/',len(rows),'at',round(row['timestamp'],2),'s; OCR',load('ocr-ledger.json')['total'],'hits',cache.hits,flush=True)
    result=dict(status='partial' if through_seconds else 'complete',battle_id=BID,observations=output,
                roster=recognizer.context.preview_observations,occurrences=groups.groups,prefix_decisions=decisions,
                events=emitted,ocr_cache_hits=cache.hits,icon_cache_hits=icons.hits,seconds=time.monotonic()-started,
                runner=runner,independent_manual_review=False)
    atomic_json(P/('probe-observations.json' if through_seconds else 'baseline-observations.json'),result)
    if not through_seconds:
        atomic_json(P/'baseline-prediction-seal.json',dict(status='frozen_before_review',
            outputs={str((P/name).relative_to(ROOT)):sha(P/name) for name in ['baseline-observations.json','recognition-runner-seal.json','acquisition.json']},
            reviewed_ground_truth_occurrences=0))


def reconstruct():
    from scripts.report_m237 import reconstruct as run
    run()


def deliver():
    from scripts.report_m237 import deliver as run
    run()


def verify():
    seal = load('baseline-freeze.json')
    verify_sources()
    assert sha(PATHS.video()) == seal['video_sha256']
    changed = []
    for name, old in load('historical-preservation.json').items():
        path = ROOT/name
        if not path.is_file() or path.stat().st_size != old['size'] or path.stat().st_mtime_ns != old['mtime_ns']:
            changed.append(name)
    for name, digest in seal['historical_sensitive'].items():
        assert sha(ROOT/name) == digest, 'Historical seal/annotation changed: ' + name
    assert not changed, changed
    for name, digest in load('baseline-prediction-seal.json')['outputs'].items():
        assert sha(ROOT/name) == digest, 'Frozen baseline prediction changed: ' + name
    atomic_json(P/'verification.json',dict(status='passed',historical_paths=len(load('historical-preservation.json')),
                                          frozen_sources=len(seal['sources']),video_sha256=seal['video_sha256']))
    print('Baseline, recording and historical artifact preservation verified', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True, choices=['freeze', 'survey', 'acquire', 'recognize', 'reconstruct', 'deliver', 'verify'])
    parser.add_argument('--through-seconds', type=float)
    args = parser.parse_args()
    P.mkdir(parents=True, exist_ok=True)
    manifest = P / 'stages' / (args.stage + '.json')
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    if args.stage != 'freeze':
        verify_sources()
    if previous.get('status') == 'complete' and args.stage not in {'verify', 'deliver'}:
        for name, digest in previous.get('outputs', {}).items():
            assert sha(ROOT / name) == digest, 'Completed stage output changed: ' + name
        print('Reused completed stage:', args.stage, flush=True)
        return
    started = time.time()
    atomic_json(manifest, dict(status='running', started=started, runner_sha256=sha(__file__),
                               resume=f'.venv/bin/python scripts/process_m237.py --stage {args.stage}'))
    try:
        if args.stage == 'recognize':
            recognize(args.through_seconds)
        else:
            globals()[{'acquire': 'acquisition'}.get(args.stage, args.stage)]()
        partial = args.stage == 'recognize' and args.through_seconds is not None
        outputs = {'freeze': ['baseline-freeze.json', 'protocol.json'], 'survey': ['survey.json'],
                   'acquire': ['acquisition.json'], 'recognize': ['baseline-observations.json', 'baseline-prediction-seal.json'],
                   'reconstruct': ['reconstruction.json']}.get(args.stage, [])
        atomic_json(manifest, dict(status='partial' if partial else 'complete', started=started,
            seconds=time.time()-started, runner_sha256=sha(__file__),
            outputs={str((P/name).relative_to(ROOT)): sha(P/name) for name in outputs if (P/name).exists()},
            resume=f'.venv/bin/python scripts/process_m237.py --stage {args.stage}'))
    except Exception as exc:
        atomic_json(manifest, dict(status='error', error=repr(exc), seconds=time.time()-started,
                                   resume=f'.venv/bin/python scripts/process_m237.py --stage {args.stage}'))
        raise


if __name__ == '__main__':
    main()
