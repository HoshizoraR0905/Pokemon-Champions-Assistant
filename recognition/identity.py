"""Conservative fusion of independently computed text and icon identities."""
from dataclasses import replace
from models import EntityResolution


def combine_identity(text,icon,knowledge,context=None):
    if icon is None or icon.status!='resolved':return text
    resolution=text.resolution or EntityResolution()
    # Never overwrite an explicit verified-team conflict.
    if resolution.status=='conflict':
        resolution.evidence.append('independent_icon:'+str(icon.species_id))
        return text
    text_sid=resolution.species_id if resolution.status=='resolved' else None
    text_fid=resolution.form_id if resolution.status=='resolved' else None
    verified=knowledge.entities.get(context.verified_id) if context and context.verified_id else None
    conflict=(text_sid is not None and text_sid!=icon.species_id) or (
        text_fid is not None and icon.form_id is not None and text_fid!=icon.form_id)
    if verified and (verified.species_id!=icon.species_id or
                     (verified.form_id and icon.form_id and verified.form_id!=icon.form_id)):
        conflict=True
    if context and context.allowed_ids is not None:
        allowed={knowledge.entities[cid].species_id for cid in context.allowed_ids if cid in knowledge.entities}
        if icon.species_id not in allowed:conflict=True
    evidence=list(resolution.evidence)+['independent_icon:'+str(icon.species_id),
            'visual_source_commit:'+icon.source_commit]
    if conflict:
        result=replace(resolution,canonical_id=None,species_id=None,form_id=None,status='conflict',
                       method='text_icon_conflict',confidence='none',evidence=evidence)
        return replace(text,value=None,resolution=result,provenance='multimodal_conflict')
    # Ambiguous exact text may expose two different plausible species. A visual
    # observation must not silently erase the alternative.
    if resolution.method=='ambiguous_exact' and any(c.species_id!=icon.species_id for c in resolution.candidates):
        return replace(text,value=None,resolution=replace(resolution,status='conflict',
                       method='ambiguous_text_icon_conflict',evidence=evidence))
    cid=icon.canonical_id
    entity=knowledge.entities.get(cid)
    if entity is None:return text
    form_id=icon.form_id if icon.form_id is not None else text_fid
    # When the icon cannot distinguish forms, keep explicit textual form evidence.
    if text_fid is not None and icon.form_id is None:cid=resolution.canonical_id;entity=knowledge.entities[cid]
    result=replace(resolution,canonical_id=cid,species_id=icon.species_id,form_id=form_id,
                   status='resolved',method='text_icon_agreement' if text_sid else 'icon_only',
                   confidence='strong' if text_sid else 'moderate',evidence=evidence)
    chinese=bool(__import__('re').search(r'[\u4e00-\u9fff]',text.raw_text)) or not text.raw_text
    base=knowledge.entities.get(f'pokeapi:species:{icon.species_id}')
    label=(entity.names.get('zh-hans') or (base.names.get('zh-hans') if base else None) or entity.label(False)) if chinese else entity.label(False)
    return replace(text,value=label,resolution=result,provenance='multimodal_identity')
