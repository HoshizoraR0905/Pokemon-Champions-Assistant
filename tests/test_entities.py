from dataclasses import replace
import json
from pathlib import Path
import pytest
from knowledge import KnowledgeBase
from models import Observation, Pokemon, Recognition
from recognition import Recognizer
from recognition.context import RecognitionContext, TeamMember
from recognition.entities import EntityContext, EntityResolver, distance
from tracking import Tracker


@pytest.fixture(scope='module')
def resolver():
    return EntityResolver()


def identify(resolver, text, kind='species', confidence=.5, context=None):
    return resolver.resolve(Observation(None,confidence,raw_text=text),kind,context,region_kind=kind)


@pytest.mark.parametrize('name,canonical,kind',[
    ('暴飞龙','pokeapi:species:373','species'),('钢铠鸦','pokeapi:species:823','species'),
    ('大狃拉','pokeapi:species:903','species'),('广域战力','pokeapi:move:797','move'),
    ('威吓','pokeapi:ability:22','ability'),('气势披带','pokeapi:item:252','item')])
def test_exact_even_zero_ocr_confidence(resolver,name,canonical,kind):
    result = identify(resolver,name,kind,0)
    assert result.resolution.canonical_id == canonical
    assert result.resolution.method == 'exact'
    assert result.confidence == 0
    assert result.raw_text == name
    assert result.resolution.verification_status=='unverified'
    assert result.resolution.confidence=='strong'


@pytest.mark.parametrize('text,canonical',[('大狙拉','pokeapi:species:903'),
                                         ('钢铠臣','pokeapi:species:823'),('班基拉期','pokeapi:species:248')])
def test_single_character_errors_not_replacement_rules(resolver,text,canonical):
    result = identify(resolver,text)
    assert result.resolution.canonical_id==canonical
    assert result.resolution.method=='fuzzy'
    assert result.resolution.candidates[0].edit_distance==1
    assert 'probabilities' in result.resolution.score_semantics


def test_chinese_shape_evidence_generic(resolver):
    radicals = resolver.knowledge.radicals
    assert distance('狙','狃',radicals) < distance('狙','狃')
    resolved = identify(resolver,'大狙拉')
    assert 'shared_unicode_radical_and_similar_strokes' in resolved.resolution.candidates[0].evidence


def test_ambiguous_fuzzy(resolver):
    # Both 敲音猴 and 啪咚猴 differ by one character from this text.
    result = identify(resolver,'啪音猴')
    assert result.value is None
    assert result.resolution.method=='ambiguous_fuzzy'
    assert len(result.resolution.candidates)>=2


@pytest.mark.parametrize('text',['于富囊','不存在的宝可梦','qzxwvv','', '鼠'])
def test_unknown_and_severe_corruption(resolver,text):
    result = identify(resolver,text)
    assert result.value is None
    assert result.resolution.status=='unresolved'


def test_corruption_not_rescued_by_singleton_context(resolver):
    ctx = EntityContext(allowed_ids={'pokeapi:species:1000'},preferred_ids={'pokeapi:species:1000'},
                        verified_id='pokeapi:species:1000',source='manual')
    assert identify(resolver,'于富囊',context=ctx).value is None


def test_high_confidence_invalid_text_and_conflicting_exact(resolver):
    assert identify(resolver,'钢铠臣',confidence=.99).value is None
    ctx = EntityContext(verified_id='pokeapi:species:373',source='manual')
    wrong = identify(resolver,'班基拉斯',confidence=.99,context=ctx)
    assert wrong.value is None
    assert wrong.resolution.status=='conflict'
    # A valid name with no conflicting evidence cannot be declared incorrect from text alone.
    assert identify(resolver,'班基拉斯',confidence=.99).resolution.method=='exact'


