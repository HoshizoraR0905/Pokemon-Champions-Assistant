"""Scoped, resumable M2.3.6 stages. Never writes M2.3.5 caches."""
import argparse
from dataclasses import asdict
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json,SamplingConfig,acquire,fingerprint
P=BattleArtifacts('sample_battle_5',ROOT).cache('m236')
OLD=BattleArtifacts('sample_battle_5',ROOT).cache('m235')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ScopedArtifacts(BattleArtifacts):
    def cache(self,name):
        name=str(name)
        if name.startswith('m233b1/'):
            return super().cache('m236/acquisition/'+name[len('m233b1/'):])
        if name.startswith('m235/reads/'):
            old=super().cache(name)
            return old if old.exists() else super().cache(name.replace('m235/','m236/',1))
        if name=='m235/reads':return super().cache('m236/reads')
        return super().cache(name)


class BudgetIcons:
    """Content-addressed independent profiles; failed/in-flight calls cost budget."""
    def __init__(self):
        from recognition.icons import IconRecognizer
        self.base=IconRecognizer();self.source=self.base.source;self.hits=0
    def identify(self,image,region):
        from models import IconEvidence,IconCandidate
        from recognition.sprite_shape import identify_shape
        from dataclasses import asdict
        x,y,X,Y=region;crop=image[y:Y,x:X]
        recipe={f:sha(ROOT/f) for f in ['recognition/icons.py','recognition/sprite_shape.py']}
        outputs=[]
        for profile in ['default','silhouette']:
            key=fingerprint(dict(pixels=hashlib.sha256(crop.tobytes()).hexdigest(),shape=crop.shape,
                recipe=recipe,source=self.source,profile=profile))
            target=P/'icons'/f'{key}.json'
            if target.exists():data=json.loads(target.read_text());self.hits+=1
            else:
                ledger=json.loads((P/'icon-ledger.json').read_text())
                if ledger['total']>=ledger['limit']:raise RuntimeError('M236 icon budget exhausted')
                ledger['total']+=1;ledger.setdefault('reservations',[]).append(dict(key=key,profile=profile))
                atomic_json(P/'icon-ledger.json',ledger)
                result=self.base.identify(image,region) if profile=='default' else identify_shape(self.base,image,region)
                data=asdict(result);atomic_json(target,data)
            data['region']=region;data['candidates']=[IconCandidate(**c) for c in data['candidates']]
            outputs.append(IconEvidence(**data))
        a,b=outputs
        if a.status=='resolved' and b.status=='resolved' and a.species_id!=b.species_id:
            result=IconEvidence(region=region,status='ambiguous',reason='independent_profiles_disagree',candidates=a.candidates)
        else:result=a if a.status=='resolved' or b.status!='resolved' else b
        # Species-only silhouette is not a form-specific assertion.
        result.independent_profiles=[asdict(v) for v in outputs]
        return result


def budget_ocr(cache):
    """Reserve attempted calls before inference; preserve failures across resumes.

    Historical successful files predate this ledger and are counted once. Their
    failed-call count is unknown, rather than retroactively claimed to be zero.
    """
    backend=cache.load();predict=backend.predict
    ledger_path=P/'ocr-ledger.json'
    if not ledger_path.exists():
        used=len(list((P/'reads').glob('*.json')))
        atomic_json(ledger_path,dict(total=used,limit=cache.budget,
            historical_successful_files=used,historical_failed_calls='unknown',reservations=[]))
    def bounded(crops):
        output=[]
        for crop in crops:
            key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**cache.identity))
            target=cache.paths.cache('m235/reads/'+key+'.json')
            if not target.exists():
                ledger=json.loads(ledger_path.read_text())
                if ledger['total']>=ledger['limit']:raise RuntimeError('M236 OCR budget exhausted')
                ledger['total']+=1;ledger['reservations'].append(dict(key=key,status='reserved'))
                atomic_json(ledger_path,ledger)
                try:reading=predict([crop])[0]
                except Exception as exc:
                    ledger['reservations'][-1].update(status='error',error=repr(exc))
                    atomic_json(ledger_path,ledger);raise
                ledger['reservations'][-1]['status']='complete';atomic_json(ledger_path,ledger)
                output.append(reading)
            else:output+=predict([crop])
        return output
    backend.predict=bounded


