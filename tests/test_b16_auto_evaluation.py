from scripts.evaluate_b16_auto import validate_reference


def test_log_reference_requires_supported_names_turn_and_consistent_text():
    entry=dict(partial=False,ocr_confidence=.99,turn=1,text_variants=['A'])
    event=dict(event_type='move_execution',actor=dict(species_id=903),canonical_references=dict(move=dict(canonical_id='pokeapi:move:182')),uncertainty=[])
    raw=dict(views=[],assembly_issues=[])
    assert validate_reference(entry,event,raw)==[]
    assert 'low_log_ocr_confidence' in validate_reference(dict(entry,ocr_confidence=.8),event,raw)
    assert 'invalid_turn' in validate_reference(dict(entry,turn=None),event,raw)
    assert 'partial_log_row' in validate_reference(dict(entry,partial=True),event,raw)
    assert 'unresolved_log_actor' in validate_reference(entry,dict(event,actor=None),raw)
    assert 'log_ocr_variants_disagree' in validate_reference(dict(entry,text_variants=['A','B']),event,raw)
    assert 'turn_scroll_assembly_uncertain' in validate_reference(entry,event,dict(views=[dict(source_id='x',turn=1)],assembly_issues=[dict(source_id='x')]))