def test_context_filters_ambiguous_fuzzy_and_disallows_exact(resolver):
    ctx = EntityContext(allowed_ids={'pokeapi:species:810'},verified_preferred_ids={'pokeapi:species:810'},source='manual_complete')
    result = identify(resolver,'啪音猴',context=ctx)
    assert result.resolution.canonical_id=='pokeapi:species:810'
    assert identify(resolver,'班基拉斯',context=ctx).resolution.status=='conflict'


def test_dictionary_regions_and_categories(resolver):
    raw = Observation(None,.1,raw_text='暴飞龙')
    assert resolver.resolve(raw,'species',region_kind='move').resolution.method=='inappropriate_region'
    assert identify(resolver,'暴飞龙','move').value is None


@pytest.mark.parametrize('cn,en,canonical',[
    ('暴飞龙','Salamence','pokeapi:species:373'),
    ('大狃拉','Sneasler','pokeapi:species:903'),
    ('超级暴飞龙','Mega Salamence','pokeapi:form:10191'),
    ('广域战力','Expanding Force','pokeapi:move:797'),
    ('威吓','Intimidate','pokeapi:ability:22'),
    ('气势披带','Focus Sash','pokeapi:item:252')])
def test_cross_language_ids(resolver,cn,en,canonical):
    kind = 'species' if ':form:' in canonical else canonical.split(':')[1]
    assert identify(resolver,cn,kind).resolution.canonical_id==canonical
    assert identify(resolver,en,kind).resolution.canonical_id==canonical


def test_bare_name_does_not_infer_form(resolver):
    result = identify(resolver,'爱管侍')
    assert result.resolution.species_id==876
    assert result.resolution.form_id is None
    female=identify(resolver,'Female Indeedee').resolution
    assert female.pokemon_id==10186
    assert female.canonical_identity=='pokeapi:pokemon:10186'
    assert female.form_id is None


def test_current_official_roster_entry_recognized(resolver):
    result = identify(resolver,'暴飞龙')
    assert result.value=='暴飞龙'
    assert result.resolution.candidates[0].availability['status'] == 'confirmed_available'


def test_verified_fields_protected_and_duplicate_instances(resolver,tmp_path):
    payload = {'schema_version':1,'complete_roster':True,'members':[
        {'instance_id':'own_team_1','species_id':'pokeapi:species:373',
         'fields':{'ability':'pokeapi:ability:22'},'source':'manual inspection A'},
        {'instance_id':'own_team_2','species_id':'pokeapi:species:373',
         'fields':{'ability':'pokeapi:ability:153'},'source':'manual inspection B'}]}
    path = tmp_path/'team.json';path.write_text(json.dumps(payload))
    context = RecognitionContext(resolver.knowledge);context.load_verified(path,resolver.knowledge)
    recognizer = Recognizer(resolver=resolver,context=context)
    result = Recognition('test',0,0,pokemon=[
        Pokemon('own_team_1',Observation(None,0,raw_text='暴飞龙'),configuration={'ability':Observation(None,.1,raw_text='威吓')}),
        Pokemon('own_team_2',Observation(None,.5,raw_text='暴飞龙'),configuration={'ability':Observation(None,.1,raw_text='自信过度')})])
    recognizer.resolve_entities(result)
    tracker = Tracker();tracker.update(result)
    assert len(tracker.team)==2
    assert tracker.team['own_team_1']['ability'].value=='威吓'
    assert tracker.team['own_team_2']['ability'].value=='自信过度'
    assert result.pokemon[0].configuration['ability'].resolution.verification_status=='verified'
    wrong = identify(resolver,'威吓','ability',.8,context.for_field('own_team_2','ability','ability'))
    assert wrong.resolution.status=='conflict'
    incoming = replace(result.pokemon[0],configuration={'ability':identify(resolver,'自信过度','ability')})
    tracker.update(Recognition('test',1,1,pokemon=[incoming]))
    assert tracker.team['own_team_1']['ability'].value=='威吓'
    assert context.verified_team['own_team_2'].fields['ability']=='pokeapi:ability:153'


