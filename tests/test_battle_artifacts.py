"""Organization must preserve identities and prevent cross-recording writes."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import subprocess
import sys
import pytest
from battle_artifacts import BattleArtifacts, canonical_id, manifest_battle, check_event_ownership
from tracking.battle_state import BattleState
from battle_events.schema import BattleEvent, Evidence, stable_id
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('bad',['../sample','a/b','a.mp4','', '/tmp/a'])
def test_invalid_namespace(bad):
    with pytest.raises(ValueError):BattleArtifacts(bad)

def test_resolution_and_input_selection(tmp_path):
    paths=BattleArtifacts.select(video='tests/fixtures/sample_battle_3.mp4',root=tmp_path)
    assert paths.cache('survey/frames.json')==tmp_path/'.cache/battles/sample_battle_3/survey/frames.json'
    assert paths.input('initial.json')==tmp_path/'reports/battles/sample_battle_3/inputs/initial.json'
    assert canonical_id('sample_battle')=='sample_battle_0'
    with pytest.raises(ValueError):BattleArtifacts.select('sample_battle_2','sample_battle_3.mp4',root=tmp_path)
    with pytest.raises(ValueError):paths.report('../other.json')

def test_cross_battle_and_symlink_output_guard(tmp_path):
    a=BattleArtifacts('sample_battle_0',tmp_path).prepare();b=BattleArtifacts('sample_battle_4',tmp_path).prepare()
    with pytest.raises(ValueError):a.guard_output(b.report('state.json'))
    a.report('escaped.json').symlink_to(b.report('state.json'))
    with pytest.raises(ValueError):a.report('escaped.json')
    a.guard_output(tmp_path/'external/state.json').write_text('zero')
    with pytest.raises(ValueError):b.guard_output(tmp_path/'external/state.json')
    assert (tmp_path/'external/state.json').read_text()=='zero'

def test_all_five_recordings_and_original_name_alias(tmp_path):
    fixture_dir=tmp_path/'tests/fixtures';fixture_dir.mkdir(parents=True)
    for n in range(5):(fixture_dir/f'sample_battle_{n}.mp4').write_bytes(f'synthetic video {n}'.encode())
    (fixture_dir/'sample_battle.mp4').symlink_to('sample_battle_0.mp4')
    videos=[BattleArtifacts(f'sample_battle_{n}',tmp_path).video() for n in range(5)]
    assert len({p.stat().st_ino for p in videos})==5
    assert (fixture_dir/'sample_battle.mp4').samefile(videos[0])
    assert not (fixture_dir/'sample_battle_5.mp4').exists()

def test_conservative_move_alias_and_collision(tmp_path,monkeypatch):
    import scripts.migrate_battle_artifacts as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    source=tmp_path/'old.json';target=tmp_path/'reports/battles/sample_battle_0/old.json'
    data={'battle_id':'sample_battle','event_id':'opaque-original-id','source_id':'sample_battle.mp4#1'}
    source.write_text(json.dumps(data));checksum=hashlib.sha256(source.read_bytes()).hexdigest();records=[]
    module.move_alias(source,target,records);module.move_alias(source,target,records)
    assert source.is_symlink() and json.loads(target.read_text())==data and len(records)==1
    assert records[0]['sha256_before_move']==checksum
    other=tmp_path/'other.json';other.write_text('other')
    with pytest.raises(FileExistsError):module.move_alias(other,target,records)
    assert other.read_text()=='other'

@pytest.mark.local_artifacts('.cache/m223-survey','.cache/m15-resolution-178-200/frames.json','.cache/m14-phases/sample_battle/manifest.json','reports/M2.2.3-battle-state.json')
def test_legacy_fixture_and_cache_references_preserved():
    assert (ROOT/'tests/fixtures/m223_annotations.json').samefile(BattleArtifacts('sample_battle_3').input('m223_annotations.json'))
    assert (ROOT/'.cache/m223-survey').samefile(BattleArtifacts('sample_battle_3').cache('m223-survey'))
    assert manifest_battle(BattleArtifacts('sample_battle_0').cache('m14-phases/manifest.json'))=='sample_battle_0'
    assert manifest_battle(BattleArtifacts('sample_battle_1').cache('m15-resolution-178-200/frames.json'))=='sample_battle_1'
    checkpoint=json.loads(BattleArtifacts('sample_battle_3').report('M2.2.3-battle-state.json').read_text())
    assert checkpoint['state_hash']=='4696ae0b62d98dbcfda1ad3595046b7997d638ef493ea33adda6ecb50b88bdbc'

def test_wrong_event_evidence_owner_rejected(tmp_path):
    paths=BattleArtifacts('sample_battle_3',tmp_path)
    with pytest.raises(ValueError):check_event_ownership(paths,{'event_candidates':[{'evidence':[{'source_id':'sample_battle_2.mp4#1'}]}]})

def test_independent_cli_outputs_and_no_cross_overwrite(tmp_path):
    def generate(n):
        bid=f'sample_battle_{n}';state=BattleState(bid)
        initial=tmp_path/f'initial{n}.json';events=tmp_path/f'events{n}.json';destination=tmp_path/f'out{n}'
        initial.write_text(json.dumps({'state':state.to_dict()}))
        event=BattleEvent(stable_id(bid,'phase'),'phase_observation','field',None,None,'Synthetic phase',{},None,
            [Evidence('synthetic',f'{bid}.mp4#1',['observation'])],None,'supported',[],{'phase':'battle_screen','sequence':1},'confirmed')
        events.write_text(json.dumps({'event_candidates':[event.to_dict()]}))
        cmd=[sys.executable,str(ROOT/'scripts/replay_m22.py'),'--battle-id',bid,'--initial',str(initial),'--events',str(events),
            '--output',str(destination/'state.json'),'--snapshots',str(destination/'snapshots.json'),'--summary',str(destination/'summary.txt')]
        subprocess.run(cmd,check=True,capture_output=True,text=True)
        return cmd,destination
    ca,a=generate(0);cb,b=generate(4)
    assert json.loads((a/'state.json').read_text())['state']['battle_id']=='sample_battle_0'
    assert json.loads((b/'state.json').read_text())['state']['battle_id']=='sample_battle_4'
    before=(a/'state.json').read_bytes();cb[cb.index('--output')+1]=str(a/'state.json')
    assert subprocess.run(cb,capture_output=True).returncode!=0
    assert (a/'state.json').read_bytes()==before

@pytest.mark.local_artifacts('reports/M2.3.1-hidden-state-timeline.html','reports/M2.2.3-evidence','.cache/m223-survey')
def test_migrated_viewer_evidence_exists_and_is_compact():
    from scripts.optimize_state_timeline import payload
    from tracking.state_timeline import unpack_timeline
    paths=BattleArtifacts('sample_battle_3');html=paths.report('M2.3.1-hidden-state-timeline.html').read_text()
    timeline=unpack_timeline(payload(html));assert len(html.encode())<3_000_000
    assert 'function evidenceHref' in html and timeline['artifact_root']=='../../../'
    images=set()
    for entry in timeline['entries']:
        e=entry['event']
        if e:
            for source in [x['details'] for x in e['evidence']]+e.get('associated_video_evidence',[]):
                if source.get('image'):images.add(source['image'])
    assert images and all((ROOT/path).is_file() for path in images)

def test_recording2_replay_uses_canonical_inputs():
    from scripts.replay_m22 import run
    p=BattleArtifacts('sample_battle_2');engine,snapshots=run(ROOT/'tests/fixtures/battles/sample_battle_2/reviewed_events.json',p.input('m22_initial_context.json'))
    assert engine.state.battle_id=='sample_battle_2' and len(snapshots)==20


def test_identically_named_different_video_cannot_reuse_namespace(tmp_path):
    registered=tmp_path/'tests/fixtures/sample_battle_3.mp4';registered.parent.mkdir(parents=True);registered.write_bytes(b'registered')
    other=tmp_path/'other/sample_battle_3.mp4';other.parent.mkdir();other.write_bytes(b'other')
    with pytest.raises(ValueError):BattleArtifacts.select(video=other,root=tmp_path)


def test_canonical_and_legacy_browser_urls_resolve_the_same_evidence(tmp_path):
    from tracking.state_timeline import render_html
    import re,shutil
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    template=(ROOT/'tracking/templates/state_timeline.html').read_text();function=re.search(r'function evidenceHref\(path\)\{.*?\n\}',template,re.S).group(0)
    root_uri=ROOT.as_uri()+'/'
    script='const assert=require("node:assert/strict");const timeline={artifact_root:"../../../"};let document={};\n'+function
    for page in ['reports/M2.3.1-hidden-state-timeline.html','reports/battles/sample_battle_3/M2.3.1-hidden-state-timeline.html']:
        script+='document.baseURI='+json.dumps((ROOT/page).as_uri())+';\n'
        for path in ['reports/M2.2.3-evidence/m223-survey-000048.jpg','.cache/m223-survey/000004.jpg']:
            script+='assert.equal(evidenceHref('+json.dumps(path)+'),'+json.dumps(root_uri+path)+');\n'
    subprocess.run([node,'-e',script],check=True,capture_output=True)


def test_renamed_original_reuses_cached_manifest_without_decode(tmp_path,monkeypatch):
    import cv2
    from scripts.reconstruct_m223 import extract
    cache=tmp_path/'cached';cache.mkdir()
    video=tmp_path/'sample_battle_0.mp4';video.write_bytes(b'no decoding permitted')
    legacy=tmp_path/'sample_battle.mp4';legacy.symlink_to(video.name)
    manifest={'schema_version':1,'video':str(legacy),'step':2,'start':0,'duration':None,'frames':[]}
    (cache/'frames.json').write_text(json.dumps(manifest))
    def forbidden(*args,**kwargs):raise AssertionError('Migration/cache reuse must not decode video')
    monkeypatch.setattr(cv2,'VideoCapture',forbidden)
    assert extract(video,cache,2)==manifest


def test_sample_specific_reconciler_refuses_another_battle():
    result=subprocess.run([sys.executable,str(ROOT/'scripts/build_m223.py'),'--battle-id','sample_battle_4'],capture_output=True,text=True)
    assert result.returncode!=0 and 'sample_battle_3-specific' in result.stderr
    assert not BattleArtifacts('sample_battle_4').report('M2.2.3-battle-state.json').exists()
