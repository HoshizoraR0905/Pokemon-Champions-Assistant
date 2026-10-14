"""Cheap normalized ROI monitoring; similarity never confirms a gameplay event.

Rates govern periodic work. A relevant visual change overrides a routine deadline;
message evidence is inspected independently of the preceding phase.
"""
from collections import deque
from dataclasses import dataclass, asdict
import base64
import hashlib
import math

import cv2
import numpy as np
from recognition import box

# Taken from Recognizer geometry and checked against supplied landscape fixtures.
ROIS = {
    'message': (.22, .685, .64, .797),
    'own_hud_0': (.084, .847, .243, .959),
    'own_hud_1': (.252, .847, .411, .959),
    'opponent_hud_0': (.567, .051, .727, .154),
    'opponent_hud_1': (.733, .051, .893, .154),
    'conditions': (.21, .052, .43, .09),
    'controls': (.12, .15, .91, .88),
}


@dataclass(frozen=True)
class MonitoringRates:
    acquisition_fps: float = 5.
    phase_fps: float = 2.
    message_fps: float = 5.
    routine_fps: float = 2.
    icon_fps: float = 1.
    stable_refresh_seconds: float = 2.
    candidate_capacity: int = 16
    message_ocr_fps: float = 5.
    def __post_init__(self):
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be positive and finite')
        if not isinstance(self.candidate_capacity, int):
            raise ValueError('candidate_capacity must be an integer')


def foreground(image, bounds):
    x1, y1, x2, y2 = bounds
    crop = image[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return ((hsv[:, :, 1] < 70) & (hsv[:, :, 2] > 200)).astype('uint8') * 255


class ROIMonitor:
    def __init__(self, rates=None):
        self.rates = rates or MonitoringRates()
        self.previous = {}
        self.last_phase_time = None
        self.last_message_time = None
        self.last_routine_time = None
        self.last_icon_time = None
        self.last_message_ocr_time = None
        self.candidates = deque(maxlen=self.rates.candidate_capacity)
        self.metrics = {'roi_checks':0, 'message_checks':0, 'phase_checks':0,
                        'routine_checks':0, 'icon_checks':0, 'candidate_evictions':0,
                        'message_monitor_gaps':0, 'blank_message_probes_avoided':0}
        self.metrics['deferred_message_versions'] = 0

    def reset(self):
        self.previous.clear()
        self.last_phase_time = self.last_message_time = None
        self.last_routine_time = self.last_icon_time = None
        self.last_message_ocr_time = None

    def message_ocr_due(self, timestamp, *, phase_entry=False):
        return (phase_entry or self.last_message_ocr_time is None or
                timestamp-self.last_message_ocr_time >= 1/self.rates.message_ocr_fps-1e-6)

    def inspect(self, frame):
        changes = []
        for label, roi in ROIS.items():
            bounds = box(frame.image, roi)
            x1,y1,x2,y2 = bounds
            crop = frame.image[y1:y2,x1:x2]
            digest = hashlib.sha256(str(crop.shape).encode()+crop.tobytes()).hexdigest()
            if self.previous.get(label) != digest:
                changes.append(label)
            self.previous[label] = digest
        self.metrics['roi_checks'] += 1
        # Cheap ROI guards always run on acquired frames. These detect short
        # control/HUD/message changes even between scheduled phase checks.
        phase_due = (self.last_phase_time is None or
                     frame.timestamp-self.last_phase_time >= 1/self.rates.phase_fps-1e-6 or
                     bool(changes))
        message_due = (self.last_message_time is None or
                       frame.timestamp-self.last_message_time >= 1/self.rates.message_fps-1e-6 or
                       'message' in changes)
        gap = (self.last_message_time is not None and
               frame.timestamp-self.last_message_time > 1/self.rates.message_fps+1e-6)
        if gap:
            self.metrics['message_monitor_gaps'] += 1
        if phase_due:
            self.last_phase_time = frame.timestamp
            self.metrics['phase_checks'] += 1
        if message_due:
            self.last_message_time = frame.timestamp
            self.metrics['message_checks'] += 1
        due = {}
        for kind in ['routine', 'icon']:
            attr = f'last_{kind}_time'
            last = getattr(self,attr)
            due[kind] = last is None or frame.timestamp-last >= 1/getattr(self.rates,f'{kind}_fps')-1e-6 or bool(changes)
            if due[kind]:
                setattr(self,attr,frame.timestamp)
                self.metrics[f'{kind}_checks'] += 1
        return {'changed_rois':changes, 'phase_check':phase_due,
                'message_check':message_due, 'message_monitor_gap':gap,
                'routine_check':due['routine'], 'icon_check':due['icon'],
                'rates':asdict(self.rates)}

    def message_has_candidate(self, image, region):
        # No glyph-count/language gate: even a single bright pixel is a
        # potential candidate. Only entirely absent foreground skips OCR.
        return bool(np.any(foreground(image, region['bounds'])))

    def preserve_candidate(self, frame, region, reason):
        x1,y1,x2,y2 = region['bounds']
        crop = frame.image[y1:y2,x1:x2].copy()
        digest = hashlib.sha256(crop.tobytes()).hexdigest()
        record = {'source':frame.source, 'frame_index':frame.index,
                  'timestamp':frame.timestamp, 'capture_monotonic':frame.capture_monotonic,
                  'region':region['bounds'], 'label':region['label'],
                  'sha256':digest, 'reason':reason, 'status':'unresolved_candidate'}
        # The downstream evidence sink receives the candidate before the bounded
        # in-memory ring can evict it. No full-size frame accumulation is needed.
        ok, encoded = cv2.imencode('.png',crop)
        if not ok:
            raise ValueError('Cannot encode candidate evidence')
        record['png_base64'] = base64.b64encode(encoded).decode('ascii')
        evicted = self.candidates[0][0] if len(self.candidates)==self.candidates.maxlen else None
        if evicted:
            self.metrics['candidate_evictions'] += 1
        self.candidates.append((record,crop))
        return record, evicted
