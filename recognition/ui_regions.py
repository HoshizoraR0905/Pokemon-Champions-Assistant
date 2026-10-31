"""Opt-in Champions landscape UI contract, separate from biological occupancy.

Reuse established detectors. A geometrically expected crop is never sufficient
visibility evidence. Fixed message rows are calibrated at 1311x603 only; other
scales are unknown until independently validated.
"""
from recognition.regions import hud_roi, FIELD_ROI
from dataclasses import asdict,dataclass,field
import cv2
from recognition import box,classify,color_fraction
from recognition.battle_log import detect_log
from recognition.party_panel import layout as party_layout
from recognition.visual_evidence import detail_layout,popup_regions,line_boxes,stage_arrows
from recognition.visual_adapter import selected_panel_side
from recognition.message_selection import ROI,features,SelectionConfig

PROFILE='champions-landscape-1311x603-ui-v1'
OVERLAYS={'party_overlay','status_overlay','battle_log_overlay','move_description_overlay','unknown_overlay','target_selection'}


@dataclass
class UIRegion:
    region_id:str
    region_type:str
    bounds:list[int]
    visibility:str
    expected:bool=True
    selected_for_ocr:bool=False
    evidence:list[str]=field(default_factory=list)
    semantics:str='observation_only'
    logical_slot:str|None=None
    screen_edge:str|None=None
    fields:dict=field(default_factory=dict)
    ocr:dict|None=None
    canonical:dict|None=None
    admission:dict=field(default_factory=lambda:dict(status='not_submitted',reason='Visibility alone establishes no battle fact'))

    def to_dict(self):return asdict(self)


def message_rows(image):
    """Two fixed visual baseline bands, not brightness-driven OCR sub-lines.

    Verified native bands y=414..443 and 445..474 encompass the supplied message
    rows. Existing line_boxes supplies glyph fragments; each fragment is assigned
    by its pixel baseline/overlap. Rows retain x order, never sentence-based joins.
    """
    if image.shape[:2]!=(603,1311):return dict(status='unknown_layout',rows=[],fragments=[])
    bounds=box(image,ROI);fragments=line_boxes(image,bounds)
    rows=[]
    for top,bottom in [(411,443),(444,478)]:
        matching=[v for v in fragments if min(v[3],bottom)-max(v[1],top)>max(0,(v[3]-v[1])*.35)]
        if matching:
            left=max(bounds[0],min(v[0] for v in matching));right=min(bounds[2],max(v[2] for v in matching))
            # Keep the whole visual row, not detector fragment heights.
            rows.append(dict(bounds=[left,top,right,bottom],fragments=matching,baseline_band=[top,bottom]))
    return dict(status='calibrated_layout',rows=rows,fragments=fragments)


def regroup_tokens(tokens):
    """Geometry-only grouping for OCR detectors that expose boxes.

    Tokens without coordinates remain unassigned; no baselines are invented.
    """
    groups=[];unplaced=[]
    for token in sorted(tokens,key=lambda t:((t.get('box') or [0,1e9,0,1e9])[3],(t.get('box') or [0,0])[0])):
        bounds=token.get('box')
        if not bounds:unplaced.append(token);continue
        baseline=bounds[3];height=bounds[3]-bounds[1]
        matches=[r for r in groups if abs(r['baseline']-baseline)<=min(height,r['height'])*.3]
        if len(matches)==1:matches[0]['tokens'].append(token)
        else:groups.append(dict(baseline=baseline,height=height,tokens=[token]))
    for r in groups:
        r['tokens'].sort(key=lambda t:t['box'][0]);r['text']=''.join(t.get('text','') for t in r['tokens'])
    return dict(rows=sorted(groups,key=lambda r:r['baseline']),unplaced_tokens=unplaced)


