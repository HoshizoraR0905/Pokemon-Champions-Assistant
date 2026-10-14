"""Opt-in ROI change-detection experiment, deliberately outside scheduling.

Proposals are visual fingerprints, not recognized values/events. Every raw
change remains a conservative fallback. No policy in StreamingPipeline changes.
"""
import hashlib
import cv2
import numpy as np
from recognition import box, color_fraction
from recognition.phases import classify_phase

MESSAGE = (.22,.685,.64,.797)
MESSAGE_LINES = [(.22,.685,.64,.735),(.22,.745,.64,.797)]
PARTY_LIST = (.115,.185,.345,.89)
# Visual boundaries checked on battle_screen/move_selection, 270/280 and target
# fixtures. Text coordinates reuse Recognizer/RegionPlanner verbatim.
PROVENANCE = {
    'hud': ['tests/fixtures/battle_screen.png','tests/fixtures/move_selection.png'],
    'moves': ['tests/fixtures/move_selection.png','reports/M1.4-evidence/m14_boundary_268.jpg'],
    'message': ['tests/fixtures/m15_message_move.png','tests/fixtures/m15_message_flinch.png'],
    'party': ['reports/M1.4-evidence/m14_boundary_270.jpg'],
    'replacement': ['reports/M1.4-evidence/m14_boundary_280.jpg'],
    'targets': ['tests/fixtures/m14_target_selection_380.png','tests/fixtures/m14_target_selection_660.png'],
}


def digest(array):
    return hashlib.sha256(str(array.shape).encode()+array.tobytes()).hexdigest()


def crop(image, roi):
    x1,y1,x2,y2 = box(image,roi)
    return image[y1:y2,x1:x2]


def white_mask(image):
    hsv = cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    return ((hsv[:,:,1]<70)&(hsv[:,:,2]>200)).astype(np.uint8)*255


def anchored_text(image):
    """Compare original white pixels in left-anchored line groups.

    Dilation finds groups only; never compare the dilated pixels themselves.
    No minimum character/word count. Unanchored/faint text still has raw fallback.
    """
    mask=white_mask(image)
    h,w=mask.shape
    joined=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_RECT,(max(3,round(h*.4)),3)))
    n,labels,stats,_=cv2.connectedComponentsWithStats(joined)
    boxes=sorted([tuple(st[:4]) for st in stats[1:]],key=lambda b:b[0])
    selected=np.zeros_like(mask)
    right=None
    for x,y,bw,bh in boxes:
        if right is None:
            if x > max(2,round(w*.03)):continue
        elif x-right > h*.8:
            break
        selected[y:y+bh,x:x+bw] = mask[y:y+bh,x:x+bw]
        right=max(right or 0,x+bw)
    return selected


def bar_signature(image):
    """Color occupancy endpoints, insensitive to green/yellow/red brightness.

    The sampled levels are retained at every timestamp. Bar-only movement is an
    intermediate display observation, never a separately inferred damage event.
    """
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    hue,sat,value=cv2.split(hsv)
    # Yellow/green HP bars span hue 20..80; red spans 0..10/170..179.
    fill=(sat>100)&(value>100)&(((hue>15)&(hue<85))|(hue<10)|(hue>170))
    columns=np.mean(fill,axis=0)>.4
    idx=np.flatnonzero(columns)
    color_counts={'red':int(np.sum(fill&((hue<10)|(hue>170)))),
                  'yellow':int(np.sum(fill&(hue>=10)&(hue<35))),
                  'green':int(np.sum(fill&(hue>=35)&(hue<85)))}
    level={'left_column':int(idx[0]) if idx.size else None,
           'right_column':int(idx[-1]) if idx.size else None,
           'filled_column_fraction':float(np.mean(columns)),
           'dominant_color_candidate':max(color_counts,key=color_counts.get) if idx.size else None,
           'status':'visible_bar_geometry' if idx.size else 'unresolved_bar_geometry'}
    return tuple(level.values()),level


