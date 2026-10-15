"""Own-party configuration panel, separate from field status and active occupancy."""
import cv2
from .visual_evidence import normalized_box, consensus


def layout(image):
    h,w=image.shape[:2]
    if not 1.9<w/h<2.35:return None
    x,y,X,Y=normalized_box(image,(.36,.06,.71,.88))
    center=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
    if ((center[:,:,0]>100)&(center[:,:,0]<150)&(center[:,:,1]>60)).mean()<.55:return None
    selected=[]
    for row in range(6):
        top=.185+row*.115
        x,y,X,Y=normalized_box(image,(.118,top,.337,min(.99,top+.105)))
        if Y<=y:return None
        hsv=cv2.cvtColor(image[y:Y,x:X],cv2.COLOR_BGR2HSV)
        fraction=((hsv[:,:,0]>20)&(hsv[:,:,0]<45)&(hsv[:,:,1]>135)&(hsv[:,:,2]>170)).mean()
        a,b,A,B=normalized_box(image,(.114,top+.01,.124,min(.99,top+.10)))
        edge=cv2.cvtColor(image[b:B,a:A],cv2.COLOR_BGR2HSV)
        border=((edge[:,:,0]>20)&(edge[:,:,0]<45)&(edge[:,:,1]>135)&(edge[:,:,2]>170)).mean()
        if fraction>.22 or border>.15:selected.append(row)
    if len(selected)!=1:return None
    row=selected[0];top=.185+row*.115
    return dict(side='self',selected_party_row=row,slot=None,basis='own-party-selected-row-v1',rois={
        'species':(.14,top+.014,.24,top+.053),'hp':(.14,top+.058,.205,top+.099),
        'ability_label':(.415,.683,.485,.738),'ability':(.565,.683,.670,.738),
        'item_label':(.415,.78,.485,.837),'item':(.565,.78,.670,.837)})


def parse(readings,selection):
    from .visual_evidence import parse_detail
    if not selection:return dict(status='unresolved')
    # The literal captions distinguish this from move-description and target UI.
    for key,text in [('ability_label','特性'),('item_label','持有物')]:
        votes={r['config_id'] for r in readings.get(key,[]) if r['text'].strip()==text and r['confidence']>=.9}
        if len(votes)<2:return dict(status='unresolved',reason='party_panel_captions_unconfirmed')
    result=parse_detail(readings,{})
    result['status']='supported' if result['species'] and result['hp'] else 'unresolved'
    result['selection']=selection
    return result
