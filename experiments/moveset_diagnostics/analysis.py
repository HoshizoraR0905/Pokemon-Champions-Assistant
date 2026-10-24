"""Occurrence-preserving distances, partitions and external SP descriptions."""
from collections import Counter
from itertools import combinations
import math
import numpy as np
from experiments.build_similarity.core import (MoveModel, moves, validate_matrix,
    kmedoids, hierarchical, cut_tree, silhouette, adjusted_rand)

MODELS = ('moves-learned','moves-jaccard','loadout-learned','loadout-jaccard')
ITEM_WEIGHT = .5  # Existing M3.5.1 optional categorical coefficient; no tuning.


def restore_embedding(saved):
    """Restore fitted vectors exactly; no call to fit/SVD on the full data."""
    model=MoveModel(**saved['parameters'])
    model.vocabulary=saved['vocabulary']
    model.index={m:i for i,m in enumerate(model.vocabulary)}
    model.embedding=np.asarray(saved['embedding'],float)
    if model.embedding.shape!=(len(model.vocabulary),saved['parameters']['dimension']):
        raise ValueError('Saved embedding shape mismatch')
    return model


def jaccard(rows, include_item=False):
    tokens=[]
    for row in rows:
        token={('move',m) for m in moves(row)}
        if include_item:
            if not row.get('item'):raise ValueError('Item-aware comparison requires known original items')
            token.add(('item',row['item']))
        tokens.append(token)
    return np.array([[1-len(a&b)/len(a|b) for b in tokens] for a in tokens])


def positive_scale(d):
    values=np.asarray(d)[np.triu_indices(len(d),1)]
    positive=values[values>1e-12]
    return float(np.median(positive)) if len(positive) else 1.


def distances(rows, model, learned_scale=None):
    learned=model.distances(rows,rows)
    scale=positive_scale(learned) if learned_scale is None else learned_scale
    item=np.array([[a['item']!=b['item'] for b in rows] for a in rows],float)
    item_scale=positive_scale(item)
    raw_j=jaccard(rows);raw_loadout=jaccard(rows,True)
    result={'moves-learned':learned/scale,
            'moves-jaccard':raw_j/positive_scale(raw_j),
            'loadout-learned':learned/scale+ITEM_WEIGHT*item/item_scale,
            'loadout-jaccard':raw_loadout/positive_scale(raw_loadout)}
    for d in result.values():validate_matrix(d)
    return result,dict(learned_scale=scale,jaccard_scale=positive_scale(raw_j),
                       loadout_jaccard_scale=positive_scale(raw_loadout),item_scale=item_scale,item_weight=ITEM_WEIGHT)


def fit_partitions(d):
    """Unchanged deterministic PAM and average linkage, K=1..4."""
    ids=list(range(len(d)))
    pam=[]
    for k in range(1,min(4,len(d))+1):
        fit=kmedoids(d,k)
        pam.append(dict(k=k,**fit,sizes=[fit['labels'].count(z) for z in range(k)],silhouette=silhouette(d,fit['labels'])))
    tree=hierarchical(d);cuts=[]
    for k in range(1,min(4,len(d))+1):
        labels=cut_tree(len(d),tree,k=k)
        medoids=[]
        for z in range(k):
            indices=[i for i in ids if labels[i]==z]
            medoids.append(min(indices,key=lambda i:(sum(d[i,j] for j in indices),i)))
        cuts.append(dict(k=k,labels=labels,medoids=medoids,sizes=[labels.count(z) for z in range(k)],silhouette=silhouette(d,labels)))
    return dict(pam=pam,hierarchical=cuts,merges=tree)


def select_k(candidates, stability):
    """Exact M3.5.1 descriptive screen, smallest qualifying K; otherwise one."""
    n=sum(candidates[0]['sizes'])
    for c in candidates:
        if c['k']==1:continue
        aris=[r['ari'] for r in stability[str(c['k'])] if r['ari'] is not None]
        if min(c['sizes'])>=max(3,math.ceil(.1*n)) and c['silhouette']>=.25 and len(aris)>=3 and np.mean(aris)>=.65:
            return c['k']
    return 1


def join_labels(occurrence_ids, partition):
    """Never join numeric positions from independently ordered artifacts."""
    ids=partition['occurrence_ids'];labels=partition['labels']
    if len(ids)!=len(labels) or len(set(ids))!=len(ids) or set(ids)!=set(occurrence_ids) or len(set(occurrence_ids))!=len(occurrence_ids):
        raise ValueError('Compared partitions must have exactly the same unique occurrence IDs')
    mapping=dict(zip(ids,labels))
    return [mapping[rid] for rid in occurrence_ids]


