"""Auditable dictionary resolution with conservative, non-probabilistic scores."""
from dataclasses import dataclass, field, replace
import re
from knowledge import Entity, KnowledgeBase, normalize
from models import EntityCandidate, EntityResolution, Observation


@dataclass
class EntityContext:
    # Hard restrictions must come from explicit verification, not fuzzy OCR.
    allowed_ids: set[str] | None = None
    verified_id: str | None = None
    preferred_ids: set[str] = field(default_factory=set)
    verified_preferred_ids: set[str] = field(default_factory=set)
    previous_id: str | None = None
    repeat_count: int = 0
    source: str = 'none'


def distance(a: str, b: str, radicals: dict | None = None) -> float:
    """Levenshtein; optional shared radical/stroke evidence discounts substitutions."""
    row = [float(i) for i in range(len(b)+1)]
    for i, ca in enumerate(a,1):
        next_row = [float(i)]
        for j, cb in enumerate(b,1):
            cost = 0.0 if ca==cb else 1.0
            if cost and radicals:
                ra, rb = radicals.get(ca), radicals.get(cb)
                if ra and rb and ra[0]==rb[0] and abs(ra[1]-rb[1]) <= 3:
                    cost = .75
            next_row.append(min(next_row[-1]+1,row[j]+1,row[j-1]+cost))
        row = next_row
    return row[-1]


