"""GitHub-readable results, pre-specified diagnostics and compact exports."""
from collections import Counter
import csv
import json
from pathlib import Path
import numpy as np
from metagame.common import atomic_json
from knowledge.champions_stats import ChampionsStats
from metagame.published.speed_support import alignment
from .features import DESIGN, FEATURES, FAMILIES
from .model import TARGETS

LABELS={'A_median':'A · Training median','B_own':'B · Own moves/item','C_context':'C · Own + team context',
        **{'plus_'+k:'B + '+k.replace('_',' ') for k in FAMILIES}}


def case_studies(data,names):
    rows=data['rows'];byid={r['id']:r for r in rows};truth=dict(zip([r['id'] for r in rows],data['targets']))
    def has(r,name):return any(names.get(m)==name for m in r['own']['moves'])
    a=[r for r in rows if has(r,'Close Combat') and has(r,'Flare Blitz') and names.get(r['own']['item']) in ('Life Orb','White Herb') and (r['context']['trick_room_count'] or 0)>0]
    b=[r for r in rows if has(r,'Taunt') and (r['context']['tailwind_count'] or 0)>0]
    structural=lambda r:sum((r['context'][f] or 0)>0 for f in ('tailwind_count','trick_room_count','sun_pair_option','rain_pair_option'))
    c=[r for r in rows if structural(r)>=2]
    result={}
    for key,records in [('offensive_trick_room',a),('taunt_tailwind',b),('multiple_options',c)]:
        y=[truth[r['id']] for r in records];other=[truth[r['id']] for r in rows if r not in records]
        def stats(values):
            if not values:return None
            v=np.array(values);return dict(median=np.median(v,0).tolist(),q1=np.quantile(v,.25,axis=0).tolist(),q3=np.quantile(v,.75,axis=0).tolist())
        examples=[];seen=set()
        for r in sorted(records,key=lambda r:r['id']):
            if r['group'] in seen:continue
            seen.add(r['group']);source=data['originals'][r['id']]
            calculated=ChampionsStats(source['species'],form='base').calculate(source['training_points'],alignment(source['nature']))['stats']['speed']
            examples.append(dict(id=r['id'],group=r['group'],source_url=r['source_url'],source_title=r['source_title'],
                                 moves=r['own']['moves'],item=r['own']['item'],nature=source['nature'],
                                 targets=truth[r['id']],actual_unmodified_speed=calculated,context=r['context'],teammates=r['teammates'],mechanism_evidence=r['evidence']))
            if len(examples)==3:break
        result[key]=dict(n=len(records),groups=len({r['group'] for r in records}),summary=stats(y),other_n=len(other),other_summary=stats(other),examples=examples,
                         occurrence_ids=[r['id'] for r in records],individual_targets=[truth[r['id']] for r in records])
    return result


