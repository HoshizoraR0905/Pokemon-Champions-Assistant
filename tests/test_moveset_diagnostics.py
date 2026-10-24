"""Portable statistics checks and consistency of the real 197-occurrence exports."""
from collections import Counter
from copy import deepcopy
from itertools import combinations
import csv
import json
from pathlib import Path

import numpy as np
import pytest
from experiments.moveset_diagnostics.analysis import (jaccard, positive_scale, distances,
    restore_embedding, join_labels, comparison, move_table, numeric, describe, fit_partitions, select_k)
from experiments.moveset_diagnostics.report import feature_collisions
from experiments.moveset_diagnostics.run import protected_snapshot
from experiments.build_similarity.core import MoveModel

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'milestone_reports/assets/m353-moveset-diagnostics'


def row(i,ms=('a','b','c','d'),item='berry',points=(32,0,1,0,10,23),group=None):
    return dict(empirical_record_id=str(i),configuration=dict(moves=list(ms),item=item,nature='careful',ability='intimidate',sp=dict(values=list(points))),
                training_points=dict(zip(('hp','attack','defense','special_attack','special_defense','speed'),points)),
                item=item,nature='careful',ability='intimidate',alignment={'increase':'special_defense','decrease':'special_attack'},
                evaluation_group=group or 'group-'+str(i),publications=[dict(id='pub'+str(i),url='https://example.com/'+str(i))])


def part(ids,labels,medoids=None):
    return dict(occurrence_ids=list(ids),labels=list(labels),medoid_ids=list(medoids or [ids[labels.index(z)] for z in sorted(set(labels))]))


def test_exact_jaccard_and_typed_item_tokens():
    rows=[row(0),row(1,item='orb'),row(2,ms=('a','b','c','e'))]
    d=jaccard(rows);di=jaccard(rows,True)
    assert d[0,1]==0 and d[0,2]==pytest.approx(1-3/5)
    assert di[0,1]==pytest.approx(1-4/6)
    assert di[0,2]==pytest.approx(1-4/6)
    # Same string identity cannot equate an item token to a move token.
    typed=jaccard([row(0,item='e'),row(1,ms=('a','b','c','e'),item='d')],True)
    assert typed[0,1]==pytest.approx(1-3/7)
    with pytest.raises(ValueError):jaccard([row(0,item=None)],True)


def test_restoring_saved_embedding_does_not_fit_or_svd(monkeypatch):
    rows=[row(0),row(1,ms=('a','b','c','e')),row(2,ms=('a','f','g','h'))]
    original=MoveModel(dimension=2).fit(rows);saved=original.diagnostics()
    def forbidden(*args,**kwargs):raise AssertionError('Full-data retraining prohibited')
    monkeypatch.setattr(MoveModel,'fit',forbidden);monkeypatch.setattr(np.linalg,'svd',forbidden)
    restored=restore_embedding(saved)
    assert np.array_equal(restored.embedding,original.embedding)
    assert np.array_equal(restored.distances(rows,rows),original.distances(rows,rows))
    ds,norm=distances(rows,restored,learned_scale=.125)
    assert norm['learned_scale']==.125
    assert np.allclose(ds['moves-learned'],original.distances(rows,rows)/.125)
    assert ds['loadout-learned'][0,1]==pytest.approx(ds['moves-learned'][0,1])
    changed=[rows[0],dict(rows[1],item='orb'),rows[2]]
    ds2,_=distances(changed,restored,learned_scale=.125)
    assert ds2['loadout-learned'][0,1]-ds2['moves-learned'][0,1]==pytest.approx(.5)


def test_positive_scale_and_permutation_safe_join():
    assert positive_scale(np.zeros((3,3)))==1
    assert positive_scale(np.array([[0,0,2],[0,0,4],[2,4,0]]))==3
    assert join_labels(['a','b','c'],part(['c','a','b'],[2,0,1]))==[0,1,2]


@pytest.mark.parametrize('partition',[part(['a','a','c'],[0,1,2]),part(['a','b'],[0,1]),dict(occurrence_ids=['a','b','c'],labels=[0,1])])
def test_missing_duplicate_or_extra_occurrences_rejected(partition):
    with pytest.raises(ValueError):join_labels(['a','b','c'],partition)


