"""Cached, staged full-battle evidence extraction using existing recognizers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from battle_artifacts import BattleArtifacts, add_arguments, legacy_video, canonical_id, manifest_battle


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def extract(video, output, step, start=0, duration=None):
    """Keep selected source PTS, rather than treating an fps grid as onset time."""
    import cv2
    import imageio_ffmpeg
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / 'frames.json'
    if manifest.exists():
        value = json.loads(manifest.read_text())
        if Path(value['video']).resolve() != Path(video).resolve() or value['step'] != step or value['start'] != start or value['duration'] != duration:
            raise ValueError('Existing cache has different extraction parameters')
        return value
    cap = cv2.VideoCapture(str(video))
    metadata = {k:cap.get(v) for k,v in [('fps',cv2.CAP_PROP_FPS),('frame_count',cv2.CAP_PROP_FRAME_COUNT),
                                       ('width',cv2.CAP_PROP_FRAME_WIDTH),('height',cv2.CAP_PROP_FRAME_HEIGHT)]}
    cap.release()
    metadata['duration_seconds'] = metadata['frame_count'] / metadata['fps']
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel','info']
    if start:
        command += ['-ss', str(start)]
    command += ['-i', str(video)]
    if duration is not None:
        command += ['-t', str(duration)]
    command += ['-an','-vf',f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{step})',scale=1311:-1,showinfo",
                '-fps_mode','vfr','-q:v','2',str(output/'%06d.jpg')]
    log = output / 'extraction.log'
    if not log.exists() or 'Lsize=' not in log.read_text():
        if list(output.glob('[0-9][0-9][0-9][0-9][0-9][0-9].jpg')):
            raise ValueError('Incomplete decode cache: inspect it before retrying')
        with log.open('w') as stream:
            subprocess.run(command, stderr=stream, stdout=subprocess.DEVNULL, check=True)
    pts = [float(t) for t in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)', log.read_text())]
    if duration is not None:
        pts = [t for t in pts if t < duration]
    paths = sorted(output.glob('[0-9][0-9][0-9][0-9][0-9][0-9].jpg'))
    if len(paths) != len(pts):
        raise ValueError('Source PTS/frame count mismatch')
    frames = [{'image':str(p.relative_to(ROOT)), 'timestamp':start+t,
               'timestamp_uncertainty_seconds':step, 'source_pts_relative_to_seek':t,
               'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
               'source_id':str(video)+'#'+str(start+t)} for p,t in zip(paths,pts)]
    result = {'schema_version':1,'battle_id':canonical_id(Path(video).stem),'video':str(video),'step':step,'start':start,'duration':duration,
              'video_metadata':metadata,'command':command,'timestamp_method':'selected source frame PTS plus seek offset; not action onset',
              'frames':frames}
    save(manifest,result)
    return result


def survey(value, output):
    import cv2
    import numpy as np
    from recognition import classify
    from recognition.battle_log import detect_log
    rows=[]
    for f in value['frames']:
        image=cv2.imread(str(ROOT/f['image']))
        phase,confidence,flags=classify(image)
        rows.append(dict(f, phase=phase,phase_confidence=confidence,flags=flags,log_geometry=detect_log(image)))
    save(output/'survey.json',dict(value,frames=rows))
    for offset in range(0,len(rows),48):
        sheet=np.full((8*160,6*300,3),245,dtype=np.uint8)
        for j,f in enumerate(rows[offset:offset+48]):
            thumb=cv2.resize(cv2.imread(str(ROOT/f['image'])),(300,138))
            y,x=(j//6)*160,(j%6)*300
            sheet[y:y+138,x:x+300]=thumb
            label=f"{f['timestamp']:.1f}s {f['phase']}"+(' LOG' if f['log_geometry'] else '')
            cv2.putText(sheet,label,(x+3,y+154),cv2.FONT_HERSHEY_SIMPLEX,.38,(0,0,0),1)
        cv2.imwrite(str(output/f'contact-{offset//48:02d}.jpg'),sheet)
    print(json.dumps({'frames':len(rows),'logs':[f['timestamp'] for f in rows if f['log_geometry']],
                      'metadata':value['video_metadata']},indent=2),flush=True)


def recognize_cached(cache, output, model):
    import cv2
    from recognition.onnx_ocr import ONNXOCRBackend
    from recognition.battle_log import extract_view, detect_log
    from recognition import classify, box
    backend=ONNXOCRBackend(model, provider='cpu', batch_size=1)
    manifest=json.loads((cache/'frames.json').read_text())
    observations=[]
    for i,f in enumerate(manifest['frames']):
        target=output/(Path(f['image']).stem+'.json')
        if target.exists():
            existing=json.loads(target.read_text())
            if 'log' not in existing or existing.get('log_segmentation_version')==2:
                observations.append(existing)
                continue
        image=cv2.imread(str(ROOT/f['image']))
        if hashlib.sha256((ROOT/f['image']).read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('Cached evidence checksum mismatch')
        phase,confidence,flags=classify(image)
        result=dict(f, phase=phase,phase_confidence=confidence,flags=flags,backend=backend.model_name)
        if detect_log(image):
            result['log_segmentation_version']=2
            result['log']=extract_view(image,backend,f['source_id'],f['timestamp'],f['sha256'])
            result['log']['path']=f['image']
        elif f['timestamp']>=74:
            # Existing battle-message ROI, retaining rejected/low-confidence text.
            message=backend.read(image,box(image,(.22,.685,.64,.797)),multiline=True)
            result['message']={'raw_text':message.raw_text,'confidence':message.confidence,'box':message.region}
        save(target,result)
        observations.append(result)
        if i%20==0:print(f"OCR {i}/{len(manifest['frames'])} at {f['timestamp']:.2f}s",flush=True)
    save(output/'observations.json',{'schema_version':1,'manifest':str(cache/'frames.json'),
                                   'model':json.loads((model/'local-manifest.json').read_text()),'observations':observations})


def recognize_snapshots(cache, output, model, times):
    import cv2
    from capture import Frame
    from recognition import Recognizer
    from recognition.onnx_ocr import ONNXOCRBackend
    from recognition.trainers import recognize_preview_trainers
    frames=json.loads((cache/'frames.json').read_text())['frames']
    backend=recognizer=None
    for t in times:
        f=min(frames,key=lambda f:abs(f['timestamp']-t))
        target=output/f'{t}.json'
        if target.exists():
            existing=json.loads(target.read_text())
            if existing['capture_metadata']['sha256']!=f['sha256']:
                raise ValueError('Snapshot cache refers to different evidence')
            continue
        if backend is None:
            backend=ONNXOCRBackend(model,provider='cpu',batch_size=1)
            recognizer=Recognizer(backend,icons=False)
        path=ROOT/f['image']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=f['sha256']:
            raise ValueError('Snapshot source checksum mismatch')
        image=cv2.imread(str(path))
        value=recognizer.recognize(Frame(image,f['source_id'],timestamp=f['timestamp'],metadata=f)).to_dict()
        if value['screen']=='team_preview':
            value['trainers']=recognize_preview_trainers(image,backend,source=f['image'],sha256=f['sha256'],
                                                       timestamp=f['timestamp'],timestamp_uncertainty=2)
        save(target,value)
        print(f'Snapshot {t}: {value["screen"]}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['survey','extract','focused','ocr','snapshots'],default='survey')
    add_arguments(parser)
    parser.add_argument('--cache',type=Path,default=None)
    parser.add_argument('--step',type=float,default=2)
    parser.add_argument('--start',type=float,default=0)
    parser.add_argument('--duration',type=float)
    parser.add_argument('--ocr-output',type=Path,default=None)
    parser.add_argument('--model',type=Path,default=ROOT/'.cache/m15-onnx-medium')
    parser.add_argument('--plan',type=Path,default=None)
    parser.add_argument('--all-focused',action='store_true')
    parser.add_argument('--snapshot-output',type=Path,default=None)
    args=parser.parse_args();paths=BattleArtifacts.select(args.battle_id,args.video,default='sample_battle_3').prepare()
    args.video=Path('tests/fixtures')/(paths.battle_id+'.mp4') if args.video is None else legacy_video(args.video)
    args.cache=paths.guard_output(args.cache or paths.cache('m223-survey'))
    args.ocr_output=paths.guard_output(args.ocr_output or paths.cache('m223-ocr-survey'))
    args.snapshot_output=paths.guard_output(args.snapshot_output or paths.cache('m223-snapshots'))
    if args.plan is None:
        args.plan=paths.input('m223_annotations.json')
    if args.stage in {'focused','snapshots'} or args.all_focused:
        if paths.battle_id!='sample_battle_3':raise ValueError('M2.2.3 focused annotations belong to sample_battle_3; use general --stage extract/survey/ocr for another video')
    if args.stage=='focused':
        for interval in json.loads(args.plan.read_text())['extraction_intervals']:
            output=paths.cache(interval['cache_name'])
            value=extract(args.video,output,interval['step'],interval['start'],interval['duration'])
            survey(value,output)
        return
    if args.stage=='snapshots':
        paths.check_identity(manifest_battle(args.cache/'frames.json'))
        recognize_snapshots(args.cache,args.snapshot_output,args.model,json.loads(args.plan.read_text())['snapshot_times'])
        return
    if args.stage=='ocr':
        if not args.all_focused:paths.check_identity(manifest_battle(args.cache/'frames.json'))
        if args.all_focused:
            for interval in json.loads(args.plan.read_text())['extraction_intervals']:
                recognize_cached(paths.cache(interval['cache_name']),paths.cache(interval['ocr_cache_name']),args.model)
        else:
            recognize_cached(args.cache,args.ocr_output,args.model)
        return
    value=extract(args.video,args.cache,args.step,args.start,args.duration)
    if args.stage=='survey':survey(value,args.cache)


if __name__=='__main__':main()
