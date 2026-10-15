"""Scoped historical cache checks; never opens a historical video."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.process_m235 import CropCache,sha
from battle_artifacts import BattleArtifacts
from recognition.message_recovery import context_variants
from recognition.video_sampling import atomic_json,fingerprint
from recognition.visual_evidence import variants,normalized_box
from recognition.move_resolution import resolve_move
from knowledge import KnowledgeBase
import cv2,hashlib


def run(allow_new=False):
    original=json.loads((ROOT/'.cache/m234/visual-results.json').read_text())['results'];details=[];new=0
    for row in original:
        req=row['request']
        if req['kind']!='message':continue
        alts=[v for key,rs in row['readings'].items() if key!='line0' for v in rs]
        # Only unresolved exact-name candidates need a context-crop attempt.
        if not row['parsed'].get('canonical_id') and any(r.get('canonical_id') for r in row['parsed'].get('alternatives',[])):
            paths=BattleArtifacts(req['battle_id']);cache=CropCache(paths,0)
            image=cv2.imread(str(ROOT/req['image']));identity=row['identity']
            assert identity['backend']==cache.identity['backend'] and identity['model']==cache.identity['model']
            for rs in row['readings'].values():
                for r in rs:
                    crop=dict(variants(image,r['box']))[r['config_id'].rsplit(':',1)[1]]
                    key=fingerprint(dict(shape=list(crop.shape),pixels=hashlib.sha256(crop.tobytes()).hexdigest(),**cache.identity))
                    p=paths.cache('m235/reads/'+key+'.json')
                    if not p.exists():atomic_json(p,dict(text=r['text'],confidence=r['confidence']))
            existing=len(list(paths.cache('m235/reads').glob('*.json')))
            cache.budget=existing+(2 if allow_new else 0)
            for name,crop,bounds in context_variants(image,alts[0]['box'],normalized_box(image,(.22,.685,.64,.797))[2]):
                if not name.startswith('context_'):continue
                alts.append(dict(**cache.predict([crop])[0],box=bounds,config_id='line1:'+name,source_sha256=req['sha256']))
            new+=cache.new
        resolved=resolve_move(req.get('original_move_text',''),KnowledgeBase(),alts)
        details.append(dict(battle_id=req['battle_id'],timestamp=req['timestamp'],source_sha256=req['sha256'],before=row['parsed']['canonical_id'],after=resolved['canonical_id'],readings=resolved['alternatives']))
    # Check every earlier output, M3 and shared knowledge path before declaring preservation.
    saved=json.loads((ROOT/'.cache/battles/sample_battle_5/m235/prechange.json').read_text())['preserve']
    assert all(sha(ROOT/p)==h for p,h in saved.items()),'Historical output or M3/shared data changed'
    assert new<=2
    target=BattleArtifacts('sample_battle_5').cache('m235/history-check.json')
    result=dict(status='complete',preserved_files=len(saved),new_historical_predictions=new,details=details)
    atomic_json(target,result);print('Historical preservation',len(saved),'paths; new context predictions',new);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--allow-new-context',action='store_true');a=p.parse_args();run(a.allow_new_context)