def test_ari_nmi_known_values_label_permutations_and_overlap_margins():
    ids=list('abcd');left=part(ids,[0,0,1,1]);right=part(ids,[0,1,0,1])
    stats=comparison(ids,left,right)
    assert stats['ari']==pytest.approx(-.5) and stats['nmi']==pytest.approx(0)
    assert stats['table']==[[1,1],[1,1]]
    assert stats['left_sizes']==stats['right_sizes']==[2,2]
    same=part(list(reversed(ids)),[0,0,1,1])
    equivalent=comparison(ids,left,same)
    assert equivalent['ari']==1 and equivalent['nmi']==pytest.approx(1)
    constant=comparison(ids,left,part(ids,[0]*4))
    assert constant['nmi']==0 and not constant['meaningful_multicluster_agreement']
    both=comparison(ids,part(ids,[0]*4),part(ids,[9]*4))
    assert both['nmi']==1 and not both['meaningful_multicluster_agreement']


def test_occurrence_weighted_frequencies_lift_and_deterministic_ranks():
    rows=[row(i) for i in range(3)]+[row(3,ms=('a','b','e','f'))]
    species=Counter(m for r in rows for m in r['configuration']['moves'])
    table=move_table(rows[:3],species,4)
    assert [(m['move'],m['occurrences']) for m in table]==[('a',3),('b',3),('c',3),('d',3)]
    assert table[0]['cluster_frequency']==1 and table[0]['species_frequency']==1 and table[0]['lift']==1
    assert table[2]['species_frequency']==.75 and table[2]['lift']==pytest.approx(4/3)
    assert sum(m['cluster_frequency'] for m in table)==4
    assert table==move_table(list(reversed(rows[:3])),species,4)
    # Identical published builds remain three votes, not one.
    assert all(m['occurrences']==3 for m in table)


def test_sp_quantiles_not_just_ranges_and_entropy_support():
    rows=[row(0),row(1),row(2,ms=('a','b','e','f'),points=(32,32,0,0,0,2)),row(3,points=(31,0,14,0,19,2))]
    model=MoveModel(dimension=2).fit(rows);d=model.distances(rows,rows)
    summaries=describe(rows,part(['0','1','2','3'],[0,0,0,1]),d)
    c=summaries[0]
    assert c['n']==3 and c['distinct_movesets']==2 and c['source_groups']==3
    assert c['sp']['attack']['frequencies']=={'0':2,'32':1}
    assert c['sp']['attack']['median']==0 and c['sp']['attack']['q3']==16
    assert c['predominantly_one_moveset']
    assert c['move_token_entropy_bits']>2
    assert c['within_dissimilarity']['pairs']==3 and c['between_dissimilarity']['pairs']==3
    assert c['overrepresented_moves']==[]  # No positively enriched move reaches support three here.
    assert summaries[1]['within_dissimilarity']['mean'] is None


def test_clustering_deterministic_and_existing_conservative_screen():
    d=np.array([[0,0,.5,.5],[0,0,.5,.5],[.5,.5,0,0],[.5,.5,0,0]])
    a=fit_partitions(d);assert a==fit_partitions(d)
    assert a['pam'][1]['sizes']==[2,2] and a['hierarchical'][1]['sizes']==[2,2]
    # At N=4 even a perfectly separated two/two split fails the minimum of 3.
    stability={str(k):[dict(ari=1.)]*3 for k in range(1,5)}
    assert select_k(a['pam'],stability)==1
    candidates=[dict(k=1,sizes=[197],silhouette=None),dict(k=2,sizes=[143,54],silhouette=.54),dict(k=3,sizes=[46,97,54],silhouette=.68)]
    assert select_k(candidates,stability)==2  # Smallest qualifying K, not max silhouette.
    stability['2']=[dict(ari=.1)]*3
    assert select_k(candidates,stability)==3
    stability['3']=[dict(ari=1.)]*2
    assert select_k(candidates,stability)==1  # Requires all three available resamples.


def test_identical_feature_conflicts_ceiling_is_occurrence_weighted():
    rows=[row(i) for i in range(5)];labels=[0,1,2,2,2]
    c=feature_collisions(rows,labels)
    assert c['distinct_patterns']==1 and c['occurrences_in_mixed_patterns']==5
    assert c['best_correct_count']==3 and c['empirical_lookup_accuracy_ceiling']==.6
    rows[0]['item']='orb'
    item=feature_collisions(rows,labels,True)
    assert item['best_correct_count']==4 and item['empirical_lookup_accuracy_ceiling']==.8
    assert c['patterns'][0]['cluster_counts']==[1,1,3]


def test_protected_file_snapshot_reads_without_modifying_annotations(tmp_path):
    study=tmp_path/'study';study.mkdir();(study/'manifest.json').write_text('{}')
    annotation=tmp_path/'.cache/research/m353/reviews.sqlite3';annotation.parent.mkdir(parents=True);annotation.write_bytes(b'unchanged human annotations')
    before=annotation.read_bytes();snapshot=protected_snapshot(study,tmp_path)
    assert str(annotation) in snapshot and annotation.read_bytes()==before
    assert protected_snapshot(study,tmp_path)==snapshot
    # The diagnostic snapshot never creates a database or changes annotation bytes.
    assert not (annotation.parent/'reviews.sqlite3-wal').exists()


