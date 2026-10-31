"""Static scientific figures and self-contained factual research summary."""
from collections import Counter
from pathlib import Path
import hashlib
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .core import STATS, sp_array, moves, SPConfig, sp_distances, adjusted_rand
from .study import slug
from speed_order.core import name, knowledge


def label(value):
    if value.startswith('nature:'):
        return value.split(':')[-1]
    entity=knowledge().entities.get(value)
    return entity.names.get('en',value) if entity else value


def build(row):
    p=row['training_points']
    return ('SP '+ '/'.join(str(p[s]) for s in STATS)+'; '+label(row['nature'])+'; '+label(row['ability'])+'; '+
            label(row['item'])+'; '+', '.join(label(m) for m in moves(row)))


def table_freq(freq, limit=6):
    return ', '.join(f'{label(k)} {v}' for k,v in sorted(freq.items(),key=lambda kv:(-kv[1],str(kv[0])))[:limit])


def figure(path):
    plt.tight_layout(); plt.savefig(path,dpi=150,bbox_inches='tight'); plt.close()


def plots(out, data, results, selected, model):
    folder=out/'figures'; folder.mkdir(exist_ok=True)
    t=np.linspace(0,1,201)
    plt.figure(figsize=(7,4))
    for gamma in (1,2,3):
        plt.plot(t,np.expm1(gamma*t),label=f'gamma={gamma}')
    plt.xlabel('Normalized absolute SP difference'); plt.ylabel('exp(gamma t) - 1')
    plt.legend(); plt.title('Exploratory nonlinear SP response'); figure(folder/'sp-response.png')
    for species,rows in data['targets'].items():
        result=results[species]['learned']; display_k=selected[species]['learned']
        k=display_k if display_k>1 else min(3,len(result['kmedoids']))
        candidate=result['kmedoids'][k-1]; labels=np.array(candidate['labels'])
        d=np.array(result['distance_matrix']); order=np.argsort(labels,kind='stable')
        plt.figure(figsize=(6,5)); plt.imshow(d[np.ix_(order,order)],cmap='viridis'); plt.colorbar(label='Combined dissimilarity')
        plt.xlabel('Occurrences ordered by cluster'); plt.ylabel('Occurrences ordered by cluster')
        plt.title(f'{species}: diagnostic K={k}; screen K={display_k}'); figure(folder/(slug(species)+'-heatmap.png'))
        # Classical MDS is a projection of dissimilarities; retain positive axes.
        n=len(d); centering=np.eye(n)-np.ones((n,n))/n
        gram=-.5*centering@(d*d)@centering
        eig,u=np.linalg.eigh(gram); order_e=np.argsort(eig)[::-1]
        positive=np.maximum(eig[order_e[:2]],0)
        xy=u[:,order_e[:2]]*np.sqrt(positive)
        plt.figure(figsize=(6,4.5)); plt.scatter(xy[:,0],xy[:,1],c=labels,cmap='tab10',alpha=.65,s=30)
        for m in candidate['medoids']:
            plt.scatter(*xy[m],marker='X',c='black',s=100)
        fraction=positive.sum()/np.maximum(eig,0).sum() if np.maximum(eig,0).sum() else 0
        plt.xlabel('Positive projection axis 1'); plt.ylabel('Positive projection axis 2')
        plt.title(f'{species}: 2D projection, diagnostic K={k}\npositive eigenmass {fraction:.1%}; negative eigenvalues {sum(eig < -1e-9)}')
        figure(folder/(slug(species)+'-projection.png'))
        x=sp_array(rows)
        fig,axes=plt.subplots(2,3,figsize=(10,6))
        for j,ax in enumerate(axes.flat):
            ax.boxplot([x[labels==z,j] for z in range(k)],tick_labels=[str(z) for z in range(k)],showmeans=True)
            ax.set_title(STATS[j]); ax.set_ylim(-1,33); ax.set_xlabel('Cluster index')
        fig.suptitle(f'{species}: diagnostic K={k}; screen K={display_k}'); figure(folder/(slug(species)+'-sp.png'))
    pairs=model.diagnostics()['pair_counts_and_associations']
    top=sorted((p for p in pairs if p['count']>=5),key=lambda p:(-p['association'],p['moves']))[:16]
    plt.figure(figsize=(9,7))
    labels=[' + '.join(label(m) for m in p['moves'])+f" (n={p['count']})" for p in top]
    plt.barh(range(len(top)),[p['association'] for p in top]); plt.yticks(range(len(top)),labels,fontsize=8)
    plt.gca().invert_yaxis(); plt.xlabel('Shrunk, capped positive association'); plt.title('Observed move-pair association; complementarity is not role equality')
    figure(folder/'move-associations.png')
    return sorted(folder.glob('*.png'))