def recognize_stage(split):
    import cv2
    from capture import Frame
    from recognition import Recognizer
    from recognition.identity_flow import recognize_hud,preview_rows,EntryWindows,hud_cards
    from recognition.message_selection import ROI
    from scripts.process_m235 import CropCache
    from dataclasses import asdict
    fixture=ROOT/'tests/fixtures/battles/m236_review.json'
    review=json.loads((P/'review-seal.json').read_text())
    assert sha(fixture)==review['sha256']
    assert sha(P/'evaluation-acquisition.json')==review['acquisition_sha256']
    code={str(f.relative_to(ROOT)):sha(f) for d in ['recognition','tracking','battle_events','models'] for f in (ROOT/d).glob('*.py')}
    recipe=fingerprint(dict(code=code,runner=sha(__file__)))
    if split=='held_out':
        seal=json.loads((P/'implementation-seal.json').read_text());assert seal['code']==code and seal['runner']==sha(__file__),'Implementation must be frozen before held-out recognition'
    rows=json.loads((P/'evaluation-acquisition.json').read_text())['frames']
    rows=[r for r in rows if r['split']==split]
    cache=CropCache(ScopedArtifacts('sample_battle_5',ROOT),600,cache_only=False)
    budget_ocr(cache)
    icons=BudgetIcons();recognizer=Recognizer(cache,icons=icons);entries=EntryWindows()
    # Automatic preview only; no evaluation fixture content enters runtime.
    for r in json.loads((P/'preview-baseline.json').read_text())['results']:
        row=r['request'];target=P/'preview-new'/f'{recipe}-{row["sha256"]}.json'
        if target.exists():snapshot=json.loads(target.read_text())
        else:
            class NoOCR:
                warnings=[]
                def read(self,image,bounds,*a,**kw):
                    from models import Observation
                    return Observation(region=bounds)
            old_ocr=recognizer.ocr;recognizer.ocr=NoOCR()
            snap=recognizer.recognize(Frame(cv2.imread(str(ROOT/row['image'])),row['source_id'],0,row['timestamp'],row))
            recognizer.ocr=old_ocr;snapshot=snap.to_dict()
            atomic_json(target,snapshot)
        from models import Recognition,Pokemon,IconEvidence,IconCandidate
        opponent=[]
        for mon in snapshot['pokemon']:
            if not mon['slot'].startswith('opponent_team_'):continue
            ic=mon['icon'];icon=IconEvidence(**{**ic,'candidates':[IconCandidate(**c) for c in ic['candidates']]})
            opponent.append(Pokemon(mon['slot'],icon=icon))
        snap=Recognition(row['source_id'],0,row['timestamp'],pokemon=opponent,capture_metadata=row)
        roster=preview_rows(snap,'sample_battle_5');recognizer.context.preview_observations+=roster
    output=[]
    for i,row in enumerate(rows):
        target=P/'observations'/f'{recipe}-{row["sha256"]}.json'
        image=cv2.imread(str(ROOT/row['image']))
        if target.exists():result=json.loads(target.read_text())
        else:
            snap=recognize_hud(recognizer,Frame(image,row['source_id'],i,row['timestamp'],row))
            # Message eligibility is separate: sample every acquired frame, with
            # exact pixel cache reuse. No sparse HUD anchors or label scheduling.
            from recognition import box
            reading=cache.read(image,box(image,ROI),multiline=True)
            result=dict(**row,snapshot=snap.to_dict(),message=asdict(reading),
                scheduling=dict(candidate_cards=len(hud_cards(image)),scheduled_cards=len(snap.pokemon)))
            atomic_json(target,result)
        windows=entries.observe(result['message'].get('raw_text',''),row['timestamp'],row['source_id'])
        entries.seen_hud(row['timestamp'],result['scheduling']['scheduled_cards']);result['entry_windows']=windows
        output.append(result)
        atomic_json(P/f'{split}-recognition-progress.json',dict(status='partial',complete=len(output),total=len(rows),
            recipe=recipe,new_ocr_files=len(list((P/'reads').glob('*.json'))),cache_hits=cache.hits))
        if i%8==0:print(split,len(output),'/',len(rows),'new OCR',len(list((P/'reads').glob('*.json'))),flush=True)
    atomic_json(P/f'{split}-observations.json',dict(recipe=recipe,status='complete',observations=output,
        roster=recognizer.context.preview_observations,entry_windows=entries.windows,ocr_cache_hits=cache.hits,icon_cache_hits=icons.hits))
    atomic_json(P/f'{split}-recognition-progress.json',dict(status='complete',complete=len(output),total=len(rows),
        recipe=recipe,new_ocr_files=len(list((P/'reads').glob('*.json'))),cache_hits=cache.hits))


def freeze():
    code={str(f.relative_to(ROOT)):sha(f) for d in ['recognition','tracking','battle_events','models'] for f in (ROOT/d).glob('*.py')}
    target=P/'implementation-seal.json'
    seal=dict(code=code,runner=sha(__file__),fixture=sha(ROOT/'tests/fixtures/battles/m236_review.json'),
        evaluator=sha(ROOT/'scripts/evaluate_m236.py'),status='frozen_before_final_held_out')
    if target.exists():assert json.loads(target.read_text())==seal,'Do not overwrite an implementation seal'
    else:atomic_json(target,seal)


