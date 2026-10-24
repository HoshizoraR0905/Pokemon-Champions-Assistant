"""GitHub Markdown, scientific figures and compact machine-readable exports."""
from collections import Counter, defaultdict
import csv
from itertools import combinations
import json
from pathlib import Path
import numpy as np
from metagame.common import atomic_json
from .analysis import MODELS, comparison

TITLES={'sp':'SP only','combined-learned':'SP + learned moves','combined-jaccard':'SP + Jaccard moves',
        'moves-learned':'Learned moves only','moves-jaccard':'Jaccard moves only',
        'loadout-learned':'Learned moves + item','loadout-jaccard':'Jaccard moves + item token'}


def feature_collisions(rows, labels, include_item=False):
    """Optimistic empirical lookup ceiling, not a fitted/evaluated predictor."""
    if len(rows)!=len(labels) or not rows:raise ValueError('Nonempty equally sized rows and labels required')
    groups=defaultdict(Counter)
    for row,z in zip(rows,labels):
        ms=tuple(sorted(row['configuration']['moves']))
        groups[(ms,row['item'] if include_item else None)][z]+=1
    patterns=[dict(moves=list(ms),item=item,n=sum(counts.values()),
                   cluster_counts=[counts[z] for z in range(3)])
              for (ms,item),counts in sorted(groups.items(),key=lambda p:(-sum(p[1].values()),p[0]))]
    best=sum(max(counts.values()) for counts in groups.values())
    return dict(include_item=include_item,patterns=patterns,distinct_patterns=len(groups),
                mixed_patterns=sum(len(c)>1 for c in groups.values()),
                occurrences_in_mixed_patterns=sum(sum(c.values()) for c in groups.values() if len(c)>1),
                best_correct_count=best,empirical_lookup_accuracy_ceiling=best/len(rows),
                unavoidable_same_feature_conflicts=len(rows)-best,
                interpretation='Optimistic ceiling only on these frozen-label observations with exactly these features; no held-out or population bound')


