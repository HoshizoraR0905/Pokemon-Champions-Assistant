"""Render the Battle 11 showcase from sealed replay data and browser receipts."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORM = 'pokeapi:form:10530'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_raichu(replay, empirical):
    rows = empirical['by_form'][FORM]['builds']
    complete = [r for r in rows if r['complete']]
    supports = [replay['support_catalog'][p['support_ref']]['observed']
                for s in replay['snapshots'] for p in s['opponents'].values()
                if p.get('current_form') == FORM]
    admitted = {key for support in supports for key in support['builds']}
    mappings = {key:value for support in supports for key,value in support.get('ability_mappings',{}).items()}
    issues = [issue for support in supports for issue in support.get('eligibility_issues',[])]
    surviving = [replay['observed_builds'][key] for key in sorted(admitted)]
    return dict(records=len(rows), complete=len(complete), incomplete=len(rows)-len(complete),
                complete_natures=dict(Counter(r['nature'] for r in complete)),
                complete_alignments=dict(Counter(f"{r['alignment']['increase']} / {r['alignment']['decrease']}" for r in complete)),
                complete_abilities=dict(Counter(r['ability'] for r in complete)),
                complete_unique_builds=len({r['build_id'] for r in complete}),
                surviving_records=len(surviving),
                surviving_unique_builds=len({r['build_id'] for r in surviving}),
                counts_over_time=sorted({s['complete_after'] for s in supports}),
                active_abilities=dict(Counter(m['active_ability'] for m in mappings.values())),
                observed_speed=sorted({m['speed'] for m in mappings.values()}),
                exclusion_reasons=sorted({i['reason'] for i in issues}),
                surviving=[{k:r[k] for k in ('build_id','observed_team_signature','nature','alignment','ability','item','speed','speed_sp','publications')} for r in surviving])


def ranges(speed):
    return ' ∪ '.join(str(a) if a == b else f'[{a}–{b}]' for a,b in speed['intervals'])


def generate(figures, output):
    receipt = json.loads((figures/'capture.json').read_text())
    replay_path = ROOT/receipt['inputs']['replay']
    assert receipt['status'] == 'complete' and not receipt['errors']
    assert sha(replay_path) == receipt['inputs']['replay_sha256'], 'Replay changed since capture'
    manifest = json.loads(replay_path.with_name('manifest.json').read_text())
    assert manifest['status'] == 'complete'
    for name, digest in manifest['outputs'].items():
        assert sha(replay_path.parent/name) == digest, f'Unsealed output: {name}'
    for name,digest in receipt['inputs']['code'].items():
        assert sha(ROOT/name) == digest, f'Capture code changed: {name}'
    replay = json.loads(replay_path.read_text())
    empirical = json.loads(replay_path.with_name('empirical.json').read_text())
    assert all(set(s) == {'observed','full','conditions'} for s in replay['support_catalog'].values())
    assert [f['display_position'] for f in receipt['figures']] == [543,575]
    for f in receipt['figures']:
        assert sha(figures/f['file']) == f['sha256']
        assert f['slider_index'] == f['display_position']-1
        assert f['state']['layers'] == ['observed','full']
        assert replay['frames'][f['slider_index']]['sha256'] == f['source_frame']['sha256']
    audit = audit_raichu(replay,empirical)
    # These assertions keep the scoped narrative honest if a future dataset changes.
    assert audit['complete_natures'] == {'nature:timid':68}
    assert audit['surviving_records'] == 68 and audit['counts_over_time'] == [68]
    assert audit['surviving_unique_builds'] == 51
    assert not audit['exclusion_reasons']
    m = replay['reviewed_metrics']
    sections = []
    for n,f in enumerate(receipt['figures'],1):
        t=f['state']['target'];o=t['observed'];full=t['full']
        image=os.path.relpath(figures/f['file'],output.parent)
        before = n == 1
        explanation = (
            'Incineroar announces Parting Shot. Mega Raichu Y has already left at 326.022 s and Basculegion arrived at 329.522 s. Incineroar remains active. Only the opening reviewed comparison is admitted; the later Earth Power observation is still unavailable. This first announcement alone cannot establish the relative order of the two priority-zero moves. The replay does not display the future pivot arrival.'
            if before else
            'Garchomp announces Earth Power. Incineroar departed through Parting Shot at 338.523 s and Volcarona arrived at 344.525 s. Incineroar is now benched, but its persistent identity retains the newly admitted order constraint. Parting Shot preceded Earth Power; both have priority zero. Under the reviewed opponent Tailwind and action-time continuity assumptions, this filters joint configurations. Choice Scarf and unresolved Quick Claw alternatives still matter; the full Speed union does not shrink.')
        sections.append(f'''### Figure {n}: {f['display_position']} / 1008 — {f['timestamp']:.3f} s

![Battle 11 at timeline position {f['display_position']} of 1008]({image})

{explanation}

Observed Incineroar support: **{o['complete_before']} → {o['complete_after']}** complete member configurations; {o['incomplete_excluded']} incomplete records excluded. Unmodified Speed: **{ranges(o['speed'])}**.

Full reference support: **{full['configuration_count']:,} joint configuration classes**, Speed **{ranges(full['speed'])}**. These figures illustrate {'time-causal withholding of future evidence' if before else 'configuration elimination even when marginal Speed bounds remain unchanged'}. Neither snapshot identifies an exact opponent build.
''')
    text=f'''# Battle 11: reconstructing action order and narrowing Speed support

## Summary

M3.2.2 now presents an evidence-linked, time-causal replay of Battle 11: OCR/event reconstruction, source-reviewed corrections, selected and prevented actions, and deterministic filtering of opponent Speed configurations. This is a mid-project demonstration, not an automatic recognition accuracy claim. The display has two support layers: **observed builds** and the **full reference model**.

The example below shows Incineroar's observed support narrowing from 192 to 163 configurations and full reference support from 5,544 to 2,055 classes. Unknown alternatives remain explicit. The admitted order constraints are preserved. A corrected original-to-Mega ability mapping restores complete published builds that were previously rejected.

## What the replay does

The replay links cached source frames and OCR/event evidence to a chronological timeline. It distinguishes executed moves from selected moves and prevented actions, preserves Pokémon identities and revealed information across switches, and tracks transformations using the form known at that timestamp. Manual source review is explicit in the curated [Battle 11 comparisons](../tests/fixtures/battle_evidence/battle11-speed-review.json) and [transition annotations](../tests/fixtures/battle_evidence/replay-transitions-reviewed.json).

Speed comparisons are admitted only when their evidence is available. Higher-priority moves, switches, Mega transformations and pivots have separate ordering semantics. An early action is not automatically evidence of a higher Speed stat. Saved snapshots expose what was known then, rather than applying final-battle knowledge to earlier frames.

## Battle 11 example

### Opening: selection, flinch and priority

Earth Power is visibly selected at 141.023 s; selection does not prove execution or a confirmed target. Raichunite Y is revealed at 148.525 s and Mega Raichu Y is confirmed at 158.027 s. The form change is conservatively applied at that confirmation, the upper bound of its evidence interval.

Fake Out executes at 160.527 s with priority +3. Grimmsnarl's Prankster Light Screen at 166.512 s has priority +1. Neither ordering directly compares ordinary Speed with priority-zero actions. Garchomp's flinch message at 172.028 s marks its prevented selected-action position under the reviewed timing interpretation; Volcarona uses Tailwind at 174.530 s. Tailwind's new effect is not retroactively applied to the earlier action positions.

The opening comparison is conditional on that flinch-position interpretation and the reviewed action-time modifiers. With the known Garchomp Speed 154, it reduces Volcarona from **5,544 to 3,966 full classes**, and **33 to 29 complete observed configurations** (48 incomplete records excluded). Its full unmodified Speed union remains **[108–152] ∪ [154–163] ∪ [165–167]**: item alternatives, including Iron Ball, prevent a single unconditional bound. Ties remain possible where admitted by the model.

### Turn 4: a pivot supplies the second comparison

The two actual browser captures show the same comparison before and after its second action becomes observable. The slider positions are one-based displayed positions, not video frame numbers; their zero-based slider indices are 542 and 574.

{''.join(sections)}
### Later evidence and form-aware ordering

Garchomp's Mega Garchomp Z confirmation at 418.003 s changes its reference unmodified Speed from 154 to 203. Power Gem at 433.523 s preceding Soak at 440.508 s conditionally reduces Basculegion from **8,316 to 8,232 full classes** and **117 to 82 observed configurations**. The subsequent reviewed voluntary-switch order (494.517–501.018 s) reduces these further to **7,566** and **62**. Switch ordering is evaluated in its own phase; Parting Shot's replacement remains part of move resolution and is not an independent voluntary-switch comparison. No new inference was introduced for this report.

## Speed support interpretation

| Layer | Meaning | Practical limit |
| --- | --- | --- |
| Observed builds / 经验配置支持 | Complete joint configurations actually present in the selected published-team corpus and compatible with admitted evidence | A finite descriptive sample, not all possible builds or a probability distribution |
| Full reference model / 完整参考模型 | Supported legal Speed/order configuration hypotheses under the maintained rules and declared conditions | Conditional on reference coverage; unsupported branches remain unresolved |

Counts refer to joint configurations, not just distinct Speed values. Nature/alignment, SP allocation, ability and item remain correlated. Missing build fields are not invented; incomplete entries are excluded from exact observed support. Speed ranges here are unmodified stats, not temporary effective action Speed. Discrete gaps are preserved. A full-model union can stay unchanged while thousands of joint classes disappear.

The full model retains Choice Scarf, Iron Ball and Quick Claw alternatives where legal. Unknown activation and unsupported ability-order handling prevent claims of complete identification. A published move list supplies possible/revealed membership only where justified; it does not establish the opponent's exact equipped slots.

## Mega Raichu Y: actual observed-build audit

The replay uses **vgcmulticalc / tournament_published / M-C / Doubles**, with {empirical['scope']['designs']} distinct observed team designs and {empirical['scope']['publications']} publications. Its observation unit is a distinct observed-team-configuration member (`published-team-identity-v1`, `observed-configuration-v3`), not an independent battle encounter.

For canonical form `{FORM}`, the scoped corpus contains **{audit['records']} member records: {audit['complete']} complete and {audit['incomplete']} incomplete**. All 68 complete records are **Timid-like: +Speed / −Attack**; none is Modest-like (+Special Attack / −Attack). These represent {audit['complete_unique_builds']} distinct Pokémon build IDs. The incomplete records also label Timid, but cannot supply exact complete build support.

Of the complete records, **65 record Lightning Rod**, a legal original Raichu ability; **3 record No Guard**, a post-Mega ability assertion. The earlier adapter incorrectly required the source ability to be native to the current Mega form and rejected the 65 Lightning Rod records. That legality bug is corrected generically using the existing Champions KnowledgeBase: validate original abilities against the pre-Mega form, preserve the source row and joint identity, then apply the canonical active Mega ability after confirmation. No Guard is not added to base Raichu, and Lightning Rod is not added to Mega Raichu Y.

**All 68 complete member records now survive**, representing **51 distinct joint Pokémon build IDs**. **No complete Mega Raichu Y records remain excluded** by the remaining checks; 12 incomplete records still cannot supply exact build support. All 68 retain Timid-like (+Speed / −Attack) alignment and Raichunite Y. Their unmodified observed Speed values are **{audit['observed_speed']}**. The compact audit preserves source abilities, nature, Speed SP, build IDs, team signatures and publication links.

After confirmation at **158.027 s**, every eligible record maps to active **No Guard**; the 65 Lightning Rod records retain Lightning Rod as their original ability. The 3 source No Guard records do not identify their original ability: it remains unknown between legal base abilities. Before confirmation, Mega forms are excluded from current active-form alternatives; original Lightning Rod/Static configurations use base-form stats and abilities. A source post-Mega assertion alone is not used to guess a pre-Mega ability. At identical training (+Speed, Speed SP 24), Raichu Speed is **169** before Mega and **191** afterward.

The confirmed Mega Raichu Y support remains **68 → 68 throughout the rest of Battle 11**: no admitted Speed comparison further narrows it. Thus speed-boosting support is present in **every complete eligible record**; no Modest-like complete record appears. The full reference Speed union remains **[135–185] ∪ [187–196] ∪ [198–200]**, and No Guard's order handler remains outside the audited subset. See [the compact audit](assets/m322-battle11-ability-v2/raichu-audit.json) for the recomputed counts and source provenance. Historical figures and the previous three-record audit are preserved separately; they document the superseded eligibility bug.

## Known limitations

The sequence combines automatic OCR/event output with curated source-grounded comparisons. Deterministic replay success does not measure recognition accuracy or comprehensive semantic coverage. The opening flinch interpretation, Tailwind continuity, relevant stat stages/status and absence of unobserved order changes remain explicit comparison assumptions. Historical banners alone do not certify their continuity at every later action.

Mega confirmation intervals are conservative. Two late Battle 11 voluntary recalls have confirmed command-phase evidence but unresolved local segment IDs. Other uncaptured or deferred actions are not silently converted into inequalities. Unsupported ability handling and item activation branches remain unresolved. Champions Fake Out +3, Follow Me +2 and Rage Powder +2 are covered by corrected catalog regressions; historical source assertions and other-generation data remain preserved.

## Reproduction and measured cost

Run from the repository root with the existing environment and cached Battle 11 evidence. No video decoding, OCR, or team database rebuild is required. The tested local URL is **{receipt['inputs']['url']}**. If this server is already running, reuse it.

```sh
.venv/bin/python scripts/serve_visual_review.py --port 8767
```

In another terminal, package/reuse the scoped replay and capture the rendered page, then generate this report:

```sh
.venv/bin/python scripts/build_reviewed_speed_replay.py --battle 11 --reviews tests/fixtures/battle_evidence/battle11-speed-review.json
node scripts/capture_battle11_report.cjs 'http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=11' docs/assets/m322-battle11-ability-v2
.venv/bin/python scripts/build_battle11_speed_report.py --figures docs/assets/m322-battle11-ability-v2
```

These corrected figures use a new directory; previous captures are retained. The capture command reuses matching, hash-verified figures. To take fresh captures without replacing them:

```sh
figure_dir=$(mktemp -d .cache/m322-battle11-figures.XXXXXX)
node scripts/capture_battle11_report.cjs 'http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=11' "$figure_dir"
.venv/bin/python scripts/build_battle11_speed_report.py --figures "$figure_dir" --output .cache/m322-battle11-reproduced.md
```

Screenshots were obtained with **{receipt['browser']}**, viewport **1600 × 1200**, device scale 1, via Chrome DevTools Protocol. The script dispatches the existing slider input at indices 542/574, waits for the original source image to decode and two animation frames, and captures the unedited viewport as JPEG quality 90. The source image, timeline, and complete Incineroar card with both layers are visible. [Capture receipt](assets/m322-battle11-ability-v2/capture.json) records replay/code/image hashes, exact timestamps, source PTS, displayed positions and browser state. These are actual rendered captures, without compositing.

The refreshed Battle 11 package took **{m['preprocessing_seconds']:.3f} s**, including **{m['solver_seconds']:.3f} s** of solver work; **0 OCR calls and 0 video decodes**. The retained Stage A Python lookup benchmark measured **0.194 ms/query over 2,000 queries**; this is not browser latency. Packaging cost is a single local measurement, not a throughput guarantee.

### Validation of the Mega ability correction

Focused regression results and browser measurements for this correction are recorded in the [targeted repair report](../reports/M3.3-M3.2.2-mega-ability-mapping.md). Tests cover Lightning Rod/Static → No Guard, preserved joint identity and training, pre-/post-Mega stats, independent exclusion reasons, another Mega species, 68 restored member records, and causal rewind/forward state. Recognition accuracy and independent human acceptance were not measured.

Receipts remain under `.cache/m322/mega-ability-repair-v1/`. The same frozen published-team data and Stage A evidence were reused. Full video recognition and the published-team database were not rebuilt. The full reference/order constraints remain unchanged; earlier current-form alternatives and empirical eligibility are corrected.

```sh
.venv/bin/python -m pytest -q tests/test_speed_replay_projection.py tests/test_speed_replay.py tests/test_speed_replay_extension.py tests/test_champions_priorities.py tests/test_battle11_speed_report.py tests/test_mega_empirical_abilities.py
review_dir=$(mktemp -d .cache/m322-battle11-review.XXXXXX)
rmdir "$review_dir"
node scripts/verify_speed_replay.cjs 'http://127.0.0.1:8767/scripts/templates/speed_replay.html?battle=11' "$review_dir"
```

Current replay: `{receipt['inputs']['replay']}`. Its sealed sibling manifest preserves inputs, outputs and resume identity. Report generation checks those output hashes, capture code, figure hashes and two-layer schema. Existing historical packages and validation figures remain intact. Semantic acceptance is conditional as described above; no new inference milestone is claimed.
'''
    output.parent.mkdir(parents=True,exist_ok=True)
    # Keep audit beside each reproduced figure set, with links relative to the report.
    (figures/'raichu-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    text=text.replace('assets/m322-battle11-ability-v2/raichu-audit.json',os.path.relpath(figures/'raichu-audit.json',output.parent))
    text=text.replace('assets/m322-battle11-ability-v2/capture.json',os.path.relpath(figures/'capture.json',output.parent))
    output.write_text(text)
    return audit


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figures',type=Path,default=ROOT/'docs/assets/m322-battle11-ability-v2')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/m3.2.2-battle11-speed-report.md')
    args=parser.parse_args()
    result=generate(args.figures.resolve(),args.output.resolve())
    print(f"Wrote {args.output}; Mega Raichu Y: {result['surviving_records']} eligible records, {result['surviving_unique_builds']} unique build")
