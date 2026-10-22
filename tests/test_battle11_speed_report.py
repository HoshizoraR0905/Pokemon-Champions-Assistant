"""Keep member counts distinct from unique builds in the showcase audit."""
from scripts.build_battle11_speed_report import FORM, audit_raichu, ranges


def test_audit_preserves_team_contexts_without_inventing_unique_builds():
    def row(team, ability='native', complete=True):
        return dict(build_id='same-build', observed_team_signature=team,
                    complete=complete, nature='nature:timid',
                    alignment=dict(increase='speed',decrease='attack'),
                    ability=ability,item='stone',speed=191,speed_sp=24,publications=[])
    rows=[row('team-a'),row('team-b'),row('team-c','conflicting'),row('team-d',complete=False)]
    replay=dict(snapshots=[dict(opponents={'raichu':dict(current_form=FORM,support_ref='live')})],
                support_catalog={'live':dict(observed=dict(builds=['a','b'],complete_after=2))},
                observed_builds={'a':rows[0],'b':rows[1]})
    result=audit_raichu(replay,dict(by_form={FORM:dict(builds=rows)}))
    assert (result['complete'],result['incomplete']) == (3,1)
    assert result['complete_abilities'] == {'native':2,'conflicting':1}
    assert result['surviving_records'] == 2
    assert result['surviving_unique_builds'] == 1
    assert {r['observed_team_signature'] for r in result['surviving']} == {'team-a','team-b'}
    assert result['complete_alignments'] == {'speed / attack':3}


def test_report_speed_notation_retains_discrete_gaps():
    assert ranges(dict(intervals=[[72,73],[80,88],[119,119]])) == '[72–73] ∪ [80–88] ∪ 119'
