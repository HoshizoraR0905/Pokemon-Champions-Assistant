"""Exact shared-KnowledgeBase resolution; unknown forms never collapse to base."""
from knowledge import KnowledgeBase, normalize


class Names:
    def __init__(self, knowledge=None):
        self.knowledge = knowledge or KnowledgeBase()

    def resolve(self, name, kind='species'):
        kb = self.knowledge
        matches = ([kb.entities[name]] if name in kb.entities else
                   kb.exact[kind].get(normalize(name), []))
        matches = {e.canonical_id: e for e in matches if e.kind == kind}
        entity = next(iter(matches.values())) if len(matches) == 1 else None
        result = dict(original_name=name, canonical_id=entity.canonical_id if entity else None,
            resolution='exact' if entity else 'ambiguous' if matches else 'unresolved',
            knowledge_snapshot=kb.snapshot_id)
        if kind == 'species':
            result.update(kb.identities.for_entity(entity))
            result['named_form_id'] = entity.form_id if entity else None
        return result
