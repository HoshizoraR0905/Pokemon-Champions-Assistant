# Battle 15: review images and deferred-record diagnosis

Scope: review UI/static assets only. OCR, parsing, identity/occupancy/state application, sealed predictions and human annotations remain unchanged. All 312 deferred records were inventoried; a separate in-memory replay reproduced all 1,074 original statuses/reasons/bindings/state hashes and final state. Representative source pixels were inspected by Codex; this is diagnostic evidence, not independent human accuracy acceptance.

**Open the repaired page:** [Battle 15 review](evaluation/fresh-heldout-20261026-v1-review/review.html), or <http://127.0.0.1:8766/reports/battles/sample_battle_15/evaluation/fresh-heldout-20261026-v1-review/review.html> while the project static server is running.

## Images

The old HTML referenced `../../../../../.cache/.../frames/*.png`, outside the review directory. Actual Chrome file-mode loading worked, so a universal browser image-decoding failure was not reproduced. Serving only the review directory reproduced the failure exactly: URLs normalized to `/.cache/...`, returned HTTP 404, and inline images had naturalWidth=0. Right-click opening a filesystem image can succeed independently of such embedded/static-root restrictions. The IDE webview's own security policy was not directly inspected.

The renderer and this existing review now use local `assets/<sha256>.png` hardlinks (copy fallback), retaining original PNG bytes and source/evidence IDs. Explicit image dimensions/eager loading make the currently paginated screenshots visible; clicking opens an in-page enlarged dialog, with normal new-tab modifier clicks retained. Load failures show a visible path message. A data favicon removes unrelated favicon 404 noise. No new review UI or annotation system was built.

Actual Battle 15 browser verification: directory-root HTTP and file loading, inline screenshot geometry/naturalWidth=1311, in-page enlargement, all nine existing modes/filters/pagination, and all **1,419 referenced images** decoding offline. Earlier probe artifacts retain a canceled Document request caused by the probe reloading a still-loading page; this was test navigation, not an image failure. Final direct-navigation HTTP verification records actual image responses and console/network results separately.

## Deferred counts

| Reason | Event type | Records |
| --- | --- | ---: |
| message_episode_occupancy_unresolved | hud_observation | 287 |
| unresolved_candidate_fields | move_execution | 11 |
| unresolved_candidate_fields | move_effect | 9 |
| unresolved_candidate_fields | stat_change | 2 |
| unresolved_candidate_fields | faint | 2 |
| unresolved_candidate_fields | terrain_change | 1 |
| **Total** | | **312** |

There are **312 distinct event IDs, 181 exact timestamps, 181 source IDs and 181 distinct screenshot evidence hashes**. HUD-only counts: **287 records at 156 timestamps**, from 460.001667–822.011667s. By side/slot: opponent.left 130, opponent.right 128, self.left 25, self.right 4. At the 156 HUD timestamps, 38 contain one deferred slot, 105 contain two, and 13 contain three. No duplicate `(timestamp, side, slot)` keys exist. Repeated time samples of unresolved occupancy inflate the headline count; they are not 287 missed gameplay actions. Semantic event duplicates are not established by equal screenshot hashes.

| Time interval (s) | Deferred |
| --- | ---: |
| 0–100 | 0 |
| 100–200 | 1 |
| 200–300 | 4 |
| 300–400 | 1 |
| 400–500 | 62 |
| 500–600 | 62 |
| 600–700 | 75 |
| 700–800 | 98 |
| 800–end | 9 |

Every deferred HUD lacks an active instance in its particular slot. **258** are opponent reads after the two replacements; **24** own reads occur with an unplaced own entry. Five remaining records have no pending entry and no HP value: 536.015/537.015 self.right, 732.013/732.513 self.left, 754.002 self.right. Inspected 536/754 frames are party overlays; 732 is animation. These are empty/irrelevant HUD candidates, not evidence of readable HP being misrecognized. Deferral prevents their application.

## Representative traces (saved pixels checked)

1. **265.501667s protection; 276.003333s and 347.000000s healing.** The screenshots really say `耿鬼在攻击中守护住了自己！` / `耿鬼的体力回复了！`. OCR text and parsed `move_effect` effects (`protected_from_attack` / `healing_announcement`) are present. After the applied 181.021667s Mega transformation, self.left stores species_id=94 but canonical_id=`pokeapi:form:10138`; generic message parsing produces `pokeapi:species:94`. `prepare_message` supplies active canonical IDs, and parser ownership compares those exact IDs, so it fails to recover self side. All four slot contexts are supported here: this is an ID-domain mismatch, not missing occupancy. `side_unknown` fails ApplicationPolicy; `actor_variant_unresolved` is explicitly allowed and is not the blocker. Five Gengar effect records share this chain (208.527, 261.002, 265.502, 276.003, 347.000). Missing healing magnitude is not the reported deferral cause; the current effect path records an announcement rather than inventing numeric healing.

