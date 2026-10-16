"""Read-only annotation analysis; writes a separate human-feedback report."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'reports/M2.3.6-review'


def substantive(row):
    return any(isinstance(v, str) and v.strip() and v not in {'cannot_determine', '(empty)'}
               for k, v in row.items() if k not in {'reading_source', 'proximity', 'reviewed', 'unsupported_proximity'})


def main():
    source = TARGET / 'm236-event-review-annotations.json'
    original = source.read_bytes()
    a = json.loads(original)
    d = json.loads(re.search(r'const DATA=(.*?);\nconst \$', (TARGET / 'review.html').read_text(), re.S)[1])
    frames = {f['id']: f for f in d['frames']}
    events = {e['id']: e for e in d['events']}
    preview = {'preview:' + r['evidence']['sha256'] + ':' + str(r['preview_row']): r for r in d['preview']}
    reviewed = {k for k, v in a['frames'].items() if substantive(v)} | {k for k, v in a['legacy_annotations'].items() if v.get('reviewed') is True and k in frames}
    occurrences = [e for e in d['events'] if e['reviewed_occurrence']]
    touched = [e for e in occurrences if substantive(a['events'].get(e['id'], {})) or reviewed.intersection(e['frame_ids'])]
    lines = ['# M2.3.6-U partial human feedback', '', 'Analysis date: 2026-10-16 (Asia/Shanghai). Primary input: `m236-event-review-annotations.json`.',
             '', f'Original SHA-256: `{hashlib.sha256(original).hexdigest()}`. The original bytes were not changed. Schema `m236-human-review-v2` is compatible; no migration is needed.', '',
             '## Counts and interpretation', '',
             f'- Reviewable actual event occurrences: {len(occurrences)}. These are the old fixture population, not proof of current human acceptance.',
             f'- Explicit human event-occurrence verdicts: 0 reviewed, 11 still without a verdict. {len(touched)} occurrences have human feedback on constituent frames; {len(occurrences)-len(touched)} have no such feedback. Frame feedback does not judge an entire occurrence.',
             f'- Individually reviewed frames: {len(reviewed)}/136; {136-len(reviewed)} remain unreviewed under the rule below. 11 structured frames contain a classification or substantive text; 9 additional frames have explicit legacy `reviewed=true`.',
             '- 12 structured frame records exist: one is entirely indeterminate/blank and is not counted as reviewed. Two say `cannot_determine`; one of those supplies a literal field transcription and counts as feedback, not a resolved visibility judgment.',
             '- Actual-event verdicts: correct 0; incorrect/missing 0; explicit unresolved/cannot-determine 0. Absence of an event verdict is unreviewed, not unresolved or accepted.',
             '- Across all 36 navigation groups (including UI cards): 1 explicit verdict, `incorrect`, at 140.023s; 8 other saved event records say `cannot_determine`, including 7 with substantive corrections/comments. No group is explicitly marked correct, missing, or unresolved.',
             '- Frame classifications (different denominator): readable_correct 5; readable_incorrect 1; readable_missed 2; no_message 2; cannot_determine 2. Legacy reviewed flags carry no correctness verdict. None of these categories is silently promoted to an event verdict.',
             '- Three preview species suggestions, two nickname suggestions, one HUD correction, and one field comment have no final event verdict. Blank fields provide no negative evidence.', '',
             '## Prioritized issues from the human corrections', '',
             '1. **Move-description layout at 140.023s — confirmed visibility/layout coverage gap.** The user marked the field card incorrect and selected `move_description_overlay`. Cached full pixels show a large move description (category, power 75, accuracy 90, effect range, effect text) while a sandstorm indicator is also visible at top left. U records only a field/command-style case and claims no verified move-description positive. Both UI elements can coexist: the correction does not show that the field itself was absent. No state event was admitted. Next: separately review overlay geometry/visibility and multi-region routing; do not infer an executed move or opponent equipped slots from the menu.', '',
             '2. **Ability banner at 128.022s — confirmed missed visible text, cause partly unresolved.** User: `班基拉斯的扬沙`, “在屏幕左侧，特性发动区域。” Cached pixels visibly contain that left-side banner; no banner text or new effect receipt exists in the packaged U evidence. This is a region coverage / scheduling / extraction issue; no new OCR was run to distinguish those causes. Next: inspect existing banner geometry and scheduling provenance. The species label alone does not establish a persistent actor instance or warrant applying a weather trigger twice.', '',
             '3. **Player double send-out at 124.522s — confirmed transcription failure and downstream partial admission.** User correction: `上吧！班基拉斯！龙头地鼠！`. Cached baseline OCR is `上吧！班基拉斯！\\n化不地：`; receipts retain the entry observation and admit only an unplaced Tyranitar arrival. The second name is not recovered. OCR failure is confirmed; row clipping vs recognizer error remains a hypothesis. Next: examine cached row bounds and tokens for the second line; preserve the independently admitted first name.', '',
             '4. **Coaching at 426.505s — profile disagreement requires care.** The user marked `readable_correct` with `reading_source=baseline` and commented that later Attack/Defense messages can identify its target. Baseline OCR actually reads `对手的lnvincible使出了\\ne\\n居` and its move receipt is deferred with unresolved move/actor. U recovers `对手的Invincible使出了\\n指导!`; its temporal interpretation is supported at 425.500s but the actor remains unbound, so no Coaching execution was admitted. The user assessment matches the U text more closely than baseline. Confirmed: transcription differs by profile; target is not stated in this announcement. Next: align the review profile and inspect later cached stat messages before any actor/target binding. The comment is an investigation direction, not proof of target or a mechanics rule.', '',
             '5. **Nickname/species and HUD association at 287.015s — human suggestions, not admitted identities.** User proposes Big Nugget → `Forretress`, Invincible → `Lucario`, and `Big Nugget/Fortress` with `15%` HP. Preserve the spelling difference as entered. Baseline keeps nickname identity unresolved; HUD/icon candidate and current-state details remain available in the viewer. The 140.023s full frame independently shows Lucario/Forretress-like HUD icons beside those nicknames, supporting further identity review, but does not establish later occupancy or exact 287s HP. Next: verify the same-frame HUD icon/HP and instance continuity. Do not derive species merely from nicknames or 3D model position.', '',
             '6. **Preview row 2 — repeated species correction.** User supplied `Sableye` on three distinct preview-frame row IDs, with verdict still indeterminate. Existing automatic species/status and candidate evidence are listed below. This concerns icon identity association, not a battle action, active slot or nickname. Next: compare the saved row crops and independent icon candidates across these exact frames; no production species rule is changed.', '',
             '7. **Pre-battle UI at 108.002/110.502/116.020s — distinguish screen information from battle messages.** User labels the first two no-message, and 116.020s readable_missed with player IDs/ranks. Baseline sees noise `3U人` / `O: O`, defers it, and admits no semantic event. Confirmed: useful user-described screen information is absent from these battle-message readings. A missing player-info extraction is distinct from a missed battle action; current crops/route applicability should be checked before attributing this to OCR alone.', '',
             '8. **Field label at 240.007s and opponent entry at 122.020s — scope clarifications.** User: weather/field state persists at top left, literal `沙暴状态           4/5`; U field canonical evidence retains the label/counter, with no new state event. Counter duration meaning stays unknown. At 122.020s user identifies custom nicknames in the send-out message; baseline transcription matches, but send-out remains deferred (side/actor unresolved). Correct transcription does not resolve identity/slots. Next: investigate persistence and identity association with evidence, without turning repeated display into repeated effects.', '',
             '## Exact saved feedback and original predictions', '',
             'All IDs, timestamps, empty strings and user text below come from the existing JSON/payload; timestamps are sampled observations, not action onsets. The annotation JSON remains the authoritative lossless input.', '']
    def emit_frame(fid, note, label):
        f = frames.get(fid)
        if not f:
            lines.extend([f'### {label}: `{fid}`', '', 'No frame match; retained in original JSON.', ''])
            return
        lines.extend([f'### {label}: {f["timestamp"]:.6f}s', '', f'Frame ID: `{fid}`. [Cached pixels]({f["image"]}). Original source: `{f.get("source_image", f["image"])}`.', '', 'User record:', '```json', json.dumps(note, ensure_ascii=False), '```', 'Baseline OCR: ' + json.dumps(f['message']['raw_text'], ensure_ascii=False) + '.', ''])
        if f.get('u'):
            lines.append('U OCR: ' + json.dumps(f['u']['message'].get('raw_text', ''), ensure_ascii=False) + '; selected=' + str(f['u']['message'].get('selected')) + '.')
        for profile, receipts in [('baseline', f['receipts']), ('U', f.get('u', {}).get('receipts', []))]:
            if not receipts:
                lines.append(f'{profile}: no new receipt at this exact timestamp (not proof of no prior occurrence admission).')
            hud = [r for r in receipts if r['kind']=='hud_observation']
            if hud:
                lines.append(f'{profile}: {len(hud)} HUD receipts; ' + '; '.join(f'{r["id"]}: {r["status"]}' for r in hud) + '.')
            for r in receipts:
                if r['kind']=='hud_observation':
                    continue
                lines.append(f'- {profile} `{r["id"]}` {r["kind"]}: {r["status"]}, admitted={r["admitted"]}; {r["reason"]}')
        lines.append('')
    for eid, note in a['events'].items():
        e, r = events.get(eid), preview.get(eid)
        lines.extend([f'### Event/card `{eid}`', '', '```json', json.dumps(note, ensure_ascii=False), '```'])
        if e:
            lines.append(f'{e["start"]:.6f}–{e["end"]:.6f}s; original card: {e["title"]}; kind={e["kind"]}; actual occurrence={e["reviewed_occurrence"]}.')
            lines.append('Source frame IDs: ' + ', '.join('`' + k + '`' for k in e['frame_ids']) + '.')
            for fid in e['frame_ids'][:1]:
                f = frames[fid]
                lines.append(f'[Representative evidence]({f["image"]}); baseline OCR: ' + json.dumps(f['message']['raw_text'], ensure_ascii=False) + '.')
            lines.append('State decisions: ' + '; '.join(f'{x["id"]}: {x["status"]}, admitted={x["admitted"]}' for x in e['receipts']) if e['receipts'] else 'No state decision on this navigation card; see per-frame evidence.')
        elif r:
            lines.append(f'{r["evidence"]["timestamp"]:.6f}s; source frame `{r["evidence"]["sha256"]}`, preview row {r["preview_row"]}; automatic species_id={r["species_id"]}, status={r["status"]}. [Source image]({r["evidence"]["image"]}). Preview observation only; no active slot/identity admission.')
        lines.append('')
    for fid, note in a['frames'].items():
        emit_frame(fid, note, 'Structured frame')
    for fid, note in a['legacy_annotations'].items():
        if note.get('reviewed') is True or note.get('note'):
            f = frames.get(fid)
            lines.extend([f'Legacy `{fid}` at {f["timestamp"]:.6f}s: ' + json.dumps(note, ensure_ascii=False) + '.', 'Baseline OCR: ' + json.dumps(f['message']['raw_text'], ensure_ascii=False) + '; frame-reviewed flag only, no event verdict.', ''])
    lines.extend(['## Limits and next work', '', 'No OCR, video decoding, recognition model, StateEngine, historical labels or frozen evaluation reports were changed. Human corrections were not promoted to ground truth. The original intermittent Chrome image failure was not reproduced; see `viewer-validation.md` for observed behavior and limits. Review remains partial.'])
    (TARGET / 'human-feedback-summary.md').write_text('\n'.join(lines) + '\n')
    assert source.read_bytes() == original
    print(f'Summary: {len(reviewed)} reviewed frames; {len(touched)}/11 occurrences with frame feedback; zero explicit occurrence verdicts.')


if __name__ == '__main__':
    main()
