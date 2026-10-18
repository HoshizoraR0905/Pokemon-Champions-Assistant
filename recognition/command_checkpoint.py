"""Bounded normal-command verification; no OCR, model positions or battle state."""
from copy import deepcopy
import cv2
import numpy as np
from recognition import box, color_fraction
from recognition.fast_profile import independent_cards, normalized, difference

VERSION='normal-command-checkpoint-v1'
SLOT_REGIONS={'own_active_1':('self','left',(.139,.847,.226,.887)),
              'own_active_2':('self','right',(.307,.847,.394,.887)),
              'opponent_active_1':('opponent','left',(.624,.051,.722,.084)),
              'opponent_active_2':('opponent','right',(.790,.051,.888,.084))}


def inspect_command(image):
    """Require both round decision controls, ordinary HUDs and overlay exclusion.

    Native layout only. Four names or a COMMAND label alone never qualify.
    """
    result=dict(version=VERSION,normal_controls=False,eligible=False,visible_slots=[],
                reason='unsupported_layout',command_context=False)
    if image.shape[:2]!=(603,1311):return result
    controls=[]
    for roi in ((.815,.48,.925,.695),(.775,.68,.89,.90)):
        x,y,X,Y=box(image,roi);hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
        white=((hsv[:,:,1]<100)&(hsv[:,:,2]>170)).astype('uint8')*255
        white=cv2.morphologyEx(white,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        contours,_=cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        candidates=[]
        for c in contours:
            a,b,w,h=cv2.boundingRect(c);area=cv2.contourArea(c)
            if 90<=w<=125 and 90<=h<=125 and .90<w/h<1.10 and .70<area/(w*h)<.86:
                purple=((hsv[b:b+h,a:a+w,0]>110)&(hsv[b:b+h,a:a+w,0]<155)
                        &(hsv[b:b+h,a:a+w,1]>90)).mean()
                if purple>.30:candidates.append([x+a,y+b,x+a+w,y+b+h])
        controls.append(candidates)
    result.update(control_bounds=controls,reason='normal_round_controls_absent')
    if not all(len(c)==1 for c in controls):return result
    from recognition.ui_regions import inspect_ui
    ui=inspect_ui(image)
    if ui.get('overlay') or ui['phase'] in {'team_preview','team_configuration','pokemon_selection','switch_selection','move_selection','move_target_selection'}:
        result.update(reason='overlay_or_selection',overlay=ui.get('overlay'),phase=ui['phase'])
        return result
    # Reject lingering move rows even when the broad phase classifier is unsure.
    rows=[color_fraction(image,(.70,.44+i*.118,.735,.49+i*.118),'purple') for i in range(4)]
    if all(p>.35 for p in rows):result['reason']='move_rows_visible';return result
    cards=independent_cards(image)
    visible=[('own' if side=='own' else 'opponent')+'_active_'+str(i+1) for side,i,_,_ in cards]
    complete=set(visible)==set(SLOT_REGIONS)
    result.update(normal_controls=True,eligible=complete,visible_slots=visible,command_context=True,
                  phase=ui['phase'],reason='normal_four_hud_command' if complete else 'incomplete_active_huds')
    return result


class CommandCheckpointSchedule:
    """Two stable observations; one attempt, including unresolved, per phase.

    Menu/overlay navigation retains the phase. A live action or a sustained
    absence of decision UI closes it. State is serializable for pipeline resume.
    """
    def __init__(self):
        self.phase=0;self.active=False;self.attempted=False;self.last_context=None
        self.previous=None;self.last_time=None

    def observe(self,row,inspection,signatures):
        t=row['timestamp']
        if self.last_time is not None and t<=self.last_time:raise ValueError('Command frames must be chronological')
        self.last_time=t
        actions={e['event_type'] for e in row.get('occurrence_decision',{}).get('events',[])}
        action=bool(actions&{'move_execution','send_out','switch_out','faint','position_change'})
        context=inspection.get('command_context') or row.get('command',{}).get('active') or row['ui'].get('phase') in {'move_selection','move_target_selection','pokemon_selection','switch_selection'}
        if action:
            self.active=False;self.previous=None;self.last_context=None
            return None
        if not context:
            self.previous=None
            if self.last_context is not None and t-self.last_context>2:
                self.active=False
            return None
        if not self.active:
            self.phase+=1;self.active=True;self.attempted=False
        self.last_context=t
        if not inspection.get('normal_controls'):
            self.previous=None;return None
        previous=self.previous
        self.previous=dict(timestamp=t,signatures=deepcopy(signatures),source_id=row['source_id'])
        stable=(previous and t-previous['timestamp']<=1.1 and set(previous['signatures'])==set(signatures)
                and all(difference(np.asarray(previous['signatures'][k],dtype=np.uint8),np.asarray(v,dtype=np.uint8))<=.08 for k,v in signatures.items()))
        if self.attempted or not stable:return None
        self.attempted=True
        return dict(phase_id='command:'+str(self.phase),stable=True,previous_source_id=previous['source_id'],
                    previous_timestamp=previous['timestamp'],inspection=deepcopy(inspection),attempt=1)

    def inspect(self,row,image):
        inspection=inspect_command(image)
        signatures={key:normalized(image,box(image,roi),text=True).tolist()
                    for key,(_,_,roi) in SLOT_REGIONS.items()} if inspection.get('normal_controls') else {}
        return inspection,self.observe(row,inspection,signatures)


def capture_checkpoint_huds(row,image,backend):
    """At most four missing names at the single scheduled attempt; no icons/HP.

    Existing same-frame OCR and icons are retained. A missing name may be read
    once; an unreadable current reading remains inconclusive without retries.
    """
    from dataclasses import asdict
    monsters={m['slot']:deepcopy(m) for m in row.get('snapshot',{}).get('pokemon',[])}
    observations=[]
    for key,(_,_,roi) in SLOT_REGIONS.items():
        mon=monsters.get(key,{})
        if not mon.get('species') or mon.get('identity_reused_from'):
            mon=dict(slot=key,species=asdict(backend.read(image,box(image,roi),italic=True,independent=True)),icon={})
        observations.append(mon)
    row['command_checkpoint']['hud_observations']=observations


def schedule_checkpoint(row,image,schedule,backend,counts):
    """Production acquisition boundary, also usable with mocked recognition."""
    inspection,attempt=schedule.inspect(row,image)
    row['command_inspection']=inspection
    if attempt:
        row['command_checkpoint']=attempt
        if inspection['eligible']:capture_checkpoint_huds(row,image,backend)
        counts['command_checkpoint_attempts']+=1


def checkpoint_event(row,battle_id):
    from battle_events.schema import BattleEvent,Evidence,stable_id
    checkpoint=row.get('command_checkpoint')
    if not checkpoint:return None
    visible=set(checkpoint['inspection']['visible_slots']);monsters={m['slot']:m for m in checkpoint.get('hud_observations',row.get('snapshot',{}).get('pokemon',[]))}
    observations=[]
    for key,(side,slot,roi) in SLOT_REGIONS.items():
        mon=monsters.get(key,{})
        observations.append(dict(region_id=key,side=side,slot=slot,visible=key in visible,
            species=deepcopy(mon.get('species') or {}),icon=deepcopy(mon.get('icon') or {}),
            identity_reused_from=mon.get('identity_reused_from'),timestamp=row['timestamp'],
            source_id=row['source_id'],sha256=row['sha256'],image=row['image'],name_roi=list(roi)))
    return BattleEvent(stable_id(battle_id,'command-checkpoint:'+row['source_id']),
        'command_checkpoint','field',None,None,'Normal command four-slot checkpoint',{},None,
        [Evidence('command_hud_checkpoint',row['source_id'],[row['sha256']],
                  dict(timestamp=row['timestamp'],image=row['image']))],None,'supported',[],
        dict(battle_id=battle_id,observation_time=row['timestamp'],checkpoint=deepcopy(checkpoint),
             observations=observations)).to_dict()