@pytest.fixture(scope='module')
def exports():
    with (ASSETS/'assignments.csv').open(newline='') as stream:records=list(csv.DictReader(stream))
    statistics=json.loads((ASSETS/'cluster-statistics.json').read_text())
    pairs=json.loads((ASSETS/'partition-comparisons.json').read_text())
    return records,statistics,pairs


def test_real_export_all_partitions_contain_same_197_original_occurrences(exports):
    records,stats,pairs=exports
    ids=[r['occurrence_id'] for r in records]
    assert len(ids)==len(set(ids))==197 and all(rid.startswith('vgc-occurrence:') and ':member:' in rid for rid in ids)
    for name,p in stats['partitions'].items():
        counts=Counter(int(r[name]) for r in records)
        assert [counts[z] for z in range(p['k'])]==p['sizes']
        assert sum(c['n'] for c in stats['clusters'][name])==197
    assert stats['partitions']['sp:k3']['sizes']==[31,24,142]
    assert stats['partitions']['combined-learned:k3']['sizes']==[34,7,156]


def test_real_export_overlaps_and_metrics_recompute_by_occurrence_id(exports):
    records,stats,pairs=exports;ids=[r['occurrence_id'] for r in records]
    for pair in pairs:
        left=part(ids,[int(r[pair['left']]) for r in records]);right=part(ids,[int(r[pair['right']]) for r in records])
        result=comparison(ids,left,right)
        assert result['table']==pair['table']
        assert result['ari']==pytest.approx(pair['ari']) and result['nmi']==pytest.approx(pair['nmi'])
        assert np.asarray(pair['table']).sum(0).tolist()==pair['right_sizes']
        assert np.asarray(pair['table']).sum(1).tolist()==pair['left_sizes']
        assert sum(pair['left_sizes'])==sum(pair['right_sizes'])==197


def test_real_export_every_move_and_complete_set_count_is_consistent(exports):
    records,stats,pairs=exports
    for name,clusters in stats['clusters'].items():
        species=Counter()
        for c in clusters:
            frequency=Counter()
            assert sum(s['occurrences'] for s in c['complete_movesets'])==c['n']
            assert len(c['complete_movesets'])==c['distinct_movesets']
            for ms in c['complete_movesets']:
                assert len(set(ms['moves']))==4
                for m in ms['moves']:frequency[m]+=ms['occurrences']
            assert sum(frequency.values())==4*c['n']
            assert {m['move']:m['occurrences'] for m in c['all_move_frequencies']}==frequency
            assert [m['move'] for m in c['all_move_frequencies']]==[m for m,n in sorted(frequency.items(),key=lambda p:(-p[1],p[0]))]
            assert c['top15_moves']==c['all_move_frequencies'][:15]
            assert all(m['occurrences']>=3 and m['lift']>1 for m in c['overrepresented_moves'])
            for m in c['all_move_frequencies']:
                assert m['cluster_frequency']==pytest.approx(m['occurrences']/c['n'])
                assert m['species_frequency']==pytest.approx(m['species_occurrences']/197)
                assert m['lift']==pytest.approx(m['cluster_frequency']/m['species_frequency'])
            species.update(frequency)
            for stat,v in c['sp'].items():assert sum(v['frequencies'].values())==c['n']
            assert sum(c['bulk']['frequencies'].values())==c['n']
        assert sum(species.values())==788
        for c in clusters:
            for m in c['all_move_frequencies']:assert m['species_occurrences']==species[m['move']]


def test_no_pairwise_distance_or_embedding_exports():
    data=json.loads((ASSETS/'cluster-statistics.json').read_text())
    encoded=json.dumps(data)
    assert 'distance_matrix' not in encoded and 'embedding' not in encoded
    assert not list(ASSETS.glob('*matrix*'))


@pytest.mark.parametrize('inside',['source','annotations'])
def test_runner_refuses_output_inside_protected_namespaces(tmp_path,monkeypatch,inside):
    import experiments.moveset_diagnostics.run as runner
    study=tmp_path/'study'
    target=study/'new-output' if inside=='source' else tmp_path/'.cache/research/m353/new-output'
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr('sys.argv',['diagnostics','--study',str(study),'--output',str(target)])
    with pytest.raises(ValueError,match='separate'):runner.main()
    assert not target.exists()
