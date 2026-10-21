"""Historical log headings stay in their own time domain, never live snapshots."""
from copy import deepcopy
from pathlib import Path
import json
from speed_inference.offline import file_hash


def reconstruct(battle_id,*,reviews=None,cached_log=None,root=Path.cwd()):
    groups={}
    for review in (reviews or {}).get('excerpts',[]):
        if review['battle_id']!=battle_id:continue
        n=review['heading_turn']
        if type(n) is not int or n<1:raise ValueError('Invalid historical displayed heading')
        image=Path(root)/review['image']
        checked=image.is_file() and file_hash(image)==review['image_sha256']
        if image.is_file() and not checked:raise ValueError('Reviewed historical frame fingerprint changed')
        groups[n]=dict(id=f'{battle_id}:historical-turn:{n}',number=n,status='partial_historical_log',
            time_domain='historical_log_order; capture time is not execution time',start=None,end=None,
            original_execution_time=None,live_instance_bindings=None,review=deepcopy(review),source_image_hash_checked=checked,
            rows=deepcopy(review['rows']),source_entries=[],numbering_status='agent_visual_review; not independent human ground truth',
            speed_eligible=False,damage_eligible=False,reasons=['decision_time_unknown','live_individual_binding_missing','own_build_and_contemporaneous_modifiers_missing','partial_log_coverage'])
    if cached_log:
        if cached_log.get('battle_id')!=battle_id:raise ValueError('Historical log ownership mismatch')
        for e in cached_log.get('entries',[]):
            n=e.get('turn')
            if type(n) is not int or n<1:continue
            if n not in groups:
                groups[n]=dict(id=f'{battle_id}:historical-turn:{n}',number=n,status='partial_historical_log',
                    time_domain='historical_log_order; capture time is not execution time',start=None,end=None,
                    original_execution_time=None,live_instance_bindings=None,rows=[],source_entries=[],
                    numbering_status='cached OCR heading, independently unverified',speed_eligible=False,damage_eligible=False,
                    reasons=['decision_time_unknown','live_individual_binding_missing','partial_log_coverage'])
            previous=next((x for x in groups[n]['source_entries'] if x.get('entry_id')==e.get('entry_id')),None)
            if previous is not None and previous!=e:raise ValueError('Historical entry revision requires review')
            if previous is None:groups[n]['source_entries'].append(deepcopy(e))
        for group in groups.values():group['assembly_issues']=deepcopy(cached_log.get('assembly_issues',[]))
    return [groups[n] for n in sorted(groups)]
