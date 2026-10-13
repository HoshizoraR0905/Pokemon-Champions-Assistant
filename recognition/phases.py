"""Fast visual phase evidence; no OCR, icons, or battle-state inference."""
import cv2
import numpy as np

from recognition import box, classify


PHASES = frozenset({'team_configuration', 'team_preview', 'battle_screen',
                    'move_selection', 'pokemon_selection', 'switch_selection', 'move_target_selection', 'battle_message',
                    'battle_animation', 'unknown'})


def _message_glyphs(image):
    x1, y1, x2, y2 = box(image, (.22, .685, .64, .797))
    crop = image[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 1] < 70) & (hsv[:, :, 2] > 200)).astype('uint8') * 255
    contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return sum(1 for c in contours if 8 < cv2.boundingRect(c)[3] < crop.shape[0] * .55
               and cv2.contourArea(c) > 10)


def _control_overlay(image):
    """Reject the supplied device control overlay's repeated cyan round controls."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    cyan = ((hsv[:, :, 0] > 85) & (hsv[:, :, 0] < 115)
            & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 130)).astype('uint8') * 255
    contours, _ = cv2.findContours(cyan, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    controls = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        fraction = area / (image.shape[0] * image.shape[1])
        if .001 < fraction < .008 and .75 < w / h < 1.3 and area / (w * h) > .55:
            controls.append((x, y, w, h))
    # Repeated, similarly sized controls in two aligned columns distinguish
    # this overlay from isolated cyan arena effects and battle HUD buttons.
    for left in controls:
        aligned = [c for c in controls if abs(c[0] - left[0]) < image.shape[1] * .02]
        other = [c for c in controls if c[0] - left[0] > image.shape[1] * .25]
        if len(aligned) >= 2 and len(other) >= 2:
            sizes = [c[2] for c in aligned + other]
            if max(sizes) / min(sizes) < 1.3:
                return True
    return False


def classify_phase(image):
    """Return (phase, heuristic confidence, evidence labels, warnings)."""
    if image.shape[1] > 1311:
        scale = 1311 / image.shape[1]
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if _control_overlay(image):
        return 'unknown', 0.0, ['unsupported_control_overlay'], ['Device overlay; battle phase unresolved']
    phase, confidence, components = classify(image)
    if phase != 'unknown':
        warnings = (['Pokémon-selection purpose is unverified; no switch event inferred']
                    if phase in {'pokemon_selection', 'switch_selection'} else [])
        return phase, confidence, components, warnings
    if 'ambiguous_target_panel' in components:
        return 'unknown', 0.0, components, ['Target-like panel lacks sufficient move-target evidence']
    h, w = image.shape[:2]
    if not 1.9 < w / h < 2.35:
        return 'unknown', 0.0, ['unsupported_aspect_ratio'], ['Unsupported layout']
    x1, y1, x2, y2 = box(image, (.12, .02, .19, .11))
    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    white = float(np.mean((hsv[:, :, 1] < 70) & (hsv[:, :, 2] > 190)))
    dark = float(np.mean(hsv[:, :, 2] < 90))
    arena_hud = white > .018 and dark > .23
    if arena_hud:
        glyphs = _message_glyphs(image)
        if glyphs >= 8:
            return 'battle_message', .68, [f'visible_message_glyphs:{glyphs}', 'battle_hud_icon'], [
                'Message phase is visual; text and battle effect are unverified']
        return 'battle_animation', .61, ['battle_hud_icon', 'no_decision_panel'], [
            'Battle view is visible; animation versus idle action resolution is uncertain']
    return 'unknown', 0.0, ['no_supported_visual_evidence'], ['Phase unresolved']


def small_signature(image):
    return cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (32, 16),
                      interpolation=cv2.INTER_AREA)
