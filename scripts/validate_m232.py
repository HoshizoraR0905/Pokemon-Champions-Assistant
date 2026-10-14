"""Sequential, checkpointed multi-recording validation using existing adapters."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts, canonical_id
VERSION='m232-v1'


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def video_identity(video):
    import cv2
    st=video.stat();h=hashlib.sha256()
    with video.open('rb') as stream:
        for offset in (0,st.st_size//2,max(0,st.st_size-1024*1024)):
            stream.seek(offset);h.update(stream.read(1024*1024))
    cap=cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():raise ValueError('Cannot open recording')
        fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps<=0 or count<=0:raise ValueError('Invalid video metadata')
        metadata={'fps':fps,'frame_count':int(count),'width':int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                  'height':int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),'duration_seconds':count/fps}
    finally:cap.release()
    return {'battle_id':canonical_id(video.stem),'path':str(video.relative_to(ROOT)),
            'size_bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'sampled_sha256':h.hexdigest(),
            'fingerprint_method':'size + mtime_ns + SHA256 of first/middle/last 1MiB','metadata':metadata}


def code_version():
    paths=['scripts/validate_m232.py','tracking/state_engine.py','tracking/hidden_state.py','tracking/knowledge_grounding.py',
           'tracking/pokemon_knowledge.py','tracking/state_timeline.py','tracking/templates/state_timeline.html',
           'recognition/battle_log.py','battle_events/parser.py']
    return digest({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})


def extract_segments(paths,identity):
    """Resume 60s raw extraction chunks; a failed chunk alone is regenerated."""
    import imageio_ffmpeg
    cache=paths.cache('m232-survey');duration=identity['metadata']['duration_seconds'];rows=[]
    for start in range(0,int(duration)+1,60):
        if start>=duration:break
        output=cache/f'segment-{start:06d}';manifest=output/'frames.json'
        if manifest.exists():
            data=json.loads(manifest.read_text())
            if data['video_fingerprint']!=identity:raise ValueError('Stale raw video segment')
            if all((ROOT/f['image']).is_file() for f in data['frames']):rows.extend(data['frames']);continue
        output.mkdir(parents=True,exist_ok=True)
        # Numbered files are outputs of this single incomplete chunk only.
        command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','info','-y',
                 '-ss',str(start),'-i',str(paths.video()),'-t',str(min(60,duration-start)),
                 '-an','-vf',"select='isnan(prev_selected_t)+gte(t-prev_selected_t,2)',scale=1311:-1,showinfo",
                 '-fps_mode','vfr','-q:v','2',str(output/'%06d.jpg')]
        log_path=output/'extraction.log'
        if not log_path.exists() or 'Lsize=' not in log_path.read_text():
            with log_path.open('w') as log:
                subprocess.run(command,stderr=log,stdout=subprocess.DEVNULL,check=True)
        pts=[float(x) for x in re.findall(r'\bn:\s*\d+.*?pts_time:([\d.]+)',(output/'extraction.log').read_text())]
        pts=[t for t in pts if t < min(60,duration-start)]
        files=sorted(output.glob('[0-9][0-9][0-9][0-9][0-9][0-9].jpg'))
        # If interruption left extra numbered files, use exactly the successfully emitted count.
        if len(files)<len(pts):raise ValueError('Decoded frame/PTS mismatch')
        frames=[{'image':str(p.relative_to(ROOT)),'timestamp':start+t,'timestamp_uncertainty_seconds':2,
                 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_id':identity['path']+'#'+str(start+t)}
                 for p,t in zip(files,pts)]
        save(manifest,{'video_fingerprint':identity,'command':command,'frames':frames})
        rows.extend(frames);print(f'{paths.battle_id}: raw survey checkpoint {start+min(60,duration-start):.1f}/{duration:.1f}s',flush=True)
    return rows


def survey(paths,identity):
    import cv2
    import numpy as np
    from recognition import classify
    from recognition.battle_log import detect_log
    cache=paths.cache('m232');destination=cache/'survey.json'
    if destination.exists():
        saved=json.loads(destination.read_text())
        if saved['video_fingerprint']==identity and saved.get('survey_adapter_version')==1 and all((ROOT/f['image']).is_file() for f in saved['frames']):return saved,True
    legacy=paths.cache('m14-phases/manifest.json');old=paths.cache('m223-survey/survey.json')
    if legacy.exists():
        data=json.loads(legacy.read_text());owner=canonical_id(Path(data['source']).stem)
        if owner!=paths.battle_id or data['source_fingerprint']['size_bytes']!=identity['size_bytes']:raise ValueError('Legacy survey belongs to different recording')
        rows=[{**f,'source_id':identity['path']+'#'+str(f['timestamp']),'timestamp_uncertainty_seconds':data['interval']} for f in data['frames']]
        reused='m14 full-video timestamped cache'
    elif old.exists():
        data=json.loads(old.read_text())
        if canonical_id(Path(data['video']).stem)!=paths.battle_id:raise ValueError('Legacy survey belongs to different recording')
        rows=data['frames'];reused='m223 full-video timestamped cache'
    else:rows=extract_segments(paths,identity);reused=None
    result=[]
    for f in rows:
        p=ROOT/f['image']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:raise ValueError('Evidence checksum mismatch')
        if 'phase' in f and 'log_geometry' in f:result.append(f);continue
        image=cv2.imread(str(p));phase,confidence,flags=classify(image)
        result.append(dict(f,phase=phase,phase_confidence=confidence,flags=flags,log_geometry=detect_log(image)))
    # Include a terminal visual check without decoding the entire recording again.
    tail_cache=cache/'tail.json'
    if tail_cache.exists():tail=json.loads(tail_cache.read_text())
    else:
        timestamp=max(0,identity['metadata']['duration_seconds']-.15)
        cap=cv2.VideoCapture(str(paths.video()));cap.set(cv2.CAP_PROP_POS_MSEC,timestamp*1000);ok,image=cap.read();cap.release()
        tail=None
        if ok:
            p=cache/'tail.jpg';p.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(p),cv2.resize(image,(1311,603)))
            phase,confidence,flags=classify(image)
            tail={'image':str(p.relative_to(ROOT)),'timestamp':timestamp,'timestamp_uncertainty_seconds':.15,
                  'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_id':identity['path']+'#'+str(timestamp),
                  'phase':phase,'phase_confidence':confidence,'flags':flags,'log_geometry':detect_log(image)}
            save(tail_cache,tail)
    if tail and tail['timestamp']>result[-1]['timestamp']:result.append(tail)
    output={'battle_id':paths.battle_id,'video_fingerprint':identity,'survey_adapter_version':1,'raw_cache_reused':reused,
            'sample_interval_seconds':2,'frames':result,'coverage_note':'Whole recording surveyed on ~2s grid plus final frame; brief UI/events may fall between samples'}
    save(destination,output)
    # Compact contact sheets are review aids, not a source of fabricated events.
    for offset in range(0,len(result),48):
        sheet=np.full((8*160,6*300,3),245,dtype=np.uint8)
        for j,f in enumerate(result[offset:offset+48]):
            y,x=(j//6)*160,(j%6)*300;sheet[y:y+138,x:x+300]=cv2.resize(cv2.imread(str(ROOT/f['image'])),(300,138))
            label=f"{f['timestamp']:.1f}s {f['phase']}"+(' LOG' if f['log_geometry'] else '')
            cv2.putText(sheet,label,(x+3,y+154),cv2.FONT_HERSHEY_SIMPLEX,.38,(0,0,0),1)
        cv2.imwrite(str(cache/f'contact-{offset//48:02d}.jpg'),sheet)
    return output,False


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--battle-id',action='append');parser.add_argument('--stage',choices=['survey','recognize','reconstruct','replay','all'],default='all')
    args=parser.parse_args()
    for bid in args.battle_id or [f'sample_battle_{n}' for n in range(5)]:
        paths=BattleArtifacts(bid).prepare()
        if args.stage in {'reconstruct','replay'}:
            from scripts.m232_replay import run
            result=run(paths)
            print(json.dumps(result,ensure_ascii=False),flush=True)
            continue
        start=time.monotonic();identity=video_identity(paths.video())
        manifest_path=paths.cache('m232/pipeline-manifest.json')
        manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema_version':1,'stages':{}}
        if manifest.get('video_fingerprint') not in (None,identity):raise ValueError('Video identity changed; preserve old artifacts before restarting')
        manifest.update(battle_id=bid,video_fingerprint=identity,pipeline_version=VERSION,implementation_hash=code_version(),rules_profile='showdown-champions-reference-v1')
        manifest['current_stage']=args.stage;manifest['status']='running';save(manifest_path,manifest)
        try:
            data,reused=survey(paths,identity)
            manifest['stages']['survey']={'status':'complete','output':str(paths.cache('m232/survey.json').relative_to(ROOT)),
                'frames':len(data['frames']),'reused':reused,'raw_cache_reused':data['raw_cache_reused'],'elapsed_seconds':round(time.monotonic()-start,3)}
            if args.stage in {'recognize','all','replay'}:
                from scripts.m232_observations import recognize
                observations,ocr_reused=recognize(paths,data)
                manifest['stages']['recognize']={'status':'complete','output':str(paths.cache('m232/observations.json').relative_to(ROOT)),'reused':ocr_reused,**observations['metrics']}
                save(manifest_path,manifest)
            if args.stage == 'all':
                save(manifest_path,manifest)
                from scripts.m232_replay import run
                print(json.dumps(run(paths),ensure_ascii=False),flush=True)
                continue
            manifest['status']='complete';save(manifest_path,manifest)
            print(json.dumps({'battle_id':bid,**manifest['stages']['survey']}),flush=True)
        except Exception as error:
            manifest.update(status='failed',error=f'{type(error).__name__}: {error}');save(manifest_path,manifest);raise

if __name__=='__main__':main()
