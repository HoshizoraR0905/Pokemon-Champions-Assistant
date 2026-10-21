import json
from pathlib import Path
import pytest
from knowledge.message_names import MessageNames
from scripts.snapshot_pokemon_titles import parse_titles


def test_whole_known_title_plus_whole_name_and_overlapping_species():
    names=MessageNames()
    assert names.resolve('开始犯困的奇麒麟')['identity']['species_id']==981
    assert names.resolve('开始犯困的超能妙喵')['identity']['species_id']==678
    assert names.resolve('开始犯困的妙喵')['identity']['species_id']==677
    assert names.resolve('超能妙喵')['identity']['species_id']==678
    for value in ['奇怪的超能妙喵','超能开始犯困的妙喵','开始犯困的某个妙喵','开始犯困的Pebble','开始犯困的']:
        assert names.resolve(value)['identity'] is None
    assert names.resolve('开始犯困的喷火龙')['identity']['canonical_identity'] is None


def test_known_title_does_not_infer_variable_trainer_name_or_repair_typo():
    names=MessageNames()
    for value in ['Guest的奇麒麟','开始犯困的奇麟麒','开始犯困的开始犯困的奇麒麟']:
        assert names.resolve(value)['identity'] is None
    result=names.resolve('开始犯困的奇麒麟')
    assert result['title_source']['revision_id']==2597624
    assert result['title']['number']==56


def test_ambiguous_decompositions_abstain(tmp_path):
    # Even a corrupted supplement cannot select a shorter suffix by ordering.
    source=MessageNames().data
    source['titles'].append(dict(title='开始犯困的超能',supported=True))
    path=tmp_path/'titles.json';path.write_text(json.dumps(source))
    assert MessageNames(titles_path=path).resolve('开始犯困的超能妙喵')['reason']=='ambiguous_title_name'


def test_snapshot_parser_fails_on_unreviewed_heading_or_incomplete_table():
    with pytest.raises(ValueError):parse_titles('<table><th>名字</th></table>')
    with pytest.raises(ValueError):parse_titles('<th>序号</th><th>称号</th><th>对应奖章／证章</th></tr></table>')