def comparison(ids, left, right):
    a=join_labels(ids,left);b=join_labels(ids,right)
    akeys=sorted(set(a));bkeys=sorted(set(b))
    table=[[sum(x==i and y==j for x,y in zip(a,b)) for j in bkeys] for i in akeys]
    n=len(ids);cells=np.asarray(table,float);row=cells.sum(1);col=cells.sum(0)
    mutual=sum(cells[i,j]/n*math.log(cells[i,j]*n/(row[i]*col[j])) for i in range(len(row)) for j in range(len(col)) if cells[i,j])
    entropy=lambda c:-sum(v/n*math.log(v/n) for v in c if v)
    ha,hb=entropy(row),entropy(col)
    nmi=2*mutual/(ha+hb) if ha+hb else 1.
    return dict(ari=adjusted_rand(a,b),nmi=float(nmi),mutual_information_nats=float(mutual),
                left_labels=akeys,right_labels=bkeys,table=table,left_sizes=row.astype(int).tolist(),right_sizes=col.astype(int).tolist(),
                left_proportions=(row/n).tolist(),right_proportions=(col/n).tolist(),
                meaningful_multicluster_agreement=len(akeys)>1 and len(bkeys)>1)


def numeric(values):
    values=np.asarray(values,float)
    q=np.quantile(values,[0,.25,.5,.75,1])
    return dict(n=len(values),min=float(q[0]),q1=float(q[1]),median=float(q[2]),q3=float(q[3]),max=float(q[4]),
                iqr=float(q[3]-q[1]),frequencies={str(int(k)):v for k,v in sorted(Counter(map(int,values)).items())})


def move_table(rows, species_counts, species_n):
    counts=Counter(m for r in rows for m in moves(r))
    result=[]
    for rank,(move,count) in enumerate(sorted(counts.items(),key=lambda p:(-p[1],p[0])),1):
        species_frequency=species_counts[move]/species_n
        result.append(dict(rank=rank,move=move,occurrences=count,cluster_frequency=count/len(rows),
                           species_occurrences=species_counts[move],species_frequency=species_frequency,
                           lift=count/len(rows)/species_frequency))
    return result


def describe(rows, partition, d):
    ids=[r['empirical_record_id'] for r in rows];labels=join_labels(ids,partition)
    byid={rid:i for i,rid in enumerate(ids)}
    species_counts=Counter(m for r in rows for m in moves(r))
    summaries=[]
    for z in sorted(set(labels)):
        indices=[i for i,label in enumerate(labels) if label==z];members=[rows[i] for i in indices]
        outside=[i for i in range(len(rows)) if i not in indices]
        move_counts=move_table(members,species_counts,len(rows))
        complete=Counter(moves(r) for r in members)
        loadouts=Counter((moves(r),r['item']) for r in members)
        entropy=-sum((m['occurrences']/(4*len(members)))*math.log2(m['occurrences']/(4*len(members))) for m in move_counts)
        full_sets=sorted(complete.items(),key=lambda p:(-p[1],p[0]))
        within=[float(d[i,j]) for i,j in combinations(indices,2)]
        between=[float(d[i,j]) for i in indices for j in outside]
        medoid=partition['medoid_ids'][z]
        m=rows[byid[medoid]]
        summaries.append(dict(cluster=z,n=len(members),share=len(members)/len(rows),source_groups=len({r['evaluation_group'] for r in members}),
            distinct_movesets=len(complete),distinct_moveset_item_combinations=len(loadouts),
            largest_moveset_share=full_sets[0][1]/len(members),predominantly_one_moveset=full_sets[0][1]/len(members)>.5,
            moveset_frequency_entropy_bits=float(-sum(c/len(members)*math.log2(c/len(members)) for c in complete.values())),
            move_token_entropy_bits=entropy,all_move_frequencies=move_counts,top15_moves=move_counts[:15],
            overrepresented_moves=sorted((m for m in move_counts if m['occurrences']>=3 and m['lift']>1+1e-12),key=lambda m:(-m['lift'],-m['occurrences'],m['move']))[:5],
            complete_movesets=[dict(moves=list(ms),occurrences=c,frequency=c/len(members)) for ms,c in full_sets],
            complete_loadouts=[dict(moves=list(ms),item=item,occurrences=c,frequency=c/len(members)) for (ms,item),c in sorted(loadouts.items(),key=lambda p:(-p[1],p[0]))],
            sp={s:numeric([r['training_points'][s] for r in members]) for s in ('hp','attack','defense','special_attack','special_defense','speed')},
            bulk=numeric([sum(r['training_points'][s] for s in ('hp','defense','special_defense')) for r in members]),
            nature=dict(Counter(r['nature'] for r in members)),alignment=dict(Counter(json_alignment(r) for r in members)),
            item=dict(Counter(r['item'] for r in members)),ability=dict(Counter(r['ability'] for r in members)),
            within_dissimilarity=dict(pairs=len(within),mean=float(np.mean(within)) if within else None,median=float(np.median(within)) if within else None),
            between_dissimilarity=dict(pairs=len(between),mean=float(np.mean(between)) if between else None,median=float(np.median(between)) if between else None),
            medoid=dict(id=medoid,configuration=m['configuration'],training_points=m['training_points'],publications=m['publications'])))
    return summaries


def json_alignment(row):
    import json
    return json.dumps(row.get('alignment'),sort_keys=True,separators=(',',':'))
