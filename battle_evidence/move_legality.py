"""Maintained canonical Champions learnset boundary; absence stays unverified."""
from damage.data import resolve,Diagnostic
from speed_order.core import knowledge


def move_legality(form,move):
    kb=knowledge()
    try:canonical=resolve(move,'move','observed_move')['canonical_id']
    except Diagnostic:return dict(status='unverified',reason='Unresolved canonical move identity')
    if canonical not in kb.facts['moves']:return dict(status='unverified',move=canonical,reason='Outside pinned Champions move catalog')
    if canonical in kb.relationships.get(form,{}).get('moves',[]):
        return dict(status='confirmed_possible',move=canonical,form=form,source='KnowledgeBase canonical Champions learnset relationships',
                    snapshot=kb.snapshot_id,scope='Possible species/form membership, not equipped slots or a usage prior')
    return dict(status='unverified',move=canonical,form=form,reason='Missing edge in pinned learnset; incomplete data is not confirmed impossibility')