def preview_baseline():
    import cv2
    from models import Observation,IconEvidence
    from recognition import Recognizer
    from recognition.icons import IconRecognizer
    from capture import Frame
    seal=json.loads((P/'initial-seal.json').read_text());assert all(sha(ROOT/k)==v for k,v in seal['code'].items()),'Freeze existing preview before edits'
    rows=json.loads((OLD/'survey.json').read_text())['frames'];rows=[r for r in rows if r['target_timestamp'] in [40,60,80,100]]
    class NoOCR:
        warnings=[]
        def read(self,image,bounds,*a,**kw):return Observation(region=bounds)
    class OpponentIcons(IconRecognizer):
        def identify(self,image,region):
            if region[0]<image.shape[1]/2:return IconEvidence(region=region,reason='own_icons_out_of_scope')
            return super().identify(image,region)
    recognizer=Recognizer(NoOCR(),icons=OpponentIcons());output=[];started=time.monotonic()
    for i,row in enumerate(rows):
        target=P/'preview-baseline'/f'{row["sha256"]}.json'
        if target.exists():result=json.loads(target.read_text())
        else:
            snap=recognizer.recognize(Frame(cv2.imread(str(ROOT/row['image'])),row['source_id'],i,row['timestamp'],row)).to_dict()
            result=dict(request=row,opponent=[m for m in snap['pokemon'] if m['slot'].startswith('opponent_team_')],propagated_roster_candidates=sorted(recognizer.context.opponent_preview),screen=snap['screen'])
            atomic_json(target,result)
        output.append(result);atomic_json(P/'preview-baseline-progress.json',dict(status='partial',completed=len(output),total=4,icon_opportunities=len(output)*6,new_ocr=0));print('Existing preview',len(output),'/4',flush=True)
    result=dict(status='complete',method='existing Recognizer + default independent IconRecognizer; opponent icons only, OCR disabled',code=seal['code'],results=output,icon_opportunities=24,new_ocr=0,seconds=time.monotonic()-started)
    atomic_json(P/'preview-baseline.json',result)
    for r in output:print(r['request']['timestamp'],[(m['icon']['status'],[(c['species_id'],c['similarity']) for c in m['icon']['candidates'][:2]]) for m in r['opponent']])


def acquisition():
    plan=json.loads((P/'plan.json').read_text());media=json.loads((OLD/'media.json').read_text());frames=[]
    for split,windows in [('development',plan['evaluation_plan']['development_windows']),('held_out',[plan['evaluation_plan']['held_out_continuous_window']])]:
        for start,end in windows:
            result=acquire(ScopedArtifacts('sample_battle_5',ROOT),media['identity'],SamplingConfig(plan['sample_fps']),start,end)
            frames += [dict(r,split=split,window=[start,end]) for r in result]
    atomic_json(P/'evaluation-acquisition.json',dict(status='complete',frames=frames,video_identity=media['identity'],sample_fps=plan['sample_fps']))


def review_sheets():
    import cv2,numpy as np
    rows=json.loads((P/'evaluation-acquisition.json').read_text())['frames']
    for split in ['development','held_out']:
        group=[r for r in rows if r['split']==split]
        for offset in range(0,len(group),12):
            page=group[offset:offset+12];sheet=np.full((4*320,3*660,3),240,np.uint8)
            for j,r in enumerate(page):
                im=cv2.resize(cv2.imread(str(ROOT/r['image'])),(660,304));x=j%3*660;y=j//3*320;sheet[y:y+304,x:x+660]=im;cv2.putText(sheet,f'{r["target_timestamp"]:.1f}s {r["timestamp"]:.6f}',(x+4,y+318),cv2.FONT_HERSHEY_SIMPLEX,.44,(0,0,0),1)
            target=P/'review-sheets'/f'{split}-{offset//12}.jpg';target.parent.mkdir(parents=True,exist_ok=True);cv2.imwrite(str(target),sheet)
    print('Review contact sheets ready; no OCR or recognition',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['preview-baseline','acquire','review-sheets','development','held_out','freeze'],required=True);args=parser.parse_args();P.mkdir(parents=True,exist_ok=True)
    manifest=P/'stages'/f'{args.stage}.json';atomic_json(manifest,dict(status='running',runner_sha256=sha(__file__)))
    try:
        {'preview-baseline':preview_baseline,'acquire':acquisition,'review-sheets':review_sheets,'development':lambda:recognize_stage('development'),'held_out':lambda:recognize_stage('held_out'),'freeze':freeze}[args.stage]()
        atomic_json(manifest,dict(status='complete',runner_sha256=sha(__file__)))
    except Exception as exc:
        atomic_json(manifest,dict(status='error',error=repr(exc),resume=f'.venv/bin/python scripts/process_m236.py --stage {args.stage}'));raise
