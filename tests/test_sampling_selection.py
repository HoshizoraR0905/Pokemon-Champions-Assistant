"""Portable timestamp, cache, selection, and scoped-resume regression tests."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np
import pytest
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import SamplingConfig,acquire
from recognition.message_selection import SelectionConfig,MessageSelector
from scripts.validate_m233b1 import battle_lock


def test_fractional_grid_and_segment_boundaries():
    c=SamplingConfig(3)
    whole=c.targets(0,1.12)
    assert whole==[0,1/3,2/3,1]
    assert c.targets(0,.5)+c.targets(.5,1.12)==whole
    assert len(set(whole))==len(whole)
    assert SamplingConfig().sample_fps==2
    assert SamplingConfig(2.5).targets(0,1)==[0,.4,.8]
    assert c.targets(.2,.3)==[]


@pytest.mark.parametrize('fps',[0,-1,float('nan'),float('inf')])
def test_invalid_sampling(fps):
    with pytest.raises(ValueError):SamplingConfig(fps)


def test_fingerprints_separate_sampling_selection_and_source():
    source=dict(sha256='source',size=100)
    assert SamplingConfig(2).identity(source)!=SamplingConfig(3).identity(source)
    assert SamplingConfig(2).identity(source)!=SamplingConfig(2).identity(dict(source,size=101))
    c=SelectionConfig()
    assert c.fingerprint!=replace(c,stroke_value=130).fingerprint
    assert c.fingerprint!=replace(c,policy='reduced').fingerprint
    assert SamplingConfig().identity(source)==SamplingConfig().identity(source)


def message_image():
    im=np.zeros((603,1311,3),np.uint8)
    cv2.putText(im,'MOVE USED!',(292,436),cv2.FONT_HERSHEY_SIMPLEX,.7,(180,180,180),1,cv2.LINE_AA)
    return im


def test_faint_text_without_eight_bright_contours_and_repeat_suppression():
    im=message_image();selector=MessageSelector()
    first=selector.select(im,'battle_animation',timestamp=100)
    assert first['glyphs']==0
    assert first['selected']
    assert not selector.select(im,'battle_animation',timestamp=100.5)['selected']
    assert not MessageSelector().select(im,'move_selection',timestamp=100)['selected']
    assert not MessageSelector().select(im,'battle_animation',timestamp=100,log_visible=True)['selected']


def test_empty_region_and_temporal_bootstrap_are_distinct():
    im=np.zeros((603,1311,3),np.uint8)
    assert not MessageSelector().select(im,'battle_animation',timestamp=100)['selected']
    selector=MessageSelector(SelectionConfig(policy='temporal'))
    assert selector.select(im,'battle_animation',timestamp=100)['selected']
    assert not selector.select(im,'battle_animation',timestamp=100.5)['selected']


def test_per_battle_lock_rejects_duplicate_process_owner(tmp_path):
    paths=BattleArtifacts('test',root=tmp_path)
    with battle_lock(paths):
        with pytest.raises(RuntimeError):
            with battle_lock(paths):pass
    with battle_lock(paths):pass


def test_real_short_sampling_partial_tail_and_resume(tmp_path,monkeypatch):
    imageio_ffmpeg=pytest.importorskip("imageio_ffmpeg")
    paths=BattleArtifacts('test',root=tmp_path);video=tmp_path/'tests/fixtures/test.mp4';video.parent.mkdir(parents=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-f','lavfi','-i','color=c=black:s=64x32:r=10:d=1.1',
        '-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    identity=dict(path='tests/fixtures/test.mp4',metadata=dict(duration_seconds=1.1,fps=10,frame_count=11))
    calls=[];real=subprocess.run
    def counted(command,**kwargs):
        calls.append(command)
        assert command.index('-t')<command.index('-i')  # Input duration bounds decoding even if selection emits no final frame.
        return real(command,**kwargs)
    monkeypatch.setattr('recognition.video_sampling.subprocess.run',counted)
    rows=acquire(paths,identity,SamplingConfig(3,64),0,1.1,chunk_seconds=1)
    assert [round(r['target_timestamp'],6) for r in rows]==[0,.333333,.666667,1]
    assert [round(r['timestamp'],3) for r in rows]==[0,.4,.7,1]
    assert len({r['timestamp'] for r in rows})==4
    first_calls=len(calls)
    assert acquire(paths,identity,SamplingConfig(3,64),0,1.1,chunk_seconds=1)==rows
    assert len(calls)==first_calls
    # Corrupting one chunk invalidates only that chunk; successful other chunks survive.
    (tmp_path/rows[-1]['image']).write_bytes(b'corrupt')
    repaired=acquire(paths,identity,SamplingConfig(3,64),0,1.1,chunk_seconds=1)
    assert len(calls)==first_calls+1 and repaired==rows


def test_cross_fps_reuses_source_grid_intersections(tmp_path,monkeypatch):
    imageio_ffmpeg=pytest.importorskip("imageio_ffmpeg")
    paths=BattleArtifacts('test',root=tmp_path);video=tmp_path/'tests/fixtures/test.mp4';video.parent.mkdir(parents=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-f','lavfi','-i','color=c=black:s=64x32:r=10:d=1.1',
        '-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    identity=dict(path='tests/fixtures/test.mp4',metadata=dict(duration_seconds=1.1,fps=10,frame_count=11))
    first=acquire(paths,identity,SamplingConfig(2,64),0,1.1)
    second=acquire(paths,identity,SamplingConfig(3,64),0,1.1)
    assert second[0]['image']==first[0]['image']
    assert second[-1]['image']==first[-1]['image']
    assert second[0]['reused_from']=='compatible_b1_sampling'


def test_raw_ocr_cache_is_independent_of_schedule_and_downstream_replay(tmp_path):
    from scripts.validate_m233b1 import CachedMessageOCR
    from types import SimpleNamespace
    ocr=object.__new__(CachedMessageOCR)
    ocr.paths=BattleArtifacts('test',root=tmp_path);ocr.identity={'video':'test'};ocr.identity_hash='model-v1';ocr.legacy={}
    ocr.counts=dict(new_read_calls=0,cache_hits=0,legacy_hits=0,inference_seconds=0.)
    class FakeBackend:
        def read(self,image,bounds,**kwargs):
            return SimpleNamespace(raw_text='test message',confidence=.99)
    ocr.backend=FakeBackend()
    image=message_image();first,_=ocr.read({'sha256':'source','timestamp':100},image)
    again,reuse=ocr.read({'sha256':'different-encoding','timestamp':101},image)
    assert first==again and reuse=='b1_cache' and ocr.counts['new_read_calls']==1
    ocr.identity_hash='different-model-or-preprocessing'
    ocr.read({'sha256':'source','timestamp':100},image)
    assert ocr.counts['new_read_calls']==2
    ocr.identity={'video':'different-battle'}
    ocr.read({'sha256':'source','timestamp':100},image)
    assert ocr.counts['new_read_calls']==3


def test_selection_rejects_invalid_configuration():
    for options in [dict(stroke_value=-1),dict(maximum_gap=-1),dict(temporal_mae=-1),dict(repeat_similarity=0)]:
        with pytest.raises(ValueError):SelectionConfig(**options)


def test_completed_run_resume_and_configuration_invalidation(tmp_path,monkeypatch):
    import scripts.validate_m233b1 as pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    for name in ['recognition/phases.py','recognition/__init__.py','recognition/message_selection.py']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test configuration')
    monkeypatch.setattr(pipeline,'source_identity',lambda paths:dict(video='source'))
    calls=[]
    monkeypatch.setattr(pipeline,'acquire',lambda *args,**kwargs:calls.append(args) or [])
    paths=BattleArtifacts('test',root=tmp_path)
    pipeline.run(paths,SamplingConfig(2),0,1,SelectionConfig(),'select')
    cached=pipeline.run(paths,SamplingConfig(2.),0.,1.,SelectionConfig(),'select')
    assert cached['reused_complete_run'] and len(calls)==1
    pipeline.run(paths,SamplingConfig(3),0,1,SelectionConfig(),'select')
    assert len(calls)==2
    pipeline.run(paths,SamplingConfig(3),0,1,SelectionConfig(policy='reduced'),'select')
    assert len(calls)==3


_DIAGNOSTIC=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/battles/m233b1_selection_diagnostics.json').read_text())['frames']
@pytest.mark.local_artifacts(*(r['image'] for r in _DIAGNOSTIC))
def test_known_misses_and_control_images_are_selection_regressions_only():
    root=Path(__file__).resolve().parents[1];positive=negative=0
    for row in _DIAGNOSTIC:
        image=cv2.imread(str(root/row['image']))
        decision=MessageSelector().select(image,row['phase'],timestamp=row['timestamp'])
        if row['label']=='visible_message':
            assert decision['selected'];positive+=1
        elif row['label']=='no_message':
            assert not decision['selected'];negative+=1
    assert (positive,negative)==(17,34)


def test_vfr_empty_grid_cells_do_not_cause_catchup_or_duplicate_samples(tmp_path):
    imageio_ffmpeg=pytest.importorskip('imageio_ffmpeg')
    paths=BattleArtifacts('test',root=tmp_path);video=tmp_path/'tests/fixtures/test.mp4';video.parent.mkdir(parents=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-f','lavfi','-i','color=c=black:s=64x32:r=10:d=1.1',
        '-vf',"select='eq(n,0)+eq(n,1)+eq(n,8)+eq(n,10)'",'-fps_mode','vfr','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    identity=dict(path='tests/fixtures/test.mp4',metadata=dict(duration_seconds=1.1,fps=4/1.1,frame_count=4))
    rows=acquire(paths,identity,SamplingConfig(3,64),0,1.1)
    assert [round(r['timestamp'],2) for r in rows]==[0,.8,1]
    assert [round(r['target_timestamp'],6) for r in rows]==[0,.666667,1]
    manifests=list(paths.cache('m233b1/sampling').glob('*/*/frames.json'))
    assert json.loads(manifests[0].read_text())['missing_target_cells']==[1/3]


def test_repeat_suppression_expires_and_resets_between_message_occurrences():
    image=message_image();blank=np.zeros_like(image);selector=MessageSelector()
    assert selector.select(image,'battle_animation',timestamp=100)['selected']
    assert not selector.select(image,'battle_animation',timestamp=100.5)['selected']
    assert selector.select(image,'battle_animation',timestamp=103)['selected']
    assert not selector.select(blank,'battle_animation',timestamp=103.2)['selected']
    assert selector.select(image,'battle_animation',timestamp=103.5)['selected']


def test_integer_pts_preserves_third_second_boundary_despite_rounded_log():
    from fractions import Fraction
    from recognition.video_sampling import selected_pts
    log='config in time_base: 1/600, frame_rate: 60/1\nn: 0 pts: 5600 pts_time:9.33333 duration:10'
    ticks,base=selected_pts(log)[0]
    assert ticks*base==Fraction(28,3)
    assert (ticks*base*3).denominator==1


def test_source_identity_supports_new_recordings_and_rejects_stale_legacy(tmp_path,monkeypatch):
    from scripts.validate_m233b1 import source_identity
    paths=BattleArtifacts('test',root=tmp_path);video=tmp_path/'tests/fixtures/test.mp4';video.parent.mkdir(parents=True);video.write_bytes(b'fixture')
    expected=dict(sampled_sha256='fingerprint',metadata={'duration_seconds':1})
    monkeypatch.setattr('scripts.validate_m232.video_identity',lambda path:expected)
    assert source_identity(paths)==expected
    survey=paths.cache('m232/survey.json');survey.parent.mkdir(parents=True);survey.write_text(json.dumps({'video_fingerprint':{'sampled_sha256':'stale'}}))
    with pytest.raises(ValueError):source_identity(paths)
    assert json.loads(survey.read_text())['video_fingerprint']['sampled_sha256']=='stale'
