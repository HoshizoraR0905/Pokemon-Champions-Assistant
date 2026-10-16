# M2.3.6-U partial human feedback

Analysis date: 2026-10-16 (Asia/Shanghai). Primary input: `m236-event-review-annotations.json`.

Original SHA-256: `d287123c7ee3f28667b2dcef269f7b8f803548fa7fcbe49807bb0fec0a23144b`. The original bytes were not changed. Schema `m236-human-review-v2` is compatible; no migration is needed.

## Counts and interpretation

- Reviewable actual event occurrences: 11. These are the old fixture population, not proof of current human acceptance.
- Explicit human event-occurrence verdicts: 5 reviewed, 6 still without a verdict. 9 occurrences have feedback on the event or its frames; 9 have constituent-frame feedback. Frame feedback does not judge an entire occurrence.
- Individually reviewed frames: 28/136; 108 remain unreviewed. 20 structured frames contain a classification or substantive text; 8 additional frames have explicit legacy `reviewed=true`. Overlapping IDs count once.
- 22 structured frame records exist. `cannot_determine` without substantive text does not count as reviewed; with text it counts as feedback, not a resolved visibility judgment.
- Actual-event verdicts: correct 5. The viewer uses `cannot_determine` for both indeterminate and unreviewed records; it cannot establish an explicit unresolved judgment. Blank records are not accepted.
- Across all 36 navigation groups (including UI cards): correct 9; incorrect 2; no_ui 1. Preview-row notes are separate from this denominator.
- Frame classifications (different denominator): cannot_determine 3; no_message 5; readable_correct 11; readable_incorrect 1; readable_missed 2. Legacy reviewed flags carry no correctness verdict. None of these categories is silently promoted to an event verdict.
- Three preview species suggestions, two nickname suggestions, one HUD correction, and one field comment have no final event verdict. Blank fields provide no negative evidence.

## Additional saved reviews

The explicit verdicts below are human assessments of the displayed conclusions. They do not independently establish recognition accuracy, complete actor/target binding, or Champions mechanics.

- `occurrence:not_effective` at 419.503s (actual occurrence): **correct** — Not very effective — target context unresolved.
- `occurrence:two_hits` at 421.005s (actual occurrence): **correct** — Two-hit notice.
- `interval:837bb40eed342913a5b1280ca8f72d3a4971e32cfc3554f67215d3a6c46e0139` at 406.002s (navigation/UI card): **correct** — Mega Evolution animation — no-text example.
- `occurrence:mega_revelation` at 413.503s (actual occurrence): **correct** — Big Mom’s Mega Evolution revelation.
- `occurrence:fake_out` at 415.503s (actual occurrence): **correct** — Fake Out — identified and attributed · baseline / U comparison.
- `occurrence:coaching_stages` at 430.005s (actual occurrence): **correct** — Attack and Defense increased.
- `u:fd9f8ab5370010159be52546d7ee891e53bb90df700c52ce902b41d651a5d400:field` at 140.023s (navigation/UI card): **incorrect** — Weather / terrain / Trick Room indicator · 140.023s.
- `u:6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243:field` at 417.003s (navigation/UI card): **incorrect** — Weather / terrain / Trick Room indicator · 417.003s.
- `u:d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619:field` at 417.503s (navigation/UI card): **no_ui** — Weather / terrain / Trick Room indicator · 417.503s.
- `u:0e2995b882068c5437a29b53457b8bd7e47758d9a3c9e228a63a5a6ec22c3f76:overlay` at 400.000s (navigation/UI card): **correct** — Target-selection overlay · 400.0s.
- `u:af2b73eaf867eff7588808109d3dbd6efdb28cd7c98e2d967a79b65628782eb1:overlay` at 384.548s (navigation/UI card): **correct** — Check Status Overlay · 384.548s.
- `u:1af4952460ffc1aa4f621a8d5de8cdb289939c375979369f92a64335b33df17d:overlay` at 374.000s (navigation/UI card): **correct** — Battle Log Overlay · 374.0s.

The Coaching stat-change comment attributes the result to Lucario using Coaching. This remains a human causal/identity assertion for investigation; the saved comment does not bind the execution actor or target in production state. The earlier 426.505s reading-profile disagreement still needs resolution.

At 417.003s the field card is marked incorrect and reclassified as a move, with the U frame reviewed as readable_correct and the comment `对手的Big Mom使出了击掌奇袭！`. At 417.503s the field card says no_ui and its message-region review says no_message. These are distinct region-scoped judgments; no_message alone would not establish absence of field UI.

## Prioritized issues from the human corrections

1. **Move-description layout at 140.023s — confirmed visibility/layout coverage gap.** The user marked the field card incorrect and selected `move_description_overlay`. Cached full pixels show a large move description (category, power 75, accuracy 90, effect range, effect text) while a sandstorm indicator is also visible at top left. U records only a field/command-style case and claims no verified move-description positive. Both UI elements can coexist: the correction does not show that the field itself was absent. No state event was admitted. Next: separately review overlay geometry/visibility and multi-region routing; do not infer an executed move or opponent equipped slots from the menu.

2. **Ability banner at 128.022s — confirmed missed visible text, cause partly unresolved.** User: `班基拉斯的扬沙`, “在屏幕左侧，特性发动区域。” Cached pixels visibly contain that left-side banner; no banner text or new effect receipt exists in the packaged U evidence. This is a region coverage / scheduling / extraction issue; no new OCR was run to distinguish those causes. Next: inspect existing banner geometry and scheduling provenance. The species label alone does not establish a persistent actor instance or warrant applying a weather trigger twice.

3. **Player double send-out at 124.522s — confirmed transcription failure and downstream partial admission.** User correction: `上吧！班基拉斯！龙头地鼠！`. Cached baseline OCR is `上吧！班基拉斯！\n化不地：`; receipts retain the entry observation and admit only an unplaced Tyranitar arrival. The second name is not recovered. OCR failure is confirmed; row clipping vs recognizer error remains a hypothesis. Next: examine cached row bounds and tokens for the second line; preserve the independently admitted first name.

4. **Coaching at 426.505s — profile disagreement requires care.** The user marked `readable_correct` with `reading_source=baseline` and commented that later Attack/Defense messages can identify its target. Baseline OCR actually reads `对手的lnvincible使出了\ne\n居` and its move receipt is deferred with unresolved move/actor. U recovers `对手的Invincible使出了\n指导!`; its temporal interpretation is supported at 425.500s but the actor remains unbound, so no Coaching execution was admitted. The user assessment matches the U text more closely than baseline. Confirmed: transcription differs by profile; target is not stated in this announcement. Next: align the review profile and inspect later cached stat messages before any actor/target binding. The comment is an investigation direction, not proof of target or a mechanics rule.

5. **Nickname/species and HUD association at 287.015s — human suggestions, not admitted identities.** User proposes Big Nugget → `Forretress`, Invincible → `Lucario`, and `Big Nugget/Fortress` with `15%` HP. Preserve the spelling difference as entered. Baseline keeps nickname identity unresolved; HUD/icon candidate and current-state details remain available in the viewer. The 140.023s full frame independently shows Lucario/Forretress-like HUD icons beside those nicknames, supporting further identity review, but does not establish later occupancy or exact 287s HP. Next: verify the same-frame HUD icon/HP and instance continuity. Do not derive species merely from nicknames or 3D model position.

6. **Preview row 2 — repeated species correction.** User supplied `Sableye` on three distinct preview-frame row IDs, with verdict still indeterminate. Existing automatic species/status and candidate evidence are listed below. This concerns icon identity association, not a battle action, active slot or nickname. Next: compare the saved row crops and independent icon candidates across these exact frames; no production species rule is changed.

