"""Read-only annotation analysis; writes a separate human-feedback report."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'reports/M2.3.6-review'


def substantive(row):
    return any(isinstance(v, str) and v.strip() and v not in {'cannot_determine', '(empty)'}
               for k, v in row.items() if k not in {'reading_source', 'proximity', 'reviewed', 'unsupported_proximity'})


def review_counts(annotations, data):
    """Keep explicit occurrence verdicts separate from frame and UI feedback."""
    frames = {f['id'] for f in data['frames']}
    structured = {k for k, v in annotations.get('frames', {}).items() if k in frames and substantive(v)}
    legacy = {k for k, v in annotations.get('legacy_annotations', {}).items()
              if k in frames and v.get('reviewed') is True}
    reviewed = structured | legacy
    occurrences = [e for e in data['events'] if e['reviewed_occurrence']]
    notes = annotations.get('events', {})
    def verdicts(events):
        return Counter(notes[e['id']]['verdict'] for e in events
                       if notes.get(e['id'], {}).get('verdict') not in {None, '', 'cannot_determine'})
    return dict(
        reviewed=reviewed, structured=structured, legacy_only=legacy - structured,
        frame_feedback=sum(bool(reviewed.intersection(e['frame_ids'])) for e in occurrences),
        touched=sum(substantive(notes.get(e['id'], {})) or bool(reviewed.intersection(e['frame_ids']))
                    for e in occurrences),
        occurrence_verdicts=verdicts(occurrences), group_verdicts=verdicts(data['events']),
        frame_classes=Counter(v.get('message_class', '(unset)') for k, v in annotations.get('frames', {}).items()
                              if k in frames),
    )


def format_counts(counts):
    return '; '.join(f'{key} {value}' for key, value in sorted(counts.items())) or 'none'


def main():
    source = TARGET / 'm236-event-review-annotations.json'
    original = source.read_bytes()
    a = json.loads(original)
    d = json.loads(re.search(r'const DATA=(.*?);\nconst \$', (TARGET / 'review.html').read_text(), re.S)[1])
    frames = {f['id']: f for f in d['frames']}
    events = {e['id']: e for e in d['events']}
    preview = {'preview:' + r['evidence']['sha256'] + ':' + str(r['preview_row']): r for r in d['preview']}
    counts = review_counts(a, d)
    reviewed = counts['reviewed']
    occurrences = [e for e in d['events'] if e['reviewed_occurrence']]
    judged = sum(counts['occurrence_verdicts'].values())
    analysis_date = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    lines = ['# M2.3.6-U partial human feedback', '', f'Analysis date: {analysis_date} (Asia/Shanghai). Primary input: `m236-event-review-annotations.json`.',
             '', f'Original SHA-256: `{hashlib.sha256(original).hexdigest()}`. The original bytes were not changed. Schema `m236-human-review-v2` is compatible; no migration is needed.', '',
             '## Counts and interpretation', '',
             f'- Reviewable actual event occurrences: {len(occurrences)}. These are the old fixture population, not proof of current human acceptance.',
             f'- Explicit human event-occurrence verdicts: {judged} reviewed, {len(occurrences)-judged} still without a verdict. {counts["touched"]} occurrences have feedback on the event or its frames; {counts["frame_feedback"]} have constituent-frame feedback. Frame feedback does not judge an entire occurrence.',
             f'- Individually reviewed frames: {len(reviewed)}/{len(frames)}; {len(frames)-len(reviewed)} remain unreviewed. {len(counts["structured"])} structured frames contain a classification or substantive text; {len(counts["legacy_only"])} additional frames have explicit legacy `reviewed=true`. Overlapping IDs count once.',
             f'- {len(a["frames"])} structured frame records exist. `cannot_determine` without substantive text does not count as reviewed; with text it counts as feedback, not a resolved visibility judgment.',
             f'- Actual-event verdicts: {format_counts(counts["occurrence_verdicts"])}. The viewer uses `cannot_determine` for both indeterminate and unreviewed records; it cannot establish an explicit unresolved judgment. Blank records are not accepted.',
             f'- Across all {len(events)} navigation groups (including UI cards): {format_counts(counts["group_verdicts"])}. Preview-row notes are separate from this denominator.',
             f'- Frame classifications (different denominator): {format_counts(counts["frame_classes"])}. Legacy reviewed flags carry no correctness verdict. None of these categories is silently promoted to an event verdict.',
             '- Three preview species suggestions, two nickname suggestions, one HUD correction, and one field comment have no final event verdict. Blank fields provide no negative evidence.', '',
             '## Additional saved reviews', '',
             'The explicit verdicts below are human assessments of the displayed conclusions. They do not independently establish recognition accuracy, complete actor/target binding, or Champions mechanics.', '']
    for e in d['events']:
        note = a['events'].get(e['id'], {})
        if note.get('verdict') in {None, '', 'cannot_determine'}:
            continue
        scope = 'actual occurrence' if e['reviewed_occurrence'] else 'navigation/UI card'
        lines.append(f'- `{e["id"]}` at {e["start"]:.3f}s ({scope}): **{note["verdict"]}** — {e["title"]}.')
    lines.extend(['',
             'The Coaching stat-change comment attributes the result to Lucario using Coaching. This remains a human causal/identity assertion for investigation; the saved comment does not bind the execution actor or target in production state. The earlier 426.505s reading-profile disagreement still needs resolution.', '',
             'At 417.003s the field card is marked incorrect and reclassified as a move, with the U frame reviewed as readable_correct and the comment `对手的Big Mom使出了击掌奇袭！`. At 417.503s the field card says no_ui and its message-region review says no_message. These are distinct region-scoped judgments; no_message alone would not establish absence of field UI.', '',
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
             'All IDs, timestamps, empty strings and user text below come from the existing JSON/payload; timestamps are sampled observations, not action onsets. The annotation JSON remains the authoritative lossless input.', ''])
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
            if f:
                lines.extend([f'Legacy `{fid}` at {f["timestamp"]:.6f}s: ' + json.dumps(note, ensure_ascii=False) + '.', 'Baseline OCR: ' + json.dumps(f['message']['raw_text'], ensure_ascii=False) + '; frame-reviewed flag only, no event verdict.', ''])
            else:
                lines.extend([f'Legacy `{fid}`: no frame match; retained in original JSON. ' + json.dumps(note, ensure_ascii=False), ''])
    lines.extend(['## Limits and next work', '', 'No OCR, video decoding, recognition model, StateEngine, historical labels or frozen evaluation reports were changed. Human corrections were not promoted to ground truth. The original intermittent Chrome image failure was not reproduced; see `viewer-validation.md` for observed behavior and limits. Review remains partial.'])
    (TARGET / 'human-feedback-summary.md').write_text('\n'.join(lines) + '\n')
    assert source.read_bytes() == original
    print(f'Summary: {len(reviewed)}/{len(frames)} reviewed frames; {counts["touched"]}/{len(occurrences)} occurrences with event/frame feedback; {judged} explicit occurrence verdicts.')


if __name__ == '__main__':
    main()
