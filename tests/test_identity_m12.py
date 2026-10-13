from pathlib import Path
import cv2
import numpy as np
import pytest
from capture import load_image
from knowledge import KnowledgeBase
from models import IconEvidence, Observation
from recognition.icons import DEFAULT_CACHE, IconRecognizer
from recognition.paddle_ocr import PaddleOCRBackend, model_path
from recognition.entities import EntityResolver
from recognition.identity import combine_identity


def test_raichu_and_alolan_raichu_source_reference_forms():
    if not (DEFAULT_CACHE/'index.json').exists():pytest.skip('Pinned local icon cache not installed')
    classifier=IconRecognizer()
    for file,sid,pid in [('raichu.png',26,26),('raichu-alola.png',26,10100),
                         ('charizard-mega-x.png',6,10034),('charizard-mega-y.png',6,10035),
                         ('indeedee.png',876,876),('indeedee-female.png',876,10186)]:
        rgba=cv2.imread(str(DEFAULT_CACHE/file),cv2.IMREAD_UNCHANGED)
        image=np.full((110,140,3),(130,78,95),np.uint8)
        sprite=cv2.resize(rgba,(85,85),interpolation=cv2.INTER_AREA)
        alpha=sprite[:,:,3:4]/255.0
        image[10:95,27:112]=(sprite[:,:,:3]*alpha+image[10:95,27:112]*(1-alpha)).astype('uint8')
        evidence=classifier.identify(image,(0,0,140,110))
        assert evidence.status=='resolved'
        assert (evidence.species_id,evidence.pokemon_id,evidence.form_id)==(sid,pid,None)
        assert evidence.canonical_identity==f'pokeapi:pokemon:{pid}'
        assert evidence.candidates[0].asset==file


def test_champions_preview_icon_only_real_capture():
    if not (DEFAULT_CACHE/'index.json').exists():pytest.skip('Pinned local icon cache not installed')
    from recognition import Recognizer
    class NoOCR:
        warnings=[]
        def read(self,image,box,numeric=False,multiline=False,italic=False):return Observation(region=box)
    result=Recognizer(NoOCR(),icons=IconRecognizer()).recognize(load_image(Path('tests/fixtures/team_preview.png')))
    opponent=[p for p in result.pokemon if p.slot.startswith('opponent_team_')]
    assert [p.species.resolution.species_id for p in opponent]==[376,1018,208,1000,212,395]


def test_multimodal_conflict_is_unresolved():
    kb=KnowledgeBase();resolver=EntityResolver(kb)
    text=resolver.resolve(Observation(None,.99,raw_text='赛富豪'),'species',region_kind='species')
    icon=IconEvidence(status='resolved',species_id=376,form_id=376,canonical_id='pokeapi:species:376')
    result=combine_identity(text,icon,kb)
    assert result.value is None
    assert result.resolution.status=='conflict'
    assert result.raw_text=='赛富豪'


def test_paddle_v6_reads_real_gholdengo_crop():
    if not (model_path()/'inference.json').exists():pytest.skip('PP-OCRv6 not installed')
    image=cv2.imread('tests/fixtures/battle_screen.png')
    h,w=image.shape[:2]
    box=tuple(round(v*(w if i%2==0 else h)) for i,v in enumerate((.79,.051,.888,.084)))
    result=PaddleOCRBackend().read(image,box,italic=True)
    assert result.raw_text=='赛富豪'
    assert result.raw_ocr.engine=='PP-OCRv6_medium_rec'


def test_identity_database_coverage_and_chinese_raichu():
    kb=KnowledgeBase()
    data=kb.identity
    assert data['coverage']['species']==1025
    assert data['coverage']['forms']==1579
    raichu=next(x for x in data['forms'] if x['source_form_id']==26)
    alolan=next(x for x in data['forms'] if x['source_form_id']==10202)
    assert raichu['species_names']['zh-hans']==alolan['species_names']['zh-hans']=='雷丘'
    assert alolan['names']['zh-hans']=='雷丘（阿罗拉的样子）'
    assert raichu['canonical_id']!=alolan['canonical_id']
    assert raichu['canonical_identity']=='pokeapi:pokemon:26'
    assert alolan['canonical_identity']=='pokeapi:pokemon:10100'
    assert len(alolan['visual_assets'])==1
    assert alolan['visual_assets'][0]['file']=='raichu-alola.png'
    assert 'champions_availability' in raichu and 'champions_availability' in alolan
    assert raichu['champions_availability']['legality']=='legal'
    assert alolan['champions_availability']['legality']=='legal'
