"""Portable safety regressions for adaptive region-driven recognition."""
import numpy as np
from recognition.experimental import AdaptiveInspection
from recognition.fast_profile import RegionGate
from recognition.fast_report import compare_receipts,compare_occurrences


def test_inspection_rates_and_transition_boost_have_no_blackout():
    s=AdaptiveInspection()
    assert s.advance(0,phase='move_selection',message_visible=False,changed=False)==1
    assert not s.due(.5) and s.due(1)
    assert s.advance(1,phase='battle_animation',message_visible=False,changed=True)==2
    assert s.due(1.5)
    assert s.advance(3,phase='battle_animation',message_visible=False,changed=False)==1
    assert s.advance(4,phase='unknown',message_visible=False,changed=False)==2
    assert s.advance(5,phase='move_selection',message_visible=True,changed=False)==2


def test_region_reuse_retains_first_source_and_disappearance_allows_identical_new_occurrence():
    g=RegionGate();sig=np.zeros((24,128),np.uint8)
    assert g.choose('message',sig,True,0)[:2]==(True,'newly_visible')
    g.store('message',sig,0,{'text':'same'},'video#0')
    selected,reason,old=g.choose('message',sig,True,1)
    assert not selected and reason=='unchanged_region'
    assert old['timestamp']==0 and old['source_id']=='video#0'
    assert g.choose('message',sig,False,2)[0] is False
    assert g.choose('message',sig,True,3)[:2]==(True,'newly_visible')


def test_unreliable_retry_is_bounded_but_changed_crop_is_always_eligible():
    g=RegionGate();sig=np.zeros((24,128),np.uint8)
    g.store('message',sig,0,'bad','a',False)
    assert g.choose('message',sig,True,1)[1]=='retry_unreliable'
    g.store('message',sig,1,'bad','b',False)
    assert g.choose('message',sig,True,2)[1]=='unchanged_region'
    assert g.choose('message',sig+100,True,3)[1]=='changed_region'


def test_regions_are_independent_and_later_observations_do_not_mutate_earlier_reading():
    g=RegionGate();sig=np.zeros((24,128),np.uint8);value={'text':'first'}
    g.store('message',sig,0,value,'a');g.store('hud',sig,0,'hp','a')
    value['text']='mutated'
    g.choose('menu',sig,False,1)
    assert g.choose('message',sig,True,1)[2]['value']['text']=='first'
    assert g.choose('hud',sig+100,True,1)[1]=='changed_region'
    assert g.choose('message',sig,True,1)[1]=='unchanged_region'


def receipt(id,t,move='protect'):
    return dict(id=id,timestamp=t,kind='move_execution',raw_text='Actor used '+move,admitted=True,
                actor={'species_id':1},target=None,references={'move':{'canonical_id':move}})


def test_comparison_cannot_reuse_one_fast_event_or_match_other_move_or_actor():
    b=[receipt('a',1),receipt('b',1.5),receipt('c',3,'tailwind')]
    f=[receipt('x',1.1),receipt('y',3,'tailwind')];f[1]['actor']={'species_id':2}
    d=compare_receipts(b,f)
    assert len(d['pairs'])==1 and len(d['baseline_only'])==2
    assert all(not r['is_ground_truth_miss'] for r in d['baseline_only'])


def test_occurrence_alignment_requires_literal_overlap_not_just_a_nearby_timestamp():
    def occ(id,t,text):return dict(id=id,first_time=t,last_time=t+.5,observations=[dict(raw_text=text,confidence=.99)])
    result=compare_occurrences([occ('a',1,'protect'),occ('b',4,'protect')],[occ('x',1,'protect'),occ('y',4,'weather ball')])
    assert [r['status'] for r in result['baseline_comparisons']]==['aligned_candidate','baseline_only_message_evidence']


def test_one_character_change_is_not_hidden_by_empty_region_background():
    import cv2
    from recognition.fast_profile import normalized
    images=[]
    for word in ['ACTOR used MOVE A','ACTOR used MOVE B']:
        image=np.zeros((80,600,3),np.uint8)
        cv2.putText(image,word,(10,30),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),1)
        images.append(normalized(image,(0,0,600,80),text=True))
    g=RegionGate(.015);g.store('message',images[0],0,'MOVE A','a')
    assert g.choose('message',images[1],True,.5)[:2]==(True,'changed_region')


def test_hud_detection_remains_active_when_menu_classifier_is_present(monkeypatch):
    import recognition.fast_profile as fast
    image=np.zeros((603,1311,3),np.uint8)
    monkeypatch.setattr(fast,'color_fraction',lambda *a:.5)
    # Empty bars and qualifying name panels are the established independent
    # visibility contract; no call to the global screen classifier is required.
    assert len(fast.independent_cards(image))==4


def test_ocr_adapter_accepts_existing_recognizer_positional_arguments():
    from collections import Counter
    from models import Observation
    from recognition.fast_video import CachedOCR
    class Backend:
        def read(self,image,bounds,**kwargs):
            assert kwargs==dict(numeric=True,multiline=False,italic=True)
            return Observation('123',.99,bounds,'123')
    ocr=CachedOCR.__new__(CachedOCR);ocr.backend=Backend();ocr.counts=Counter()
    ocr.gate=RegionGate(.004);ocr.read_costs={};ocr.timestamp=0;ocr.source='frame';ocr.reuses=[]
    obs=ocr.read(np.zeros((20,20,3),np.uint8),(0,0,20,20),True,False,italic=True)
    assert obs.raw_text=='123'
    assert ocr.read(np.zeros((20,20,3),np.uint8),(0,0,20,20),True,False,italic=True).raw_text=='123'
    assert ocr.counts['ocr_region_reads_reused']==1