def test_multiple_same_species_active_not_assigned_to_one_instance(resolver):
    context = RecognitionContext(resolver.knowledge)
    context.observed_team = {f'own_team_{i}':TeamMember(f'own_team_{i}','pokeapi:species:373') for i in (1,2)}
    r = Recognizer(resolver=resolver,context=context)
    state = Recognition('test',0,0,pokemon=[Pokemon('own_active_1',Observation(None,.2,raw_text='暴飞龙'))])
    r.resolve_entities(state)
    assert state.pokemon[0].team_instance_id is None


def test_consecutive_observations_remain_separate_from_verified(resolver):
    ctx = RecognitionContext(resolver.knowledge)
    for i in range(3):
        ctx.begin_frame('video',i)
        obs = identify(resolver,'暴飞龙',context=ctx.for_field('own_active_1','species'))
        ctx.remember(Recognition('video',i,float(i),pokemon=[Pokemon('own_active_1',obs)]))
    assert obs.resolution.verification_status=='corroborated'
    assert not ctx.verified_team
    ctx.begin_frame('other image',0)
    assert ctx.for_field('own_active_1','species').previous_id is None


def test_opponent_preview_is_soft_context(resolver):
    ctx = RecognitionContext(resolver.knowledge)
    ctx.opponent_preview = {'pokeapi:species:1000'}
    field = ctx.for_field('opponent_active_1','species')
    assert field.allowed_ids is None
    assert identify(resolver,'于富囊',context=field).value is None
    assert identify(resolver,'巨金怪',context=field).value=='巨金怪'


def test_source_manifest_and_checksum(resolver,tmp_path):
    kb = resolver.knowledge
    assert kb.manifest['champions']['metadata']['version']=='2026-10-13-M-C.1'
    assert kb.manifest['historical_champions']['metadata']['lastUpdated']=='2026-04-16'
    assert kb.manifest['champions']['license'].startswith('MIT')
    source = Path(__file__).parents[1]/'knowledge/data'
    (tmp_path/'manifest.json').write_bytes((source/'manifest.json').read_bytes())
    (tmp_path/'entities.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum'):
        KnowledgeBase(tmp_path)


def test_zero_similarity_filtered_with_debug_evidence(resolver):
    result = identify(resolver, 'qzxwvv').resolution
    assert all(c.similarity > 0 for c in result.candidates)
    assert result.filtered_zero_similarity_count > 0
    assert result.debug_candidates
    assert all(c.similarity == 0 for c in result.debug_candidates)


@pytest.mark.parametrize('cn,en,sid,status',[
    ('巨金怪','Metagross',376,'confirmed_available'),
    ('赛富豪','Gholdengo',1000,'confirmed_available'),
    ('大狃拉','Sneasler',903,'confirmed_available'),
    ('龙头地鼠','Excadrill',530,'confirmed_available')])
def test_screenshot_species_dictionary_and_availability(resolver,cn,en,sid,status):
    for name in (cn,en):
        result = identify(resolver,name)
        assert result.resolution.canonical_id == f'pokeapi:species:{sid}'
        assert result.resolution.candidates[0].availability['status'] == status
    assert resolver.knowledge.entities[f'pokeapi:species:{sid}'].champions_entries == ()


