"""Conservative fusion of independently computed text and icon identities."""
from dataclasses import replace
from models import EntityResolution


def combine_identity(text,icon,knowledge,context=None):
    if icon is None:return text
    if icon.status=='ambiguous' and text.resolution and text.resolution.status=='resolved':
        sid=text.resolution.species_id
        eligible=[c for c in icon.candidates if c.species_id==sid and c.canonical_identity
                  and c.similarity>=.80]
        if eligible:
            top=eligible[0]
            near=[c for c in eligible if top.similarity-c.similarity<.10]
            if len({c.canonical_identity for c in near})==1:
                icon=replace(icon,status='resolved',species_id=sid,form_id=top.form_id,
                             pokemon_id=top.pokemon_id,canonical_identity=top.canonical_identity,
                             canonical_id=top.canonical_id,
                             identity_status=knowledge.identities.for_key(top.canonical_identity)['identity_status'],
                             reason='text_species_filters_visual_candidates')
    if icon.status!='resolved':return text
    if icon.canonical_identity is None:
        mapped=(knowledge.identities.for_form(icon.form_id) if icon.form_id is not None
                else knowledge.identities.for_key(icon.canonical_id))
        icon=replace(icon,form_id=mapped['form_id'],pokemon_id=mapped['pokemon_id'],
                     canonical_identity=mapped['canonical_identity'],identity_status=mapped['identity_status'])
    elif icon.identity_status == 'unresolved':
        mapped=knowledge.identities.for_key(icon.canonical_identity)
        icon=replace(icon,identity_status=mapped['identity_status'])
    resolution=text.resolution or EntityResolution()
    # Never overwrite an explicit verified-team conflict.
    if resolution.status=='conflict':
        resolution.evidence.append('independent_icon:'+str(icon.species_id))
        return text
    text_sid=resolution.species_id if resolution.status=='resolved' else None
    text_identity=resolution.canonical_identity if resolution.status=='resolved' else None
    verified=knowledge.entities.get(context.verified_id) if context and context.verified_id else None
    conflict=(text_sid is not None and text_sid!=icon.species_id) or (
        text_identity is not None and icon.canonical_identity is not None
        and text_identity != icon.canonical_identity)
    if verified and (verified.species_id!=icon.species_id or
                     (knowledge.identities.for_entity(verified)['canonical_identity'] and
                      knowledge.identities.for_entity(verified)['canonical_identity']!=icon.canonical_identity)):
        conflict=True
    if context and context.allowed_ids is not None:
        allowed={knowledge.entities[cid].species_id for cid in context.allowed_ids if cid in knowledge.entities}
        if icon.species_id not in allowed:conflict=True
    evidence=list(resolution.evidence)+['independent_icon:'+str(icon.species_id),
            'visual_source_commit:'+icon.source_commit]
    if conflict:
        result=replace(resolution,canonical_id=None,species_id=None,pokemon_id=None,
                       form_id=None,canonical_identity=None,identity_status='conflicting_variant',status='conflict',
                       method='text_icon_conflict',confidence='none',evidence=evidence)
        return replace(text,value=None,resolution=result,provenance='multimodal_conflict')
    # Ambiguous exact text may expose two different plausible species. A visual
    # observation must not silently erase the alternative.
    if resolution.method=='ambiguous_exact' and any(c.species_id!=icon.species_id for c in resolution.candidates):
        return replace(text,value=None,resolution=replace(resolution,status='conflict',
                       canonical_identity=None,pokemon_id=None,form_id=None,
                       identity_status='conflicting_variant',method='ambiguous_text_icon_conflict',evidence=evidence))
    cid=icon.canonical_id
    entity=knowledge.entities.get(cid)
    if entity is None:return text
    form_id=icon.form_id
    result=replace(resolution,canonical_id=cid,species_id=icon.species_id,form_id=form_id,
                   pokemon_id=icon.pokemon_id,canonical_identity=icon.canonical_identity,
                   identity_status=icon.identity_status,
                   status='resolved',method='text_icon_agreement' if text_sid else 'icon_only',
                   confidence='strong' if text_sid else 'moderate',evidence=evidence)
    chinese=bool(__import__('re').search(r'[\u4e00-\u9fff]',text.raw_text)) or not text.raw_text
    base=knowledge.entities.get(f'pokeapi:species:{icon.species_id}')
    label=(entity.names.get('zh-hans') or (base.names.get('zh-hans') if base else None) or entity.label(False)) if chinese else entity.label(False)
    return replace(text,value=label,resolution=result,provenance='multimodal_identity')
