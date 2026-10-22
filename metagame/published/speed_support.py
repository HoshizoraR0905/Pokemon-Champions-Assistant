"""Read-only, population-scoped observed builds. Never a legality restriction."""
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
from .store import Teams
from .observed import distinct, eligibility, VERSION as OBSERVED_VERSION
from . import VERSION
from knowledge.champions_stats import ChampionsStats, STATS
from knowledge.stat_feasibility import summary
from speed_order.core import knowledge

# The pinned 52Poké nature/stat profile already used by published canonicalization.
NATURE_GRID = [
    ['hardy','lonely','brave','adamant','naughty'],
    ['bold','docile','relaxed','impish','lax'],
    ['timid','hasty','serious','jolly','naive'],
    ['modest','mild','quiet','bashful','rash'],
    ['calm','gentle','sassy','careful','quirky']]
NATURE_STATS = ['attack','defense','speed','special_attack','special_defense']


def alignment(nature):
    if not nature:
        return None
    label = nature.removeprefix('nature:')
    for i, row in enumerate(NATURE_GRID):
        if label in row:
            j = row.index(label)
            return dict(increase=NATURE_STATS[i] if i != j else None,
                        decrease=NATURE_STATS[j] if i != j else None)
    return None


class SpeedSupportIndex:
    def __init__(self, rows, scope):
        self.rows = deepcopy(rows)
        self.scope = deepcopy(scope)
        self.by_species = defaultdict(list)
        for row in self.rows:
            self.by_species[row['species']].append(row)

    @classmethod
    def load(cls, root, *, source, population, regulation, battle_format='Doubles'):
        db = Teams(root, readonly=True)
        try:
            rows = [r for r in db.scoped(population, regulation, battle_format, VERSION)
                    if r['source_id'] == source]
        finally:
            db.close()
        groups, audit = distinct(rows, with_audit=True)
        members = []
        for signature, publications in groups.items():
            canonical = json.loads(publications[0]['canonical'])
            for m in canonical['members']:
                n = m['normalized']; valid = eligibility(m)
                a = alignment(n['nature']) if valid['nature'] else None
                points = dict(zip(STATS, n['sp']['values'])) if valid['sp'] else None
                speed = None; issue = None
                if points is not None and a is not None and n['species']:
                    try:
                        form = 'as_named' if knowledge().entities[n['species']].form_id else 'base'
                        speed = ChampionsStats(n['species'], form=form).calculate(points, a)['stats']['speed']
                    except (ValueError, NotImplementedError) as exc:
                        issue = str(exc)
                members.append(dict(species=n['species'], item=n['item'] if valid['item'] else None,
                    ability=n['ability'] if valid['ability'] else None, nature=n['nature'] if valid['nature'] else None,
                    alignment=a, speed_alignment=None if a is None else 1.1 if a['increase']=='speed' else 0.9 if a['decrease']=='speed' else 1.,
                    speed_sp=n['sp']['values'][5] if valid['sp_spe'] else None,
                    training_points=points, speed=speed, configuration=deepcopy(n),
                    complete=bool(m['exact_complete'] and speed is not None),
                    build_id=m.get('pokemon_build_id'), team_build_id=canonical.get('build_id'),
                    observed_team_signature=signature, missing=m['missing'], issues=m['issues'], stat_issue=issue,
                    publications=[dict(id=p['id'], extraction_id=p['extraction_id'], url=p['source_url'],
                                       source_key=p['source_key']) for p in publications]))
        return cls(members, dict(source=source, population=population, regulation=regulation, format=battle_format,
            canonical_version=VERSION, observed_version=OBSERVED_VERSION, observation_unit='distinct_observed_team_configuration_member',
            designs=len(groups), publications=len(rows), publication_family_audit=audit,
            interpretation='Descriptive published configurations; neither independent ranked encounters nor Bayesian probabilities'))

    def statistic(self, species, event, *, given=None):
        """Only records with known condition and target fields enter a denominator."""
        given = given or {}; rows = self.by_species.get(species, [])
        condition_known = [r for r in rows if all(r.get(k) is not None for k in given)]
        conditioned = [r for r in condition_known if all(r[k] == v for k,v in given.items())]
        eligible = [r for r in conditioned if all(r.get(k) is not None for k in event)]
        numerator = sum(all(r[k] == v for k,v in event.items()) for r in eligible)
        return dict(numerator=numerator, denominator=len(eligible), frequency=numerator/len(eligible) if eligible else None,
            sample_size=len(rows), condition_known=len(condition_known), condition_matches=len(conditioned),
            missing_condition=len(rows)-len(condition_known), missing_target=len(conditioned)-len(eligible),
            status='descriptive_frequency' if eligible else 'insufficient_evidence', scope=self.scope)

    def support(self, species):
        rows = self.by_species.get(species, [])
        complete = [r for r in rows if r['complete']]
        return dict(scope=self.scope, sample_size=len(rows), complete_builds=len(complete),
            incomplete_builds=len(rows)-len(complete), speed=summary(r['speed'] for r in complete),
            builds=deepcopy(rows), interpretation='Observed joint builds only; missing fields are unknown; absent builds remain legal possibilities')


def search_support(empirical, legal, evaluate, *, mode='expand_on_contradiction', expand=False):
    """Authoritative legal result stays separate even when empirical search succeeds.

    evaluate must return a complete exact/empty result; unresolved never triggers
    automatic expansion and never means empirical support was exhausted.
    """
    if mode not in {'empirical_only','expand_on_contradiction','full_legal'}:
        raise ValueError('Unknown empirical search mode')
    observed = evaluate(empirical) if empirical else dict(status='empty', feasible=None)
    exhaustion = observed['status'] == 'empty'
    expanded = expand or mode == 'full_legal' or (mode=='expand_on_contradiction' and exhaustion)
    full = evaluate(legal) if expanded else None
    return dict(empirical=observed, full_legal=full, expanded=expanded,
                reason='manual_or_full_mode' if expand or mode=='full_legal' else 'empirical_exhausted' if expanded else None,
                completeness='full_legal_evaluated' if full and full['status'] in {'exact','empty'} else 'empirical_subset_only')
