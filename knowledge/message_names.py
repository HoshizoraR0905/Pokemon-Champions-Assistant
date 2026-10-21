"""Offline whole-name/title resolution through the maintained KnowledgeBase.

Static title vocabulary is a versioned 52Poke supplement, not a species database.
An exact complete name or exact complete title + name must uniquely support the
same identity across every possible decomposition. Arbitrary suffixes abstain.
"""
import json
from pathlib import Path
from battle_events.aliases import alias_key
from battle_events.parser import EventParser

DEFAULT_TITLES = Path(__file__).parent/'data/52poke_titles_v1.json'


class MessageNames:
    def __init__(self, knowledge=None, *, titles_path=DEFAULT_TITLES):
        self.parser = EventParser(knowledge)
        self.data = json.loads(Path(titles_path).read_text())
        self.titles = [r for r in self.data['titles'] if r['supported']]

    def resolve(self, literal):
        raw = alias_key(literal)
        candidates = []
        bare = self.parser.identity(raw, 'species')
        if bare:
            candidates.append(dict(identity=bare, title=None, name=literal))
        for row in self.titles:
            title = alias_key(row['title'])
            if not raw.startswith(title) or len(raw) <= len(title):
                continue
            name = raw[len(title):]
            ref = self.parser.identity(name, 'species')
            if ref:
                candidates.append(dict(identity=ref, title=row, name=name))
        claims = {(c['identity']['canonical_id'], c['identity'].get('canonical_identity')) for c in candidates}
        if len(claims) != 1:
            return dict(identity=None, reason='ambiguous_title_name' if claims else 'unmapped_complete_display_reference',
                        literal=literal, candidates=candidates)
        chosen = next((c for c in candidates if c['title'] is None), candidates[0])
        return dict(identity=chosen['identity'], literal=literal, title=chosen['title'], name=chosen['name'],
                    reason='exact_canonical_name' if chosen['title'] is None else 'verified_title_and_exact_canonical_name',
                    title_source=self.data['source'] if chosen['title'] else None)
