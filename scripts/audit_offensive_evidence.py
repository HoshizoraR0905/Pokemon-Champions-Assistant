"""Prepare one battle's source review queue from sealed caches, without OCR."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from battle_evidence.action_offline import inputs_for
from battle_evidence.offensive import candidate_inventory
from battle_evidence.speed_replay_offline import atomic,digest,file_hash
from damage.selectors import select_stats
from speed_order.core import knowledge,name


def run(number,contact_sheets=False):
    battle=BattleArtifacts(f'sample_battle_{number}',ROOT)
    pointer=json.loads(battle.cache('m322-reviewed-speed/latest.json').read_text())
    source=Path(pointer['path']);seal=json.loads(source.with_name('manifest.json').read_text())
    if seal['status']!='complete' or seal['outputs']['replay.json']!=file_hash(source):
        raise ValueError('Sealed Speed replay required')
    replay=json.loads(source.read_text());_,states,raw,paths=inputs_for(battle)
    identity=dict(version='damage-review-queue-v1',inputs={str(p):file_hash(p) for p in [source,Path(__file__),*paths]})
    dest=battle.cache('m343-damage-review/'+digest(identity)[:16]);dest.mkdir(parents=True,exist_ok=True)
    manifest=dest/'manifest.json'
    atomic(manifest,dict(status='running',identity=identity,resume_command=f'.venv/bin/python scripts/audit_offensive_evidence.py --battle {number} --contact-sheets'))
    rows=candidate_inventory(replay,states)
    for i,row in enumerate(rows):
        fact=knowledge().facts['moves'][row['move']];t=row['timestamp']
        row.update(category=fact['category'],selector=select_stats(name(row['move'],'move'),fact['category']),
                   move_name=name(row['move'],'move'),review_status='not_reviewed')
        times=[t-2,t,t+2,t+4,t+6,t+8,t+12,t+18]
        for c in row['hp_candidates']:times.extend([c['pre']['timestamp'],c['post']['timestamp']])
        frames={f['source_id']:f for target in times for f in [min(replay['frames'],key=lambda f:abs(f['timestamp']-target))]}
        row['inspection_frames']=sorted(frames.values(),key=lambda f:f['timestamp'])
        row['nearby_messages']=[]
        for event in raw.values():
            ts=[s.get('details',{}).get('timestamp') for s in event.get('evidence',[])]
            ts=[v for v in ts if v is not None]
            if ts and t-40<=min(ts)<=t+20 and event.get('original_text'):
                row['nearby_messages'].append(dict(id=event['event_id'],timestamp=min(ts),text=event['original_text']))
        row['priority']=('special_exact_candidate' if row['category']=='Special' and row['hp_candidates'] else
                         'physical_exact_candidate' if row['hp_candidates'] else 'no_temporal_HP_pair')
        if contact_sheets:
            from PIL import Image,ImageDraw
            frames=row['inspection_frames'];height=((len(frames)+1)//2)*328
            canvas=Image.new('RGB',(1312,height),'#151a22');draw=ImageDraw.Draw(canvas)
            for j,f in enumerate(frames):
                with Image.open(ROOT/f['image']) as im:
                    im.thumbnail((656,304));x=j%2*656;y=j//2*328;canvas.paste(im,(x,y+24))
                draw.text((x+5,y+5),f"B{number} {f['timestamp']:.3f}s {Path(f['image']).name}",fill='white')
            path=dest/f'action-{i+1:02d}.png';canvas.save(path);row['contact_sheet']=str(path.relative_to(ROOT))
        atomic(dest/'queue.json',dict(battle_id=battle.battle_id,identity=identity,rows=rows[:i+1],complete=i+1==len(rows)))
        print(f'{battle.battle_id} {i+1}/{len(rows)} {row["move_name"]} {t:.3f}s',flush=True)
    atomic(manifest,dict(status='complete',identity=identity,outputs={'queue.json':file_hash(dest/'queue.json')},
                        video_decodes=0,ocr_calls=0,source_frames_modified=False))
    atomic(battle.cache('m343-damage-review/latest.json'),dict(path=str(dest/'queue.json')))
    print(dest,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--battle',type=int,required=True,choices=[10,11,12])
    p.add_argument('--contact-sheets',action='store_true');args=p.parse_args();run(args.battle,args.contact_sheets)