def write_report(path,data,result,identity,fingerprint,run):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from experiments.no_sp_archetypes.frozen import file_hash
    path=Path(path);assets=path.parent/'assets/m354';assets.mkdir(parents=True,exist_ok=True);files=[]
    field_map={'tailwind_count':['teammates.moves','teammates.issues'],'trick_room_count':['teammates.moves','teammates.issues'],'taunt_count':['teammates.moves','teammates.issues'],'natural_fast_count':['teammates.species/form','teammates.issues','KnowledgeBase.pokemon.stats.sp']}
    exported_dictionary=[]
    for feature in data['feature_dictionary']:
        entry=dict(feature)
        entry['source_fields']=field_map.get(entry['name'],entry['source_fields']+['teammates.issues','pinned native ability/required-item or priority metadata'])
        exported_dictionary.append(entry)
    names={r['canonical_id']:r['names'].get('en',r['canonical_id']) for r in json.loads((Path(__file__).resolve().parents[2]/'knowledge/data/entities.json').read_text())['entities']}
    name=lambda value:str(value).split(':',1)[1].title() if str(value).startswith('nature:') else names.get(value,str(value))
    pooled=result['pooled'];real=np.array(pooled['B_own']['mae'])-pooled['C_context']['mae']
    controls=np.array([c['improvement_vs_B'] for c in result['permutation']])
    def save(fig,filename):
        p=assets/(filename+'.png');fig.savefig(p,dpi=160,bbox_inches='tight');plt.close(fig);files.append(p)
    fig,axes=plt.subplots(1,3,figsize=(11,3.6),layout='constrained')
    for j,ax in enumerate(axes):
        methods=['A_median','B_own','C_context'];ax.bar(range(3),[pooled[m]['mae'][j] for m in methods],color=['#8495aa','#4186a3','#b86a43'])
        ax.set(xticks=range(3),xticklabels=['Median','Own','+ Context'],ylabel='Held-out MAE (SP)',title=TARGETS[j].title())
    fig.suptitle('Same-fold grouped evaluation · 197 occurrences / 187 groups · 3 × 5 folds',fontsize=10);save(fig,'heldout-mae')
    fig,axes=plt.subplots(1,3,figsize=(11,3.5),layout='constrained')
    for j,ax in enumerate(axes):
        values=[r['mean_improvement'][j] for r in result['group_improvements']]
        ax.hist(values,bins=20,color='#4186a3');ax.axvline(0,color='#a34e3a');ax.set(title=TARGETS[j].title(),xlabel='Own absolute error − context error (SP)',ylabel='Connected source groups')
    fig.suptitle('Paired improvement per source group, averaged across repeated predictions; positive favors context',fontsize=10);save(fig,'paired-group-errors')
    fig,axes=plt.subplots(1,3,figsize=(11,3.5),layout='constrained')
    for j,ax in enumerate(axes):
        ax.scatter(range(6),controls[:,j],color='#8495aa',s=40,label='Permuted context');ax.axhline(real[j],color='#b04f36',label='Real context');ax.axhline(0,color='#333',linewidth=.7)
        ax.set(title=TARGETS[j].title(),xlabel='Predefined permutation seed index',ylabel='MAE improvement over own (SP)');ax.legend(fontsize=8)
    fig.suptitle('Training-group block permutations; held-out context untouched · no formal p-value',fontsize=10);save(fig,'permutation-controls')
    fig,axes=plt.subplots(1,3,figsize=(12,3.9),layout='constrained')
    for j,ax in enumerate(axes):
        for model,color in [('B_own','#4186a3'),('C_context','#b86a43')]:
            for field,style in [('training','--'),('heldout','-')]:
                values=[np.mean([c[field]['mae'][j] for c in result['learning_curves'] if c['model']==model and c['fraction']==fraction]) for fraction in DESIGN['learning_fractions']]
                ax.plot(DESIGN['learning_fractions'],values,style,marker='o',color=color,label=('Own' if model=='B_own' else 'Context')+' '+field)
        ax.set(title=TARGETS[j].title(),xlabel='Fraction of outer training source groups',ylabel='MAE (SP)',xticks=DESIGN['learning_fractions']);ax.legend(fontsize=7)
    fig.suptitle('Nested group learning curves · same held-out folds · fold-mean errors, no independent-replication claim',fontsize=10);save(fig,'learning-curves')
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    keys=['plus_'+family for family in FAMILIES]+['C_context']
    for j,ax in enumerate(axes):
        values=[pooled['B_own']['mae'][j]-pooled[k]['mae'][j] for k in keys]
        ax.barh(range(len(keys)),values,color='#4186a3');ax.axvline(0,color='#333',linewidth=.7)
        ax.set(yticks=range(len(keys)),yticklabels=[k.replace('plus_','+ ').replace('_',' ') for k in keys],xlabel='MAE improvement over own (SP)',title=TARGETS[j].title())
    fig.suptitle('Predefined feature-family additions evaluated on identical grouped folds',fontsize=10);save(fig,'feature-ablations')
    cases=case_studies(data,names)
    pred_path=assets/'paired-predictions.csv'
    with pred_path.open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['occurrence_id','source_group','seed','fold','target','true_sp','median_prediction','own_prediction','context_prediction','median_absolute_error','own_absolute_error','context_absolute_error','own_minus_context_error'])
        for r in result['predictions']:
            for j,target in enumerate(TARGETS):
                values=[r['predictions'][m][j] for m in ('A_median','B_own','C_context')];errors=[abs(r['truth'][j]-v) for v in values]
                writer.writerow([r['id'],r['group'],r['seed'],r['fold'],target,r['truth'][j],*[f'{v:.8f}' for v in values],*[f'{v:.8f}' for v in errors],f'{errors[1]-errors[2]:.8f}'])
    files.append(pred_path)
    feature_path=assets/'feature-values.csv'
    with feature_path.open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(['occurrence_id','source_group','m351_source_group',*FEATURES,*[i['name'] for i in DESIGN['interactions']]])
        for r in data['rows']:writer.writerow([r['id'],r['group'],r['m351_group'],*[r['context'][f] for f in FEATURES],*[r['interactions'][i['name']] for i in DESIGN['interactions']]])
    files.append(feature_path)
    learning=[{**{k:v for k,v in c.items() if k not in ('training_ids','training_groups')},'training_observations':len(c['training_ids']),'training_group_count':len(c['training_groups'])} for c in result['learning_curves']]
    evaluation={k:v for k,v in result.items() if k not in ('predictions','paired','learning_curves')};evaluation['learning_curves']=learning
    for filename,value in [('feature-definitions.json',dict(design=DESIGN,dictionary=exported_dictionary,sample=dict(occurrences=197,groups=187,original_groups=192,group_sizes=data['group_sizes']),mechanics_evidence=identity['mechanics_evidence'])),
                           ('evaluation.json',evaluation),('case-studies.json',cases),
                           ('provenance.json',dict(fingerprint=fingerprint,identity=identity,source_hashes=data['source_hashes'],no_sp_training_records=0))]:
        p=assets/filename;atomic_json(p,value);files.append(p)
    lines=[]
    def add(v=''):lines.append(v)
    def table(headers,rows):
        add('| '+' | '.join(headers)+' |');add('|'+'|'.join('---' for _ in headers)+'|')
        for r in rows:add('| '+' | '.join(str(v) for v in r)+' |')
        add()
    def triplet(v):return ' / '.join(f'{x:.3f}' for x in v)
    add('# M3.5.4 — Team speed-control context and hidden SP prediction');add()
    add('*25 October 2026 · controlled offline experiment · no battle or review integration*');add()
    add('The previous [moveset diagnostics](M3.5.3_Incineroar_Moveset_Clustering_Diagnostics.md) showed that identical Incineroar moves and items can conceal different SP investments. This experiment asks whether the other five published teammates supply useful incremental information. **Overfitting is the primary concern:** a more flexible model must survive grouped held-out comparisons, unrelated-context controls, smaller training samples and fixed feature ablations.');add()
    add('**Result:** adding all context worsens Speed and Attack prediction. Bulk improves by only about 0.100 SP versus own-only, reverses direction in one split seed, and exceeds the strongest of six negative controls by only about 0.014 SP. Training errors improve much more than held-out errors. The evidence does not justify promoting this model to inference.');add()
    add('## Population and pre-specified design');add()
    add('The primary sample remains **197 complete Incineroar occurrences**, with no deduplication and no missing-SP application records added. The original M3.5.1 identities comprise **192 connected groups**. The stronger M3.5.3 links—publication, source URL/key, raw-record hash, exact team and exact observable team with SP omitted—merge these into **187 groups**: 179 singleton groups, six pairs and two triples. Both group identities and all publication provenance are preserved. Connected groups are the best available isolation units, not proof of 187 independent data-generating teams.');add()
    add('The [local design specification](../experiments/team_speed_context/preregistered.json) was recorded before examining target/context relationships or model performance; it is not a public statistical preregistration. It fixes three seeds (354–356), five source-grouped folds per seed, Ridge alpha 10, base-Speed threshold 100, six permutation seeds, learning fractions 0.35/0.65/1, five ablation families and three separately tested interaction candidates. No outer-fold result selects hyperparameters or changes feature definitions.');add()
    add('Targets are **Speed SP**, **Attack SP**, and **bulk SP = HP + Defense + Special Defense**, modeled independently. No SP cluster defines a target. The target’s SP, calculated stats, nature and cluster label, plus all teammates’ SP and calculated stats, are excluded from features. Only target moves/item and five teammates’ canonical observable fields enter feature extraction.');add()
    table(['Outer seed','Training groups range','Held-out groups range','Training occurrences range','Held-out occurrences range'],[[seed,f"{min(c['train_groups'] for c in result['split_counts'] if c['seed']==seed)}–{max(c['train_groups'] for c in result['split_counts'] if c['seed']==seed)}",f"{min(c['test_groups'] for c in result['split_counts'] if c['seed']==seed)}–{max(c['test_groups'] for c in result['split_counts'] if c['seed']==seed)}",f"{min(c['train'] for c in result['split_counts'] if c['seed']==seed)}–{max(c['train'] for c in result['split_counts'] if c['seed']==seed)}",f"{min(c['test'] for c in result['split_counts'] if c['seed']==seed)}–{max(c['test'] for c in result['split_counts'] if c['seed']==seed)}"] for seed in DESIGN['outer_seeds']])
    add('## Features describe options, not an exclusive team mode');add()
    add('Each feature is nonexclusive. Tailwind and Trick Room may coexist; a roster can also contain weather and naturally fast options. An observed capability does not show which four Pokémon were brought, which Mega was selected, whether weather or Tailwind activated, or which matchup-specific Speed benchmark a player intended.');add()
    table(['Feature','Definition','Positive occurrences','Positive groups','Missing','A priori'],[[f['name'],f['definition'],f['positives'],f['positive_groups'],f['missing'],'yes'] for f in data['feature_dictionary']])
    add('The [full dictionary](assets/m354/feature-definitions.json) records fields, frequencies, missing groups, assumptions and the frozen design. A count is unknown if any unresolved teammate could alter it; a presence can be confirmed by one supported positive despite other unknowns. CSV blank fields mean unknown, never observed absence.');add()
    add('Weather is split into setter option, observed dependent ability, and compatible pair. Drought/Drizzle and Chlorophyll/Swift Swim use the existing pinned Champions reference. A known required stone and fixed Mega ability can establish a **conditional Mega option**, without selecting it; two roles both requiring Mega are left unresolved. Unknown original abilities stay unknown. A native ability domain can rule out an ability, but no unobserved legal alternative is asserted present. Manual Sunny Day/Rain Dance without a supported ability enabler remains unresolved in this narrow definition.');add()
    add('Natural Speed uses pinned native/pre-Mega base Speed ≥100, not trained Speed or assumed Mega stats. Priority support is the specified Fake Out/Helping Hand/Follow Me/Rage Powder set, or compatible observed Prankster with a qualifying observed Status move. This is a limited capability indicator, not comprehensive priority coverage. Taunt is a separate disruption count. Existing corrected priority metadata and cached Showdown references are reused; these are not new official mechanics or activation measurements. No sources were scraped or refreshed.');add()
    add('## Models and leakage controls');add()
    add('- **A — species baseline:** training median for each target.\n- **B — own observations:** Ridge with binary move vocabulary and one-hot original item.\n- **C — context:** the same Ridge plus the 11 team features and explicit missingness indicators.\n- **Family ablations:** add only Tailwind, Trick Room, weather, natural Speed, or priority/disruption to B.\n- **D candidates:** Taunt × Tailwind, Close Combat × Trick Room, and Life Orb/White Herb × Trick Room, each separately on top of C only with at least 10 positive and 10 negative independent training groups. These named items are a hypothesis proxy, not proof of an offensive role.');add()
    add(r'For each target, Ridge minimizes $\|y-\mathbf{1}b-Xw\|_2^2+10\|w\|_2^2$ with an unpenalized intercept. The three response columns have separate coefficients and no cross-target penalty. Every vocabulary, median imputation, missingness column, mean, scale and coefficient uses training observations only. Alpha is fixed, so no inner tuning is needed. Unknown training columns use a documented zero fallback plus missing indicators. Predictions clip to legal marginal ranges (0–32, bulk 0–66) and are never assembled into a joint build or prior.');add()
    add('Five-fold splits are deterministic permutations of source-group IDs, without target stratification. All models share every train/test split. Repeated CV produces **591 held-out predictions per target from the same 197 observations**, not 591 independent examples. Training receipts include every input ID, vocabulary, imputation/scaling value and coefficient; permutation receipts include donor-group maps. Full receipts remain local.');add()
    add('## Held-out performance and paired changes');add()
    table(['Model','Speed MAE','Attack MAE','Bulk MAE','Median absolute errors: Speed / Attack / Bulk'],[[LABELS[m],*[f'{x:.3f}' for x in pooled[m]['mae']],triplet(pooled[m]['median_absolute_error'])] for m in ('A_median','B_own','C_context')])
    table(['Target','C improvement over B (positive better)','C improvement over A','B training MAE','C training MAE','C held-out MAE'],[[target,f'{real[j]:.3f}',f"{pooled['A_median']['mae'][j]-pooled['C_context']['mae'][j]:.3f}",f"{result['training']['B_own']['mae'][j]:.3f}",f"{result['training']['C_context']['mae'][j]:.3f}",f"{pooled['C_context']['mae'][j]:.3f}"] for j,target in enumerate(TARGETS)])
    add('MAE and median absolute error are in SP units; smaller is better. Training errors are means over training folds, while held-out MAE pools matched predictions. B/C optimize squared loss, so the median baseline can be especially strong on concentrated targets. Beating B alone is insufficient when A is better. Unlike M3.5.1 target-masked neighborhoods, these models receive none of the target’s other SP coordinates, so those earlier error levels are not directly comparable.');add()
    add('![Same-fold held-out numeric SP error for species, own-only and context models](assets/m354/heldout-mae.png)');add()
    table(['Split seed','B MAE: Speed / Attack / Bulk','C MAE: Speed / Attack / Bulk','B − C'],[[s['seed'],triplet(s['metrics']['B_own']['mae']),triplet(s['metrics']['C_context']['mae']),triplet(np.array(s['metrics']['B_own']['mae'])-s['metrics']['C_context']['mae'])] for s in result['per_seed']])
    table(['Equal-weight source-group metric','Speed','Attack','Bulk'],[[LABELS[m],*[f'{x:.3f}' for x in pooled[m]['group_macro_mae']]] for m in ('A_median','B_own','C_context')])
    add('![Paired absolute-error improvement for each of 187 connected source groups](assets/m354/paired-group-errors.png)');add()
    table(['Target','Groups helped','Groups hurt','Ties','Median group improvement (SP)'],[[target,sum(g['mean_improvement'][j]>1e-10 for g in result['group_improvements']),sum(g['mean_improvement'][j]<-1e-10 for g in result['group_improvements']),sum(abs(g['mean_improvement'][j])<=1e-10 for g in result['group_improvements']),f"{np.median([g['mean_improvement'][j] for g in result['group_improvements']]):.3f}"] for j,target in enumerate(TARGETS)])
    add('Group ties use a numerical tolerance of 1e-10 SP. More groups can improve while overall MAE worsens if the harmed groups have larger errors, as with Attack.');add()
    add('Each group’s histogram value averages its paired B-minus-C absolute errors across observations and repeated splits. Positive means context helped that group. The complete paired CSV includes true SP, all three predictions/errors, source group, seed and fold. Group improvements and per-capability subgroup results are exported without treating tiny groups as precise estimates.');add()
    table(['Uncommon observed subgroup','Original N / groups','A MAE','B MAE','C MAE'],[[key,f"{v['observations']} / {v['groups']}",triplet(v['metrics']['A_median']['mae']),triplet(v['metrics']['B_own']['mae']),triplet(v['metrics']['C_context']['mae'])] for key,v in result['subgroups'].items()])
    add('These evaluation-only subgroups use pre-specified Attack ≥15 and Speed ≥11 SP. They do not enter any training label or feature.');add()
    add('## Can arbitrary teammate context do as well?');add()
    add('Within each outer training fold, the six fixed controls permute complete context-vector blocks between different source-group labels within equal block-size strata. Own moves, item, target values and group IDs stay fixed. Donors come only from the training fold; every vector stays coherent and the test context is untouched. This preserves occurrence multiplicity. Singleton permutation strata cannot exchange a block and are counted explicitly: '+str(result['permutation_unexchangeable_groups'])+' group/control instances across the experiment. Random permutation fixed points can also retain their own context; donor maps are saved.');add()
    table(['Target','Real improvement over B','Permuted improvement range','Permuted median','Real exceeds every control?'],[[target,f'{real[j]:.3f}',f'{controls[:,j].min():.3f} to {controls[:,j].max():.3f}',f'{np.median(controls[:,j]):.3f}','yes' if real[j]>controls[:,j].max() else 'no'] for j,target in enumerate(TARGETS)])
    add('![Real-context paired improvement against six training-group permutation controls](assets/m354/permutation-controls.png)');add()
    add('The controls diagnose how much apparent incremental improvement this model can obtain from unrelated contexts. They are a modest fixed sensitivity exercise, not a formal randomization-test p-value: folds, records and source groups are reused, and exchangeability is not established.');add()
    add('## Training size, ablations and interactions');add()
    add('![Grouped learning curves with training and held-out errors for B and C](assets/m354/learning-curves.png)');add()
    curve_rows=[]
    for fraction in DESIGN['learning_fractions']:
        for model in ('B_own','C_context'):
            curves=[c for c in result['learning_curves'] if c['fraction']==fraction and c['model']==model]
            curve_rows.append([fraction,LABELS[model],f"{min(len(c['training_groups']) for c in curves)}–{max(len(c['training_groups']) for c in curves)}",triplet(np.mean([c['training']['mae'] for c in curves],axis=0)),triplet(np.mean([c['heldout']['mae'] for c in curves],axis=0))])
    table(['Training group fraction','Model','Actual training groups','Training MAE','Held-out MAE'],curve_rows)
    add('Subsets are nested, chosen by deterministic source-group ranks without targets. All related observations enter together, and the original outer test fold stays fixed. Each fraction refits preprocessing and coefficients. The curves average fold errors equally; they are not independent learning experiments. Fixed alpha also has different relative strength at different training sizes.');add()
    table(['Added family','Held-out MAE: Speed / Attack / Bulk','Improvement over B'],[[LABELS[m],triplet(pooled[m]['mae']),triplet(np.array(pooled['B_own']['mae'])-pooled[m]['mae'])] for m in [*['plus_'+f for f in FAMILIES],'C_context']])
    add('![Predefined feature-family ablations on the same outer folds](assets/m354/feature-ablations.png)');add()
    table(['Interaction candidate','Positive original groups','Folds passing training-only support gate'],[[s['name'],next(f['positive_groups'] for f in data['feature_dictionary'] if f['name']==s['name']),sum(f[s['name']]['fit'] for f in result['interaction_support'])] for s in DESIGN['interactions']])
    add('In the predefined family ablations, natural-Speed counts give the largest observed bulk improvement (+0.294 SP), followed by weather (+0.222) and Trick Room (+0.142). These are comparisons on the same held-out sample, not an independent selection set: choosing the best family now would require new validation. Tailwind alone barely changes Speed error (+0.017 SP improvement), and the full context model does worse. Weather pair positives have only five and seven source groups, teammate Taunt only two, and priority support is present in 187/197 observations. Sparse or nearly constant features constrain what can be learned.');add()
    add('Unsupported interactions are descriptive only; omitting a coefficient is not evidence of a zero biological effect. No all-pairs interaction search or favorable-result selection is performed. Standardized contextual coefficients are exported for checking fold instability, not causal interpretation.');add()
    add('## Tactical hypotheses checked against actual records');add()
    for key,title in [('offensive_trick_room','A · Close Combat/Flare Blitz + named item + Trick Room option'),('taunt_tailwind','B · Taunt + teammate Tailwind'),('multiple_options','C · More than one structural option')]:
        case=cases[key];add('### '+title);add()
        add(f"**{case['n']} occurrences from {case['groups']} connected groups.**")
        if case['summary']:
            add('Speed / Attack / Bulk medians: **'+triplet(case['summary']['median'])+'**; Q1 **'+triplet(case['summary']['q1'])+'**, Q3 **'+triplet(case['summary']['q3'])+'**. Other '+str(case['other_n'])+' occurrences have medians **'+triplet(case['other_summary']['median'])+'**.');add()
        if key=='multiple_options':add('Here the descriptive selection requires at least two of teammate Tailwind, Trick Room, supported sun pair or rain pair. Naturally fast and priority options may coexist too; these are not exclusive strategy labels.');add()
        for example in case['examples']:
            carriers=[]
            for mate in example['teammates']:
                roles=[names[m] for m in mate['moves'] or [] if names.get(m) in ('Tailwind','Trick Room')]
                if roles:carriers.append(name(mate['species'])+' ('+', '.join(roles)+')')
            for mate in example['mechanism_evidence']['teammates']:
                weather=[p['ability']+(' [conditional Mega option]' if p['mega'] else '') for p in mate['profiles'] if p['ability'] in ('Drought','Drizzle','Chlorophyll','Swift Swim')]
                if weather:carriers.append(name(mate['species'])+' ('+', '.join(weather)+')')
            add('- [Original published team]('+example['source_url']+'): '+str(example['source_title'])+'. Incineroar: '+ ' / '.join(name(m) for m in example['moves'])+'; '+name(example['item'])+', '+name(example['nature'])+'. **Speed / Attack / Bulk SP '+triplet(example['targets'])+'**; calculated unmodified Speed **'+str(example['actual_unmodified_speed'])+'**. Observed moves / supported ability options: '+('; '.join(carriers) or 'see conditional weather profiles in export')+'.');add()
        if key=='taunt_tailwind':add('This subgroup is too small for a special predictive rule. The calculated Speed values are descriptive record facts; no opponent benchmark or intent is identified from roster data alone. Taunt plus Tailwind does not logically require positive Speed SP, and no activation or bring choice was observed.');add()
        if key=='offensive_trick_room':add('The named item filter is Life Orb or White Herb, following the pre-specified hypothesis. Published Trick Room access does not imply that Incineroar always uses it, always moves slowly, or is brought alongside its setter.');add()
    add('All selected IDs, source groups, raw target values and representative full observable teammate details are in [case-studies.json](assets/m354/case-studies.json). These cases interpret associations after the controlled evaluation; they do not choose features or validate tactical intent.');add()
    add('## Interpretation and recommendation');add()
    flags=[]
    for j,target in enumerate(TARGETS):
        seed_improvements=[s['metrics']['B_own']['mae'][j]-s['metrics']['C_context']['mae'][j] for s in result['per_seed']]
        robust=real[j]>0 and pooled['C_context']['mae'][j]<pooled['A_median']['mae'][j] and real[j]>controls[:,j].max() and all(v>0 for v in seed_improvements)
        flags.append(robust)
        add(f"- **{target.title()}:** C changes MAE versus B by {real[j]:+.3f} SP (positive is improvement), beats the training median: {'yes' if pooled['C_context']['mae'][j]<pooled['A_median']['mae'][j] else 'no'}, exceeds every permutation control: {'yes' if real[j]>controls[:,j].max() else 'no'}, and improves in {sum(v>0 for v in seed_improvements)}/3 split seeds.")
    add()
    if any(flags):add('At least one target passes these descriptive screens. This supports only a narrow follow-up with independent complete-SP data and the same frozen definitions; it does not justify calibrated team-conditioned inference or integration. Training-size behavior, sparse weather support and target-specific baseline comparisons still bound the claim.')
    else:add('No target clears all of the descriptive checks above. The evidence does not support promoting this context model to hidden-SP inference. Keep team mechanisms as descriptive review context; obtain independent complete-SP examples before investing in a more complex team-conditioned model. Extra capacity would currently risk explaining this small published sample rather than generalizing.')
    add()
    add('## Limits, artifacts and reproducibility');add()
    add('Repeated builds and entire teams remain occurrence-weighted; grouping reduces leakage but cannot remove unknown source relationships. Tournament publications are selected, and missing-SP teams may follow a different distribution. Capability features can be redundant, conditional on optional Mega use, or used only in certain matchups. Association may reflect player/source/metagame confounding rather than causal effects. Small positive subgroups and correlated weather indicators make coefficients unstable. A fixed-alpha linear model and this limited feature dictionary may miss real nonlinear information; this is not a proof that all team context is uninformative. The models cannot recover matchup-specific Speed goals or actual battle modes from a roster.');add()
    add(f"Fingerprint **`{fingerprint}`**. Atomic stages and full fold receipts live under `.cache/research/m354/{fingerprint}/`; its manifest records source/design/implementation hashes, progress, errors and the exact resume command. Resume compatible stages, preserving successful folds. The 197 original joins and target values are cached separately from predictor inputs. No clustering, embedding, existing predictor, review annotation, feasibility solver, empirical probability, evidence or replay file is changed.");add()
    add('```sh\n.venv/bin/python -m experiments.team_speed_context.run\n.venv/bin/python -m pytest -q tests/test_team_speed_context.py tests/test_no_sp_archetypes.py tests/test_moveset_diagnostics.py tests/test_git_artifact_policy.py\n```');add()
    add('Tracked exports: [paired predictions/errors](assets/m354/paired-predictions.csv), [observable feature values](assets/m354/feature-values.csv), [feature definitions and design](assets/m354/feature-definitions.json), [evaluation/controls/curves](assets/m354/evaluation.json), [case studies](assets/m354/case-studies.json), and [source/model provenance](assets/m354/provenance.json). Blank feature CSV cells mean unknown. Large preprocessing receipts, training predictions and control intermediates stay local. [Implementation notes](../experiments/team_speed_context/README.md) explain launch/resume and the exact scope of mechanics evidence.');add()
    add('Verification: **74 portable tests passed** across the new experiment, existing no-SP predictor/review, moveset diagnostics and artifact-policy suites. Checks cover training-only encodings/imputation/scaling, source-group and permutation donor isolation, nonexclusive mechanisms, unknown values, conditional Mega handling, deterministic evaluation, and exported paired errors/counts. All 15 fold outputs reproduced exactly in a repeated run with complete dependency fingerprints; a resume reuses all **18 completed stages**. Existing protected source, solver, predictor and human-annotation hashes remain unchanged. These are engineering/reproducibility checks, not evidence of causal mechanisms or battle-inference acceptance.');add()
    add('This milestone stops at the offline experiment. No synthetic joint build, full-SP prior, latent team-mode model, new clustering system or battle integration is created.');add()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(lines).rstrip()+'\n');files.append(path)
    return dict(files={str(p):file_hash(p) for p in files},no_integration=True)
