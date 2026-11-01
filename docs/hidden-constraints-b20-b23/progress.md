# B20–B23 hidden-constraint experiment

2026-10-31. Experiment outputs complete; no commit or push authorized.

Scope: six preview members per battle, chronological hidden-stat/item constraints,
no usage priors or empirical weights, saved recognition only. Original runs and
diagnoses remain immutable. New outputs use `diagnosis/hidden-constraints-20261031-v1`.

User confirmations:

- All four recordings are ranked doubles with Item Clause applying to all six
  roster members, not only selected/revealed members.
- User-specified negative Life Orb evidence: a successful damaging attack, no
  Protect/immunity and no displayed Life Orb HP loss can exclude current Life Orb
  when Magic Guard and applicable Sheer Force suppression are excluded. Preserve
  the difference between an absent display and an unread observation window.

Inspection completed:

- Existing Speed v2 and offensive inverse APIs, compact Champions SP domains,
  item clause propagation and Life Orb gates inspected; reuse these components.
- Original B20–B23 accepted states leave many stages/status/modifier fields unknown.
  Never fill those with zero/neutral values just to obtain a numerical result.
- B22 has a saved corrected, team-linked Mega-stat replay and 3/4 FPS hit projection;
  other battles have original sealed production data and separately scoped diagnoses.
- B23 has two Incineroar encounter identities with unresolved persistent continuity;
  do not merge them by species. B22's saved Ditto correction is a distinct source.
- Official M-C notice corroborates Item Clause; its scope on these four battles is
  established by the user's explicit confirmation. Life Orb reference callbacks and
  52Poké corroboration remain distinct from independently certified Champions UI rules.

Stages: inspect complete; implement/test minimal gates and trace adapter; pilot B22;
then process B20, B21 and B23 separately, reusing completed fingerprinted stages.
Detailed resume commands and results will be recorded here as stages complete.

## Completion / handoff

- Four context stages complete and checksum-reused; four final trace stages complete. No video decoding, new OCR/icon recognition or production replay. Original input hashes and readonly public database hashes verified unchanged.
- Main report: [B20–B23 summary](/Users/yyi/Pokemon-Champions-Assistant/reports/B20-B23-hidden-constraint-traces-20261031.md). Per-battle final report/JSON links are in that report and each diagnostic latest.json. Pilot outputs remain preserved.
- 24 roster panels, 16 revealed members; unproven encounter continuity remains separate. 102 unique order candidates, 24 causal damage relations (17 physical/7 special), 0 unconditional native-stat numerical reductions, 2 temporary Ditto stat snapshots.
- 1 current Life Orb exclusion under the user-specified display rule; 17 existing B22 frames reviewed. Magic Guard and applicable Sheer Force explicitly handled. 35 conditional original-item cross-member relations; 0 unconditional original-item exclusions.
- B20/B21 context final hashes differ from saved state; B21 additionally has 8 receipt-status differences. These are unresolved diagnostic limitations, not overwritten source acceptance. B22/B23 final hashes match.
- Focused regression suite: 579 passed, 3 deselected (command in main report). B20 identical trace invocation verified cache reuse.
- Resume only the required battle: `.venv/bin/python scripts/trace_hidden_constraints.py --battle 22 --stage trace --resume`. Completed contexts are reusable. Partial replay files must be preserved; there is no safe engine suffix-resume API.
- Numeric joint projection remains unsupported when ordering decision, stages/status/field, identities or defender stats are incomplete. No neutral filling, new Defense/HP solver, statistical prior, legal-universe claim from library absence, or accuracy percentage.
