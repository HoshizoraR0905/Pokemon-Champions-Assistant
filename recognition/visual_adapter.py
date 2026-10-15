"""Convert cached visual facts into ordinary event-sourced observations."""
from copy import deepcopy
from battle_events.schema import BattleEvent, Evidence, stable_id
from .visual_evidence import normalized_box, detail_layout
import cv2


def selected_panel_side(image):
    """Layout-v1 selection border: left pair blue/self, right pair red/opponent.

    A selection identifies the panel side, not an active doubles slot. Unknown
    layouts and multiple highlights are withheld. This UI mapping is provisional.
    """
    if not detail_layout(image):return None
    choices=[]
    for index,x in enumerate((.39,.453,.544,.611)):
        a,b,A,B=normalized_box(image,(x-.025,.038,x+.025,.13))
        hsv=cv2.cvtColor(image[b:B,a:A],cv2.COLOR_BGR2HSV)
        yellow=((hsv[:,:,0]>20)&(hsv[:,:,0]<45)&(hsv[:,:,1]>150)&(hsv[:,:,2]>180)).mean()
        if yellow>.18:choices.append(index)
    if len(choices)!=1:return None
    return dict(side='self' if choices[0]<2 else 'opponent',basis='selected-panel-border-v1',selected_index=choices[0])


def visual_events(row, *, selection=None):
    request=row['request'];kind=request['kind'];parsed=row['parsed'];out=[]
    candidates=parsed if kind=='popup' else [parsed] if kind in {'detail','party_panel'} else []
    for p in candidates:
        if p.get('status')!='supported':continue
        if kind in {'detail','party_panel'} and not selection:continue
        side=p['side'] if kind=='popup' else selection['side']
        fields={k:deepcopy(p[k]) for k in ('ability','item','hp') if p.get(k)}
        if kind=='detail':fields['field']=deepcopy(p.get('field',{}))
        if kind=='detail':fields['stages']={k:v['value'] for k,v in p.get('stages',{}).items()}
        source_kind='ability_popup' if kind=='popup' else 'party_configuration_panel' if kind=='party_panel' else 'selected_detail_panel'
        details=dict(timestamp=request['timestamp'],image=request['image'],sha256=request['sha256'],
                     layout=row['identity'].get('layout'),readings=deepcopy(row['readings']),selection=deepcopy(selection))
        out.append(BattleEvent(stable_id(request['battle_id'],'m234:'+request['sha256']+':'+kind+':'+side),
            'visual_observation',side,deepcopy(p['species']),None,'cached '+source_kind,{},None,
            [Evidence('cached_'+source_kind,request['image'],[request['sha256']],details)],None,'supported',[],
            dict(battle_id=request['battle_id'],observation_time=request['timestamp'],source_kind=source_kind,fields=fields)))
    return out


def move_alternatives(row):
    """Geometry candidates only. EventParser must still establish move execution."""
    if row['request']['kind']!='message':return []
    return [deepcopy(r) for key,rows in row['readings'].items() if key!='line0' for r in rows]