def highlight_signature(image):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    h,w=hsv.shape[:2]
    border=np.zeros((h,w),bool)
    dy,dx=max(1,round(h*.08)),max(1,round(w*.025))
    border[:dy]=True;border[-dy:]=True;border[:,:dx]=True;border[:,-dx:]=True
    green=(hsv[:,:,0]>20)&(hsv[:,:,0]<90)&(hsv[:,:,1]>110)&(hsv[:,:,2]>140)
    fraction=float(np.mean(green[border]))
    return 'green_border_candidate' if fraction>.08 else 'no_green_border_candidate'


def fields_for(image,phase):
    groups={'messages':{'envelope':MESSAGE,'fields':[(f'line_{i}',r,'anchored') for i,r in enumerate(MESSAGE_LINES)]}}
    if phase in {'battle_screen','move_selection'}:
        for side,offsets in [('own',[0,.168]),('opponent',[0,.166])]:
            for i,offset in enumerate(offsets):
                if side=='own':
                    envelope=(.084+offset,.847,.260+offset,.959)
                    name=(.139+offset,.847,.226+offset,.887)
                    number=(.176+offset,.915,.243+offset,.955)
                    bar=(.146+offset,.905,.244+offset,.929)
                else:
                    envelope=(.567+offset,.051,.737+offset,.154)
                    name=(.624+offset,.051,.722+offset,.084)
                    number=(.681+offset,.113,.727+offset,.154)
                    bar=(.631+offset,.103,.728+offset,.128)
                groups[f'hud_{side}_{i}']={'envelope':envelope,
                    'fields':[('name',name,'white'),('hp_text',number,'white'),('hp_bar',bar,'bar')],
                    'residual_guard':True}
    if phase=='move_selection':
        fields=[]
        for i in range(4):
            y=.444+i*.118
            fields.extend([(f'name_{i}',(.75,y,.859,y+.048),'white'),
                           (f'pp_current_{i}',(.875,y-.006,.903,y+.031),'white'),
                           (f'pp_maximum_{i}',(.897,y+.032,.910,y+.06),'white'),
                           (f'highlight_{i}',(.693,y-.022,.919,y+.086),'highlight')])
        groups['move_controls']={'envelope':(.693,.422,.919,.884),'fields':fields}
    if phase in {'pokemon_selection','switch_selection'}:
        fields=[]
        for i in range(6):
            y=.203+i*.116
            fields.extend([(f'name_{i}',(.145,y,.275,y+.037),'white'),
                           (f'hp_{i}',(.145,y+.042,.24,y+.08),'white'),
                           (f'highlight_{i}',(.115,y-.014,.342,y+.082),'highlight')])
        groups['party_list']={'envelope':PARTY_LIST,'fields':fields,'residual_guard':True}
    if phase=='switch_selection':
        anchors=[(color_fraction(image,(.16,float(y),.35,float(y)+.20),'purple'),float(y))
                 for y in np.arange(.24,.72,.02)]
        score,y=max(anchors)
        top=max(.0,y-.02)
        # Popover edges measured on 280s image; scan anchor comes from M1.4.
        roi=(.16,top,.365,top+.24)
        groups['replacement_controls']={'envelope':roi,
            'fields':[('replacement_text',(.18,top+.025,.35,top+.115),'white'),
                      ('exit_text',(.18,top+.125,.35,top+.22),'white'),
                      ('popover_outline',roi,'highlight')],
            'anchor_score':score,'anchor_method':'existing_M1.4_vertical_popover_scan'}
    if phase=='move_target_selection':
        fields=[]
        for side,y in [('opponent',.256),('own',.589)]:
            for i,x in enumerate([.374,.586]):
                fields.extend([(f'{side}_name_{i}',(x,y,x+.09,y+.052),'white'),
                               (f'{side}_hp_{i}',(x+.025,y+.067,x+.09,y+.11),'white')])
        fields.extend([(f'selected_move_{i}',r,'white') for i,r in enumerate(
            [(.355,.46,.475,.51),(.565,.46,.685,.51)])])
        groups['target_controls']={'envelope':(.30,.185,.70,.77),'fields':fields,'residual_guard':True}
    return groups


