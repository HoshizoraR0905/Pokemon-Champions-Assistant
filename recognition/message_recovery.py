"""Layout-derived recovery candidates; the canonical move threshold is unchanged."""
from .visual_evidence import line_boxes, normalized_box, variants
from .message_selection import features, SelectionConfig
from knowledge import normalize
import cv2
import re


def message_layout(image,phase):
    if phase not in {'battle_message','battle_animation','unknown','battle_screen'}:return []
    if not features(image,SelectionConfig())['text_geometry']:return []
    bounds=normalized_box(image,(.22,.685,.64,.797));boxes=line_boxes(image,bounds)
    if len(boxes)!=2 or boxes[0][0]-bounds[0]>8:return []
    return boxes


def context_variants(image,bounds,right):
    """Pad short suffixes horizontally, using line height rather than word identity."""
    result=[(name,crop,bounds) for name,crop in variants(image,bounds)]
    x,y,X,Y=bounds;expanded=[x,y,min(right,max(X,x+6*(Y-y))),Y]
    if expanded!=bounds:
        result += [('context_'+name,crop,expanded) for name,crop in variants(image,expanded)]
    return result


def execution_prefix(readings):
    # Only a literal, concordant execution prefix can bootstrap a missing message.
    supported=[r['text'].strip() for r in readings if r['confidence']>=.9]
    if len(supported)<2 or len({normalize(t) for t in supported})!=1:return None
    return supported[0] if re.fullmatch(r'.+使出了[！!。]?',supported[0]) else None