def render(out, report, data, results, stabilities, evaluation, selected, model):
    files=plots(out,data,results,selected,model)
    report=Path(report); report.parent.mkdir(parents=True,exist_ok=True)
    relative=lambda p:os.path.relpath(p,report.parent)
    lines=[]
    def add(s=''): lines.append(s)
    def heading(s): add();add('## '+s);add()
    def image(p): add(f'![{p.stem}]({relative(p)})');add()
    add('# M3.5.1 — Offline build similarity and archetype discovery')
    add()
    add('Local cached VGC study. No battle inference, empirical ranking, solver, replay, team constraints or alpha was changed. Cluster indices below have no tactical labels. This experiment creates no synthetic builds and assigns no probability to unobserved builds.')
    add()
    add(f"Reproduce/resume: `.venv/bin/python -m experiments.build_similarity.study`. Run fingerprint: `{out.name}`. Full original builds, occurrence/source IDs, pair statistics, all assignments, medoid alternatives, component contributions, grouped folds and predictions are preserved in [{out.name}]({relative(out)}) and its [manifest]({relative(out/'manifest.json')}). Commands and exact dependency identities are in the manifest. Identical configurations retain separate observations in every fit.")
    heading('Data selection and provenance')
    scope=data['audit']['source_scope']
    add('Read existing vgcmulticalc exports through `load_vgc` and the established `catalog` compatibility adapter: tournament_published, M-C, Doubles, pinned canonical version `'+scope['canonical_version']+'`. No collection, import, database write, network knowledge refresh, OCR or decoding. Each input is an observed complete configuration; original form, ability, SP, nature, item, moves, team and publication identities remain unchanged. Context form is stored separately in the target audit.')
    add()
    add(f"Source scope: {scope['raw_publications']} publications; {scope['raw_member_records']} member records; {scope['selected_complete_raw_records']} complete records; {scope['incomplete_records_excluded']} incomplete records excluded by the existing adapter. After compatible complete-core/four-move filtering, association training uses {len(data['training'])} occurrences from {data['audit']['evaluation_groups']} connected source/team groups. Zero observations are removed for build equality. ESS with equal occurrence weights equals N; independent effective sample size is unknown because publications and teams are related.")
    add()
    add('| Context | Occurrences | Distinct full builds | Distinct training cores | Source groups | Core exclusions |')
    add('|---|---:|---:|---:|---:|---:|')
    from .data import core_signature
    from battle_evidence.empirical_measure import full_record_signature
    for species,rows in data['targets'].items():
        audit=data['audit']['targets'][species]
        add(f"| {species} | {len(rows)} | {len({full_record_signature(r) for r in rows})} | {len({core_signature(r) for r in rows})} | {len({r['evaluation_group'] for r in rows})} | {len(audit['excluded_cores'])} |")
    add()
    add('Base/Mega contexts use the existing required-stone and active-ability compatibility checks; no other species are pooled for clustering. Global move association learning uses all eligible species, with each immutable occurrence ID entering once. Evaluation groups connect publication IDs, source keys, URLs and exact team signatures. Incomplete team signatures can conservatively overgroup records; unknown related sources may still remain. Grouping never changes empirical counts. Full exclusion audit: [population.json]('+relative(out/'population.json')+').')
    for species,audit in data['audit']['targets'].items():
        if audit['excluded_cores']:
            add();add(species+' excluded cores: '+table_freq(dict(Counter(e['reason'] for e in audit['excluded_cores'])))+'.')
    heading('Dissimilarities and mathematical properties')
    add('Let B=H+D+R and φγ(t)=exp(γt)−1. Baseline:')
    add()
    add('`d_SP = λB φγ(|Bx−By|/66) + λD Σ[j∈{H,D,R}] φγ(|xj−yj|/48) + λA φγ(|Ax−Ay|/32) + λC φγ(|Cx−Cy|/32) + λV φγ(|Vx−Vy|/32)`.')
    add()
    add('Defaults: γ=2, λB=1, λD=.3, λA=1, λC=1, λV=1.2. Scales 66/48/32 are experimental sensitivity choices; 48 is not a legal stat cap. Existing Champions validation requires integer SP in [0,32], six explicitly supplied values and total ≤66; unspent points remain legal.')
    add()
    add('Alternative: replace the defensive terms with `λB φγ(|Bx−By|/66) + λQ min(Bx,By)/66 ||qx−qy||₁`, q=(H,D,R)/B and λQ=.3. At zero bulk, q is represented as zero and the allocation term is exactly zero whenever either bulk is zero. Offensive terms are identical. We compare both formulations rather than treating either as verified optimal.')
    add()
    add('All configurations are symmetric, nonnegative and zero on identical builds. These are dissimilarities, not mathematical metrics. With legal Attack values 0,16,32 and all other SP zero: d(0,32)=exp(2)−1≈6.389 > 2(exp(1)−1)≈3.437, violating the triangle inequality under both SP formulations. The min-bulk allocation term alone also fails: (16,0,0) and (0,16,0) have positive allocation distance but both have zero allocation distance through zero bulk. Cosine distance can fail triangle inequalities. Jaccard is a metric on move sets and identity mismatch is a categorical metric; the combined build dissimilarity need not be a metric and can be zero for distinct builds because ability is retained for diagnostics but is not a distance term. No metric pruning or Euclidean clustering is used.')
    image(out/'figures/sp-response.png')
    heading('Learned complete-moveset association')
    diag=model.diagnostics()
    add(f"Binary build-by-move incidence preserves all occurrences: N={model.n}, vocabulary={len(model.vocabulary)} moves. For each move i, fᵢ is its observation count; cᵢⱼ counts builds containing both. Smooth all four cells of each pair’s Bernoulli table with a=.5: pᵢ=(fᵢ+2a)/(N+4a), pᵢⱼ=(cᵢⱼ+a)/(N+4a). Association `min(3,max(0,log(pᵢⱼ/(pᵢpⱼ)))) × cᵢⱼ/(cᵢⱼ+5)`; diagonal is zero. Positive clipping, cap 3 and support shrinkage 5 are explicit regularizers. A zero-support pair receives zero association. {diag['rare_pairs_at_most_two']} observed pairs have at most two occurrences, out of {len(diag['pair_counts_and_associations'])} observed pairs.")
    add()
    add('SVD of the symmetric association matrix supplies move embeddings `U[:, :d] sqrt(S[:d])`, default d=16, compared with d=8 and 32. Complete four-move embeddings use mean pooling with a fixed denominator four; the API also supports unit-normalizing each move vector before pooling, but this alternative is not evaluated here. Learned moveset dissimilarity is 1−cosine. Unknown moves contribute zero; a zero-norm comparison has distance one except identical exact move sets have distance zero. Pooling loses interactions: distinct combinations can share an average. Vocabulary, counts, association, SVD and species-specific scales are fitted inside training folds for evaluation. Descriptive full-population fits are reported separately. No language embeddings or manual tactical labels enter training.')
    add()
    add('Co-occurrence captures empirical association and complementarity, not equivalent function. Common moves can add little discrimination, rare pairs remain uncertain, and equal-weight ESS is not independent evidence. Full frequencies, observed-pair support, shrink factors, singular values and embeddings: [moves.json]('+relative(out/'moves.json')+'). Non-observed pairs have c=0 and association=0.')
    add()
    for move in sorted(range(len(model.vocabulary)),key=lambda i:-model.frequency[i])[:8]:
        add(f"- {label(model.vocabulary[move])}: {int(model.frequency[move])}/{model.n} occurrences ({model.frequency[move]/model.n:.1%}).")
    add();image(out/'figures/move-associations.png')
    heading('Combination, normalization and experimental grid')
    add('`d_build = βSP dSP/sSP + βmove dmove/sMove + βitem 1[item differs]/sItem + βnature 1[nature differs]/sNature`. Each s is the median strictly positive off-diagonal distance in the training species context; constant components use scale one and contribute zero. Repeated observations influence the pair distribution. Default β=(1,1,0,0); categorical item/nature ablation β=(1,1,.5,.5). Ability is preserved and summarized but is not an extra distance component. Nature is categorical; actual calculated stats are not included.')
    add()
    add('Thirteen predefined configurations: SP only; SP+Jaccard; SP+learned; learned+item/nature; proportional defensive allocation; γ=1 or 3; defensive suballocation weight .1 or .6; move weight .5 or 2; embedding dimension 8 or 32. All other settings retain defaults. This is a one-factor sensitivity study, not an optimized hyperparameter search.')
    add()
    add('| Species | Component (learned default) | Raw median | IQR | p90 | p95 | Positive-median scale | Weighted median | Weighted p95 |')
    add('|---|---|---:|---:|---:|---:|---:|---:|---:|')
    for species,methods in results.items():
        for key,c in zip(('SP','moves','item','nature'),methods['learned']['normalization']):
            r=c['raw']; w=c['weighted_contribution']
            add(f"| {species} | {key} | {r['median']:.3f} | {r['iqr']:.3f} | {r['p90']:.3f} | {r['p95']:.3f} | {c['scale']:.3f} | {w['median']:.3f} | {w['p95']:.3f} |")
    add();add('Full contribution distributions for every ablation are in its JSON. Constants never cause division by zero. No target held-out pair is used to fit scales. Positive-median scaling does not equalize tails: a small median positive moveset distance can magnify rare combinations. The upper weighted quantiles expose this effect rather than treating equal nominal weights as equal influence.')
    heading('Clustering, stability and cluster-count screen')
    add('Deterministic PAM BUILD+best SWAP accepts the full precomputed matrix with one unit of mass per occurrence; every medoid is an observed legal build. Average-linkage hierarchy uses occurrence-weighted intercluster means and no Euclidean assumptions. Explore K=1–3 for Hatterene and K=1–4 for the larger contexts; also inspect hierarchy cuts at merge-height quartiles .25/.5/.75. Exact-distance ties use source-order determinism; forced ownership of duplicate medoids only keeps candidate K clusters nonempty.')
    add()
    add('Three deterministic 80% source-group subsamples refit the global move representation, species scales and clustering. Adjusted Rand indices compare only retained occurrence anchors, not unmatched bootstrap rows. This is limited descriptive stability, not a confidence interval. A conservative display screen keeps K=1 unless a candidate has silhouette≥.25, every cluster at least max(3,ceil(.1N)), and mean ARI≥.65 across all three resamples; take the smallest qualifying K. Thresholds are exploratory assumptions, not validated archetype criteria, and held-out prediction does not tune this screen. All candidates remain inspectable. For informative plots when the screen retains K=1, diagnostic figures show candidate K=3 with the screen result explicitly stated; this is not acceptance of a three-cluster partition.')
    add()
    add('| Species | Configuration | Display K | Sizes | Silhouette | Mean resample ARI | ARI vs learned at same K |')
    add('|---|---|---:|---|---:|---:|---:|')
    for species,methods in results.items():
        for key,result in methods.items():
            k=selected[species][key]; c=result['kmedoids'][k-1]
            aris=[r['ari'] for r in stabilities[species][key][str(k)] if r['ari'] is not None]
            ari=adjusted_rand(c['labels'],methods['learned']['kmedoids'][k-1]['labels'])
            sil='undefined (K=1)' if c['silhouette'] is None else f"{c['silhouette']:.3f}"
            add(f"| {species} | {key} | {k} | {c['sizes']} | {sil} | {np.mean(aris):.3f} | {ari:.3f} |")
    add()
    add('K=1 always has ARI=1 and is not evidence of learned stability. To expose parameter changes even when the conservative display stays at K=1, compare all configurations at the fixed diagnostic K=2:')
    add()
    add('| Species | Configuration | K=2 sizes | Silhouette | Mean resample ARI | ARI vs learned K=2 |')
    add('|---|---|---|---:|---:|---:|')
    for species,methods in results.items():
        for key,result in methods.items():
            c=result['kmedoids'][1]
            aris=[r['ari'] for r in stabilities[species][key]['2'] if r['ari'] is not None]
            ari=adjusted_rand(c['labels'],methods['learned']['kmedoids'][1]['labels'])
            add(f"| {species} | {key} | {c['sizes']} | {c['silhouette']:.3f} | {np.mean(aris):.3f} | {ari:.3f} |")
    add()
    add('Neighborhood change across the four main ablations (all-source descriptive top-three occurrence neighbors; duplicate builds remain):')
    add()
    add('| Species | Configuration | Mean top-3 overlap with SP-only |')
    add('|---|---|---:|')
    for species,methods in results.items():
        for key in ('sp','jaccard','learned','item-nature'):
            overlaps=[]
            for base,current in zip(methods['sp']['nearest_neighbors'],methods[key]['nearest_neighbors']):
                a={v['id'] for v in base['nearest']}; b={v['id'] for v in current['nearest']}
                overlaps.append(len(a&b)/len(a))
            add(f"| {species} | {key} | {np.mean(overlaps):.3f} |")
    heading('Species-specific factual cluster inspection')
    for species,rows in data['targets'].items():
        result=results[species]['learned']; lookup={r['empirical_record_id']:r for r in rows}
        add('### '+species);add()
        add(f"Default learned display K={selected[species]['learned']}. Candidate partitions below retain every occurrence; distinct-core counts are diagnostics only. Complete source-preserving drill-down: [{slug(species)}-learned.json]({relative(out/(slug(species)+'-learned.json'))}), with [original records]({relative(out/'population.json')}).")
        add()
        add('| Algorithm | K/cut | Occurrence sizes | Silhouette | Resample ARIs (PAM) |')
        add('|---|---|---|---|---|')
        for c in result['kmedoids']:
            add(f"| PAM | {c['k']} | {c['sizes']} | {c['silhouette']} | {[round(x['ari'],3) if x['ari'] is not None else None for x in stabilities[species]['learned'][str(c['k'])]]} |")
        for c in result['hierarchical']['k_cuts']:
            add(f"| Average linkage | {c['k']} | {c['sizes']} | {c['silhouette']} | — |")
        for c in result['hierarchical']['threshold_cuts']:
            add(f"| Average linkage threshold | {c['threshold']:.3f} (height q={c['height_quantile']}) | {c['sizes']} | {c['silhouette']} | — |")
        add()
        # Every learned candidate cluster, not just the displayed partition.
        for candidate in result['kmedoids']:
            for c in candidate['summaries']:
                add(f"**K={candidate['k']}, cluster {c['cluster']}**: {c['occurrences']} occurrences, {c['distinct_training_cores']} distinct training cores, {c['distinct_full_builds']} distinct full builds. Medoid `{c['medoid']}`: {build(lookup[c['medoid']])}.")
                add()
                add('SP median [range max] in H/A/D/C/R/V order: '+', '.join(f"{c['sp'][s]['summary']['median']:g} [{min(map(int,c['sp'][s]['frequencies']))}–{c['sp'][s]['summary']['max']:g}]" for s in STATS)+f". Bulk median={c['bulk']['median']:g}, IQR={c['bulk']['iqr']:g}; mean H/D/R bulk proportions="+'/'.join(f'{q:.2f}' for q in c['allocation_proportion_mean'])+'.')
                add()
                add('Nature: '+table_freq(c['nature'])+'. Items: '+table_freq(c['item'])+'. Moves: '+table_freq(c['move_frequencies'])+'.')
                add()
                add('Common complete sets: '+'; '.join(', '.join(label(m) for m in ms['moves'])+f" ×{ms['occurrences']}" for ms in c['complete_movesets'][:3])+'.')
                add()
        add('**Observed neighborhoods (no assigned roles).** All nearest neighbors are exported; examples below require a different connected source/team group. Each ID resolves to the full original build and source URL in population.json. Fields are H/A/D/C/R/V SP, nature, ability, item and four moves.')
        add()
        # Inspect extremes plus medoid and an actual mixed Incineroar moveset.
        candidates=[int(np.argmax(sp_array(rows)[:,1])),int(np.argmin(sp_array(rows)[:,1])),int(np.argmax(sp_array(rows)[:,5])),result['kmedoids'][selected[species]['learned']-1]['medoids'][0]]
        if species=='Incineroar':
            for i,r in enumerate(rows):
                names={label(m) for m in moves(r)}
                if 'Fake Out' in names and ('U-turn' in names or 'Parting Shot' in names) and 'Flare Blitz' in names:
                    candidates.append(i); break
        for i in dict.fromkeys(candidates):
            row=rows[i]; near=result['nearest_neighbors'][i]['nearest_other_source_group']
            add(f"- Query `{row['empirical_record_id']}`: {build(row)}.")
            for n in near[:1]:
                other=lookup[n['id']]
                add(f"  Nearest other-group observation `{n['id']}`, d={n['distance']:.3f}: {build(other)}. [Source]({other['publications'][0]['url']}).")
        add()
        x=sp_array(rows)
        add('Targeted observations: Attack SP frequencies '+str(dict(sorted(Counter(map(int,x[:,1])).items())))+'; Special Attack SP frequencies '+str(dict(sorted(Counter(map(int,x[:,3])).items())))+'; Speed SP frequencies '+str(dict(sorted(Counter(map(int,x[:,5])).items())))+'.')
        if species=='Hatterene':
            close=[(i,j) for i in range(len(rows)) for j in range(i) if x[i,5]==x[j,5] and x[i,3]==x[j,3] and not np.array_equal(x[i,[0,2,4]],x[j,[0,2,4]])]
            ds=np.array(result['distance_matrix']); spd=np.array(results[species]['sp']['distance_matrix'])
            add(f"There are {len(close)} pairs with equal Speed and Special Attack SP but different defensive allocations; "+(f"median normalized SP-only dissimilarity {np.median([spd[i,j] for i,j in close]):.3f}, learned-combined {np.median([ds[i,j] for i,j in close]):.3f}." if close else 'no qualifying comparison.'))
            add('Every observed Hatterene has zero Attack and Speed SP. The K=2 singleton has Special Attack 24, whereas the other twelve have 32; a high silhouette does not justify accepting that singleton as a recurring archetype. The defensive variation among the remaining builds is visible without forcing multiple groups.')
        elif species=='Incineroar':
            add('At K=2, the seven-occurrence small cluster has Attack SP 31–32 and the same complete set: Fake Out, Close Combat, Flare Blitz and Darkest Lariat. The other 190 occurrences include both low-Attack builds and several high-Attack builds, so the learned partition is not an attack/support binary. K=3 additionally separates a 34-occurrence group with Speed SP 11–32, but retains the seven-occurrence group. The conservative size screen rejects these as the final display partition even though the rare attacking neighborhood is factually distinguishable. Hybrid Fake Out/Flare Blitz/Parting Shot examples remain actual complete observed configurations and are inspected through neighbors, not assigned an exclusive tactical role.')
        else:
            add('Every compatible Raichu Y observation has zero Attack SP, so this dataset cannot test Attack-investment discrimination. The K=2 groups have Speed ranges 9–28 and 28–32; their representative complete sets also differ. K=3 isolates a single Special Attack 32 configuration. Stable K=2 under the default is descriptive evidence of neighborhood structure, but its sensitivity to weights and the lack of held-out numeric gain prevent treating it as a validated archetype partition. Displayed ability is the original published assertion; the existing adapter separately checks its compatibility with the target Mega context.')
        add('No tactical name follows from a cluster index. Small residual clusters and unstable partitions are diagnostic evidence rather than accepted archetypes. Similarity-derived soft scores use observed cluster frequencies and τ=1; all medoid distances, alternatives and scores are exported, and these scores are not calibrated posterior probabilities.')
        add()
        for suffix in ('heatmap','projection','sp'):
            image(out/'figures'/(slug(species)+'-'+suffix+'.png'))
    heading('Held-out target-masked prediction')
    add('Three deterministic hash folds at the connected source/team level. Fit vocabulary, frequencies, shrinkage association/SVD, species normalization and medoids on training only. Use five nearest training occurrences and median numeric target or majority item identity; compare with the species-specific training median/mode. Numeric targets mask the relevant SP term; bulk masks all HP/Defense/Special Defense terms. Item prediction removes item mismatch. No target final stat is present. Item/nature and the other observed SP fields can remain predictors. This tests conditional reconstruction, not battle prediction. Fold training IDs, groups, target-specific normalization, medoids, neighbors and every prediction are exported in [heldout.json]('+relative(out/'heldout.json')+').')
    add()
    add('| Species | Configuration | Target | N / groups | MAE SP or item error rate | Training median/mode baseline |')
    add('|---|---|---|---|---:|---:|')
    for species,methods in evaluation['summaries'].items():
        for key,ts in methods.items():
            for target,summary in ts.items():
                fmt=lambda v:'not evaluated' if v is None else f'{v:.3f}'
                add(f"| {species} | {key} | {target} | {summary['n']} / {summary['groups']} | {fmt(summary['loss'])} | {fmt(summary['baseline_loss'])} |")
    add()
    add('OOV move tokens by held-out fold: '+str(evaluation['oov'])+'. All observations retain unit weight; repeated builds across unrelated groups can legitimately remain, while exact full teams stay together. Results are small-sample, correlated exploratory comparisons. Hatterene has especially weak support; a zero-error constant feature does not demonstrate learned generalization. No independent external test, uncertainty calibration or feature-usage probabilities were estimated.')
    heading('Conclusions and limits')
    for species,methods in results.items():
        learned_k=selected[species]['learned']; raw_k=selected[species]['sp']
        add(f'- {species}: conservative display K is {learned_k} with learned moves and {raw_k} with SP only. ' + ('The available screen does not support a repeatable multi-cluster learned partition.' if learned_k==1 else 'The descriptive screen supports a repeatable partition under its stated assumptions; it does not establish tactical roles.'))
        numeric=('speed','attack','special_attack','bulk')
        wins=[]; losses=[]
        for target in numeric:
            ts=evaluation['summaries'][species]
            a,b=ts['sp'][target]['loss'],ts['learned'][target]['loss']
            if a is not None and b is not None:
                (wins if b<a else losses).append(f'{target} ({a:.2f}→{b:.2f})')
        add('  Learned versus SP-only held-out numeric MAE: improves '+(', '.join(wins) or 'none')+'; ties/worsens '+(', '.join(losses) or 'none')+'.')
    add()
    add('Move association can alter neighborhoods beyond raw SP, but improvement must be judged target by target against the empirical baseline above. Greater separation or an attractive projection alone is not evidence of better similarity. The study does not establish universal tactical archetypes or an optimal distance. It uses one pinned regulation/source population, a small parameter grid, only three resamples and three grouped folds; pooling conceals interactions and rare-pair uncertainty remains. Defensive decomposition, categorical weights and the cluster-count screen remain modeling assumptions. No Champions mechanics or learnsets were inferred from co-occurrence. No new 52Poké data was needed or retrieved; existing pinned canonicalization, rule validation and form compatibility are reused unchanged.')
    add()
    add('Concrete assessment: the learned representation identifies observed moveset-associated neighborhoods, including the seven high-Attack Incineroar occurrences, but does not improve any of the four numeric prediction targets over SP-only in these three species. For Incineroar, learned item-identity error is 0.305 versus SP-only 0.381 and training-mode 0.310, a small exploratory gain over the mode. SP+Jaccard has lower numeric error than SP+learned for Incineroar Speed and bulk; neither outperforms SP-only there. Hatterene has no demonstrated predictive gain. Raichu Y has a repeatable default partition but no numeric gain, and its constant Attack/item targets are uninformative. There is insufficient evidence here to replace raw SP neighborhoods with the learned combined distance or accept a universal tactical partition. This negative/mixed result is a completed offline experiment, not a reason to tune weights until the hypotheses hold.')
    add()
    add('Stop at this offline study. No hierarchical prior, posterior over unknown builds, kernel smoothing, synthetic sampling, strategy recommendation or battle-facing UI integration is implemented.')
    report.write_text('\n'.join(lines)+'\n')
    files.append(report)
    return dict(files={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                report=str(report.resolve()),figures=len(files)-1)