class EntityResolver:
    def __init__(self, knowledge: KnowledgeBase | None = None):
        self.knowledge = knowledge or KnowledgeBase()

    def resolve(self, observation: Observation, kind: str,
                context: EntityContext | None = None, *, region_kind: str | None = None) -> Observation:
        context = context or EntityContext()
        kb = self.knowledge
        text = observation.raw_ocr.text if observation.raw_ocr else observation.raw_text
        # Programmatic observations may provide a value but no OCR text.
        if not text and isinstance(observation.value,str):
            text = observation.value
        normalized = normalize(text)
        resolution = EntityResolution(normalized_text=normalized,
            evidence=[f'knowledge_snapshot:{kb.snapshot_id}',f'context:{context.source}'])
        if region_kind != kind or kind not in kb.by_kind:
            resolution.method = 'inappropriate_region'
            return replace(observation,value=None,resolution=resolution)
        if not normalized:
            resolution.method = 'empty_ocr'
            return replace(observation,value=None,resolution=resolution)
        candidates: list[EntityCandidate] = []
        exact = kb.exact[kind].get(normalized,[])
        pool = exact if exact else kb.by_kind[kind]
        for entity in pool:
            names = set(entity.names.values()) | set(entity.aliases)
            # Avoid cross-script fuzzy matching (Latin garbage is not Chinese evidence).
            cjk = bool(re.search(r'[\u3400-\u9fff]',normalized))
            compatible = [n for n in names if bool(re.search(r'[\u3400-\u9fff]',n))==cjk]
            if not compatible:
                continue
            best = min(compatible,key=lambda n:(distance(normalized,normalize(n)),len(n),n))
            target = normalize(best)
            edits = int(distance(normalized,target))
            # Rank a small, explainable neighborhood; retain distant candidates for audit.
            weighted = distance(normalized,target,kb.radicals)
            similarity = max(0.0,1-weighted/max(len(normalized),len(target),1))
            evidence = [entity.name_source]
            score = similarity
            if weighted < edits:
                evidence.append('shared_unicode_radical_and_similar_strokes')
            if entity.canonical_id in context.preferred_ids:
                score += .04
                evidence.append('preferred_observed_roster')
            if entity.canonical_id in context.verified_preferred_ids:
                score += .12
                evidence.append('preferred_explicit_verified_roster')
            if entity.canonical_id == context.previous_id:
                score += min(.06,.02*context.repeat_count)
                evidence.append('previous_visible_identification')
            if entity.canonical_id == context.verified_id:
                score += .15
                evidence.append('explicit_verified_field')
            availability = kb.availability(entity.canonical_id) if kind == 'species' else None
            if availability:
                evidence.append('champions_availability:' + availability['status'])
                if availability['status'] == 'confirmed_available':
                    score += .04
                    evidence.append('preferred_champions_roster_source_assertion')
            if context.allowed_ids is not None and entity.canonical_id not in context.allowed_ids:
                evidence.append('excluded_by_explicit_verified_constraint')
            candidates.append(EntityCandidate(entity.canonical_id,kind,entity.names,entity.species_id,
                entity.form_id,best,edits,round(similarity,4),round(score,4),evidence,availability))
        candidates.sort(key=lambda c:(-c.ranking_score,c.edit_distance,c.canonical_id))
        zero = [c for c in candidates if c.similarity == 0]
        resolution.filtered_zero_similarity_count = len(zero)
        resolution.debug_candidates = zero[:5]
        candidates = [c for c in candidates if c.similarity > 0]
        resolution.candidates = candidates[:5]
        eligible = [c for c in candidates if context.allowed_ids is None or c.canonical_id in context.allowed_ids]
        # An exact canonical name outside a verified complete roster is conflicting evidence.
        if exact and not eligible:
            resolution.status, resolution.method = 'conflict','verified_context_conflict'
            return replace(observation,value=None,resolution=resolution)
        if not eligible:
            resolution.method = 'no_candidates'
            return replace(observation,value=None,resolution=resolution)
        chosen = eligible[0]
        if chosen not in resolution.candidates:
            resolution.candidates = resolution.candidates[:4]+[chosen]
        verified_entity = kb.entities.get(context.verified_id) if context.verified_id else None
        compatible_species = (kind=='species' and verified_entity and chosen.form_id is None
                              and chosen.species_id==verified_entity.species_id)
        if context.verified_id and chosen.canonical_id != context.verified_id and not compatible_species:
            resolution.status, resolution.method = 'conflict','verified_field_conflict'
            resolution.evidence.append('verified_value_preserved_by_context_store')
            return replace(observation,value=None,resolution=resolution)
        if exact:
            # Multiple aliases for one entity do not constitute ambiguity.
            if len({c.canonical_id for c in eligible}) > 1:
                resolution.method = 'ambiguous_exact'
                return replace(observation,value=None,resolution=resolution)
            resolution.method, resolution.confidence = 'exact','strong'
        else:
            runner_score = eligible[1].ranking_score if len(eligible)>1 else 0.0
            margin = chosen.ranking_score-runner_score
            # Roster preference orders review candidates but cannot remove ambiguity.
            def without_roster_bonus(candidate):
                return candidate.ranking_score - (.04 if candidate.availability and
                    candidate.availability['status'] == 'confirmed_available' else 0)
            visual_margin = without_roster_bonus(chosen) - max(
                (without_roster_bonus(c) for c in eligible[1:]), default=0)
            margin = min(margin, visual_margin)
            resolution.evidence += [f'ranking_margin:{margin:.4f}',f'raw_ocr_confidence:{observation.confidence:.3f}']
            supported = (chosen.canonical_id in context.preferred_ids or chosen.canonical_id in context.verified_preferred_ids
                         or chosen.canonical_id==context.previous_id or chosen.canonical_id==context.verified_id)
            # Context cannot turn severely corrupted/short text into an identification.
            acceptable = (len(normalized)>=3 and chosen.edit_distance==1
                          and chosen.similarity>=.65 and margin>=.12)
            if observation.confidence >= .95 and not supported:
                acceptable = False
                resolution.evidence.append('high_confidence_noncanonical_text_requires_support')
            if not acceptable:
                resolution.method = 'ambiguous_fuzzy' if margin<.12 else 'insufficient_text_evidence'
                return replace(observation,value=None,resolution=resolution)
            resolution.method = 'context_fuzzy' if supported else 'fuzzy'
            resolution.confidence = 'moderate'
        resolution.status = 'resolved'
        resolution.canonical_id = chosen.canonical_id
        resolution.species_id, resolution.form_id = chosen.species_id, chosen.form_id
        if chosen.canonical_id==context.verified_id:
            resolution.verification_status = 'verified'
        elif chosen.canonical_id==context.previous_id and context.repeat_count>=2:
            resolution.verification_status = 'corroborated'
        entity = kb.entities[chosen.canonical_id]
        return replace(observation,value=entity.label(bool(re.search(r'[\u3400-\u9fff]',normalized))),
                       resolution=resolution,provenance='knowledge_resolved_ocr')