def inspect_ui(image):
    h,w=image.shape[:2];phase,confidence,components=classify(image)
    regions=[]
    def add(key,typ,roi,vis,why,**kw):
        region=UIRegion(key,typ,list(box(image,roi)),vis,evidence=why,**kw);regions.append(region);return region
    if (h,w)!=(603,1311):
        for kind in ['battle_message','active_hud','command_menu','field_indicator','ability_banner','information_panel']:
            add(kind,kind,(0,0,1,1),'unknown_layout',['Unvalidated resolution / UI scale'])
        return dict(profile=PROFILE,phase=phase,overlay=None,regions=[r.to_dict() for r in regions])
    # Large panels take precedence. Existing detectors remain independently auditable.
    moves=[color_fraction(image,(.70,.44+i*.118,.735,.49+i*.118),'purple') for i in range(4)]
    selected=[color_fraction(image,(.70,.44+i*.118,.735,.49+i*.118),'green') for i in range(4)]
    move_menu=all(p>.35 or g>.35 for p,g in zip(moves,selected))
    log=detect_log(image);party=party_layout(image);detail=detail_layout(image)
    status_selection=selected_panel_side(image) if detail else None
    status_specific=detail and bool(status_selection or stage_arrows(image))
    overlay=('battle_log_overlay' if log else 'party_overlay' if party else
             'target_selection' if phase=='move_target_selection' else
             'status_overlay' if detail and (status_specific or not move_menu) and phase not in {'team_preview','team_configuration'} else None)
    if overlay is None:
        center=color_fraction(image,(.36,.10,.71,.86),'purple')
        if center>.45 and not move_menu and phase not in {'move_selection','team_preview','team_configuration'}:overlay='unknown_overlay'
    if overlay:
        add('overlay',overlay,(.10,.02,.91,.94),'visible' if overlay!='unknown_overlay' else 'partial',
            ['Existing source-specific panel geometry',*components],
            semantics={'battle_log_overlay':'historical_timing_unknown','party_overlay':'party_membership_not_active',
                       'status_overlay':'selected_subject_not_slot','target_selection':'intended_target_not_execution'}.get(overlay,'unresolved_overlay'),
            fields=dict(selection=party if overlay=='party_overlay' else status_selection,
                        original_event_time=None,opening_is_transition=False,
                        suppressed_command_candidate=bool(move_menu)))
        for typ,roi in [('battle_message',ROI),('active_hud',(.08,.03,.96,.97)),('command_menu',(.68,.4,.94,.94))]:
            add('covered:'+typ,typ,roi,'occluded',['Large overlay obscures or supersedes ordinary layout'])
        return dict(profile=PROFILE,phase=phase,overlay=overlay,regions=[r.to_dict() for r in regions])
    if phase in {'team_preview','team_configuration','pokemon_selection','switch_selection'}:
        kind='party_overlay' if phase in {'pokemon_selection','switch_selection'} else 'information_panel'
        add('panel',kind,(.10,.04,.92,.95),'visible',components,semantics='roster_or_selection_not_active')
        add('message','battle_message',ROI,'occluded',['Non-battle panel active'])
        return dict(profile=PROFILE,phase=phase,overlay=kind,regions=[r.to_dict() for r in regions])
    # Move rows are detected independently of whether every HUD is visible.
    moves=[color_fraction(image,(.70,.44+i*.118,.735,.49+i*.118),'purple') for i in range(4)]
    selected=[color_fraction(image,(.70,.44+i*.118,.735,.49+i*.118),'green') for i in range(4)]
    move_menu=all(p>.35 or g>.35 for p,g in zip(moves,selected))
    add('command','command_menu',(.68,.40,.95,.95),'visible' if move_menu else 'absent',
        ['Four command rows corroborated'] if move_menu else ['No verified move rows'],
        semantics='available_choices_not_execution',fields=dict(menu_type='move_selection' if move_menu else 'none_or_unknown'))
    from recognition.identity_flow import hud_cards
    cards={(s,i):(s,i,o,name) for s,i,o,name in hud_cards(image)}
    for side,offsets in [('own',[0,.168]),('opponent',[0,.166])]:
        for i,o in enumerate(offsets):
            name=hud_roi('own',o,'name') if side=='own' else hud_roi('opponent',o,'name')
            exists=(side,i) in cards
            bar=hud_roi('own',o,'bar') if side=='own' else hud_roi('opponent',o,'bar')
            a,b,A,B=box(image,bar);hsv=cv2.cvtColor(image[b:B,a:A],cv2.COLOR_BGR2HSV)
            green=((hsv[:,:,0]<85)&(hsv[:,:,1]>100)&(hsv[:,:,2]>90)).mean()
            faded=(not exists and color_fraction(image,name,'purple' if side=='own' else 'pink')>.12 and green>.15)
            card=hud_roi('own',o,'card') if side=='own' else hud_roi('opponent',o,'card')
            add(f'{side}_active_{i+1}','active_hud',card,'visible' if exists else 'partial' if faded else 'absent',
                ['Independent name panel and HP-bar structure'] if exists else ['No qualifying card; biological presence unchanged'],
                logical_slot=('self' if side=='own' else 'opponent')+(' / left' if i==0 else ' / right'),
                semantics='ui_card_not_scene_model',fields=dict(card_index=i,side=side,offset=o,
                    name_bounds=box(image,name),bar_bounds=box(image,bar),partial_is_not_identity_support=bool(faded)))
    f=features(image,SelectionConfig());geometry=message_rows(image)
    crop=image[413:481,288:839];gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    flash=float((gray>240).mean())>.97 and float(gray.std())<8
    visible=bool(f['text_geometry']) and bool(geometry['rows']) and not move_menu
    vis='visible' if visible else 'absent' if flash or move_menu or not geometry['fragments'] else 'partial'
    add('message','battle_message',ROI,vis,['Coherent baseline geometry'] if visible else
        ['Uniform bright transition; no text support'] if flash else ['Insufficient / conflicting message geometry'],
        fields=geometry,semantics='live_message_candidate')
    # Field indicator is a distinct top-left label + counter structure. Glyphs
    # alone remain partial until both literal crops are independently read.
    field_bounds=FIELD_ROI;fb=box(image,field_bounds)
    lines=line_boxes(image,fb)
    add('field','field_indicator',field_bounds,'partial' if lines else 'absent',
        ['Possible header glyphs; label/counter confirmation required'] if lines else ['No coherent field-label text'],
        semantics='presence_not_trigger_or_duration',fields=dict(original_event_time=None,counter_meaning='unverified'))
    banners=popup_regions(image)
    for b in banners:
        side=b['side'];edge='left' if side=='self' else 'right'
        regions.append(UIRegion('ability:'+edge,'ability_banner',b['box'],'visible',evidence=['Existing two-line dark-blue banner geometry'],
            screen_edge=edge,semantics='ability_revelation_not_native_or_move',fields=dict(lines=b['lines'],battle_side=None,instance_id=None)))
    if not banners:add('ability','ability_banner',(.08,.31,.94,.46),'absent',['No verified banner structure'])
    return dict(profile=PROFILE,phase=phase,overlay=None,regions=[r.to_dict() for r in regions])


def read_message(image,ocr,region):
    """Visibility before inference; keep original rows and detector comparison."""
    if region['region_type']!='battle_message' or region['visibility']!='visible':
        return dict(selected=False,reason='message_visibility_not_supported',raw_text='',confidence=0.,rows=[])
    rows=[]
    for r in region['fields']['rows']:
        obs=ocr.read(image,tuple(r['bounds']),multiline=False)
        rows.append(dict(bounds=r['bounds'],text=obs.raw_text,confidence=obs.confidence,
                         tokens=asdict(obs.raw_ocr) if obs.raw_ocr else None))
    text='\n'.join(r['text'] for r in rows)
    score=sum(len(r['text'])*r['confidence'] for r in rows)/max(1,sum(len(r['text']) for r in rows))
    return dict(selected=True,source_region_type='battle_message',raw_text=text,confidence=score,rows=rows,
                box=region['bounds'],row_method='verified_visual_baselines',original_fragments=region['fields']['fragments'])
