"""Freeze manually transcribed text and icon labels for the supplied captures.

Run only when intentionally updating the benchmark. The runtime code never imports this.
"""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capture import load_image
from recognition import Recognizer

ROOT=Path('tests/fixtures')
NAMES=['暴飞龙','班基拉斯','钢铠鸦','龙头地鼠','爱管侍','大狃拉']
OWN_IDS=[373,248,823,530,876,903]
PREVIEW_OPP=[376,1018,208,1000,212,395]
VIDEO_OPP=[354,1019,637,981,553,691]
ABILITIES=['威吓','扬沙','镜甲','拔沙','精神制造者','轻装']
ITEMS=['暴飞龙进化石','班基拉斯进化石','精神种子','气势披带','讲究围巾','白色香草']
MOVES=[['巨声','流星群','喷射火焰','守住'],
       ['岩崩','拍落','踢倒','守住'],
       ['勇鸟猛攻','嚣张','健美','羽栖'],
       ['十万马力','岩崩','铁头','守住'],
       ['广域战力','魔法火焰','戏法','守住'],
       ['克命爪','近身战','指导','守住']]
STATS=[[172,139,100,162,100,167],
       [177,186,130,103,120,124],
       [173,139,125,65,117,119],
       [185,205,81,63,86,140],
       [137,76,75,172,115,147],
       [157,200,80,54,100,172]]
STAT_KEYS=['hp','attack','defense','special_attack','special_defense','speed']
records=[]
def add(image,region,kind,expected,*,species_id=None,form_id=None,split='development'):
    records.append({'image':image,'region':region,'kind':kind,'expected':expected,
                    'species_id':species_id,'form_id':form_id,'split':split})
for image,split in [('team_preview.png','development'),('team_configuration_moves.png','development'),
                    ('team_configuration_stats.png','development'),('m12_video_stats.png','held_out_video')]:
    for n,(name,sid) in enumerate(zip(NAMES,OWN_IDS)):
        row,col=divmod(n,2)
        region=(f'team_name_{n}' if image=='team_preview.png' else f'config_name_{row}_{col}')
        add(image,region,'species_text',name,species_id=sid,form_id=876 if sid==876 else None,split=split)
        if image=='team_preview.png':
            add(image,f'own_icon_{n}','icon',sid,species_id=sid,form_id=876 if sid==876 else None,split=split)
        else:
            add(image,f'config_icon_{row}_{col}','icon',sid,species_id=sid,form_id=876 if sid==876 else None,split=split)
        if image=='team_configuration_moves.png':
            add(image,f'ability_{row}_{col}','ability',ABILITIES[n],split=split)
            add(image,f'item_{row}_{col}','item',ITEMS[n],split=split)
            for j,m in enumerate(MOVES[n]):
                add(image,f'config_move_{row}_{col}_{j}','move',m,split=split)
        elif image in ('team_configuration_stats.png','m12_video_stats.png'):
            for j,(key,value) in enumerate(zip(STAT_KEYS,STATS[n])):
                add(image,f'config_{row}_{col}_{key}','numeric',str(value),split=split)
for image,ids,split in [('team_preview.png',PREVIEW_OPP,'development'),
                        ('m12_video_preview.png',VIDEO_OPP,'held_out_video')]:
    for i,sid in enumerate(ids):
        add(image,f'opponent_icon_{i}','icon',sid,species_id=sid,split=split)
for image,ids,split in [('battle_screen.png',[530,903,376,1000],'held_out_screenshot'),
                        ('move_selection.png',[876,823,36,497],'held_out_screenshot')]:
    for i,sid in enumerate(ids):
        side='own' if i<2 else 'opponent';j=i if i<2 else i-2
        expected={530:'龙头地鼠',903:'大狃拉',376:'巨金怪',1000:'赛富豪',876:'爱管侍',823:'钢铠鸦',36:'皮可西',497:'君主蛇'}[sid]
        add(image,f'{side}_name_{j}','species_text',expected,species_id=sid,split=split)
        add(image,f'{side}_icon_{j}','icon',sid,species_id=sid,split=split)
for j,m in enumerate(['广域战力','魔法火焰','戏法','守住']):
    add('move_selection.png',f'move_name_{j}','move',m,split='held_out_screenshot')
for image,values in [('battle_screen.png',['185','185','157','157']),
                     ('move_selection.png',['137','137','173','173'])]:
    for j,v in enumerate(values):
        add(image,['own_hp_0_current','own_hp_0_maximum','own_hp_1_current','own_hp_1_maximum'][j],
            'numeric',v,split='held_out_screenshot')

class NoOCR:
    warnings=[]
    def read(self,image,box,numeric=False,multiline=False,italic=False):
        from models import Observation
        return Observation(region=box)

recognizer=Recognizer(NoOCR(),icons=False)
images={}
for image in sorted({r['image'] for r in records}):
    path=ROOT/image
    result=recognizer.recognize(load_image(path))
    images[image]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                   'screen':result.screen,'source':'supplied screenshot' if not image.startswith('m12_video_') else 'sample_battle.mp4',
                   'video_second':15 if image=='m12_video_stats.png' else 60 if image=='m12_video_preview.png' else None}
    for r in records:
        if r['image']==image:
            if r['region'] not in result.regions:raise ValueError((image,r['region']))
            r['box']=result.regions[r['region']]
write={'schema_version':1,'annotation':'Manual visual transcription; see report for split limitations',
       'images':images,'regions':records}
Path('tests/fixtures/m12_ground_truth.json').write_text(json.dumps(write,ensure_ascii=False,indent=2)+'\n')
print('Annotated',len(records),'regions in',len(images),'images')
