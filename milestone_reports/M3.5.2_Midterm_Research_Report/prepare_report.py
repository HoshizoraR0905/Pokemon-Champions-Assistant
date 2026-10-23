"""Prepare presentation assets from saved M3.5.1 results; no fitting/imports.

Rebuild the document directly from checked-in assets with build.sh. This optional
script needs the original local study cache only to refresh figures/tables.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATS=('hp','attack','defense','special_attack','special_defense','speed')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tex(s):
    return str(s).replace('\\',r'\textbackslash{}').replace('_',r'\_').replace('&',r'\&').replace('%',r'\%')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path)
    args=parser.parse_args()
    study=args.study or Path(json.loads((ROOT/'.cache/research/m351/latest.json').read_text())['path'])
    manifest=json.loads((study/'manifest.json').read_text())
    if manifest.get('status')!='complete':raise ValueError('Incomplete source study')
    sources={}
    def read(filename):
        path=study/filename
        stage=manifest['stages'][path.stem]
        if stage['status']!='complete' or sha(path)!=stage['sha256']:raise ValueError('Source integrity: '+filename)
        sources[filename]=sha(path)
        return json.loads(path.read_text())
    data=read('population.json'); selection=read('selection.json'); heldout=read('heldout.json')
    diagnostics=read('moves.json')
    names={e['canonical_id']:e['names'].get('en',e['canonical_id']) for e in json.loads((ROOT/'knowledge/data/entities.json').read_text())['entities']}
    def label(x):return x.split(':',1)[1] if x.startswith('nature:') else names.get(x,x)
    def build(row):
        return dict(id=row['empirical_record_id'],original_record_ids=row['original_record_ids'],
                    source_species=row['species'],configuration=row['configuration'],
                    training_points=row['training_points'],nature=label(row['nature']),ability=label(row['ability']),
                    item=label(row['item']),moves=[label(m) for m in row['configuration']['moves']],
                    publications=row['publications'],team_id=row['observed_team_signature'])
    summaries={}; results={}; stab={}
    inspected={('Hatterene','learned',1),('Hatterene','learned',2),('Hatterene','learned',3),
               ('Incineroar','sp',3),('Incineroar','learned',3),('Mega Raichu Y','learned',2)}
    for species,rows in data['targets'].items():
        slug=species.lower().replace(' ','-')
        results[species]={k:read(slug+'-'+k+'.json') for k in selection[species]}
        stab[species]=read(slug+'-stability.json')
        byid={r['empirical_record_id']:r for r in rows}
        summaries[species]=dict(n=len(rows),groups=len({r['evaluation_group'] for r in rows}),
            distinct_full_builds=len({json.dumps(r['configuration'],sort_keys=True) for r in rows}),
            selected_k=selection[species],models={})
        for method in ('sp','jaccard','learned','item-nature'):
            result=results[species][method]
            candidates=[]
            for c in result['kmedoids']:
                candidates.append(dict(k=c['k'],sizes=c['sizes'],silhouette=c['silhouette'],
                    resample_ari=[z['ari'] for z in stab[species][method][str(c['k'])]],
                    clusters=[dict(cluster=z['cluster'],n=z['occurrences'],distinct_cores=z['distinct_training_cores'],
                        medoid=build(byid[z['medoid']]),sp={stat:dict(summary=v['summary'],min=min(map(int,v['frequencies']))) for stat,v in z['sp'].items()},bulk=z['bulk'],
                        items={label(k):v for k,v in z['item'].items()},
                        movesets=[dict(moves=[label(m) for m in m['moves']],n=m['occurrences']) for m in z['complete_movesets']]) for z in c['summaries']] if (species,method,c['k']) in inspected else []))
            summaries[species]['models'][method]=dict(config=result['config'],normalization=result['normalization'],candidates=candidates,
                hierarchical_cuts=[dict(k=c['k'],sizes=c['sizes'],silhouette=c['silhouette']) for c in result['hierarchical']['k_cuts']],
                hierarchical_thresholds=[dict(threshold=c['threshold'],sizes=c['sizes'],silhouette=c['silhouette']) for c in result['hierarchical']['threshold_cuts']])
    a=results['Incineroar']['sp']['kmedoids'][2]['labels']; b=results['Incineroar']['learned']['kmedoids'][2]['labels']
    cross=np.zeros((3,3),int)
    for i,j in zip(a,b):cross[i,j]+=1
    # Copy all eleven existing scientific plots byte-for-byte.
    figures=HERE/'figures'; figures.mkdir(exist_ok=True)
    original_files=read('report.json')['files']
    provenance=[]
    for source in sorted((study/'figures').glob('*.png')):
        if original_files.get(str(source.resolve()))!=sha(source):raise ValueError('Figure integrity: '+source.name)
        destination=figures/source.name;shutil.copyfile(source,destination)
        provenance.append(dict(file=source.name,kind='existing figure copied byte-for-byte',source=str(source.relative_to(ROOT)),sha256=sha(source)))
    # Required missing comparison: saved SP-only matrix and saved K=3 labels.
    result=results['Incineroar']['sp']; d=np.asarray(result['distance_matrix'])
    c=result['kmedoids'][2]; labels=np.asarray(c['labels']); order=np.argsort(labels,kind='stable')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    def save(name):
        plt.tight_layout(); plt.savefig(figures/name,dpi=180,bbox_inches='tight');plt.close()
        provenance.append(dict(file=name,kind='new presentation plot from saved SP-only matrix/labels; no clustering refit',
            source=str((study/'incineroar-sp.json').relative_to(ROOT)),source_sha256=sources['incineroar-sp.json'],sha256=sha(figures/name)))
    plt.figure(figsize=(6,5));plt.imshow(d[np.ix_(order,order)],cmap='viridis');plt.colorbar(label='Combined dissimilarity (SP-only weights)')
    plt.xlabel('Occurrences ordered by cluster');plt.ylabel('Occurrences ordered by cluster');plt.title('Incineroar: SP-only; selected K=3')
    save('incineroar-sp-only-heatmap.png')
    n=len(d); center=np.eye(n)-np.ones((n,n))/n; gram=-.5*center@(d*d)@center
    eig,u=np.linalg.eigh(gram); idx=np.argsort(eig)[::-1];positive=np.maximum(eig[idx[:2]],0)
    xy=u[:,idx[:2]]*np.sqrt(positive);mass=float(positive.sum()/np.maximum(eig,0).sum())
    plt.figure(figsize=(6,4.5));plt.scatter(xy[:,0],xy[:,1],c=labels,cmap='tab10',alpha=.65,s=30)
    for m in c['medoids']:plt.scatter(*xy[m],marker='X',c='black',s=100)
    plt.xlabel('Positive projection axis 1');plt.ylabel('Positive projection axis 2')
    plt.title(f'Incineroar: SP-only 2D projection; selected K=3\npositive eigenmass {mass:.1%}; negative eigenvalues {sum(eig < -1e-9)}')
    save('incineroar-sp-only-projection.png')
    x=np.array([[r['training_points'][s] for s in STATS] for r in data['targets']['Incineroar']])
    fig,axes=plt.subplots(2,3,figsize=(10,6))
    for j,ax in enumerate(axes.flat):
        ax.boxplot([x[labels==z,j] for z in range(3)],tick_labels=[str(z) for z in range(3)],showmeans=True)
        ax.set_title(STATS[j]);ax.set_ylim(-1,33);ax.set_xlabel('Cluster index')
    fig.suptitle('Incineroar: SP-only; selected K=3');save('incineroar-sp-only-boxplots.png')
    summary=dict(study_fingerprint=study.name,source_scope=data['audit'],species=summaries,
        incineroar_k3_membership_cross_tab=cross.tolist(),heldout=heldout['summaries'],oov=heldout['oov'],
        move_diagnostics=dict(observations=diagnostics['observations'],vocabulary_size=len(diagnostics['vocabulary']),
            observed_pairs=len(diagnostics['pair_counts_and_associations']),rare_pairs_at_most_two=diagnostics['rare_pairs_at_most_two'],parameters=diagnostics['parameters']),
        figure_provenance=provenance,source_sha256=sources,
        sp_only_projection=dict(positive_eigenmass=mass,negative_eigenvalues=int(sum(eig < -1e-9))),
        sensitivity={species:{method:dict(selected_k=selection[species][method],
            k2_sizes=r['kmedoids'][1]['sizes'],k2_silhouette=r['kmedoids'][1]['silhouette'])
            for method,r in methods.items()} for species,methods in results.items()})
    (HERE/'evidence-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
    tables=[]
    def line(s=''):tables.append(s)
    line('% Generated only from preserved M3.5.1 numerical results.')
    line(r'\newcommand{\CandidateTable}{%')
    line(r'\begin{tabular}{llrrrl}\toprule Species & Model & $K$ & Sizes & Silhouette & Subsample ARI\\\midrule')
    for species,method,k in [('Hatterene','learned',1),('Hatterene','learned',2),('Incineroar','sp',3),('Incineroar','learned',1),('Incineroar','learned',2),('Incineroar','learned',3),('Mega Raichu Y','sp',1),('Mega Raichu Y','learned',2)]:
        c=summaries[species]['models'][method]['candidates'][k-1]
        sil='---' if c['silhouette'] is None else f"{c['silhouette']:.3f}"
        line(f"{species} & {tex(method)} & {k} & {'/'.join(map(str,c['sizes']))} & {sil} & {'/'.join(f'{a:.3f}' for a in c['resample_ari'])}"+r'\\')
    line(r'\bottomrule\end{tabular}}')
    line(r'\newcommand{\HoldoutTable}{%')
    line(r'\begin{tabular}{llrrrrr}\toprule Species & Model & Speed & Attack & Sp. Atk & Bulk & Item error\\\midrule')
    for species,methods in heldout['summaries'].items():
        baseline=methods['sp']
        values=[baseline[t]['baseline_loss'] for t in ('speed','attack','special_attack','bulk','item')]
        line(species+r' & Train baseline & '+' & '.join(f'{v:.3f}' for v in values)+r'\\')
        for method in ('sp','jaccard','learned','item-nature'):
            line(species+' & '+tex(method)+' & '+' & '.join(f"{methods[method][t]['loss']:.3f}" for t in ('speed','attack','special_attack','bulk','item'))+r'\\')
        line(r'\addlinespace')
    line(r'\bottomrule\end{tabular}}')
    line(r'\newcommand{\CrossTable}{%')
    line(r'\begin{tabular}{lrrrr}\toprule & Learned 0 & Learned 1 & Learned 2 & Total\\\midrule')
    for i,row in enumerate(cross):line(f'SP-only {i} & '+' & '.join(map(str,row))+f' & {sum(row)}'+r'\\')
    line(r'\midrule Total & '+' & '.join(map(str,cross.sum(0)))+r' & 197\\\bottomrule\end{tabular}}')
    line(r'\newcommand{\SensitivityTable}{%')
    line(r'\begin{tabular}{lrrr}\toprule Configuration & Hatterene & Incineroar & Raichu Y\\\midrule')
    for method in selection['Incineroar']:
        line(tex(method)+' & '+' & '.join(str(selection[s][method]) for s in ('Hatterene','Incineroar','Mega Raichu Y'))+r'\\')
    line(r'\bottomrule\end{tabular}}')
    (HERE/'results_tables.tex').write_text('\n'.join(tables)+'\n')
    print('Prepared',len(provenance),'figures; no numerical study output changed.')


if __name__=='__main__':main()