2. **452.500/456.001667s arrivals → 460.001667s HUD.** Both arrival screenshots visibly name Roger/Archaludon and Roger/Sneasler. The two earlier occupants faint at 433.013/440.032. Each separately announced arrival has two vacant slots and no uniquely supported slot; both named instances are recorded as `unplaced_entry`, leaving both active slots empty. At 460.001667, pixels independently show opponent.left Archaludon 100% and opponent.right Sneasler 100%. The lightweight candidates contain those HP percentages but empty species objects. HUD application first requires an occupied supported message episode and therefore defers both. Shared hash `cae2ff95d5f9d8043ebc9dc64f32049d0cef506575ccee228df7671090934dc5` is the same full screenshot; the two distinct events use different slot/ROI coordinates, so they are not duplicate gameplay events. This unresolved double replacement persists through **258 opponent HUD records**. `message_identity_v1` does not use the ordinary HUD identity-placement observer; conservative gating is intentional, while the resulting state coverage is incomplete.

3. **513.010000s Close Combat.** Pixels and OCR agree: opponent Sneasler used Close Combat. Species, move and opponent side are parsed. The corresponding named encounter still has no active slot, producing `active_identity_context_unresolved`. The move-membership path removes `target_not_in_entry` before policy checking, so lack of an announced target is not the decisive blocker; missing supported actor context is. Fourteen opponent message deferrals (10 moves, 2 stat changes, 2 faints) follow the unresolved opponent placement chain. Do not guess the move target from the sentence.

4. **758.518333s own Rillaboom arrival → 778.021667s Protect.** Both source messages are visible. The new encounter is recorded but not placed; both self active slots are empty at the Protect message. The canonical move/side are recognized, but actor-instance resolution fails (`active_identity_context_unresolved`). Three later unprefixed Rillaboom effect messages cannot establish side either. Together this own-placement gap accounts for 24 HUD reads and 4 message deferrals. This is state incompleteness, not proof of an OCR failure or permission to infer slot from typical team order.

5. **108.008333s generic terrain announcement.** Pixels say `脚下传来了奇妙的感觉！`; the candidate has `terrain_identity_unknown`. The ordinary message does not name a terrain. The same screenshot separately shows Indeedee's Psychic Surge popup, but this live-message record does not contain its structured supporting ability evidence. The deferral is conservative given the admitted fields; the missing cross-region evidence explains incomplete semantic coverage. One other context-free failure message at 717.012s similarly lacks an identified affected side. Neither should be fixed by assuming a mechanic from wording alone.

## Highest-impact next experiments (not implemented)

1. **Proof-backed slot placement after multiple simultaneous vacancies**, including the lightweight path: independently read/confirm visible HUD names, species/forms and slots, then reconcile named arrivals prospectively. This targets 258 opponent HUD records + 14 messages, and the analogous 24 own HUD + 4 messages. These are affected records, not a promised recovery score. Preserve separate arrival identity and slot certainty; do not guess based on announcement order.
2. **Form-aware species/instance matching for unprefixed effects.** Preserve the actual Mega form while matching base-species message names to the correct supported active instance; the five Gengar effects give a small exact diagnostic regression set. Do not weaken side/instance ambiguity checks.
3. **Review-count and region/evidence coverage cleanup.** Separate repeated per-slot observations from unique gameplay occurrences; reject blank HUD candidates on overlays/animations; retain the generic terrain line separately from verified ability-banner evidence. Do not inflate accuracy by hiding deferrals or merge distinct slots solely because they share a frame hash.

Refresh only presentation, without state replay or annotation writes:

```sh
.venv/bin/python scripts/build_battle_evaluation.py --battle sample_battle_15 --run-id fresh-heldout-20261026-v1 --evaluation-id fresh-heldout-20261026-v1-review --refresh-images-only
```

Changed source: `scripts/build_battle_evaluation.py` and `scripts/templates/battle_evaluation.html`. Two existing offline-evaluator tests pass. The full source screenshot audit is diagnostic-only; benchmark truth remains pending. No parsing fix, commit or push.

Evidence: [312-row inventory](../../../.cache/battles/sample_battle_15/evaluation/review-usability-diagnostic-v1/deferred-inventory.csv) · [181 timestamp/evidence groups](../../../.cache/battles/sample_battle_15/evaluation/review-usability-diagnostic-v1/unique-evidence.json) · [prefix traces](../../../.cache/battles/sample_battle_15/evaluation/review-usability-diagnostic-v1/prefix-traces.json) · [counts](../../../.cache/battles/sample_battle_15/evaluation/review-usability-diagnostic-v1/counts.json) · [representative visual checks](../../../.cache/battles/sample_battle_15/evaluation/review-usability-diagnostic-v1/agent-visual-checks.json) · [preservation/browser verification](../../../.cache/battles/sample_battle_15/evaluation/review-usability-diagnostic-v1/preservation-verification.json).
