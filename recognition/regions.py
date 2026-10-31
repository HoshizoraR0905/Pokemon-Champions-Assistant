"""Visual extraction registry. Geometry is evidence acquisition, not occupancy.

Normalized bounds use exclusive right/bottom edges. Dynamic geometry remains in
the named extractor; it must establish visibility before reading any text.
"""
from dataclasses import dataclass

MESSAGE_ROI = (.22, .685, .64, .797)
FIELD_ROI = (.204, .043, .424, .095)
DETAIL_ROIS = {'species': (.25,.185,.435,.239), 'hp': (.365,.25,.436,.294),
    'ability': (.350,.355,.417,.405), 'item': (.330,.403,.44,.462),
    'field0': (.520,.285,.650,.335), 'field1': (.520,.380,.655,.435),
    'field2': (.520,.475,.655,.525)}


def hud_roi(side, offset, field):
    """Current independent HUD geometry; older screenshot icons differ on purpose."""
    bounds = {
        'own': {'name': (.139,.847,.226,.887), 'bar': (.177,.898,.232,.920),
            'card': (.08,.825,.244,.961), 'icon': (.080,.825,.137,.961),
            'current': (.177,.915,.213,.955), 'maximum': (.220,.925,.243,.955)},
        'opponent': {'name': (.624,.051,.722,.084), 'bar': (.650,.094,.713,.117),
            'card': (.563,.030,.727,.157), 'icon': (.563,.030,.623,.157),
            'percent': (.681,.113,.727,.154)},
    }[side][field]
    x, y, X, Y = bounds
    return x + offset, y, X + offset, Y


@dataclass(frozen=True)
class Extraction:
    phases: tuple[str, ...]
    geometry: str
    content: str
    method: str
    acceptance: str
    refresh: str
    output: str


REGISTRY = {
    'message': Extraction(('battle', 'unknown'), 'MESSAGE_ROI; ui_regions.message_rows',
        'literal message rows', 'PP-OCRv6 ONNX, visual baselines',
        'coherent glyph geometry; semantic identity >= .95 and complete punctuation',
        '2 FPS default; visible messages override COMMAND; RegionGate .015',
        'row.message: raw_text/confidence/rows/tokens; occurrence_decision separately'),
    'hud': Extraction(('battle', 'menus'), 'hud_roi; fast_profile.independent_cards',
        'displayed HP; independent identity only on qualified verification',
        'numeric OCR; optional icon matching', 'panel > .30; colored bar > .15 or empty > .40; numeric validation',
        'visible card and RegionGate .015; OCR reuse .004; double-faint retry >= 2 seconds',
        'row.snapshot.pokemon: slot/species/icon/hp and original evidence'),
    'preview': Extraction(('team_preview',), 'Recognizer.recognize preview branch; event_schedule.IdentitySchedule.acquire_team',
        'six own labels/items; six opponent icons', 'OCR and icon matching',
        'phase >= .9 for trainer reads; independent icon admission',
        'changed panel; unresolved opponent rows retried', 'roster rows and trainer_observations'),
    'configuration': Extraction(('team_configuration',), 'Recognizer.recognize configuration branch',
        'names, displayed stats/allocation, ability/item/moves, gender', 'OCR and color masks',
        'OCR .75 plus canonical resolution; unknown EV/IV/nature preserved',
        'changed panel until six resolved rows', 'roster.configuration; models.Observation'),
    'popup': Extraction(('battle', 'unknown'), 'visual_evidence.popup_regions/line_boxes',
        'display species and ability/item', 'variant OCR and exact-name consensus',
        'parse_popup supported; screen edge is not battle side', 'visible/changed region',
        'row.visual.readings and parsed popup'),
    'detail': Extraction(('selection',), 'DETAIL_ROIS; visual_evidence.detail_layout/stage_arrows',
        'selected subject, HP, ability/item, effects and stages', 'variant OCR; triangle counting',
        'selected_panel_side plus parse_detail supported', 'changed independently selected overlay',
        'row.visual.readings/parsed/selection'),
    'field': Extraction(('battle', 'unknown'), 'FIELD_ROI; visual_evidence.line_boxes',
        'literal field label/counter', 'OCR variants', 'glyphs alone only partial; counter meaning unverified',
        'visible/changed RegionGate', 'row.visual.field; no invented trigger time'),
    'battle_log': Extraction(('battle_log_overlay',), 'battle_log.detect_log/extract_view (scaled separators and text bounds)',
        'turn heading, historical rows and scroll provenance', 'geometry plus line OCR',
        'panel mean >= .85; heading >= .75; assembly ambiguity retained',
        'separate Pass B after live seal; changed panel .004',
        'views/entries/events; inspection timestamp is not original event time'),
}
