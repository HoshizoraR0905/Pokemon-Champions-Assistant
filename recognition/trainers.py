"""Observed team-preview display names; internal side IDs are not trainer IDs."""
import cv2
from battle_events.schema import Participant


def recognize_preview_trainers(image, backend, *, source, sha256, timestamp=None, timestamp_uncertainty=None):
    h,w=image.shape[:2];observations={}
    for side,bounds,color in [('self',(.165,.058,.305,.11),'purple'),('opponent',(.745,.058,.888,.11),'red')]:
        box=tuple(round(v*(w if i%2==0 else h)) for i,v in enumerate(bounds))
        x1,y1,x2,y2=box;hsv=cv2.cvtColor(image[y1:y2,x1:x2],cv2.COLOR_BGR2HSV)
        colored=((hsv[:,:,0]>165)|(hsv[:,:,0]<10))&(hsv[:,:,1]>100) if color=='red' else (hsv[:,:,0]>=110)&(hsv[:,:,0]<=145)&(hsv[:,:,1]>70)
        # Unrecognized preview layout must not calibrate ownership colors.
        if colored.mean()<.35:continue
        o=backend.read(image,box)
        observations[side]={'display_name':o.raw_text if o.confidence>=.75 and o.raw_text else None,
            'raw_text':o.raw_text,'unique_trainer_id':None,'ocr_confidence':o.confidence,
            'evidence':[{'source':source,'sha256':sha256,'box':box,'timestamp':timestamp,
                         'timestamp_uncertainty_seconds':timestamp_uncertainty,'color':color,
                         'basis':'visible_team_preview_panel'}]}
    return observations
