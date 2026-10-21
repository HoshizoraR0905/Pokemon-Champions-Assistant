"""Native selected Fight variant, confined to the visual evidence sidecar."""
from copy import deepcopy
import cv2
import numpy as np
from recognition.fast_profile import independent_cards

VERSION='selected-native-fight-v1'


def selected_fight(image,inspection,ui):
    result=deepcopy(inspection)
    if image.shape[:2]!=(603,1311) or result.get('normal_controls'):return result
    controls=result.get('control_bounds',[])
    if len(controls)!=2 or controls[0] or len(controls[1])!=1:return result
    if ui.get('phase')!='battle_screen' or ui.get('overlay') not in (None,'status_overlay'):return result
    # The pressed native Fight button contracts and changes purple to yellow.
    # Require its annulus and central purple emblem, plus the independently
    # detected ordinary Pokemon control and all four ordinary HUD cards.
    crop=image[298:407,1087:1196];hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    y,x=np.ogrid[:109,:109];radius=np.sqrt((x-54)**2+(y-54)**2)
    yellow=(hsv[:,:,0]>=15)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>100)&(hsv[:,:,2]>150)
    purple=(hsv[:,:,0]>110)&(hsv[:,:,0]<155)&(hsv[:,:,1]>90)
    if yellow[(radius>=32)&(radius<=40)].mean()<.60 or purple[radius<25].mean()<.25:return result
    cards=independent_cards(image)
    visible=[side+'_active_'+str(i+1) for side,i,_,_ in cards]
    if len(set(visible))!=4:return result
    result.update(normal_controls=True,eligible=True,visible_slots=visible,reason='selected_yellow_fight_and_native_pokemon_four_huds',
        visual_variant=VERSION,variant_evidence=dict(roi=[1087,298,1196,407],yellow_annulus_threshold=.60,purple_emblem_threshold=.25))
    return result


FLEX_VERSION='context-native-controls-v2.1'


def flexible_controls(image,inspection,ui):
    """Return native button geometry and independent cards, without a HUD quorum.

    Geometry is evidence only. The temporal estimator must apply timer, occupancy,
    overlay, phase-continuity and pending-selection gates before accepting it.
    """
    result=deepcopy(inspection)
    if image.shape[:2]!=(603,1311):return result
    if ui.get('phase') in ('battle_animation','unknown'):
        from recognition.ui_regions import inspect_ui
        refreshed=inspect_ui(image)
        if refreshed.get('overlay')=='status_overlay':result['command_panel']='status_overlay'
    if ui.get('phase') in ('team_preview','team_configuration','move_selection','move_target_selection','pokemon_selection','switch_selection'):return result
    if ui.get('overlay') not in (None,'status_overlay'):return result
    controls=[]
    for cx,cy in ((1141,352),(1092,474)):
        crop=image[cy-100:cy+101,cx-100:cx+101];hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
        white=(hsv[:,:,1]<120)&(hsv[:,:,2]>155)
        yellow=(hsv[:,:,0]>=15)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>100)&(hsv[:,:,2]>150)
        mask=cv2.morphologyEx((white|yellow).astype('uint8')*255,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        candidates=[]
        for contour in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]:
            x,y,w,h=cv2.boundingRect(contour);area=cv2.contourArea(contour)
            if not (70<=w<=132 and 70<=h<=132 and .85<w/h<1.17 and .62<area/(w*h)<.90):continue
            if not (-55<=x+w/2-100<=15 and -10<=y+h/2-100<=55):continue
            yy,xx=np.ogrid[:201,:201];core=((xx-(x+w/2))**2+(yy-(y+h/2))**2)<(.30*min(w,h))**2
            purple=(hsv[:,:,0]>110)&(hsv[:,:,0]<155)&(hsv[:,:,1]>90)
            if (purple|yellow)[core].mean()<.50:continue
            candidates.append([cx-100+x,cy-100+y,cx-100+x+w,cy-100+y+h])
        controls.append(candidates)
    if inspection.get('normal_controls') or all(len(c)==1 for c in inspection.get('control_bounds',[[],[]])):
        controls=inspection['control_bounds']
    cards=independent_cards(image)
    slots=[side+'_active_'+str(i+1) for side,i,_,_ in cards]
    dual=all(len(c)==1 for c in controls)
    if dual:
        centers=[((c[0][0]+c[0][2])/2,(c[0][1]+c[0][3])/2) for c in controls]
        dx=centers[1][0]-centers[0][0];dy=centers[1][1]-centers[0][1]
        dual=(-75<=dx<=-10 and 85<=dy<=150)
    result.update(flexible_version=FLEX_VERSION,native_dual_controls=dual,flexible_control_bounds=controls,
        independent_visible_slots=slots)
    if dual:result.update(normal_controls=True,visible_slots=slots,eligible=False,reason='native_dual_geometry; temporal_context_required')
    return result