7. **Pre-battle UI at 108.002/110.502/116.020s — distinguish screen information from battle messages.** User labels the first two no-message, and 116.020s readable_missed with player IDs/ranks. Baseline sees noise `3U人` / `O: O`, defers it, and admits no semantic event. Confirmed: useful user-described screen information is absent from these battle-message readings. A missing player-info extraction is distinct from a missed battle action; current crops/route applicability should be checked before attributing this to OCR alone.

8. **Field label at 240.007s and opponent entry at 122.020s — scope clarifications.** User: weather/field state persists at top left, literal `沙暴状态           4/5`; U field canonical evidence retains the label/counter, with no new state event. Counter duration meaning stays unknown. At 122.020s user identifies custom nicknames in the send-out message; baseline transcription matches, but send-out remains deferred (side/actor unresolved). Correct transcription does not resolve identity/slots. Next: investigate persistence and identity association with evidence, without turning repeated display into repeated effects.

## Exact saved feedback and original predictions

All IDs, timestamps, empty strings and user text below come from the existing JSON/payload; timestamps are sampled observations, not action onsets. The annotation JSON remains the authoritative lossless input.

### Event/card `preview:d3283a8d47c0606896ade51b74f908c110a7527ea199a43911e0fc6314fda00a:1`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
100.016667s; source frame `d3283a8d47c0606896ade51b74f908c110a7527ea199a43911e0fc6314fda00a`, preview row 1; automatic species_id=115, status=resolved. [Source image](assets/d3283a8d47c0606896ade51b74f908c110a7527ea199a43911e0fc6314fda00a.png). Preview observation only; no active slot/identity admission.

### Event/card `preview:d3283a8d47c0606896ade51b74f908c110a7527ea199a43911e0fc6314fda00a:2`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "Sableye", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
100.016667s; source frame `d3283a8d47c0606896ade51b74f908c110a7527ea199a43911e0fc6314fda00a`, preview row 2; automatic species_id=None, status=unresolved. [Source image](assets/d3283a8d47c0606896ade51b74f908c110a7527ea199a43911e0fc6314fda00a.png). Preview observation only; no active slot/identity admission.

### Event/card `preview:12cbfca8309edf643a77355eb436210285ffef04588c207261168b7971fe9b7a:2`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "Sableye", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
80.013333s; source frame `12cbfca8309edf643a77355eb436210285ffef04588c207261168b7971fe9b7a`, preview row 2; automatic species_id=None, status=unresolved. [Source image](assets/12cbfca8309edf643a77355eb436210285ffef04588c207261168b7971fe9b7a.png). Preview observation only; no active slot/identity admission.

### Event/card `preview:86de564a340b86e65c1716feaf42af2d61042b2c3a0c6c6af68ab08a34fd2820:2`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "Sableye", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
40.006667s; source frame `86de564a340b86e65c1716feaf42af2d61042b2c3a0c6c6af68ab08a34fd2820`, preview row 2; automatic species_id=302, status=resolved. [Source image](assets/86de564a340b86e65c1716feaf42af2d61042b2c3a0c6c6af68ab08a34fd2820.png). Preview observation only; no active slot/identity admission.

### Event/card `nickname:development:Big Nugget`