def test_version_and_regulation_scoping(resolver,tmp_path):
    import hashlib
    import shutil
    source = Path(__file__).parents[1]/'knowledge/data'
    for name in ('entities.json','manifest.json','champions_roster.json'):
        shutil.copyfile(source/name,tmp_path/name)
    roster = json.loads((tmp_path/'champions_roster.json').read_text())
    snapshot = dict(roster['snapshots'][0], scope_id='test-build',game_version='test-build',
        entries=[{'canonical_id':'pokeapi:species:376','status':'confirmed_unavailable',
                  'source':{'test':'explicit negative evidence'}}],
        regulations=[{'regulation_id':'test-regulation','entries':[
            {'canonical_id':'pokeapi:species:530','status':'illegal',
             'source':{'test':'regulation evidence'}}]}])
    roster['snapshots'].append(snapshot)
    raw = json.dumps(roster).encode()
    (tmp_path/'champions_roster.json').write_bytes(raw)
    manifest = json.loads((tmp_path/'manifest.json').read_text())
    manifest['files']['champions_roster.json'] = hashlib.sha256(raw).hexdigest()
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    kb = KnowledgeBase(tmp_path,game_version='test-build',regulation='test-regulation')
    assert kb.availability('pokeapi:species:376')['status']=='confirmed_unavailable'
    assert kb.availability('pokeapi:species:530')['status']=='unknown'
    assert kb.availability('pokeapi:species:530')['legality']=='illegal'
    assert identify(EntityResolver(kb),'巨金怪').value=='巨金怪'
    assert KnowledgeBase(tmp_path,game_version='other-build').availability('pokeapi:species:376')['status']=='unknown'
    assert resolver.knowledge.availability('pokeapi:species:530')['legality']=='legal'


def test_roster_bonus_does_not_force_ambiguous_match(resolver,monkeypatch):
    original = resolver.knowledge.availability
    def availability(cid):
        value = dict(original(cid))
        value['status'] = 'confirmed_available' if cid=='pokeapi:species:810' else 'unknown'
        return value
    monkeypatch.setattr(resolver.knowledge,'availability',availability)
    assert identify(resolver,'啪音猴').value is None


@pytest.mark.parametrize('sid',[1,150,151,249,384,493])
def test_national_dex_omission_is_illegal_not_game_unavailable(resolver,sid):
    entity = resolver.knowledge.entities[f'pokeapi:species:{sid}']
    result = identify(resolver,entity.names['en'])
    assert result.resolution.canonical_id == entity.canonical_id
    availability = result.resolution.candidates[0].availability
    assert availability['status'] == 'unknown'
    assert availability['legality'] == 'illegal'


def test_moves_forms_and_species_are_separate(resolver):
    kb = resolver.knowledge
    assert kb.availability('pokeapi:species:373')['legality'] == 'legal'
    assert kb.availability('pokeapi:form:10191')['legality'] == 'legal'
    assert kb.availability('pokeapi:move:797')['status'] == 'confirmed_available'
    assert kb.availability('pokeapi:move:237')['status'] == 'unknown'
    # A species assertion cannot confer availability on its Gigantamax form.
    forms = [e for e in kb.entities.values() if e.species_id == 6 and e.form_id and
             any('gigantamax' in n.lower() for n in list(e.names.values())+list(e.aliases))]
    assert forms
    for form in forms:
        assert kb.availability(form.canonical_id)['status'] == 'unknown'
        assert kb.availability(form.canonical_id)['legality'] == 'unknown'


def test_current_stats_and_learnsets_have_mapped_endpoints(resolver):
    kb = resolver.knowledge
    for sid in [376,1000,903,530]:
        cid = f'pokeapi:species:{sid}'
        assert set(kb.facts['pokemon'][cid]['stats']) == {'hp','at','df','sa','sd','sp'}
        assert kb.relationships[cid]['moves']
        assert all(mid in kb.facts['moves'] for mid in kb.relationships[cid]['moves'])
    assert kb.facts['moves']['pokeapi:move:453']['pp'] == '20'


def test_historical_snapshot_still_loads():
    archive = Path(__file__).parents[1]/'knowledge/archive/2026-04-16-v1.1.0'
    kb = KnowledgeBase(archive)
    assert kb.version == '1.1.0'
    assert kb.availability('pokeapi:species:376')['status'] == 'unknown'


def test_structured_facts_checksum(resolver,tmp_path):
    import shutil
    source = Path(__file__).parents[1]/'knowledge/data'
    for name in ['entities.json','manifest.json','champions_roster.json','champions_facts.json']:
        shutil.copyfile(source/name,tmp_path/name)
    (tmp_path/'champions_facts.json').write_text('{}')
    with pytest.raises(ValueError,match='facts checksum'):
        KnowledgeBase(tmp_path)