def write_report(path,source,summary,distance_output,identity,fingerprint,run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .run import file_hash
    path=Path(path);assets=path.parent/'assets/m353-moveset-diagnostics';assets.mkdir(parents=True,exist_ok=True)
    names_path=Path(__file__).resolve().parents[2]/'knowledge/data/entities.json'
    names={r['canonical_id']:r['names'].get('en',r['canonical_id']) for r in json.loads(names_path.read_text())['entities']}
    def label(v):return str(v).split(':',1)[1].title() if str(v).startswith('nature:') else names.get(v,str(v))
    def pname(key):
        p=summary['partitions'][key]
        status='selected + diagnostic' if p['selected'] and p['diagnostic'] else 'selected' if p['selected'] else 'diagnostic'
        return f"{TITLES[p['model']]} K={p['k']} ({status})"
    rows=source['population.json']['targets']['Incineroar'];ids=[r['empirical_record_id'] for r in rows]
    order=['sp:k3']
    for key in MODELS:
        for k in (summary['models'][key]['selected_k'],3):
            name=key+f':k{k}'
            if name not in order:order.append(name)
    order+=['combined-learned:k3','combined-jaccard:k3']
    parts={key:summary['partitions'][key] for key in order};clusters=summary['clusters'];files=[]
    def save(fig,name):
        destination=assets/(name+'.png');fig.savefig(destination,dpi=160,bbox_inches='tight');plt.close(fig);files.append(destination)
    for key in MODELS:
        p=parts[key+':k3'];d=np.asarray(distance_output['matrices'][key]);order=np.argsort(p['labels'],kind='stable')
        fig,ax=plt.subplots(figsize=(6,5))
        im=ax.imshow(d[np.ix_(order,order)],cmap='viridis',interpolation='nearest',aspect='auto')
        ax.set(title=f'{TITLES[key]} · diagnostic PAM K=3 · N=197\nconservative selected K={summary["models"][key]["selected_k"]}; sizes {p["sizes"]}',xlabel='Occurrences ordered by this partition',ylabel='Occurrences ordered by this partition')
        fig.colorbar(im,ax=ax,label='Normalized dissimilarity (own scale)');save(fig,key+'-distance')
    for key in MODELS:
        pair=comparison(ids,parts[key+':k3'],parts['sp:k3']);table=np.asarray(pair['table'])
        fig,ax=plt.subplots(figsize=(5.9,4.6));im=ax.imshow(table,cmap='Blues',vmin=0)
        for i in range(len(table)):
            for j in range(3):ax.text(j,i,str(table[i,j]),ha='center',va='center',color='white' if table[i,j]>table.max()/2 else 'black')
        ax.set(title=f'{TITLES[key]} diagnostic K=3 vs SP-only selected K=3\nN=197 · ARI {pair["ari"]:.3f} · NMI {pair["nmi"]:.3f}',xticks=range(3),yticks=range(3),xlabel='SP-only cluster (31 / 24 / 142)',ylabel=f'{TITLES[key]} cluster')
        fig.colorbar(im,ax=ax,label='Original occurrence count');save(fig,key+'-overlap-sp')
    for methods,filename in [(MODELS[:2],'moves-sp-distributions'),(MODELS[2:],'loadout-sp-distributions')]:
        fig,axes=plt.subplots(2,6,figsize=(17,6),layout='constrained')
        for i,key in enumerate(methods):
            p=parts[key+':k3'];labels=np.asarray(p['labels'])
            for j,stat in enumerate(('attack','speed','bulk','hp','defense','special_defense')):
                values=np.array([sum(r['training_points'][s] for s in ('hp','defense','special_defense')) if stat=='bulk' else r['training_points'][stat] for r in rows])
                axes[i,j].boxplot([values[labels==z] for z in range(3)],tick_labels=['0','1','2'],showmeans=True)
                axes[i,j].set(title=stat.replace('_',' ').title(),xlabel='Local diagnostic cluster',ylabel='Original SP')
            axes[i,0].set_ylabel(TITLES[key]+'\nOriginal SP')
        fig.suptitle('Original SP within diagnostic PAM K=3 partitions · same 197 occurrences; cluster IDs are model-specific',fontsize=11)
        save(fig,filename)
    vocabulary=Counter(m for r in rows for m in r['configuration']['moves'])
    move_ids=sorted(vocabulary,key=lambda m:(-vocabulary[m],m))[:18]
    chosen=['sp:k3',*[(k+':k3') for k in MODELS],'combined-learned:k3']
    heat_rows=[];heat_labels=[]
    for partition in chosen:
        for c in clusters[partition]:
            frequencies={m['move']:m['cluster_frequency'] for m in c['all_move_frequencies']}
            heat_rows.append([100*frequencies.get(m,0) for m in move_ids]);heat_labels.append(f"{TITLES[parts[partition]['model']]} · C{c['cluster']} (n={c['n']})")
    fig,ax=plt.subplots(figsize=(13,8));im=ax.imshow(heat_rows,cmap='YlGnBu',vmin=0,vmax=100,aspect='auto')
    ax.set(xticks=range(len(move_ids)),xticklabels=[label(m) for m in move_ids],yticks=range(len(heat_labels)),yticklabels=heat_labels,
           title='Canonical move presence within PAM K=3 clusters · N=197 per partition\nSP-only selected; move/item-only diagnostic (selected K shown in tables); combined selected K=1',xlabel='Most frequent species moves (up to 18)',ylabel='Partition and its own cluster ID')
    plt.setp(ax.get_xticklabels(),rotation=50,ha='right');fig.colorbar(im,ax=ax,label='Occurrences containing move / cluster size (%)')
    save(fig,'cluster-move-frequency')
    # No matrices, embeddings or full training intermediates in tracked exports.
    collisions={key:feature_collisions(rows,parts['sp:k3']['labels'],item) for key,item in [('moves',False),('moves_item',True)]}
    collision_path=assets/'feature-collisions.json';atomic_json(collision_path,collisions);files.append(collision_path)
    assignment_path=assets/'assignments.csv'
    with assignment_path.open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['occurrence_id',*parts])
        for i,rid in enumerate(ids):writer.writerow([rid,*[p['labels'][i] for p in parts.values()]])
    files.append(assignment_path)
    for filename,value in [('partition-comparisons.json',[summary['comparisons'][key] for key in sorted(summary['comparisons'])]),
                           ('cluster-statistics.json',dict(partitions={key:{k:v for k,v in p.items() if k not in ('occurrence_ids','labels')} for key,p in parts.items()},clusters=clusters)),
                           ('provenance.json',dict(fingerprint=fingerprint,identity=identity,occurrences=197,source_groups=summary['source_groups'],
                               distinct_full_builds=summary['distinct_full_builds'],distinct_movesets=summary['distinct_movesets'],normalization=summary['normalization'],
                               models={key:dict(selected_k=v['selected_k'],candidates=[{k:c[k] for k in ('k','sizes','silhouette')} for c in v['candidates']],
                                   stability=v['stability'],hierarchical=[{k:c[k] for k in ('k','sizes','silhouette')} for c in v['hierarchical']]) for key,v in summary['models'].items()}))]:
        destination=assets/filename;atomic_json(destination,value);files.append(destination)
    lines=[]
    def add(value=''):lines.append(value)
    def table(headers,body):
        add('| '+' | '.join(headers)+' |');add('|'+'|'.join('---' for _ in headers)+'|')
        for row in body:add('| '+' | '.join(str(v) for v in row)+' |')
        add()
    def freq(values,limit=5):return '; '.join(f'{label(k)} ×{v}' for k,v in sorted(values.items(),key=lambda p:(-p[1],p[0]))[:limit]) or 'None'
    def overlap(left,right):
        pair=comparison(ids,parts[left],parts[right])
        add(f'**Rows: {pname(left)}. Columns: {pname(right)}.**')
        add()
        table(['Row cluster',*[f'C{z}' for z in pair['right_labels']],'Row total'],[[f'C{z}',*row,sum(row)] for z,row in zip(pair['left_labels'],pair['table'])]+[['Column total',*pair['right_sizes'],197]])
        add('Row-conditional memberships: '+ '; '.join(f"C{z} → "+' / '.join(f'{100*v/sum(row):.1f}%' for v in row) for z,row in zip(pair['left_labels'],pair['table']))+'.')
        add('Column-conditional memberships (column clusters back to row clusters): '+ '; '.join(f"C{z} → "+' / '.join(f'{100*pair["table"][i][j]/pair["right_sizes"][j]:.1f}%' for i in range(len(pair['table']))) for j,z in enumerate(pair['right_labels']))+'.')
        add()
    add('# M3.5.3 follow-up — Incineroar movesets, items and SP clusters');add()
    add('*25 October 2026 · offline diagnostic experiment · no predictor or annotation changes*');add()
    add('Manual review of the no-SP predictions fell below expectations. Before changing that predictor, this study asks whether moveset neighborhoods actually align with the SP investment neighborhoods they were being used to predict. It also follows the request to include held items as part of the observed four-move package.');add()
    add('The main finding is **weak SP alignment despite recurring moveset packages**. Jaccard selects a stable 143/54 split, but its ARI with SP-only is 0.056. Learned moves isolate rare Close Combat and Helping Hand packages; the conservative screen selects K=1. Adding items leaves the selected and forced K=3 memberships unchanged under both definitions tested here.');add()
    add('## Same observations, different questions');add()
    add(f"Every comparison retains the same **197 original complete Incineroar occurrences**, representing **{summary['distinct_full_builds']} distinct full builds**, **{summary['distinct_movesets']} complete movesets**, and **{summary['source_groups']} connected M3.5.1 source groups**. Identical published builds keep their original occurrence weights. Assignments join by immutable occurrence ID, never by cluster number. Original SP, canonical moves, nature/alignment, ability, item and publications remain in the source artifacts and local diagnostic run.");add()
    add('The SP-only selected K=3 (31/24/142), combined SP + learned diagnostic K=3 (34/7/156; selected K=1), and combined SP + Jaccard diagnostic K=3 (112/66/19; selected K=1) are reused unchanged. No baseline is refitted. Source-stage hashes are checked against the completed manifest and the tracked M3.5.2 evidence where available.');add()
    add('Four new dissimilarities are compared:');add()
    add('- **Learned moves only:** saved shrunk-PPMI/SVD move vectors, original mean pooling and cosine dissimilarity, divided by the exact saved Incineroar positive-median scale. The full-population embedding is restored, never retrained.\n- **Jaccard moves only:** one minus intersection/union of the four canonical move sets.\n- **Jaccard moves + item:** the set has four typed move tokens and one typed item token. Item identity contributes to exact package overlap without pretending it is a learned move. All 197 original items are known.\n- **Learned moves + item:** normalized learned move dissimilarity plus **0.5 × normalized item mismatch**. The 0.5 coefficient comes from M3.5.1’s existing categorical ablation; nature is excluded and no weight is tuned. This is a separate diagnostic, not an item embedding or predictor change.');add()
    add(r'For move sets, $d_J=1-|M_i\cap M_j|/|M_i\cup M_j|$; the item-token variant uses the same expression on five typed tokens. Positive-median normalization changes units, not PAM or linkage partitions. Each model has its own scale; combining learned moves with item mismatch does depend on their stated relative weight.');add()
    add('## What clustering produces');add()
    add('All new models use the existing deterministic precomputed-distance PAM and occurrence-weighted average linkage, with K=1–4. The conservative PAM screen is unchanged: silhouette ≥0.25, minimum cluster size ≥20, and mean retained-anchor ARI ≥0.65 computed from three available resamples; choose the smallest qualifying K, otherwise K=1. K=1 silhouette is undefined and its ARI of one is automatic. Forced K=3 remains diagnostic.');add()
    body=[]
    for key in MODELS:
        model=summary['models'][key];selected=next(c for c in model['candidates'] if c['k']==model['selected_k']);forced=next(c for c in model['candidates'] if c['k']==3)
        body.append([TITLES[key],model['selected_k'],' / '.join(map(str,selected['sizes'])),'—' if selected['silhouette'] is None else f"{selected['silhouette']:.3f}",' / '.join(map(str,forced['sizes'])),f"{forced['silhouette']:.3f}"])
    table(['Distance','Selected K','Selected sizes','Selected silhouette','Diagnostic K=3 sizes','K=3 silhouette'],body)
    add('Full-data learned distances reconstruct the original combined matrix after adding the saved SP component. Jaccard likewise reconstructs its saved combined baseline. For stability only, three 80% source-group subsets use exactly the original seeds 351–353 and global group pool. The embedding is refitted on each subset once and shared across new methods; normalization and PAM are also refitted. These are pipeline-stability checks, not a new full-data representation, tuning, independent validation, or confidence intervals.');add()
    add('<details>\n<summary>All K candidates, stability values and average-linkage cuts</summary>\n')
    candidate_rows=[]
    for key in MODELS:
        for c in summary['models'][key]['candidates']:
            aris=summary['models'][key]['stability'][str(c['k'])]
            candidate_rows.append([TITLES[key],c['k'],' / '.join(map(str,c['sizes'])),'—' if c['silhouette'] is None else f"{c['silhouette']:.3f}",' / '.join(f"{r['ari']:.3f}" for r in aris), 'selected' if c['k']==summary['models'][key]['selected_k'] else 'candidate'])
    table(['PAM distance','K','Sizes','Silhouette','Three resample ARIs','Status'],candidate_rows)
    table(['Average-linkage distance','K','Sizes','Silhouette'],[[TITLES[key],c['k'],' / '.join(map(str,c['sizes'])),'—' if c['silhouette'] is None else f"{c['silhouette']:.3f}"] for key in MODELS for c in summary['models'][key]['hierarchical']])
    add('Average linkage is a descriptive cross-check; the conservative selection rule applies to PAM, as in M3.5.1. Resamples retain 158, 155 and 159 Incineroar anchors.');add();add('</details>');add()
    for key in MODELS:
        add(f"![{TITLES[key]} diagnostic K=3 distance heatmap, N=197](assets/m353-moveset-diagnostics/{key}-distance.png)");add()
    add('Each distance cell compares two original occurrences. Rows and columns follow that model’s diagnostic K=3 labels; low-distance blocks may reflect repeated exact packages. Color is dissimilarity, not a tactical class. The heatmaps have separate scales/orderings and cannot be compared pixel for pixel.');add()
    add('The learned K=3 groups are 179 broad observations, seven sharing Fake Out / Close Combat / Flare Blitz / Darkest Lariat, and 11 all carrying Helping Hand. The seven-member group contains five connected source groups and is one exact moveset; the 11-member group has three complete movesets, nine of them identical. Both groups fall below the 20-occurrence size threshold. Their separation therefore does not establish three recurring SP archetypes.');add()
    add('Jaccard PAM instead separates the 54 Darkest Lariat observations from 143 others at selected K=2. Forced K=3 separates a 97-member Throat Chop group and a 46-member mixture centered on Snarl/Protect/Helping Hand variants. This partition is stable under the narrow resampling check, but average linkage gives a very different 187/10 K=2 split. The clustering algorithm matters as well as the dissimilarity.');add()
    add('## How much do the partitions agree with SP?');add()
    against=[]
    for key,p in parts.items():
        if key=='sp:k3':continue
        pair=comparison(ids,p,parts['sp:k3'])
        against.append([pname(key),' / '.join(map(str,p['sizes'])),f"{pair['ari']:.3f}",f"{pair['nmi']:.3f}",'K=1: no grouping claim' if p['k']==1 else 'descriptive'])
    table(['Partition versus SP-only K=3','Sizes','ARI','NMI','Interpretation'],against)
    add('ARI adjusts pair agreement for chance. NMI uses arithmetic-mean entropy normalization, $2I/(H_1+H_2)$, with natural logarithms. Both are invariant to renumbering clusters. K=1 comparisons are exported but cannot establish successful multicluster grouping. Unequal group sizes and related publications still affect what apparent agreement means.');add()
    for key in MODELS:
        add(f"![{TITLES[key]} diagnostic K=3 versus SP-only selected K=3, occurrence-count overlap](assets/m353-moveset-diagnostics/{key}-overlap-sp.png)");add()
        overlap(key+':k3','sp:k3')
        selected=summary['models'][key]['selected_k']
        if selected!=3:overlap(key+f':k{selected}','sp:k3')
    add('### Learned versus exact overlap, and combined distances');add()
    primary_pair=comparison(ids,parts['moves-learned:k3'],parts['moves-jaccard:k3'])
    add(f"Forced K=3 learned versus Jaccard moves-only agreement is **ARI {primary_pair['ari']:.3f}, NMI {primary_pair['nmi']:.3f}**. Similar-looking moveset groups need not have similar SP composition.");add()
    overlap('moves-learned:k3','moves-jaccard:k3');overlap('combined-learned:k3','sp:k3');overlap('combined-jaccard:k3','sp:k3')
    add('<details>\n<summary>All pairwise comparison metrics, including selected and item-aware partitions</summary>\n')
    table(['Left','Right','ARI','NMI'],[[pname(v['left']),pname(v['right']),f"{v['ari']:.3f}",f"{v['nmi']:.3f}"] for v in [summary['comparisons'][key] for key in sorted(summary['comparisons'])]]);add('</details>');add()
    add('All pairwise occurrence-count contingency tables, sizes and proportions are in [partition-comparisons.json](assets/m353-moveset-diagnostics/partition-comparisons.json); the principal cross-tabs above show both directions explicitly.');add()
    add('## Do moveset groups separate original SP allocations?');add()
    for filename in ('moves-sp-distributions','loadout-sp-distributions'):
        add(f'![Original SP distributions inside diagnostic K=3 move or item-aware partitions, N=197]'+f'(assets/m353-moveset-diagnostics/{filename}.png)');add()
    add('Each row uses its own model’s cluster IDs. Boxes span Q1–Q3, lines are medians, triangles are means, and circles are outliers. Bulk is HP + Defense + Special Defense. SP values are the original observations, not inferred allocations.');add()
    for key in [p for p in parts if parts[p]['model'] in MODELS]:
        add('### '+pname(key));add()
        table(['Cluster','N / share','Attack median [Q1–Q3]','Speed median [Q1–Q3]','Bulk median [Q1–Q3]','HP / Def / SpD medians','SP ranges: Attack; Speed'],[[c['cluster'],f"{c['n']} / {100*c['share']:.1f}%",*[f"{c[field]['median']:g} [{c[field]['q1']:g}–{c[field]['q3']:g}]" if field=='bulk' else f"{c['sp'][field]['median']:g} [{c['sp'][field]['q1']:g}–{c['sp'][field]['q3']:g}]" for field in ('attack','speed','bulk')], ' / '.join(f"{c['sp'][s]['median']:g}" for s in ('hp','defense','special_defense')),f"{c['sp']['attack']['min']:g}–{c['sp']['attack']['max']:g}; {c['sp']['speed']['min']:g}–{c['sp']['speed']['max']:g}"] for c in clusters[key]])
        for c in clusters[key]:
            add(f"**C{c['cluster']}** — Attack SP : counts `{c['sp']['attack']['frequencies']}`; Speed SP : counts `{c['sp']['speed']['frequencies']}`. Natures: {freq(c['nature'])}. Items: {freq(c['item'])}.");add()
    add('Full distributions for every SP coordinate and bulk, all nature/alignment and item counts, and original medoid builds are in [cluster-statistics.json](assets/m353-moveset-diagnostics/cluster-statistics.json). Tables report both central spread and full Attack/Speed frequencies so low/high-investment mixtures remain visible.');add()
    add('### Identical observed packages already hide different SP groups');add()
    add('The most common exact moveset—**Fake Out / Flare Blitz / Parting Shot / Throat Chop**—occurs 88 times: **17 higher-Speed, eight higher-Attack, and 63 lower-Speed defensive** builds. Fixing its item to **Sitrus Berry** still leaves **15 / 6 / 50** across those SP groups in 71 occurrences. These are identical predictor inputs with conflicting frozen SP labels, not an embedding artifact.');add()
    table(['Observed features','Distinct packages','Packages spanning SP groups','Occurrences in mixed packages','Best empirical lookup accuracy','Unavoidable conflicting-label errors'],[[title,c['distinct_patterns'],c['mixed_patterns'],c['occurrences_in_mixed_patterns'],f"{100*c['empirical_lookup_accuracy_ceiling']:.2f}% ({c['best_correct_count']}/197)",c['unavoidable_same_feature_conflicts']] for title,c in [('Moves only',collisions['moves']),('Moves + item',collisions['moves_item'])]])
    add('The lookup calculation assigns each exact feature package its most frequent frozen SP label and sums the resulting correct counts. It is an **optimistic in-sample ceiling on these 197 frozen labels**, not a trained classifier, cross-validation result, or bound on future battles. The frozen majority share is 142/197 = 72.08%; exact moves allow at most 77.16%, and adding item raises this only to 77.66%. Earlier M3.5.3 cross-validation used fold-refitted SP labels, so its accuracy has a different target and is not directly comparable. All package counts are exported in [feature-collisions.json](assets/m353-moveset-diagnostics/feature-collisions.json).');add()
    add('## Which moves characterize each cluster?');add()
    add('In SP-only clusters, moves and items are **external descriptions**: neither formed those clusters. Within moveset-based clusters, move enrichment is partly tautological; in item-aware clusters item enrichment is also partly tautological. The test of practical relevance is their agreement with external SP, not whether their defining moves look coherent.');add()
    add(r'For each canonical move, $f_z(m)=n_{z,m}/|C_z|$, species frequency $f(m)=n_m/197$, and $\operatorname{Lift}_z(m)=f_z(m)/f(m)$. Primary ranks sort occurrence count descending, then canonical move ID for ties. Lift never determines the main rank. Frequencies sum to **400%** over the full move vocabulary because each occurrence has four distinct moves; the displayed top 15 can sum to less. Items are separate package tokens and are not inserted into move tables.');add()
    add(r'Supplementary overrepresentation lists require **lift >1 and at least three occurrences within that cluster**, then sort lift descending, count descending and canonical ID. No entry is fabricated when fewer than 15 moves or five supported enrichments exist. Move-token entropy is $-\sum_m p_m\log_2 p_m$, where $p_m=n_{z,m}/(4|C_z|)$; complete-set entropy instead uses whole-moveset occurrence shares. Neither is a tactical diversity score.');add()
    add('![Canonical cluster-by-move presence frequencies, PAM K=3 comparisons with N=197 each](assets/m353-moveset-diagnostics/cluster-move-frequency.png)');add()
    add('Color shows the percentage of that row’s occurrences containing a move. This common 0–100% scale makes external move differences in SP clusters comparable with the more expected concentrations in move-based groups.');add()
    add('A few useful external contrasts are visible before opening the full tables. Fake Out and Flare Blitz occur in every higher-Speed and higher-Attack SP build, so they do not distinguish those two groups. Close Combat occurs in seven of 24 higher-Attack builds and nowhere else: a specific minority signal with limited coverage. The remaining 17 higher-Attack observations retain Parting Shot and mostly share the same Throat Chop or Darkest Lariat combinations as other SP groups.');add()
    add('In forced learned moves-only K=3, Close Combat has lift 28.14 in the seven-member group, while Helping Hand has lift 17.91 in the 11-member group. In forced Jaccard K=3, Snarl occurs 18/46 (lift 4.28), Throat Chop 97/97 (lift 2.03), and Darkest Lariat 54/54 (lift 3.65) in their respective groups. Those clear move identities coexist with weak SP separation. Items are fully described in the exported distributions and package tables below.');add()
    for key,p in parts.items():
        add('<details>\n<summary>'+pname(key)+' — full top-15 tables and complete-set summaries</summary>\n')
        for c in clusters[key]:
            add(f"### Cluster {c['cluster']} · {c['n']} occurrences ({100*c['share']:.1f}%)");add()
            add(f"{c['source_groups']} connected source groups; {c['distinct_movesets']} distinct complete movesets; {c['distinct_moveset_item_combinations']} distinct moveset/item packages. Largest exact moveset share **{100*c['largest_moveset_share']:.1f}%**; predominantly one set (>50%): **{'yes' if c['predominantly_one_moveset'] else 'no'}**. Move-token entropy {c['move_token_entropy_bits']:.3f} bits; complete-set entropy {c['moveset_frequency_entropy_bits']:.3f} bits.");add()
            ms=c['medoid']['configuration'];pub=c['medoid']['publications'][0]
            add(f"Observed medoid: **{' / '.join(label(m) for m in ms['moves'])}**, {label(ms['item'])}, {label(ms['nature'])}, {label(ms['ability'])}; SP {' / '.join(map(str,ms['sp']['values']))}. [Original publication]({pub['url']}).");add()
            def distance_text(value):return 'undefined (no pairs)' if value['mean'] is None else f"mean {value['mean']:.3f}, median {value['median']:.3f}, {value['pairs']} pairs"
            add('Within-cluster dissimilarity: '+distance_text(c['within_dissimilarity'])+'. Versus all outside occurrences: '+distance_text(c['between_dissimilarity'])+'. Distances use that model’s normalized units.');add()
            table(['Rank','Move','Occurrences','Cluster frequency (%)','Species-wide frequency (%)','Lift'],[[m['rank'],label(m['move']),m['occurrences'],f"{100*m['cluster_frequency']:.2f}",f"{100*m['species_frequency']:.2f}",f"{m['lift']:.3f}"] for m in c['top15_moves']])
            add('**Top complete four-move combinations:**');add()
            table(['Four-move set','Occurrences','Cluster share (%)'],[[' / '.join(label(m) for m in ms['moves']),ms['occurrences'],f"{100*ms['frequency']:.1f}"] for ms in c['complete_movesets'][:5]])
            if p['model'].startswith('loadout'):
                add('**Top move/item packages:**');add()
                table(['Moves','Item','Occurrences'],[[' / '.join(label(m) for m in ms['moves']),label(ms['item']),ms['occurrences']] for ms in c['complete_loadouts'][:5]])
            add('**Most overrepresented moves (support ≥3):** '+('; '.join(f"{label(m['move'])}: {m['occurrences']} occurrences, lift {m['lift']:.3f}" for m in c['overrepresented_moves']) or 'none meet support')+'.');add()
        add('</details>');add()
    add('## Interpretation and implications');add()
    add('The learned 179-member group contains 17 higher-Attack SP builds alongside 29 higher-Speed and 133 defensive builds; only seven of all 24 higher-Attack occurrences form its isolated Close Combat group. The selected Jaccard Darkest Lariat group contains 3 / 15 / 36 SP memberships. Its Attack median is only 0, even though 15 members belong to the higher-Attack SP group. Calling the whole group offensive would hide its majority low-Attack membership.');add()
    add('The figures and full count tables above separate three questions: recurring observed move/item packages, agreement with SP-defined investment groups, and success at predicting a held-out SP group. These are not interchangeable. A dominant common set can contain several Speed investments; a minority high-Attack package can be clear while broader Attack investment remains distributed across other sets. Item-aware groupings can become more homogeneous in held item by construction without acquiring correspondingly clearer SP separation.');add()
    add('This is a descriptive full-population diagnostic, not a new cross-validated predictor evaluation. It can help explain disappointing no-SP reviews when moveset clusters mix SP groups, but cannot diagnose each human judgment or establish the true SP of reviewed no-SP records. Human notes and annotations are not used as labels or rewritten. No new prior, prediction rule, embedding hyperparameter, SP coefficient, team-context model, or battle integration is introduced.');add()
    add('## Reproduction and limits');add()
    add(f"Run fingerprint: **`{fingerprint}`**. The input is the completed M3.5.1 cache only; no database collection, scraping, external knowledge retrieval, OCR or replay is needed. New matrices and intermediate resample fits stay under `.cache/research/m353-moveset-diagnostics/{fingerprint}/`. The atomic manifest records source hashes, progress, successful/failed stages and the exact resume command. Existing source results and no-SP predictor/review files are hash-checked before and after execution.");add()
    add('```sh\n.venv/bin/python -m experiments.moveset_diagnostics.run\n.venv/bin/python -m pytest -q tests/test_moveset_diagnostics.py tests/test_git_artifact_policy.py\n```');add()
    add('See [implementation and cache notes](../experiments/moveset_diagnostics/README.md). Tracked lightweight exports: [occurrence assignments](assets/m353-moveset-diagnostics/assignments.csv), [all pairwise metrics and overlaps](assets/m353-moveset-diagnostics/partition-comparisons.json), [cluster counts and SP distributions](assets/m353-moveset-diagnostics/cluster-statistics.json), and [configuration, stability and source provenance](assets/m353-moveset-diagnostics/provenance.json). Large pairwise matrices and fitted intermediates remain local.');add()
    add('Verification completed: **51 portable tests passed** across the diagnostic, existing no-SP, and artifact-policy suites. Tests cover occurrence joins and weighting, all exported move/set counts and ranks, frequencies/lift, ARI/NMI and overlap margins, item tokens, restored embeddings, source protection and annotation persistence. A same-command resume reused all **11 completed stages**, with no new fitting. GitHub’s renderer recognized all 11 figures and 27 top-15 tables inside collapsible sections; figure labels and SP distributions were visually inspected. Protected source, predictor and annotation file hashes were unchanged. These checks do not establish tactical roles or human acceptance.');add()
    add('There are only three stability resamples, one selectively published source/regulation population, correlated repeated occurrences, and no tactical ground-truth labels. Stability is conditional on these methods and source groups; frequencies are published-sample shares, not usage probabilities in all Champions battles. Global association captures co-occurrence rather than interchangeable function. Average pooling, normalization, categorical weight and K-selection thresholds remain modeling assumptions. No new mechanics or learnset claims are made. **Stop at these diagnostics; the predictor and human review remain unchanged.**');add()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(lines).rstrip()+'\n');files.append(path)
    return dict(files={str(p):file_hash(p) for p in files},matrix_exports=False,predictor_changed=False)
