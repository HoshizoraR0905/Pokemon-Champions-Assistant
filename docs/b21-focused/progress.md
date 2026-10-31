# B21 recovery/miss fixes and read-only occupancy diagnosis — 2026-10-29

Scope:fix possessive recovery recipient; conditional Grassy Terrain end-of-turn
attribution; move_miss parser/target/action association. Diagnose occupancy only.
No full decoding/OCR, frozen B21/reference overwrite, occupancy/identity/switch
changes, Confusion/Struggle changes, performance work, new videos, commit/push.

Namespace:.cache/battles/sample_battle_21/diagnosis/recovery-miss-occupancy-20261029-v1/.
Protected hashes and before-source copies recorded before editing. Existing
benchmark source/receipts/reference remain original. No running jobs at start.

Plan:source inspection, localized implementation/tests, scoped saved-event replay,
per-message before/after semantic and separate HP results, causal occupancy timeline
from frozen receipts plus saved-image/HUD review. Stop before occupancy repair.

Initial facts:6 early own-right occupancy deferrals are replacement gaps. Persistent
opponent gap starts at522.005s after two accepted faints(488.032/510.020):Rillaboom
unplaced with two vacant slots;Staraptor526.505 send_out loses actor at .9471875
identity admission threshold .95. Later HUD starts535.507. Investigate exact state,
raw OCR, reconstruction and missed recovery path; no threshold/placement edits.

Completed:
- Localized recipient grammar, conditional terrain recovery, late named-HP
  attribution and missed-target/action support implemented in existing modules.
- Final focused saved replay is v3:177 original unchanged events +5 observed
  command-cycle phase markers +1 miss =183 events through435s. Nine semantic
  records recovered;6 supported terrain HP deltas;2 remain numerically unknown.
- v1/v2 development outputs retained, not overwritten. v3 manifest identity and
  output hashes verified by successful compatible-cache reuse.
- Read-only occupancy audit saved under v1/occupancy-diagnosis.json.37 identity
  transitions projected;original frozen receipts remain authoritative.200
  occupancy deferrals =6 temporary own replacement gaps +194 persistent opponent
  gap535.506667–684.531667.522.005 ambiguity;526.505 Staraptor admission failure
  prevents the existing two-entry HUD verifier from obtaining an eligible pair.
- Saved536.006667 frame visibly identifies opponent leftStaraptor/rightRillaboom;
  structured lightweight cards contain no species/icon identities. No repair.
-322 integrated portable regressions passed;final16 focused checks passed,
  including one additional command-session test (323 distinct passing checks).
- Frozen observations/replay/video-only/HP benchmark and reference hashes match.
  Protected occupancy/identity files andStateEngine._resolve AST unchanged.
- git diff --check passed. No commit or push. No decoding/OCR or other recording.

Final report:docs/b21-focused/report.md. Exact bounded verification/resume commands
are in that report. No running stages or required fix work remain;occupancy repair
is intentionally left for a separately authorized task.
