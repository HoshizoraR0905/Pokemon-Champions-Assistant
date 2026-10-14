"""Reuse the existing region geometry, OCR, entity resolver and icon backend."""
from dataclasses import asdict, replace
from models import Observation
from recognition import Recognizer, box
from recognition.entities import EntityResolver
from recognition.phases import _message_glyphs


class PlanningOCR:
    warnings = []
    def __init__(self):
        self.calls = []
    def read(self, image, bounds, numeric=False, multiline=False, italic=False):
        self.calls.append((bounds, numeric, multiline, italic))
        return Observation(region=bounds)


class RegionPlanner:
    def __init__(self):
        self.recorder = PlanningOCR()
        self.geometry = Recognizer(self.recorder, knowledge=False, icons=False)

    def plan(self, frame, phase, *, include_icons=True):
        self.recorder.calls.clear()
        result = self.geometry.recognize(frame)
        regions = []
        for bounds, numeric, multiline, italic in self.recorder.calls:
            label = next((k for k,v in result.regions.items() if v == bounds), 'unlabelled')
            if label == 'battle_message':
                continue  # independent high-recall message path below
            regions.append({'label':label, 'bounds':bounds, 'kind':'ocr', 'priority':1,
                            'numeric':numeric, 'multiline':multiline, 'italic':italic,
                            'required': label != 'condition_banner',
                            'cache_policy': 'white_glyphs' if label.startswith(('own_name','opponent_name','own_hp','opponent_hp','move_name','move_pp')) else 'raw'})
        if include_icons:
            for label,bounds in result.regions.items():
                if 'icon' in label:
                    regions.append({'label':label, 'bounds':bounds, 'kind':'icon',
                                    'priority':2, 'required':True})
        # Probe resolution even when the phase heuristic misses the message.
        # Exact region changes schedule reads; scene similarity never deduplicates text.
        if phase in {'battle_message','battle_animation','unknown','battle_screen'}:
            regions.insert(0, {'label':'battle_message', 'bounds':box(frame.image,(.22,.685,.64,.797)),
                              'kind':'ocr', 'priority':0, 'numeric':False, 'multiline':True,
                              'italic':False, 'required':phase == 'battle_message' or _message_glyphs(frame.image) >= 4})
        return regions


class RegionBackend:
    """Exactly one initialized OCR model, called by one worker. Icons are independent."""
    def __init__(self, ocr, icons=None, resolver=None):
        self.ocr, self.icons = ocr, icons
        self.resolver = resolver or EntityResolver()

    def recognize(self, frame, region):
        if region['kind'] == 'icon':
            if self.icons is None:
                return {'status':'unavailable', 'provenance':'icon_backend_unavailable'}
            return asdict(self.icons.identify(frame.image, region['bounds']))
        obs = self.ocr.read(frame.image, region['bounds'], region.get('numeric',False),
                            region.get('multiline',False), italic=region.get('italic',False))
        label = region['label']
        message_validation = None
        if label == 'battle_message':
            # Visible text can be short or partially revealed during animation.
            # Length/language is not evidence that an OCR observation is invalid.
            candidate = str(obs.value).strip() if obs.value is not None else ''
            accepted = bool(candidate) and obs.confidence >= .8
            message_validation = {
                'status': 'accepted' if accepted else 'unresolved',
                'reason': 'confidence_threshold_met' if accepted else
                          'low_confidence' if candidate else 'no_accepted_ocr_text',
                'confidence_threshold': .8,
                'semantics': 'visible text observation, not a confirmed gameplay event',
            }
            obs = replace(obs, value=obs.value if accepted else None,
                          raw_text=obs.raw_text or candidate)
        # Preserve canonical references without introducing battle-state inference.
        kind = ('species' if 'name' in label and 'move' not in label else
                'move' if 'move' in label and 'pp' not in label else
                'ability' if label.startswith('ability') else
                'item' if label.startswith(('item','team_item')) else None)
        if kind:
            obs = self.resolver.resolve(obs,kind,region_kind=kind)
        result = asdict(obs)
        if message_validation is not None:
            result['message_validation'] = message_validation
        result['backend_warnings'] = list(self.ocr.warnings)
        return result
