"""Reproduce M2.1 extraction from cached images, or evaluate saved OCR without models."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from recognition.battle_log import extract_view, assemble_views
from recognition.trainers import recognize_preview_trainers
from battle_events import EventParser, BattleContext, Participant
from battle_events.evaluation import evaluate

ROOT=Path(__file__).resolve().parents[1]


def recognize(args):
    from recognition.onnx_ocr import ONNXOCRBackend
    backend=ONNXOCRBackend(args.model_directory,provider='cpu',batch_size=1)
    model=json.loads((args.model_directory/'local-manifest.json').read_text())
    if model['model']!='PP-OCRv6_medium_rec':raise ValueError('M2.1 requires the existing Medium model')
    manifest=json.loads((args.frames/'frames.json').read_text());views=[]
    for f in manifest['frames']:
        p=args.frames/f['image'];raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        expected=f.get('metadata',{}).get('sha256')
        if expected and expected!=sha:raise ValueError('Frame checksum mismatch')
        v=extract_view(cv2.imread(str(p)),backend,f'{manifest["frames"][0]["metadata"]["original_source"]}#{f["timestamp"]}',f['timestamp'],sha)
        v['path']=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        views.append(v)
        if v['detected']:print(f['timestamp'],[(r['raw_text'],round(r['ocr_confidence'],3),r['color']) for r in v['observations']],flush=True)
    trainer_path=args.trainer_image
    trainers={}
    if trainer_path.exists():
        trainers=recognize_preview_trainers(cv2.imread(str(trainer_path)),backend,source=str(trainer_path.relative_to(ROOT)) if trainer_path.is_relative_to(ROOT) else str(trainer_path),sha256=hashlib.sha256(trainer_path.read_bytes()).hexdigest(),timestamp=28,timestamp_uncertainty=2)
    import importlib.metadata
    runtime={name:importlib.metadata.version(name) for name in ('onnxruntime','numpy','opencv-python-headless')}
    result={'schema_version':1,'model':model,'runtime':runtime,'backend':backend.model_name,'provider':'CPUExecutionProvider','input_manifest':{'path':str(args.frames/'frames.json'),'sha256':hashlib.sha256((args.frames/'frames.json').read_bytes()).hexdigest(),'extraction_command':manifest.get('extraction_command'),'timestamp_uncertainty_seconds':manifest.get('timestamp_uncertainty_seconds')},'views':views,'trainer_observations':trainers}
    args.ocr_output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=Path,default=ROOT/'.cache/m2-log-survey-360-400')
    p.add_argument('--model-directory',type=Path,default=ROOT/'.cache/m15-onnx-medium')
    p.add_argument('--ocr-output',type=Path,default=ROOT/'reports/M2.1-battle-log-raw-ocr.json')
    p.add_argument('--reuse-ocr',action='store_true')
    p.add_argument('--battle-id',default='sample_battle_2')
    p.add_argument('--trainer-image',type=Path,default=ROOT/'reports/M2.1-battle-log-evidence/team-preview-28.png')
    p.add_argument('--reference',type=Path,default=ROOT/'tests/fixtures/m21_battle_log_ground_truth.json')
    p.add_argument('--evaluation-output',type=Path,default=ROOT/'reports/M2.1-battle-log-evaluation.json')
    p.add_argument('--output',type=Path,default=ROOT/'reports/M2.1-battle-log-events.json')
    args=p.parse_args();raw=json.loads(args.ocr_output.read_text()) if args.reuse_ocr else recognize(args)
    entries,issues=assemble_views(raw['views']);c=BattleContext()
    for s,v in raw.get('trainer_observations',{}).items():
        c.participants[s]=Participant(s,v['display_name'],None,v['evidence'])
        if v['ocr_confidence']>=.75:c.color_sides[v['evidence'][0]['color']]=s
    parser=EventParser();events=[e.to_dict() for e in parser.parse_sequence(entries,c,args.battle_id)]
    result={'schema_version':1,'raw_observations_file':str(args.ocr_output.relative_to(ROOT)) if args.ocr_output.is_relative_to(ROOT) else str(args.ocr_output),
            'participants':{s:asdict(v) for s,v in c.participants.items()},'entries':entries,'event_candidates':events,'assembly_issues':issues}
    truth=json.loads(args.reference.read_text())
    evaluation=evaluate(raw,result,truth)
    args.evaluation_output.write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n')
    # Ground truth is first accessed after all predictions are complete.
    by_order={e['order']:e for e in truth['events']}
    for event,order in zip(result['event_candidates'],evaluation['chronological_order']['ordered_reference_ids']):
        if order:event['associated_video_evidence']=[by_order[order]['video_evidence']]
    result['evaluation_file']=str(args.evaluation_output)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('ASSEMBLED',len(entries),'ISSUES',issues,flush=True)
    for e in events:print(e['log_order'],e['event_type'],e['side'],repr(e['original_text']),e['uncertainty'],flush=True)

if __name__=='__main__':main()
