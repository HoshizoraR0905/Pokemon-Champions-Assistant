"""Prediction-blind chronological source-frame sheets for agent/human review."""
from pathlib import Path
import argparse
import html
import json
import time
import cv2
import numpy as np
from battle_artifacts import BattleArtifacts
from speed_inference.offline import RUNS,atomic_json,file_hash


def source_rows(number):
    battle=BattleArtifacts(f'sample_battle_{number}',Path.cwd())
    run='m238-live-1' if number==6 else RUNS[number]
    source=battle.cache(f'event-driven/{run}/observations.json')
    data=json.loads(source.read_text());battle.check_identity(data['battle_id'])
    return battle,source,data['observations']


def prepare(number,*,step=5,start=0,end=None,tag='chronological'):
    started=time.perf_counter();battle,source,rows=source_rows(number)
    end=rows[-1]['timestamp'] if end is None else min(end,rows[-1]['timestamp'])
    chosen={};t=start
    while t<=end:
        row=min(rows,key=lambda r:abs(r['timestamp']-t));chosen[row['source_id']]=row;t+=step
    for t in (start,end):
        row=min(rows,key=lambda r:abs(r['timestamp']-t));chosen[row['source_id']]=row
    selected=sorted(chosen.values(),key=lambda r:r['timestamp'])
    directory=battle.cache(f'm34-visual-review/{tag}-{start:g}-{end:g}-step{step:g}');directory.mkdir(parents=True,exist_ok=True)
    manifest=battle.guard_output(directory/'manifest.json')
    identity=dict(source=str(source),sha256=file_hash(source),step=step,start=start,end=end,
        reader=file_hash(Path(__file__)),policy='fixed chronological sampling; no predictions, UI classifications, event ledger, counters or prior turn boundaries used for selection')
    if manifest.exists():
        saved=json.loads(manifest.read_text())
        if saved.get('identity')==identity and saved.get('status')=='complete':return saved
    atomic_json(manifest,dict(identity=identity,status='running'))
    refs=[];sheets=[];cells=[]
    for i,row in enumerate(selected):
        im=cv2.imread(row['image'])
        if im is None:raise FileNotFoundError(row['image'])
        cell=np.zeros((178,336,3),np.uint8);cell[:154]=cv2.resize(im,(336,154))
        cv2.putText(cell,f'{i:03}  {row["timestamp"]:.3f}s  {Path(row["image"]).stem}',(4,171),cv2.FONT_HERSHEY_SIMPLEX,.45,(255,255,255),1)
        cells.append(cell);refs.append(dict(index=i,timestamp=row['timestamp'],image=row['image'],source_id=row['source_id'],image_sha256=file_hash(Path(row['image']))))
        if len(cells)==32 or i==len(selected)-1:
            while len(cells)%4:cells.append(np.zeros_like(cell))
            sheet=np.vstack([np.hstack(cells[k:k+4]) for k in range(0,len(cells),4)])
            path=battle.guard_output(directory/f'sheet-{len(sheets):02}.jpg');cv2.imwrite(str(path),sheet,[cv2.IMWRITE_JPEG_QUALITY,88]);sheets.append(str(path));cells=[]
            atomic_json(manifest,dict(identity=identity,status='running',frames_read=len(refs),sheets=sheets))
    links=['<!doctype html><meta charset="utf-8"><title>Chronological source review</title>',
        '<style>body{background:#151515;color:#eee;font:16px system-ui}a{color:#9cf}img{max-width:100%}details{margin:1em}</style>',
        f'<h1>{battle.battle_id}: prediction-blind chronological review</h1><p>Agent review proposed; human approval pending. Labels are not detector predictions. Click timestamps for original PNGs.</p>']
    for sheet in sheets:links.append(f'<img loading="lazy" src="{html.escape(Path(sheet).name)}">')
    for ref in refs:
        rel=__import__('os').path.relpath(Path(ref['image']).absolute(),directory)
        links.append(f'<a href="{html.escape(rel)}">{ref["timestamp"]:.3f}s</a> · ')
    battle.guard_output(directory/'index.html').write_text('\n'.join(links))
    result=dict(identity=identity,status='complete',battle_id=battle.battle_id,frames=refs,sheets=sheets,
        seconds=time.perf_counter()-started,new_video_decodes=0,new_OCR=0,index=str(directory/'index.html'))
    atomic_json(manifest,result);print(json.dumps(dict(battle_id=battle.battle_id,frames=len(refs),sheets=sheets,seconds=result['seconds'])),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',required=True,type=int,choices=range(5,10));p.add_argument('--step',type=float,default=5);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float);p.add_argument('--tag',default='chronological');a=p.parse_args()
    if a.step<=0:raise ValueError('step must be positive')
    prepare(a.battle,step=a.step,start=a.start,end=a.end,tag=a.tag)