class FocusedROIMonitor:
    """Per-ROI experiment with raw fallback and timestamped intermediate rows."""
    def __init__(self):
        self.previous={}
        self.last_timestamp=None
        self.last_source=None

    def inspect(self,frame,phase=None):
        if self.last_source is not None and frame.source!=self.last_source:
            raise ValueError('Use a separate monitor per source/experiment')
        if self.last_timestamp is not None and frame.timestamp<=self.last_timestamp:
            raise ValueError('Experiment timestamps must increase')
        phase=phase or classify_phase(frame.image)[0]
        profiles=fields_for(frame.image,phase)
        rows=[]
        for label in self.previous.keys()-profiles.keys():
            rows.append({'label':label,'visibility':'exit','raw_trigger':True,
                         'proposal_trigger':True,'conservative_trigger':True,'components':[]})
        current={}
        for label,profile in profiles.items():
            previous=self.previous.get(label)
            raw=digest(crop(frame.image,profile['envelope']))
            components=[];signatures={};bar_levels={}
            for name,roi,mode in profile['fields']:
                pixels=crop(frame.image,roi)
                if mode=='bar':sig,level=bar_signature(pixels);bar_levels[name]=level
                elif mode=='highlight':sig=highlight_signature(pixels)
                elif mode=='anchored':sig=digest(anchored_text(pixels))
                else:sig=digest(white_mask(pixels))
                sig=(tuple(roi),sig)
                signatures[name]=sig
                components.append({'label':name,'normalized_roi':roi,'pixel_roi':box(frame.image,roi),
                    'mode':mode,'changed':previous is None or previous['fields'].get(name)!=sig})
            changed=[c['label'] for c in components if c['changed']]
            if profile.get('residual_guard'):
                residual=crop(frame.image,profile['envelope']).copy()
                ex1,ey1,ex2,ey2=box(frame.image,profile['envelope'])
                for name,roi,mode in profile['fields']:
                    x1,y1,x2,y2=box(frame.image,roi)
                    residual[max(0,y1-ey1):min(ey2,y2)-ey1,
                             max(0,x1-ex1):min(ex2,x2)-ex1]=0
                sig=digest(residual)
                signatures['unresolved_indicator_pixels']=sig
                components.append({'label':'unresolved_indicator_pixels','mode':'raw_residual',
                    'changed':previous is None or previous['fields'].get('unresolved_indicator_pixels')!=sig,
                    'role':'fallback_only','status':'not_a_validated_status_recognizer'})
            raw_changed=previous is None or previous['raw']!=raw
            proposal=previous is None or bool(changed)
            # Status/portraits, target highlights and unknown overlay pixels have
            # no validated foreground grammar: retain their residual raw guard.
            observation_kind=('bar_intermediate_or_display_change' if changed==['hp_bar'] else
                              'text_or_indicator_change_candidate' if changed else 'unchanged_foreground_candidate')
            rows.append({'label':label,'visibility':'entry' if previous is None else 'visible',
                'roi_observation_id':hashlib.sha256(f'{frame.source}:{frame.index}:{label}:{raw}'.encode()).hexdigest(),
                'normalized_roi':profile['envelope'],'pixel_roi':box(frame.image,profile['envelope']),
                'raw_trigger':raw_changed,'proposal_trigger':proposal,
                'conservative_trigger':raw_changed or proposal,
                'raw_only_ambiguity':raw_changed and not proposal,
                'residual_guard_required':profile.get('residual_guard',False),
                'components':components,'bar_levels':bar_levels,
                'observation_kind':observation_kind,'gameplay_event':False,
                'hp_status_semantics':'Bar-only versus text/indicator pixels; actual HP/status values and animation cause remain unconfirmed.',
                'anchor_method':profile.get('anchor_method'),'anchor_score':profile.get('anchor_score')})
            current[label]={'raw':raw,'fields':signatures}
        self.previous=current
        self.last_source,self.last_timestamp=frame.source,frame.timestamp
        return {'source':frame.source,'frame_index':frame.index,'timestamp':frame.timestamp,
                'phase':phase,'roi_observations':rows,
                'scope':'Experimental visual observations only; raw fallback remains authoritative.'}
