"""Small, GitHub-readable presentation generated from the completed offline run."""
from collections import Counter
import json
from pathlib import Path
import numpy as np
from metagame.common import atomic_json
from .frozen import file_hash
from .study import cluster_reference


def write_report(path,audit,frozen,evaluation,application,fingerprint,run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from speed_order.core import name
    path=Path(path);assets=path.parent/'assets/m353';assets.mkdir(parents=True,exist_ok=True)
    records=application['records'];pool=[r for r in records if r['primary_independent_pool']]
    refs=cluster_reference(frozen)
    methods=('prior','moves','moves_item');titles=('Occurrence prior','Moves only','Moves + item')
    fig,axes=plt.subplots(1,3,figsize=(11,3.6),layout='constrained')
    for ax,method,title in zip(axes,methods,titles):
        matrix=np.array(evaluation['pooled'][method]['confusion'])
        ax.imshow(matrix,cmap='Blues',vmin=0,vmax=max(1,matrix.max()))
        for i in range(3):
            for j in range(3):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>matrix.max()/2 else 'black')
        ax.set(title=title,xlabel='Predicted cluster',ylabel='Held-out nearest training medoid',xticks=range(3),yticks=range(3))
    fig.suptitle('Grouped internal evaluation: 3 seeds × 3 folds (591 predictions; 197 recurring occurrences)',fontsize=10)
    fig.savefig(assets/'internal-confusion.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    for key,label in [('moves_only','Moves only'),('moves_item','Moves + item')]:
        axes[0].hist([(r['prediction'][key] or r['prediction']['moves_only'])['margin'] for r in pool],bins=np.linspace(0,1,16),histtype='step',linewidth=2,label=label)
    axes[0].set(xlabel='Top minus runner-up weight',ylabel='No-SP occurrences',title=f'Primary pool: {len(pool)} observations');axes[0].legend()
    moves_top=Counter(r['prediction']['moves_only']['top'] for r in pool)
    item_top=Counter((r['prediction']['moves_item'] or r['prediction']['moves_only'])['top'] for r in pool)
    xx=np.arange(3);axes[1].bar(xx-.18,[moves_top[z] for z in range(3)],.36,label='Moves only');axes[1].bar(xx+.18,[item_top[z] for z in range(3)],.36,label='Moves + item')
    axes[1].set(xticks=xx,xlabel='Top-ranked frozen cluster',ylabel='No-SP occurrences',title='Predicted assignments, not true labels');axes[1].legend()
    fig.savefig(assets/'application-scores.png',dpi=160);plt.close(fig)
    known=[r for r in pool if r['prediction']['moves_item'] is not None]
    changed=sum(r['prediction']['moves_only']['top']!=r['prediction']['moves_item']['top'] for r in known)
    no_sp=Counter(r['sp_status'] for r in audit['records'])
    incomplete=[r for r in audit['records'] if not r['complete']]
    excluded_reasons=Counter(reason for r in incomplete for reason in r['reasons'])
    overlap_counts=Counter(key for r in records for key in r['source_overlap']['direct'])
    names=lambda values:' / '.join(name(v,'move') for v in values)
    cluster_rows=[]
    for c in refs:
        attack=c['quantiles']['attack'];speed=c['quantiles']['speed']
        cluster_rows.append(f"| {c['cluster']} · {c['name']} | {c['occurrences']} ({100*c['share']:.1f}%) | {attack['median']:g} [{attack['q1']:g}–{attack['q3']:g}] | {speed['median']:g} [{speed['q1']:g}–{speed['q3']:g}] | {c['bulk']['median']:g} |")
    metrics_rows=[]
    for method,label in [('majority','Hard majority'),('prior','Occurrence prior'),('moves','Moves only'),('moves_item','Moves + item')]:
        m=evaluation['pooled'][method]
        metrics_rows.append(f"| {label} | {m['accuracy']:.3f} | {' / '.join('—' if r is None else f'{r:.3f}' for r in m['recall'])} | {m['brier']:.3f} | {m['nll']:.3f} |")
    variation=[]
    for seed in evaluation['per_seed']:
        m=seed['metrics'];variation.append(f"| {seed['seed']} | {m['prior']['accuracy']:.3f} | {m['moves']['accuracy']:.3f} | {m['moves_item']['accuracy']:.3f} | {m['moves']['recall'][1]:.3f} | {m['moves_item']['recall'][1]:.3f} |")
    representatives=[]
    for z in range(3):
        candidates=sorted((r for r in pool if r['prediction']['moves_only']['top']==z),key=lambda r:(-r['prediction']['moves_only']['margin'],r['empirical_record_id']))
        if candidates:
            r=candidates[0];p=r['prediction'];representatives.append(dict(id=r['empirical_record_id'],source_url=r['source_url'],configuration=r['configuration'],prediction=p))
    summary=dict(model_fingerprint=fingerprint,source_audit=audit['summary'],incomplete_reason_counts=dict(excluded_reasons),
                 frozen_source_hashes=frozen['source_hashes'],frozen_config=frozen['config'],
                 clusters=[{k:c[k] for k in ('cluster','name','occurrences','share','quantiles','bulk','sp','item','nature','complete_movesets','allocation_proportion_mean')}|dict(medoid={k:c['medoid'][k] for k in ('empirical_record_id','source_url','configuration')}) for c in refs],
                 application=dict(total=len(records),independent=len(pool),overlap=len(records)-len(pool),direct_overlap_fields=dict(overlap_counts),moves_top=dict(moves_top),item_top=dict(item_top),item_changes_top=changed,
                    unseen_movesets=sum(r['prediction']['novelty']['unseen_complete_set'] for r in pool),ood=sum(r['prediction']['novelty']['out_of_distribution'] for r in pool),weak=sum(r['prediction']['weak_evidence'] for r in pool)),
                 evaluation=dict(pooled=evaluation['pooled'],per_seed=evaluation['per_seed'],fold_sizes=[dict(seed=f['seed'],fold=f['fold'],train=f['train_sizes'],test=f['test_sizes']) for f in evaluation['folds']]),
                 queue=application['queue'],representatives=representatives,human_review='pending')
    atomic_json(assets/'evidence-summary.json',summary)
    app=summary['application'];counts=audit['summary']['counts'];team_counts=audit['summary']['teams_by_sp_status']
    c1=evaluation['pooled']['moves']['recall'][1];ci1=evaluation['pooled']['moves_item']['recall'][1]
    medoid_lines='\n'.join(f"- Cluster {c['cluster']}: **{' / '.join(map(str,c['medoid']['configuration']['sp']['values']))}**, {c['medoid']['nature'].split(':')[-1]}, {name(c['medoid']['item'],'item')}; [original medoid source]({c['medoid']['source_url']})." for c in refs)
    example_lines='\n'.join(f"- [Published case]({r['source_url']}): {names(r['configuration']['moves'])}; {name(r['configuration']['item'],'item') if r['configuration']['item'] else 'item unknown'}. Moves-only weights **{' / '.join(f'{v:.3f}' for v in r['prediction']['moves_only']['weights'])}**; exact moveset support {r['prediction']['exact_support']}. Full occurrence ID is retained in the [evidence summary](assets/m353/evidence-summary.json)." for r in representatives)
    body=fr'''# M3.5.3 — Predicting build neighborhoods when SP is missing

*Pokémon Champions Assistant · 24 October 2026 · offline exploratory study*

This milestone asks whether published **moves and held items**, without training points, can identify neighborhoods of Incineroar builds. It freezes the [M3.5.1 SP-only K=3 partition](M3.5.1_Build_Clustering.md), evaluates a transparent count-based predictor, and applies it to real publications lacking SP. A local interface lets a human inspect those predictions alongside the original teammates.

**Human review is pending.** No application record has a verified SP label, and model weights are not calibrated opponent probabilities. Nothing is integrated into battle inference or replay.

## What the source audit actually found

The existing read-only VGC M-C Doubles scope contains **{audit['summary']['publications']:,} publications and {counts['member_records']:,} member occurrences**. The earlier complete-build adapter's count is reproduced: **{counts['complete_adapter']:,} complete and {counts['incomplete_adapter']:,} excluded**. Exclusion does not mean “missing SP” in every case.

| Direct SP audit, all species | Member occurrences |
|---|---:|
| Complete valid SP vectors | {no_sp['valid_sp']:,} |
| No SP supplied | {no_sp['missing_sp']:,} |
| Partial SP | {no_sp['partial_sp']} |
| Invalid or conflicting SP | {no_sp['invalid_sp']+no_sp['conflicting_sp']} |

At team level, {team_counts['all_six_valid_sp']} publications have valid SP for all six members, {team_counts['all_six_missing_sp']} lack SP for all six, and {team_counts['mixed_partial_or_invalid']} are mixed or partial. The recollection of roughly half with SP and half without was accurate for this source snapshot.

Within the 3,106 adapter exclusions, overlapping reasons are: {', '.join(f"**{k.replace('_',' ')}: {v}**" for k,v in sorted(excluded_reasons.items()))}. Reason counts overlap and must not be added. Separately, native-ability compatibility conflicts occur in {counts.get('reason:form_ability_incompatibility',0)} all-species records, including records considered complete by the earlier adapter. Completeness and compatibility are separate tests. No exclusions in this snapshot have missing/conflicting moves, missing/conflicting ability, invalid SP, form/item incompatibility, or other adapter-conflict reasons.

Incineroar has **197 complete-SP** occurrences and **202 with SP missing**; all 202 have a canonical identity, four uncontested moves and no known non-SP compatibility conflict. Two application records lack nature; they remain eligible because nature is not a predictor. All observed items, abilities, natures, teammate details, and original IDs are retained. Missing SP stays null—never zero-filled.

### Separating training and application sources

Groups connect publication IDs, URLs, source keys, identical raw-record hashes, exact complete teams, and exact six-member **observable teams with SP omitted**. The last check detects republished teams with the same species, moves, items, abilities and natures despite SP missing in one export. Grouping runs across all selected publications, so indirect overlaps can also be flagged. Equal individual builds alone do not connect sources.

**{len(records)-len(pool)} application records overlap training sources and are excluded from the primary pool; {len(pool)} remain.** Direct overlap fields: {dict(overlap_counts)}. All 202 records and their flags remain available in the interface and complete local output. No detected overlap is weaker than proof of independence; related sources can still evade these checks. These remain out-of-sample records for application, without an external labeled test set.

## The frozen neighborhoods

The saved SP-only model has **31 / 24 / 142** occurrences. This is not the learned combined-distance diagnostic partition of 34 / 7 / 156. Input hashes, occurrence order, all 197 configurations, unchanged SP parameters, saved pairwise distances, assignment counts and medoid identities are checked before use. Application records never alter these labels or medoids.

| Frozen cluster | Occurrences / share | Attack median [Q1–Q3] | Speed median [Q1–Q3] | Bulk median |
|---|---:|---|---|---:|
{chr(10).join(cluster_rows)}

Bulk means HP + Defense + Special Defense SP. Medoid SP order below is HP / Attack / Defense / Special Attack / Special Defense / Speed:

{medoid_lines}

![Frozen Incineroar SP-only allocations, selected K=3](M3.5.2_Midterm_Research_Report/figures/incineroar-sp-only-boxplots.png)

The 24-member group is higher-Attack: its Attack values span 15–32, with median 28 and IQR 10.75. Ten observations have Attack 32; the rest are distributed over 15, 16, 18, 19, 22, 23, 25 and 31. Speed is variable: 11 have zero, while three have 32. This is broader than the seven-member complete-moveset package highlighted by the combined model. Descriptive names are provisional, not true tactical roles.

The interface exposes every SP coordinate's median and quartiles, full Attack/Speed frequency tables, bulk and defensive allocation patterns, common moves, complete sets, item/nature counts, medoids and representative source builds.

## A predictor whose evidence can be inspected

The model uses the occurrence-weighted prior $P(Z=z)=n_z/197$. Repeated publications retain their votes. It uses only the complete four-move set and optional original item; nature, ability, teammates and SP are excluded from prediction features.

For a query moveset, take all subsets of size 1, 2, 3 and 4. For each subset $S$, count training occurrences containing it, both overall ($n_S$) and in cluster $z$ ($n_{{z,S}}$). Shrink toward the species prior $p_z$:

$$
q_z(S)=\frac{{n_{{z,S}}+5p_z}}{{n_S+5}}.
$$

Average within each subset size, then mix sizes with fixed weights 0.1 / 0.2 / 0.3 / 0.4. This is a coherent mixture of normalized categorical conditional estimates: equivalently, a latent projection chooses a subset size and then a uniformly selected query subset. **Overlapping subset likelihoods are never multiplied or summed as independent evidence.** The mixture is a modeling choice, not an estimated generative likelihood for complete movesets.

With known item $I$, an item-only cluster distribution is first shrunk toward $p_z$. Each joint subset/item distribution is then shrunk toward that item distribution:

$$
q_z(I)=\frac{{n_{{z,I}}+5p_z}}{{n_I+5}},\qquad
q_z(S,I)=\frac{{n_{{z,S,I}}+5q_z(I)}}{{n_{{S,I}}+5}}.
$$

The same fixed mixture combines these joint estimates. This avoids a conditional-independence claim about moves and items. Missing or entirely unseen items add no evidence and preserve moves-only scores. Fully unseen moves return prior-like moves-only weights. Raw subset and joint counts are shown, along with novelty indicators. Positive smoothing keeps every cluster weight nonnegative and normalized, without making the estimates calibrated.

## Internal evaluation before unlabeled application

Three deterministic seeds each define three source-grouped folds. Every fold refits K=3 PAM using only training SP and the frozen SP settings, then trains the predictor on those fold labels. True held-out SP assigns evaluation labels by nearest **training** medoid; the predictor receives only moves and optional item.

Fold medoids are matched to the frozen reference medoids by a minimum-distance permutation solely to keep column names consistent. The full-data medoids are not predictor inputs or held-out labeling centers. Consequently, evaluation labels can differ from the original frozen assignments; the pooled held-out label counts are {[sum(evaluation['pooled']['prior']['confusion'][z]) for z in range(3)]}. Renaming columns cannot change accuracy, Brier score or log loss. Full train/test IDs, groups, scales, medoids, permutations and predictions are saved for inspection.

| Method | Top-1 accuracy | Recall C0 / C1 / C2 | Multiclass Brier | Negative log-likelihood |
|---|---:|---|---:|---:|
{chr(10).join(metrics_rows)}

Brier is the mean sum of three squared probability errors; lower is better. Log loss also favors lower values. Hard-majority log loss uses a $10^{{-15}}$ numerical floor for zero weights; the smoothed occurrence prior is the useful probabilistic baseline. These pooled summaries contain **591 predictions of 197 recurring observations**, not 591 independent examples.

| Split seed | Prior accuracy | Moves accuracy | Moves + item accuracy | Moves C1 recall | Moves + item C1 recall |
|---|---:|---:|---:|---:|---:|
{chr(10).join(variation)}

![Three grouped-evaluation confusion matrices](assets/m353/internal-confusion.png)

Rows are held-out nearest-medoid labels; columns are predictions. The larger defensive group makes majority accuracy easy to achieve, so minority recall and proper scores matter. Moves-only C1 recall is **{c1:.3f}**, versus **0** for the majority baseline; item-conditioned recall is **{ci1:.3f}**. Minority recovery remains poor: almost all held-out higher-Attack cases are missed, and no higher-Speed cases are recovered. The improvement over majority accuracy is only about half a percentage point; moves-only proper scores improve modestly, while item conditioning does not improve them further. These results assess recovery of model-defined neighborhoods, not tactical ground truth. Small folds and changing fold partitions limit precision; the three seeds are variation checks, not independent replications or hyperparameter optimization.

## Applying the model where true SP is unavailable

The primary pool contains {len(pool)} records. Moves-only top-cluster counts are **{[moves_top[z] for z in range(3)]}**; item-conditioned counts are **{[item_top[z] for z in range(3)]}**. Item evidence changes the top cluster in **{changed}** cases. There are **{app['unseen_movesets']} unseen complete sets**, **{app['ood']} records with unseen moves**, and **{app['weak']} weak/prior-like moves-only predictions** under the documented support/shift heuristic. These are model diagnostics, not observed classification errors.

![Prediction margins and assignments in the independent no-SP pool](assets/m353/application-scores.png)

A larger top-versus-runner-up margin means this model prefers one neighborhood more strongly. It does not measure calibration or establish actual SP. The assignment bars show what the model outputs, not the population's true archetype frequencies.

Representative highest-margin moves-only cases for each predicted cluster that actually occurs:

{example_lines}

Every eligible record is retained, including low-margin predictions and overlap cases. Failure modes include common movesets that mostly reproduce the majority prior, item correlations with selectively published builds, and unusual combinations with little direct support. Team context may challenge a prediction, but is not yet modeled. No medoid is substituted for an opponent's missing SP.

## Review 10–20 cases locally

From the repository root, using the existing environment and completed caches:

```sh
.venv/bin/python -m experiments.no_sp_archetypes.review
```

Open **http://127.0.0.1:8353**. The standalone page contains the cluster reference, one target, all five original teammates with available moves/items/ability/nature and source links, both prediction variants, all cluster weights, margins, supporting counts, novelty and overlap flags. It is separate from replay.

The curated initial queue contains **{len(application['queue']['ids'])} cases**, selected only from the primary pool with distinct moveset/item patterns. Its fixed category order offers up to three high-margin predictions per cluster, ambiguous boundaries, rare/unseen sets, and substantial item changes, then fills from distinct ambiguity-ordered cases. Actual available category counts are retained rather than forced: **{application['queue']['availability']}**. Queue predicted-cluster counts are **{application['queue']['selected_by_cluster']}**. Category labels can overlap; this is a contrast-seeking review sample, not a representative accuracy sample. All eligible records remain accessible through the population selector.

Choose reasonable / another cluster / ambiguous / insufficient information / source issue, optionally select a preferred cluster and write notes. **Save review** appends a durable revision; **Save & next** advances. Navigation supports previous/next, review-status and predicted-cluster filters, margin/uncertainty/item-change sorting, direct index/ID jump, progress, and resume after reopening.

Annotations and queue state are stored in **`.cache/research/m353/reviews.sqlite3`**, keyed by model fingerprint. They remain separate from immutable predictions and source records. Saves preserve the original observation ID, suggested weights, assessment, preferred cluster, notes and server timestamp. The API exports latest reviews via **`/api/export.json`** and **`/api/export.csv`**; the page provides download links. Old revisions remain in SQLite. A new model fingerprint starts its own review/session view rather than relabeling old reviews. No human assessments have been supplied by this experiment.

## Reproduction, limits and stopping point

Model fingerprint: **`{fingerprint}`**. The run directory is `.cache/research/m353/{fingerprint}/`; its manifest records input/implementation identities, hashes, stage status and exact resume command. Audit, frozen reference, evaluation, application and review payloads are separate atomic stages. Reuse compatible stages; no source scraping, external retrieval, OCR or video processing is involved.

```sh
.venv/bin/python -m experiments.no_sp_archetypes.study
.venv/bin/python -m pytest -q tests/test_no_sp_archetypes.py tests/test_git_artifact_policy.py
```

Numerical reproduction requires the existing published-team database and preserved M3.5.1 run; neither is bundled as a large Git artifact. [Code and dependency notes](../experiments/no_sp_archetypes/README.md) describe paths and launch options. The tracked [compact evidence summary](assets/m353/evidence-summary.json) records audit totals, cluster distributions, source hashes, configuration, evaluation results, queue IDs and representative cases. Full source joins, per-fold predictions and every application record stay local.

Verification completed: **31 portable M3.5.3 tests and 2 artifact-policy tests passed**. The 31 tests also passed from an isolated copy of the staged files, without unrelated working-tree changes. A local Chrome check exercised five-teammate rendering, both weight displays, durable save, export, filters, navigation and resume using a separate test annotation database. GitHub's renderer recognized both display equations, three figures and four tables. A second study run reused all six completed stages without new fitting. These engineering checks do not constitute human review or scientific acceptance.

This milestone validates source selection, reproducible scoring, internal grouped evaluation and the review workflow. It does not establish unknown true SP, independent source identity, calibration, strategy quality, Champions move legality, or human acceptance. The data are selectively published, occurrence-correlated, and small for the minority neighborhood. Future team-conditioned models and live integration are outside scope. **Stop here for human interpretation; review conclusions remain pending.**
'''
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
    files=[path,assets/'evidence-summary.json',assets/'internal-confusion.png',assets/'application-scores.png']
    return dict(files={str(p):file_hash(p) for p in files},human_review='pending')
