"""Audited ordering scope, pinned independently of empirical metagame data."""
SOURCE_POLICY=dict(
    version='m341-ordering-audit-v1',
    independently_verified_champions_ordering=False,
    strict_profile='champions-evidence-only-v1',
    conditional_reference_profile='showdown-champions-reference-v1',
    pair_tie_probability=.5,
    tie_reference=dict(
        url='https://github.com/smogon/pokemon-showdown/blob/3a766f2cfb5e51c1e428cfe87d0dba91a8f01640/sim/battle.ts#L403-L435',
        revision='3a766f2cfb5e51c1e428cfe87d0dba91a8f01640',
        sha256='3eb941313832729ee043407c39ced894b4338301fed5d29a45ae8b36e49a09f2',
        retrieved_date='2026-10-20',license='MIT',
        interpretation='PRNG shuffle of equal comparison groups supports a conditional pairwise half probability; not independent in-game validation'),
    sampling_unit='At most one pair per individual per turn; no multiplication of correlated ranks from the same tie draw',
    limitations=['No independently certified Champions tie/randomization or mid-turn ordering model',
        'Closed M3.2 modifier/move subset only; unhandled positive-weight hypotheses exclude the whole observation',
        'Native ability/form catalog assertions are community reference evidence, not observed opponent configurations'])