```json
{"verdict": "cannot_determine", "eventKind": "identity", "actualEvent": "Big Nugget", "actor": "", "target": "", "species": "Forretress", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
287.015000–297.533333s; original card: Unresolved nickname: Big Nugget; kind=nickname; actual occurrence=False.
Source frame IDs: `e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3`, `7ac281afbdd9b5c522016599e43522da5a83775f0d6c076ed2c41de29e7ad556`, `416fa15bae97476e81ae1f217c0e8376052a035cd5fc0a812d3382dde5fb62fa`, `66fb20f438999f964931323c55b8be9d5c98296af70c28e864b758ee7f112029`, `c6cc9c65dbe8924e21eadc97a97a713af96e6dfc3098e76bcfc593ed53cb7cf3`, `9ffdc365dd9fdd841bd4c5df62edae3ea081a5d96ea927c5a4a52500781b8f46`, `c47d13a152f1e2c5c97c31e9d55399a115725d7b1d79ef07430c311a0f254492`, `010df8b0684d8df41a519040e8dba7cad73f29377def4fe7db17d0b152f824a1`, `6829fd64940f9dec19bd93b55ede6005ee6df9435874a0dd7213e4292d4c7e11`, `5bd176d87df1aaebb7bc501ca81489d3033211e62e80337326a339665f1dee9a`, `3507c9fcdd05a0ec3eb36e83c167f084c1a5a3ea957611d6eaa41aad9f3d7be3`, `204a12876ce1732de34c47fc8f5655a9cfaa6dbb628cb47c71d8f8ae1795dbe8`, `293c200acf42a2a00ae74cac696f7b95f6c2371809f88a8bfce8ff818ecfa0dd`, `82c23913f64a1cc312dd4bd0d4cd2760eac2a547b911dfd5bb7535de51568c67`, `879e69145baf15f49a4dd43c0513ac100b61a6dc276712e52c712949791548ae`, `d24be9c1ca9ee8de0997300bf7a7c232f99fcbcadbea82ec175725fe786ed298`, `3aba72a947279fe56002dd297cd20504a7f7c2728144cc0e35ad5fc8ebae2b85`, `101b5e8e74481f84446fd97b0f86c2aa24d18bb8e7cc686cbb6e263a64ac4a54`, `7e5ed03b1b675a7a765f60d562739cc97eb46859eda468c246595d47f9ca7c8e`, `e1a14e317194855ffe15b66a446c6571ae7b21cd7ddc12da46f9bb89aca14657`, `dc8f0fe764a26bdc257ccbfe38c81c23b886a7043ed5b6ee6fbc9c2898814e0a`, `32ce0d490ef00150a319886fead390dc7bc124c321d0045d00a1d71705a3d864`.
[Representative evidence](assets/e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3.png); baseline OCR: "0".
State decisions: event:5cef7adcc1ee6f45c62076f3: recorded_observation, admitted=False; event:6540389fbaf5ae69c133f8a2: recorded_observation, admitted=False; event:712041954c0f508fbd7a4470: applied_candidate, admitted=True; event:c6878965f68de1a5843bd991: applied_candidate, admitted=True; event:439952ad637f582a5415523b: recorded_observation, admitted=False; event:7806fdf000cc5a653b089449: applied_candidate, admitted=True; event:9a769487798ebf73fab29c22: recorded_observation, admitted=False; event:a87d0701d641d799965e3c21: applied_candidate, admitted=True; event:21232a9c7207d455e3393449: recorded_observation, admitted=False; event:3aa290d270af03dfe8972cc5: applied_candidate, admitted=True; event:7250e89668c09717e634f80d: recorded_observation, admitted=False; event:c5354e9bbb55eea948137ac5: applied_candidate, admitted=True; event:6012e5bffb87ada5a7607870: applied_candidate, admitted=True; event:b9e2d53cb468dd1114b185cc: recorded_observation, admitted=False; event:cb95752adb10aeb42d1be91c: applied_candidate, admitted=True; event:f9522ffbff4eb76c83da56d3: recorded_observation, admitted=False; event:42b4fd625e9da63093b21512: applied_candidate, admitted=True; event:915507538d85520c54626b1d: recorded_observation, admitted=False; event:e9136bedc3e04970a130bf48: applied_candidate, admitted=True; event:ffc51bdf5cddd33c3646f0bc: recorded_observation, admitted=False; event:4ed0fa32f66c81b2f88f7591: applied_candidate, admitted=True; event:69cbff7ac2fa7111ee9eb34f: recorded_observation, admitted=False; event:71d9cf331ee032b92d91b74d: applied_candidate, admitted=True; event:79b2ff316750130bed5199dc: applied_candidate, admitted=True; event:29414f005a3a468fd360538e: applied_candidate, admitted=True; event:acadbc203cb493739f4a3d20: applied_candidate, admitted=True; event:d8e4674fecd8c911becc833e: recorded_observation, admitted=False; event:f62e14fec51cd0eddb8bc992: applied_candidate, admitted=True; event:69e6d919d6b63dc910b03b17: applied_candidate, admitted=True; event:6cac71c6b55892cc6dd5ca1f: applied_candidate, admitted=True; event:ba697487ff9a9e4e2c559bec: recorded_observation, admitted=False; event:da0056cbcac3d37afca09f21: applied_candidate, admitted=True; event:8e13aec74c77ca3c41fbff04: applied_candidate, admitted=True; event:a0989022c5b5d7d52aa4aa21: applied_candidate, admitted=True; event:bb23967deb764efe8c0db073: applied_candidate, admitted=True; event:dc977546e2b460072f94951c: recorded_observation, admitted=False; event:8797b621c0d3b12c256da838: applied_candidate, admitted=True; event:9974483e1270e152393b63e6: recorded_observation, admitted=False; event:eaa67e4bde9529c604b1569f: applied_candidate, admitted=True; event:f85b88df6a0837d2fc86376a: applied_candidate, admitted=True; event:11f5e1317c2691862689fd3d: applied_candidate, admitted=True; event:1c701453cc5eacce3cf04e81: applied_candidate, admitted=True; event:3ee1e1e3e06b689f6771665a: recorded_observation, admitted=False; event:93920889481295a5c1ba46ff: applied_candidate, admitted=True; event:7e1b890e8b2f7f47c356afd0: applied_candidate, admitted=True; event:c102e2cfe669ac90f23f2446: applied_candidate, admitted=True; event:d3bc1325feeefe2194bd3bab: recorded_observation, admitted=False; event:eea76ff08819cdad7ea80760: applied_candidate, admitted=True; event:1181b2225451506e9e3ad99c: recorded_observation, admitted=False; event:79623fc67f948854e017ad31: applied_candidate, admitted=True; event:9ead4512519833d8dfcc0367: applied_candidate, admitted=True; event:f4c339f6d04509b1b6e8374e: applied_candidate, admitted=True; event:1156dc2baad6123bd4ba274a: applied_candidate, admitted=True; event:44f96e14132959149d474c6f: applied_candidate, admitted=True; event:77d118996c5835a8b855549d: recorded_observation, admitted=False; event:c51fb1876ccd7b4ea2126503: applied_candidate, admitted=True; event:03b496a593a6ed88d55c0a7f: applied_candidate, admitted=True; event:46a017429e0993bfdf661a47: applied_candidate, admitted=True; event:6817c9383854518ec136ee1d: applied_candidate, admitted=True; event:f09c57d2b22f464f7df136e4: recorded_observation, admitted=False; event:1980a3cf9556b8ccd4f11620: applied_candidate, admitted=True; event:72b98fe619e6d6d8a3ee886d: recorded_observation, admitted=False; event:9fd62424fa46e324a9e72e85: applied_candidate, admitted=True; event:f37f3a51aa09d2372fffa226: applied_candidate, admitted=True; event:0a169f23382beeaf9771e589: applied_candidate, admitted=True; event:b3bd03287e798b86d890f224: recorded_observation, admitted=False; event:b4fd0fc32db1d68ffa0d3cd8: applied_candidate, admitted=True; event:e7b8ffa0dc6f23d9da548a7c: applied_candidate, admitted=True

### Event/card `nickname:development:Invincible`

```json
{"verdict": "cannot_determine", "eventKind": "identity", "actualEvent": "", "actor": "", "target": "", "species": "Lucario", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
287.015000–293.516667s; original card: Unresolved nickname: Invincible; kind=nickname; actual occurrence=False.
Source frame IDs: `e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3`, `7ac281afbdd9b5c522016599e43522da5a83775f0d6c076ed2c41de29e7ad556`, `416fa15bae97476e81ae1f217c0e8376052a035cd5fc0a812d3382dde5fb62fa`, `66fb20f438999f964931323c55b8be9d5c98296af70c28e864b758ee7f112029`, `c6cc9c65dbe8924e21eadc97a97a713af96e6dfc3098e76bcfc593ed53cb7cf3`, `9ffdc365dd9fdd841bd4c5df62edae3ea081a5d96ea927c5a4a52500781b8f46`, `c47d13a152f1e2c5c97c31e9d55399a115725d7b1d79ef07430c311a0f254492`, `010df8b0684d8df41a519040e8dba7cad73f29377def4fe7db17d0b152f824a1`, `293c200acf42a2a00ae74cac696f7b95f6c2371809f88a8bfce8ff818ecfa0dd`, `82c23913f64a1cc312dd4bd0d4cd2760eac2a547b911dfd5bb7535de51568c67`.
[Representative evidence](assets/e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3.png); baseline OCR: "0".
State decisions: event:5cef7adcc1ee6f45c62076f3: recorded_observation, admitted=False; event:6540389fbaf5ae69c133f8a2: recorded_observation, admitted=False; event:712041954c0f508fbd7a4470: applied_candidate, admitted=True; event:c6878965f68de1a5843bd991: applied_candidate, admitted=True; event:439952ad637f582a5415523b: recorded_observation, admitted=False; event:7806fdf000cc5a653b089449: applied_candidate, admitted=True; event:9a769487798ebf73fab29c22: recorded_observation, admitted=False; event:a87d0701d641d799965e3c21: applied_candidate, admitted=True; event:21232a9c7207d455e3393449: recorded_observation, admitted=False; event:3aa290d270af03dfe8972cc5: applied_candidate, admitted=True; event:7250e89668c09717e634f80d: recorded_observation, admitted=False; event:c5354e9bbb55eea948137ac5: applied_candidate, admitted=True; event:6012e5bffb87ada5a7607870: applied_candidate, admitted=True; event:b9e2d53cb468dd1114b185cc: recorded_observation, admitted=False; event:cb95752adb10aeb42d1be91c: applied_candidate, admitted=True; event:f9522ffbff4eb76c83da56d3: recorded_observation, admitted=False; event:42b4fd625e9da63093b21512: applied_candidate, admitted=True; event:915507538d85520c54626b1d: recorded_observation, admitted=False; event:e9136bedc3e04970a130bf48: applied_candidate, admitted=True; event:ffc51bdf5cddd33c3646f0bc: recorded_observation, admitted=False

### Event/card `hud:development:284`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "Big Nugget/Fortress", "target": "", "species": "", "hp": "15%", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
287.015000–297.533333s; original card: HUD identities and HP after entry; kind=hud_hp; actual occurrence=False.
Source frame IDs: `e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3`, `7ac281afbdd9b5c522016599e43522da5a83775f0d6c076ed2c41de29e7ad556`, `416fa15bae97476e81ae1f217c0e8376052a035cd5fc0a812d3382dde5fb62fa`, `66fb20f438999f964931323c55b8be9d5c98296af70c28e864b758ee7f112029`, `c6cc9c65dbe8924e21eadc97a97a713af96e6dfc3098e76bcfc593ed53cb7cf3`, `9ffdc365dd9fdd841bd4c5df62edae3ea081a5d96ea927c5a4a52500781b8f46`, `c47d13a152f1e2c5c97c31e9d55399a115725d7b1d79ef07430c311a0f254492`, `010df8b0684d8df41a519040e8dba7cad73f29377def4fe7db17d0b152f824a1`, `6829fd64940f9dec19bd93b55ede6005ee6df9435874a0dd7213e4292d4c7e11`, `5bd176d87df1aaebb7bc501ca81489d3033211e62e80337326a339665f1dee9a`, `3507c9fcdd05a0ec3eb36e83c167f084c1a5a3ea957611d6eaa41aad9f3d7be3`, `204a12876ce1732de34c47fc8f5655a9cfaa6dbb628cb47c71d8f8ae1795dbe8`, `293c200acf42a2a00ae74cac696f7b95f6c2371809f88a8bfce8ff818ecfa0dd`, `82c23913f64a1cc312dd4bd0d4cd2760eac2a547b911dfd5bb7535de51568c67`, `879e69145baf15f49a4dd43c0513ac100b61a6dc276712e52c712949791548ae`, `d24be9c1ca9ee8de0997300bf7a7c232f99fcbcadbea82ec175725fe786ed298`, `3aba72a947279fe56002dd297cd20504a7f7c2728144cc0e35ad5fc8ebae2b85`, `101b5e8e74481f84446fd97b0f86c2aa24d18bb8e7cc686cbb6e263a64ac4a54`, `7e5ed03b1b675a7a765f60d562739cc97eb46859eda468c246595d47f9ca7c8e`, `e1a14e317194855ffe15b66a446c6571ae7b21cd7ddc12da46f9bb89aca14657`, `dc8f0fe764a26bdc257ccbfe38c81c23b886a7043ed5b6ee6fbc9c2898814e0a`, `32ce0d490ef00150a319886fead390dc7bc124c321d0045d00a1d71705a3d864`.
[Representative evidence](assets/e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3.png); baseline OCR: "0".
State decisions: event:5cef7adcc1ee6f45c62076f3: recorded_observation, admitted=False; event:6540389fbaf5ae69c133f8a2: recorded_observation, admitted=False; event:712041954c0f508fbd7a4470: applied_candidate, admitted=True; event:c6878965f68de1a5843bd991: applied_candidate, admitted=True; event:439952ad637f582a5415523b: recorded_observation, admitted=False; event:7806fdf000cc5a653b089449: applied_candidate, admitted=True; event:9a769487798ebf73fab29c22: recorded_observation, admitted=False; event:a87d0701d641d799965e3c21: applied_candidate, admitted=True; event:21232a9c7207d455e3393449: recorded_observation, admitted=False; event:3aa290d270af03dfe8972cc5: applied_candidate, admitted=True; event:7250e89668c09717e634f80d: recorded_observation, admitted=False; event:c5354e9bbb55eea948137ac5: applied_candidate, admitted=True; event:6012e5bffb87ada5a7607870: applied_candidate, admitted=True; event:b9e2d53cb468dd1114b185cc: recorded_observation, admitted=False; event:cb95752adb10aeb42d1be91c: applied_candidate, admitted=True; event:f9522ffbff4eb76c83da56d3: recorded_observation, admitted=False; event:42b4fd625e9da63093b21512: applied_candidate, admitted=True; event:915507538d85520c54626b1d: recorded_observation, admitted=False; event:e9136bedc3e04970a130bf48: applied_candidate, admitted=True; event:ffc51bdf5cddd33c3646f0bc: recorded_observation, admitted=False; event:4ed0fa32f66c81b2f88f7591: applied_candidate, admitted=True; event:69cbff7ac2fa7111ee9eb34f: recorded_observation, admitted=False; event:71d9cf331ee032b92d91b74d: applied_candidate, admitted=True; event:79b2ff316750130bed5199dc: applied_candidate, admitted=True; event:29414f005a3a468fd360538e: applied_candidate, admitted=True; event:acadbc203cb493739f4a3d20: applied_candidate, admitted=True; event:d8e4674fecd8c911becc833e: recorded_observation, admitted=False; event:f62e14fec51cd0eddb8bc992: applied_candidate, admitted=True; event:69e6d919d6b63dc910b03b17: applied_candidate, admitted=True; event:6cac71c6b55892cc6dd5ca1f: applied_candidate, admitted=True; event:ba697487ff9a9e4e2c559bec: recorded_observation, admitted=False; event:da0056cbcac3d37afca09f21: applied_candidate, admitted=True; event:8e13aec74c77ca3c41fbff04: applied_candidate, admitted=True; event:a0989022c5b5d7d52aa4aa21: applied_candidate, admitted=True; event:bb23967deb764efe8c0db073: applied_candidate, admitted=True; event:dc977546e2b460072f94951c: recorded_observation, admitted=False; event:8797b621c0d3b12c256da838: applied_candidate, admitted=True; event:9974483e1270e152393b63e6: recorded_observation, admitted=False; event:eaa67e4bde9529c604b1569f: applied_candidate, admitted=True; event:f85b88df6a0837d2fc86376a: applied_candidate, admitted=True; event:11f5e1317c2691862689fd3d: applied_candidate, admitted=True; event:1c701453cc5eacce3cf04e81: applied_candidate, admitted=True; event:3ee1e1e3e06b689f6771665a: recorded_observation, admitted=False; event:93920889481295a5c1ba46ff: applied_candidate, admitted=True; event:7e1b890e8b2f7f47c356afd0: applied_candidate, admitted=True; event:c102e2cfe669ac90f23f2446: applied_candidate, admitted=True; event:d3bc1325feeefe2194bd3bab: recorded_observation, admitted=False; event:eea76ff08819cdad7ea80760: applied_candidate, admitted=True; event:1181b2225451506e9e3ad99c: recorded_observation, admitted=False; event:79623fc67f948854e017ad31: applied_candidate, admitted=True; event:9ead4512519833d8dfcc0367: applied_candidate, admitted=True; event:f4c339f6d04509b1b6e8374e: applied_candidate, admitted=True; event:1156dc2baad6123bd4ba274a: applied_candidate, admitted=True; event:44f96e14132959149d474c6f: applied_candidate, admitted=True; event:77d118996c5835a8b855549d: recorded_observation, admitted=False; event:c51fb1876ccd7b4ea2126503: applied_candidate, admitted=True; event:03b496a593a6ed88d55c0a7f: applied_candidate, admitted=True; event:46a017429e0993bfdf661a47: applied_candidate, admitted=True; event:6817c9383854518ec136ee1d: applied_candidate, admitted=True; event:f09c57d2b22f464f7df136e4: recorded_observation, admitted=False; event:1980a3cf9556b8ccd4f11620: applied_candidate, admitted=True; event:72b98fe619e6d6d8a3ee886d: recorded_observation, admitted=False; event:9fd62424fa46e324a9e72e85: applied_candidate, admitted=True; event:f37f3a51aa09d2372fffa226: applied_candidate, admitted=True; event:0a169f23382beeaf9771e589: applied_candidate, admitted=True; event:b3bd03287e798b86d890f224: recorded_observation, admitted=False; event:b4fd0fc32db1d68ffa0d3cd8: applied_candidate, admitted=True; event:e7b8ffa0dc6f23d9da548a7c: applied_candidate, admitted=True

### Event/card `u:fd9f8ab5370010159be52546d7ee891e53bb90df700c52ce902b41d651a5d400:field`

```json
{"verdict": "incorrect", "eventKind": "move_description_overlay", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
140.023333–140.023333s; original card: Weather / terrain / Trick Room indicator · 140.023s; kind=field_indicator; actual occurrence=False.
Source frame IDs: `fd9f8ab5370010159be52546d7ee891e53bb90df700c52ce902b41d651a5d400`.
[Representative evidence](assets/fd9f8ab5370010159be52546d7ee891e53bb90df700c52ce902b41d651a5d400.png); baseline OCR: "".
No state decision on this navigation card; see per-frame evidence.

### Event/card `u:b5b5dc9a30c511e57e0b60bdfea6f84ed6abadab22c0c832d198cb50f4cb99c0:field`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "天气/场地状态，持续在画面左上角显示。", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
240.006667–240.006667s; original card: Weather / terrain / Trick Room indicator · 240.007s; kind=field_indicator; actual occurrence=False.
Source frame IDs: `b5b5dc9a30c511e57e0b60bdfea6f84ed6abadab22c0c832d198cb50f4cb99c0`.
[Representative evidence](assets/b5b5dc9a30c511e57e0b60bdfea6f84ed6abadab22c0c832d198cb50f4cb99c0.png); baseline OCR: "".
No state decision on this navigation card; see per-frame evidence.

### Event/card `interval:837bb40eed342913a5b1280ca8f72d3a4971e32cfc3554f67215d3a6c46e0139`

```json
{"verdict": "correct", "eventKind": "mega", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
406.001667–413.003333s; original card: Mega Evolution animation — no-text example; kind=background; actual occurrence=False.
Source frame IDs: `837bb40eed342913a5b1280ca8f72d3a4971e32cfc3554f67215d3a6c46e0139`, `c32230b187757b598d900693821fb3fc30885f94e7db4d43bcfa449cee795193`, `6b2119d74b81f282c9dc03f40719f8d4dafe6ef9d660f047b4c434123c460953`, `af9c5dfbafa380de211406f2b15b9e2f6c8d1be37c2bd05c2a56161d751e09ed`, `9ea7c063fc692555c72e5d948fdcc7c242e5f8bc219f669fcad8de959147b195`, `0d2afc7e4af2553fd4a2084375bf4341a4ae07f6cbd3e602bd70bf0769791278`, `c5aff75122b2ad8b802544c65ed2eac9873f211e83f966813df578d11ad8a582`, `2be97bcee2b6723123da881d9cf87293f7631bbc42683de8992814098bb2418d`, `94eca23a6cc3c940610090eb0bf270531f5bf4e936de2cf0c2302e1a31e3b03e`, `5eb82fbeff0f6770f15fb92d8fe81f84a15e36bc4f46216c322cab9ac99770c9`, `23638ae9fe8952aea53325eda7cadfe4496c2516f74e3be7c9998821976d11ee`, `6002b7d8ecbadf0b50020615792457e5375d5dc3767bd675fa8e4ecf2c31a241`, `b4564eb4478cef762140005bafd7938a4c9a4eb8fad4ea30d4889c99728321b4`, `9a6786ef18da14eeb24733c7baeb78c516b923a9d78c7b8dbfca2112e2482d86`, `4331062f087e7c66ac890a36b7dfa08161ac45ae07c9451c5c794f396b0e9eb3`.
[Representative evidence](assets/837bb40eed342913a5b1280ca8f72d3a4971e32cfc3554f67215d3a6c46e0139.png); baseline OCR: "2".
State decisions: event:06e58dd171670926aff0d906: deferred, admitted=False; event:5cb91f31805589c0103e12e1: deferred, admitted=False; event:a6c1d5799abe597f1911be1a: deferred, admitted=False; event:efa14441c582eeaea3f8e50b: deferred, admitted=False; event:eed8f09e3d822e37250734b9: deferred, admitted=False

### Event/card `interval:302f72f6f034f3921f6d385a24360c85d1e5bcd279bfde5f91a163f154436c9a`

```json
{"verdict": "cannot_determine", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
423.505000–423.505000s; original card: Message visibility / transition interval; kind=background; actual occurrence=False.
Source frame IDs: `302f72f6f034f3921f6d385a24360c85d1e5bcd279bfde5f91a163f154436c9a`.
[Representative evidence](assets/302f72f6f034f3921f6d385a24360c85d1e5bcd279bfde5f91a163f154436c9a.png); baseline OCR: "1\n1".
State decisions: event:b25a6658ff046a950558fc3e: deferred, admitted=False

### Event/card `occurrence:mega_revelation`

```json
{"verdict": "correct", "eventKind": "mega", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
413.503333–415.003333s; original card: Big Mom’s Mega Evolution revelation; kind=transformation; actual occurrence=True.
Source frame IDs: `a3aa8271f87239a8cb740c32dbe20c6e7949966a8e406b1f92f4999b3dccddbb`, `1d20b0053544d3d1d1917d227f6e38fb82e440b54d2679fbfc9e453b5a457bf4`, `0601b6c98e386dd166f33217f2d7e6af05968d07aa319dbc583ebaf2a821fd91`, `2eeb4c991fdb2342f2aa623166006b56a3f1606db7e3539701ec0af4a8f8e6d5`.
[Representative evidence](assets/a3aa8271f87239a8cb740c32dbe20c6e7949966a8e406b1f92f4999b3dccddbb.png); baseline OCR: "对手的Big Mom超级进化成了超级袋兽！".
State decisions: event:e9edf03eb60c1b617706d22f: recorded_observation, admitted=True; event:3fc190b64ed4987f41a5a681: applied_candidate, admitted=True; event:2a3a1505977e2e33afadf06f: deferred, admitted=False

### Event/card `occurrence:fake_out`

```json
{"verdict": "correct", "eventKind": "move", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
415.503333–417.503333s; original card: Fake Out — identified and attributed · baseline / U comparison; kind=move_execution; actual occurrence=True.
Source frame IDs: `a3a5a701dadfd45d9796047845befd74e1b00a63c11e177cc3835fdc2bb2242a`, `3dd6574562b4d8a43230defd483611cdb004c1a9641f1ccbb738496022f93f8b`, `3ebb1d91de297581b1edb8b08f184185568f236a025c634bcd2890ea8c4c53fe`, `6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243`, `d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619`.
[Representative evidence](assets/a3a5a701dadfd45d9796047845befd74e1b00a63c11e177cc3835fdc2bb2242a.png); baseline OCR: "对手的BigMom使出了击堂奇龚出手可表！".
State decisions: event:6f15947550c45b67a9e1175e: deferred, admitted=False; event:813ff44b7eb9a37dd3afc8a4: deferred, admitted=False; event:81531417c53140f189550aa5: applied_partial, admitted=True; event:d51e8f57b0c8c09e518a5db3: deferred, admitted=False; event:4d140db768b2894d29b0f5a8: deferred, admitted=False

### Event/card `occurrence:coaching_stages`

```json
{"verdict": "correct", "eventKind": "stat", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "this is a result of Lucario used Coaching. ", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
430.005000–431.506667s; original card: Attack and Defense increased; kind=stat_change; actual occurrence=True.
Source frame IDs: `a021396b94439ae7c86b8fd0b39b08db5a66896cca46c0b62b353ddfcc9368cd`, `e2198e7f34af4d6bd71ff48586f184f69b43001bb8b143a6a22da623c74ccd6f`, `be6ebb6656f2b3e66afe78d8b66731f765dddf2a07f74fa03830111118c1ec4a`, `f47194e29f08666948e61510d3a95969dd3d2a37a24b66fb99205c49bec824c6`.
[Representative evidence](assets/a021396b94439ae7c86b8fd0b39b08db5a66896cca46c0b62b353ddfcc9368cd.png); baseline OCR: "对手的BigMom的攻击、防御提高了！".
State decisions: event:8f42bdc4568012e655e07c6b: applied_candidate, admitted=True

### Event/card `occurrence:not_effective`

```json
{"verdict": "correct", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
419.503333–421.005000s; original card: Not very effective — target context unresolved; kind=effectiveness; actual occurrence=True.
Source frame IDs: `31c15c5e1afb462baced53a3507543e6e6ba242ca64aee0c4594f1e51c388078`, `c41cceb61e046e78369068a806e169fd9296ece425b36919fbe6af431c63bdda`, `fc4fbb54328f12a4bf316884be8650d8acc46a703fbede07c436f8634b20684b`, `8401a74729ce9d86df6ec1a097bb1ebc17b8b2cc9f75f5351bf6b924a29bc192`.
[Representative evidence](assets/31c15c5e1afb462baced53a3507543e6e6ba242ca64aee0c4594f1e51c388078.png); baseline OCR: "对龙头地鼠效果不好。".
State decisions: event:2080b1b77f1d1d7f85d971ea: deferred, admitted=False

### Event/card `occurrence:two_hits`

```json
{"verdict": "correct", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
421.005000–423.005000s; original card: Two-hit notice; kind=multi_hit; actual occurrence=True.
Source frame IDs: `8401a74729ce9d86df6ec1a097bb1ebc17b8b2cc9f75f5351bf6b924a29bc192`, `6faede718c9657dae7fb20ec0d3f5ed37d8371a4872a65378ccf4d45eae6090a`, `675affc35ff8a50db096138f63316cfbf46986dc556c894a728f133ad7545944`, `9084a200a21155ba989d64861f330a4f8b558b2434cc944deab11381f8a9fef8`, `3748f48edb948adb074da3034e82b2fea6a37fb623b0aed56fe33cb20534cf60`.
[Representative evidence](assets/8401a74729ce9d86df6ec1a097bb1ebc17b8b2cc9f75f5351bf6b924a29bc192.png); baseline OCR: "".
State decisions: event:6db7260af289bbb3a567cea5: deferred, admitted=False; event:36d4513f009faad475e2637b: deferred, admitted=False

### Event/card `u:d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619:field`

```json
{"verdict": "no_ui", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
417.503333–417.503333s; original card: Weather / terrain / Trick Room indicator · 417.503s; kind=field_indicator; actual occurrence=False.
Source frame IDs: `d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619`.
[Representative evidence](assets/d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619.png); baseline OCR: "\n\n一\n\n".
No state decision on this navigation card; see per-frame evidence.

### Event/card `u:6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243:field`

```json
{"verdict": "incorrect", "eventKind": "move", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
417.003333–417.003333s; original card: Weather / terrain / Trick Room indicator · 417.003s; kind=field_indicator; actual occurrence=False.
Source frame IDs: `6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243`.
[Representative evidence](assets/6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243.png); baseline OCR: "对手的Big Mom使出了".
No state decision on this navigation card; see per-frame evidence.

### Event/card `u:0e2995b882068c5437a29b53457b8bd7e47758d9a3c9e228a63a5a6ec22c3f76:overlay`

```json
{"verdict": "correct", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
400.000000–400.000000s; original card: Target-selection overlay · 400.0s; kind=target_selection; actual occurrence=False.
Source frame IDs: `0e2995b882068c5437a29b53457b8bd7e47758d9a3c9e228a63a5a6ec22c3f76`.
[Representative evidence](assets/0e2995b882068c5437a29b53457b8bd7e47758d9a3c9e228a63a5a6ec22c3f76.png); baseline OCR: "".
No state decision on this navigation card; see per-frame evidence.

### Event/card `u:af2b73eaf867eff7588808109d3dbd6efdb28cd7c98e2d967a79b65628782eb1:overlay`

```json
{"verdict": "correct", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
384.548333–384.548333s; original card: Check Status Overlay · 384.548s; kind=status_overlay; actual occurrence=False.
Source frame IDs: `af2b73eaf867eff7588808109d3dbd6efdb28cd7c98e2d967a79b65628782eb1`.
[Representative evidence](assets/af2b73eaf867eff7588808109d3dbd6efdb28cd7c98e2d967a79b65628782eb1.jpg); baseline OCR: "".
No state decision on this navigation card; see per-frame evidence.

### Event/card `u:1af4952460ffc1aa4f621a8d5de8cdb289939c375979369f92a64335b33df17d:overlay`

```json
{"verdict": "correct", "eventKind": "cannot_determine", "actualEvent": "", "actor": "", "target": "", "species": "", "hp": "", "feedback": "", "proximity": false, "fieldAbility": "", "errorCategory": "cannot_determine"}
```
374.000000–374.000000s; original card: Battle Log Overlay · 374.0s; kind=battle_log_overlay; actual occurrence=False.
Source frame IDs: `1af4952460ffc1aa4f621a8d5de8cdb289939c375979369f92a64335b33df17d`.
[Representative evidence](assets/1af4952460ffc1aa4f621a8d5de8cdb289939c375979369f92a64335b33df17d.png); baseline OCR: "".
No state decision on this navigation card; see per-frame evidence.

### Structured frame: 108.001667s

Frame ID: `d2cd6410992a5f298626f2836e9f1fa7bf189c1552f5a9a0689d9200fd849903`. [Cached pixels](assets/d2cd6410992a5f298626f2836e9f1fa7bf189c1552f5a9a0689d9200fd849903.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/4a22bdeaa893b36794a00e05/000001.png`.

User record:
```json
{"message_class": "no_message", "visible_message": "", "feedback": "pre-battle Pokemon selection page", "reading_source": "baseline"}
```
Baseline OCR: "\n3U人".

- baseline `event:eac365d2a6e5782f2ce71930` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 110.501667s

Frame ID: `599ade1064189f6cdd4f4a2ff3ac7ca68de43dbdd0ca2b52ad0e277c9e0db0c3`. [Cached pixels](assets/599ade1064189f6cdd4f4a2ff3ac7ca68de43dbdd0ca2b52ad0e277c9e0db0c3.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c7cba21458aeb98b5904b1e3/000002.png`.

User record:
```json
{"message_class": "no_message", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "".

baseline: no new receipt at this exact timestamp (not proof of no prior occurrence admission).
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 116.020000s

Frame ID: `00bd6d5e86ce9fcb37483ea299e62590dc5b0f1b6113a477f34a50f46a5b9481`. [Cached pixels](assets/00bd6d5e86ce9fcb37483ea299e62590dc5b0f1b6113a477f34a50f46a5b9481.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c7cba21458aeb98b5904b1e3/000013.png`.

User record:
```json
{"message_class": "readable_missed", "visible_message": "", "feedback": "pre-battle player information, contains each player id, and current rank", "reading_source": "baseline"}
```
Baseline OCR: "O: O".

- baseline `event:73d16051a57fa99f6bd69275` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 426.505000s

Frame ID: `39075cf76ef83434847f991aa0981c7707d6906f32fb583a98c487d24f6a90ba`. [Cached pixels](assets/39075cf76ef83434847f991aa0981c7707d6906f32fb583a98c487d24f6a90ba.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c9c516c2bdc377b888a49e95/000014.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "Correctly recognized. Coach does not show its target, but you can tell by next visible message, who's attack & defense has been changed. ", "reading_source": "baseline"}
```
Baseline OCR: "对手的lnvincible使出了\ne\n居".

U OCR: "对手的Invincible使出了\n指导!"; selected=True.
- baseline `event:74930922d0021acc798db51d` move_execution: deferred, admitted=False; Required identity, side, move or effect information was unresolved; state mutation was withheld.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 292.516667s

Frame ID: `204a12876ce1732de34c47fc8f5655a9cfaa6dbb628cb47c71d8f8ae1795dbe8`. [Cached pixels](assets/204a12876ce1732de34c47fc8f5655a9cfaa6dbb628cb47c71d8f8ae1795dbe8.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/0504c4414a29daf6726590cb/000006.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "00".

baseline: 4 HUD receipts; event:8e13aec74c77ca3c41fbff04: applied_candidate; event:a0989022c5b5d7d52aa4aa21: applied_candidate; event:bb23967deb764efe8c0db073: applied_candidate; event:dc977546e2b460072f94951c: recorded_observation.
- baseline `event:934dd4cfe4fa125cdee8b61c` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 420.003333s

Frame ID: `c41cceb61e046e78369068a806e169fd9296ece425b36919fbe6af431c63bdda`. [Cached pixels](assets/c41cceb61e046e78369068a806e169fd9296ece425b36919fbe6af431c63bdda.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c9c516c2bdc377b888a49e95/000001.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "对龙头地鼠效果不好。".

baseline: 1 HUD receipts; event:011b121065a8f2d51af04c2d: applied_candidate.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 122.020000s

Frame ID: `7ac92a1f0d805c04939cfe12436578185e376e649b6d7dc6bc78d90276f1788d`. [Cached pixels](assets/7ac92a1f0d805c04939cfe12436578185e376e649b6d7dc6bc78d90276f1788d.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/e74239531a14c26350a424ae/000005.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "J派出了级别对战大师BigNugget\n和喜欢宝可梦的Invincible！\n可以看出对手使用的都是自定义宝可梦名字，而非默认的种族名。", "reading_source": "baseline"}
```
Baseline OCR: "J派出了级别对战大师BigNugget\n和喜欢宝可梦的Invincible！".

- baseline `event:a730b0ab76646edc1a0af555` entry_observation: recorded_observation, admitted=False; Stored as an observation; this does not establish an active slot or a mechanical effect.
- baseline `event:626eb5302082ea3f468efbdf` send_out: deferred, admitted=False; Required identity, side, move or effect information was unresolved; state mutation was withheld.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 124.521667s

Frame ID: `3278e3ad5920ac6c8650bc5bd8f1462450c069b7b108822aa1ff69f0c27a26ae`. [Cached pixels](assets/3278e3ad5920ac6c8650bc5bd8f1462450c069b7b108822aa1ff69f0c27a26ae.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/e74239531a14c26350a424ae/000010.png`.

User record:
```json
{"message_class": "readable_incorrect", "visible_message": "上吧！班基拉斯！龙头地鼠！", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "上吧！班基拉斯！\n化不地：".

- baseline `event:e91dc635d861d7dc7d077c54` entry_observation: recorded_observation, admitted=False; Stored as an observation; this does not establish an active slot or a mechanical effect.
- baseline `event:96229e875d15c0b696df3ecb` send_out: recorded_observation, admitted=True; Only named identity is supported; placement and biological continuity are not established.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 128.021667s

Frame ID: `9383ac8aaa34bf7156298fa92374b04e3861756a32663308fa6661688f7b6ade`. [Cached pixels](assets/9383ac8aaa34bf7156298fa92374b04e3861756a32663308fa6661688f7b6ade.png). Original source: `../../.cache/battles/sample_battle_5/m235/acquisition/sampling/df80a9b1e4c77d2514ab79f3/5dcb2b2aecb0e078d34bd12b/000001.png`.

User record:
```json
{"message_class": "readable_missed", "visible_message": "班基拉斯的扬沙", "feedback": "在屏幕左侧，特性发动区域。", "reading_source": "ui_u"}
```
Baseline OCR: "".

U OCR: ""; selected=False.
baseline: no new receipt at this exact timestamp (not proof of no prior occurrence admission).
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 140.023333s

Frame ID: `fd9f8ab5370010159be52546d7ee891e53bb90df700c52ce902b41d651a5d400`. [Cached pixels](assets/fd9f8ab5370010159be52546d7ee891e53bb90df700c52ce902b41d651a5d400.png). Original source: `../../.cache/battles/sample_battle_5/m235/acquisition/sampling/df80a9b1e4c77d2514ab79f3/f619b066e0650ea726efd027/000001.png`.

User record:
```json
{"message_class": "cannot_determine", "visible_message": "", "feedback": "", "reading_source": "ui_u"}
```
Baseline OCR: "".

U OCR: ""; selected=False.
baseline: no new receipt at this exact timestamp (not proof of no prior occurrence admission).
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 240.006667s

Frame ID: `b5b5dc9a30c511e57e0b60bdfea6f84ed6abadab22c0c832d198cb50f4cb99c0`. [Cached pixels](assets/b5b5dc9a30c511e57e0b60bdfea6f84ed6abadab22c0c832d198cb50f4cb99c0.png). Original source: `../../.cache/battles/sample_battle_5/m235/acquisition/sampling/df80a9b1e4c77d2514ab79f3/ef70d43cb93438833f5a5a9f/000001.png`.

User record:
```json
{"message_class": "cannot_determine", "visible_message": "沙暴状态           4/5", "feedback": "", "reading_source": "ui_u"}
```
Baseline OCR: "".

U OCR: ""; selected=False.
baseline: no new receipt at this exact timestamp (not proof of no prior occurrence admission).
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 284.015000s

Frame ID: `57a8e90c78adad7d98bb583f581cf752f0cd61b5af251d154022d1d4fa05db1b`. [Cached pixels](assets/57a8e90c78adad7d98bb583f581cf752f0cd61b5af251d154022d1d4fa05db1b.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/2e4df209b17e1036eab60cac/000001.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "班基拉斯 switched in", "reading_source": "baseline"}
```
Baseline OCR: "上吧！班基拉斯！".

- baseline `event:dd2aaca70e4491d102d343c8` entry_observation: recorded_observation, admitted=False; Stored as an observation; this does not establish an active slot or a mechanical effect.
- baseline `event:48a4566027412a14340704cb` send_out: recorded_observation, admitted=True; Only named identity is supported; placement and biological continuity are not established.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 423.505000s

Frame ID: `302f72f6f034f3921f6d385a24360c85d1e5bcd279bfde5f91a163f154436c9a`. [Cached pixels](assets/302f72f6f034f3921f6d385a24360c85d1e5bcd279bfde5f91a163f154436c9a.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c9c516c2bdc377b888a49e95/000008.png`.

User record:
```json
{"message_class": "no_message", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "1\n1".

- baseline `event:b25a6658ff046a950558fc3e` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 429.005000s

Frame ID: `afeb72a7a2d3e9f9e16f50d7569e8ddb1779a1900b95190aa47314b0216441eb`. [Cached pixels](assets/afeb72a7a2d3e9f9e16f50d7569e8ddb1779a1900b95190aa47314b0216441eb.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c9c516c2bdc377b888a49e95/000019.png`.

User record:
```json
{"message_class": "no_message", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "O\nCN\n101N".

- baseline `event:bb9f6dc93e1373d3f2c29e75` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 413.503333s

Frame ID: `a3aa8271f87239a8cb740c32dbe20c6e7949966a8e406b1f92f4999b3dccddbb`. [Cached pixels](assets/a3aa8271f87239a8cb740c32dbe20c6e7949966a8e406b1f92f4999b3dccddbb.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/436c8f82ad40c0ee5e246c44/000008.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "对手的Big Mom超级进化成了超级袋兽！".

U OCR: "对手的Big Mom超级进化成了\n超级袋兽！"; selected=True.
- baseline `event:e9edf03eb60c1b617706d22f` alias_observation: recorded_observation, admitted=True; Only named identity is supported; placement and biological continuity are not established.
- baseline `event:3fc190b64ed4987f41a5a681` transformation: applied_candidate, admitted=True; The supported observation passed the existing state policy.
- U `event:e9edf03eb60c1b617706d22f` alias_observation: recorded_observation, admitted=True; Only named identity is supported; placement and biological continuity are not established.
- U `event:3fc190b64ed4987f41a5a681` transformation: applied_candidate, admitted=True; The supported observation passed the existing state policy.

### Structured frame: 416.503333s

Frame ID: `3ebb1d91de297581b1edb8b08f184185568f236a025c634bcd2890ea8c4c53fe`. [Cached pixels](assets/3ebb1d91de297581b1edb8b08f184185568f236a025c634bcd2890ea8c4c53fe.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/436c8f82ad40c0ee5e246c44/000014.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "对手的Big Mom使出了击掌奇袭！".

U OCR: "对手的Big Mom使出了\n击掌奇袭！"; selected=True.
- baseline `event:81531417c53140f189550aa5` move_execution: applied_partial, admitted=True; Actor and executed move were supported. Targets and move effects were not established.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 430.005000s

Frame ID: `a021396b94439ae7c86b8fd0b39b08db5a66896cca46c0b62b353ddfcc9368cd`. [Cached pixels](assets/a021396b94439ae7c86b8fd0b39b08db5a66896cca46c0b62b353ddfcc9368cd.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/312d2dcf3cd27cb2d4ffc550/000001.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "对手的BigMom的攻击、防御提高了！".

U OCR: "对手的Big Mom的\n攻击、防御提高了！"; selected=True.
- baseline `event:8f42bdc4568012e655e07c6b` stat_change: applied_candidate, admitted=True; The supported observation passed the existing state policy.
- U `event:8f42bdc4568012e655e07c6b` stat_change: applied_candidate, admitted=True; The supported observation passed the existing state policy.

### Structured frame: 422.005000s

Frame ID: `675affc35ff8a50db096138f63316cfbf46986dc556c894a728f133ad7545944`. [Cached pixels](assets/675affc35ff8a50db096138f63316cfbf46986dc556c894a728f133ad7545944.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c9c516c2bdc377b888a49e95/000005.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "击中了2次！".

baseline: 1 HUD receipts; event:0fbe852096799864da715a89: applied_candidate.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 420.520000s

Frame ID: `fc4fbb54328f12a4bf316884be8650d8acc46a703fbede07c436f8634b20684b`. [Cached pixels](assets/fc4fbb54328f12a4bf316884be8650d8acc46a703fbede07c436f8634b20684b.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/c9c516c2bdc377b888a49e95/000002.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "", "reading_source": "baseline"}
```
Baseline OCR: "对龙头地鼠效果不好。".

baseline: 1 HUD receipts; event:f276e739d94b41535dfdcdd8: applied_candidate.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 417.503333s

Frame ID: `d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619`. [Cached pixels](assets/d0c87bd13fc24621bb5f6f4ffbac7c4b3e1069b2faa98ca6809a750d357a0619.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/436c8f82ad40c0ee5e246c44/000016.png`.

User record:
```json
{"message_class": "no_message", "visible_message": "", "feedback": "", "reading_source": "ui_u"}
```
Baseline OCR: "\n\n一\n\n".

U OCR: ""; selected=False.
baseline: 1 HUD receipts; event:b74a659efc954cc5eed7ff92: applied_candidate.
- baseline `event:4d140db768b2894d29b0f5a8` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: 1 HUD receipts; event:b74a659efc954cc5eed7ff92: applied_candidate.

### Structured frame: 417.003333s

Frame ID: `6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243`. [Cached pixels](assets/6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/436c8f82ad40c0ee5e246c44/000015.png`.

User record:
```json
{"message_class": "readable_correct", "visible_message": "", "feedback": "对手的Big Mom使出了击掌奇袭！", "reading_source": "ui_u"}
```
Baseline OCR: "对手的Big Mom使出了".

U OCR: "对手的Big Mom使出了\n击掌奇袭!"; selected=True.
- baseline `event:d51e8f57b0c8c09e518a5db3` move_execution: deferred, admitted=False; Required identity, side, move or effect information was unresolved; state mutation was withheld.
U: no new receipt at this exact timestamp (not proof of no prior occurrence admission).

### Structured frame: 287.015000s

Frame ID: `e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3`. [Cached pixels](assets/e87440048ba46508452331874880cc93a2888fdbbc04debc0b736870af4170b3.png). Original source: `../../.cache/battles/sample_battle_5/m236/acquisition/sampling/df80a9b1e4c77d2514ab79f3/2e4df209b17e1036eab60cac/000007.png`.

User record:
```json
{"message_class": "cannot_determine", "visible_message": "", "feedback": "", "reading_source": "ui_u"}
```
Baseline OCR: "0".

U OCR: ""; selected=False.
baseline: 4 HUD receipts; event:5cef7adcc1ee6f45c62076f3: recorded_observation; event:6540389fbaf5ae69c133f8a2: recorded_observation; event:712041954c0f508fbd7a4470: applied_candidate; event:c6878965f68de1a5843bd991: applied_candidate.
- baseline `event:d6f7af5b667d5356fa3d4668` unknown: deferred, admitted=False; OCR confidence was below the admission threshold. No semantic event was admitted.
U: 4 HUD receipts; event:5cef7adcc1ee6f45c62076f3: recorded_observation; event:6540389fbaf5ae69c133f8a2: recorded_observation; event:712041954c0f508fbd7a4470: applied_candidate; event:c6878965f68de1a5843bd991: applied_candidate.

Legacy `a30e0e26f0b7843dbe52c186f78c5221ee6271a9880012f0e975a49c414c9478` at 418.020000s: {"reviewed": true, "unsupported_proximity": false, "note": "(empty)"}.
Baseline OCR: "0\n1"; frame-reviewed flag only, no event verdict.

Legacy `9ea7c063fc692555c72e5d948fdcc7c242e5f8bc219f669fcad8de959147b195` at 408.001667s: {"reviewed": true, "unsupported_proximity": false, "note": "(empty)"}.
Baseline OCR: "ype"; frame-reviewed flag only, no event verdict.

Legacy `b4564eb4478cef762140005bafd7938a4c9a4eb8fad4ea30d4889c99728321b4` at 412.003333s: {"reviewed": true, "unsupported_proximity": false, "note": "(empty)"}.
Baseline OCR: "一\nn"; frame-reviewed flag only, no event verdict.

Legacy `9a6786ef18da14eeb24733c7baeb78c516b923a9d78c7b8dbfca2112e2482d86` at 412.503333s: {"reviewed": true, "unsupported_proximity": false, "note": "(empty)"}.
Baseline OCR: "\nn"; frame-reviewed flag only, no event verdict.

Legacy `4331062f087e7c66ac890a36b7dfa08161ac45ae07c9451c5c794f396b0e9eb3` at 413.003333s: {"reviewed": true, "unsupported_proximity": false, "note": "(empty)"}.
Baseline OCR: "\nD"; frame-reviewed flag only, no event verdict.

Legacy `2eeb4c991fdb2342f2aa623166006b56a3f1606db7e3539701ec0af4a8f8e6d5` at 415.003333s: {"reviewed": true, "unsupported_proximity": false, "note": "(empty)"}.
Baseline OCR: "\n01"; frame-reviewed flag only, no event verdict.

Legacy `a3a5a701dadfd45d9796047845befd74e1b00a63c11e177cc3835fdc2bb2242a` at 415.503333s: {"reviewed": true, "unsupported_proximity": false, "note": "对手的Big Mom使出了击掌奇袭！"}.
Baseline OCR: "对手的BigMom使出了击堂奇龚出手可表！"; frame-reviewed flag only, no event verdict.

Legacy `3dd6574562b4d8a43230defd483611cdb004c1a9641f1ccbb738496022f93f8b` at 416.003333s: {"reviewed": true, "unsupported_proximity": false, "note": "对手的Big Mom使出了击掌奇袭！"}.
Baseline OCR: "对手的Big Mom使出了击堂奇袭山手可表！"; frame-reviewed flag only, no event verdict.

Legacy `6ac5b365e94ce6b20ce69b5dfe784f0dcf429ff63b2b39e62fb3adfe2308f243` at 417.003333s: {"reviewed": true, "unsupported_proximity": false, "note": "对手的Big Mom使出了击掌奇袭！"}.
Baseline OCR: "对手的Big Mom使出了"; frame-reviewed flag only, no event verdict.

## Limits and next work

No OCR, video decoding, recognition model, StateEngine, historical labels or frozen evaluation reports were changed. Human corrections were not promoted to ground truth. The original intermittent Chrome image failure was not reproduced; see `viewer-validation.md` for observed behavior and limits. Review remains partial.
