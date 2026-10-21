"""Configuration-level log weights, deterministic normalization and evidence ledger."""
from copy import deepcopy
from collections import Counter
import math
from .domains import digest,encoded,configuration_space
from .likelihood import admission,likelihoods
from .policy import SOURCE_POLICY
from speed_order.core import PROFILES,provenance as order_provenance


def logsumexp(values):
    values=[v for v in values if math.isfinite(v)]
    if not values:return -math.inf
    peak=max(values)
    return peak+math.log(math.fsum(math.exp(v-peak) for v in values))


class SpeedBelief:
    def __init__(self,model,*,battle_id,instance_id,stat_epoch,profile='champions-evidence-only-v1',credible_mass=.95):
        if not all(isinstance(v,str) and v for v in (battle_id,instance_id,stat_epoch)):raise ValueError('Explicit battle/individual/stat epoch required')
        if profile not in PROFILES:raise ValueError('Unknown ordering profile')
        if type(credible_mass) not in (float,int) or not 0<credible_mass<1:raise ValueError('Credible mass must be in (0,1)')
        m=deepcopy(model);fingerprint=m.pop('fingerprint',None)
        if fingerprint!=digest(m):raise ValueError('Configuration space fingerprint mismatch')
        m['fingerprint']=fingerprint
        if not m['candidates']:raise ValueError('Empty candidate model')
        if configuration_space(**m['specification'])['fingerprint']!=fingerprint:
            raise ValueError('Candidate model is not reproducible under maintained legal stat rules')
        self.model=m;self.key=(battle_id,instance_id,stat_epoch);self.profile=profile;self.credible_mass=float(credible_mass)
        self.log_weights=[-math.log(len(m['candidates']))]*len(m['candidates'])
        self.history=[];self.seen={};self.decisions=set();self.actions=set();self.contradiction=None
        self.log_evidence=0.;self.initial=self.summary()

    def summary(self,*,include_configurations=True):
        groups={}
        for row,weight in zip(self.model['candidates'],self.log_weights):
            if math.isfinite(weight):groups.setdefault(row['unmodified_speed'],[]).append(weight)
        marginal=[]
        for value,weights in sorted(groups.items()):
            lp=logsumexp(weights);p=math.exp(lp)
            marginal.append(dict(speed=value,probability=p,log_probability=lp,display_underflow=p==0.,configuration_support=len(weights)))
        mean=math.fsum(r['speed']*r['probability'] for r in marginal)
        peak=max((r['log_probability'] for r in marginal),default=-math.inf)
        modes=[r['speed'] for r in marginal if abs(r['log_probability']-peak)<=1e-12]
        def quantile(q):
            cumulative=0.
            for row in marginal:
                cumulative+=row['probability']
                if cumulative>=q:return row['speed']
            return marginal[-1]['speed'] if marginal else None
        tail=(1-self.credible_mass)/2
        result=dict(belief_key=list(self.key),identity=self.model['identity'],profile=self.profile,
            status='contradiction' if self.contradiction else 'posterior' if self.decisions else 'prior_only',
            marginal_speed=marginal,support=[r['speed'] for r in marginal],mean=mean,
            map_speed=min(modes) if modes else None,map_speeds=modes,map_tolerance=1e-12,
            credible_interval=dict(kind='discrete_equal_tailed',mass=self.credible_mass,lower=quantile(tail),upper=quantile(1-tail),
                interpretation='Conditional Bayesian interval under the declared non-empirical model; not a recognition-accuracy or sampling guarantee'),
            probability_sum=math.fsum(r['probability'] for r in marginal),configuration_support=sum(math.isfinite(w) for w in self.log_weights),
            log_evidence=self.log_evidence,contradiction=deepcopy(self.contradiction),
            posterior_defined=self.contradiction is None,
            distribution_scope='last_consistent_weights_for_diagnosis_only' if self.contradiction else 'current_conditional_distribution',
            numerical_policy='Finite log weights retain positive support even if displayed exp(log_weight) underflows',
            information_gain_nats=self._speed_gain(marginal) if self.decisions else 0.,
            configuration_information_gain_nats=self._information_gain() if self.decisions else 0.,
            empirical_prior_used=False,model_fingerprint=self.model['fingerprint'])
        if include_configurations:
            result['configurations']=[dict(configuration=deepcopy(c),log_probability=w if math.isfinite(w) else None,
                probability=math.exp(w) if math.isfinite(w) else 0.,positive_support=math.isfinite(w)) for c,w in zip(self.model['candidates'],self.log_weights)]
        return result

    def _information_gain(self):
        log_prior=-math.log(len(self.log_weights))
        return max(0.,math.fsum(math.exp(w)*(w-log_prior) for w in self.log_weights if math.isfinite(w)))

    def _speed_gain(self,marginal):
        prior=Counter(c['unmodified_speed'] for c in self.model['candidates']);n=len(self.log_weights)
        return max(0.,math.fsum(r['probability']*(r['log_probability']-math.log(prior[r['speed']]/n)) for r in marginal))

    def update(self,observation):
        o=deepcopy(observation)
        if not isinstance(o,dict) or not isinstance(o.get('id'),str) or not o['id']:raise ValueError('Observation requires a stable ID')
        # JSON validation rejects NaN/inf and non-reproducible runtime objects.
        fingerprint=digest(o);oid=o['id']
        if oid in self.seen:
            record=dict(id=oid,observation=o,status='duplicate_ignored' if self.seen[oid]==fingerprint else 'evidence_revision_requires_explicit_replay',posterior_unchanged=True)
            self.history.append(record);return deepcopy(record)
        self.seen[oid]=fingerprint
        before=self.summary(include_configurations=False)
        reasons=admission(o,self.key,self.model['identity'])
        decision=None
        if not reasons:
            # Multiple pairwise ranks in one turn can share the same tie draw.
            # Only one pair per individual/turn is admitted, even if relabeled.
            timing=o['context']['timing'];decision=(timing['turn'],)
            if decision in self.decisions:reasons.append('dependent_pair_at_same_ordering_decision_already_used')
            if self.decisions and timing['turn']<max(d[0] for d in self.decisions):reasons.append('out_of_order_observation_requires_explicit_replay')
            if set(o['action_ids'].values())&self.actions:reasons.append('underlying_action_evidence_already_used')
        if self.contradiction:reasons.append('model_evidence_contradiction_is_unresolved; no_reset_or_further_update')
        values=None;details=[]
        if not reasons:
            values,reasons,details=likelihoods(self.model,o,[math.isfinite(w) for w in self.log_weights],self.profile)
        record=dict(id=oid,observation=o,status='ineligible',reasons=reasons,
            before=before,likelihood_details=details,predictive_probability=None,log_predictive_probability=None)
        if values is not None:
            proposed=[w+math.log(p) if p and math.isfinite(w) else -math.inf for w,p in zip(self.log_weights,values)]
            normalizer=logsumexp(proposed)
            if not math.isfinite(normalizer):
                self.contradiction=dict(observation_id=oid,prior_applied_observation_ids=[h['id'] for h in self.history if h['status']=='updated'],
                    reason='Every positive-weight configuration has zero likelihood; posterior is undefined. Last consistent weights retained only for diagnosis.')
                record.update(status='contradiction',predictive_probability=0.,log_predictive_probability=None)
            else:
                self.log_weights=[w-normalizer if math.isfinite(w) else w for w in proposed]
                self.log_evidence+=normalizer;self.decisions.add(decision);self.actions.update(o['action_ids'].values())
                record.update(status='updated',predictive_probability=math.exp(normalizer),log_predictive_probability=normalizer,
                    predictive_display_underflow=math.exp(normalizer)==0.)
        record['after']=self.summary(include_configurations=False)
        if record['status']=='updated':
            record['information_gain_this_step_nats']=self._relative_entropy(before['marginal_speed'])
            record['marginal_changed']=any(abs(a['probability']-b['probability'])>1e-13 for a,b in zip(before['marginal_speed'],record['after']['marginal_speed'])) or before['support']!=record['after']['support']
        else:record['posterior_unchanged']=True
        self.history.append(record)
        return deepcopy(record)

    def _relative_entropy(self,previous):
        old={r['speed']:r['log_probability'] for r in previous}
        return max(0.,math.fsum(r['probability']*(r['log_probability']-old[r['speed']]) for r in self.summary(include_configurations=False)['marginal_speed']))

    def export(self):
        return dict(schema_version=1,model=deepcopy(self.model),belief_key=list(self.key),profile=self.profile,credible_mass=self.credible_mass,
            prior=deepcopy(self.initial),posterior=self.summary(),history=deepcopy(self.history),
            verification='conditional provisional Champions executable reference' if self.profile!='champions-evidence-only-v1' else 'strict evidence profile; numerical updates disabled',
            source_policy=deepcopy(SOURCE_POLICY),ordering_provenance=order_provenance())

    @classmethod
    def restore(cls,value):
        if value.get('schema_version')!=1:raise ValueError('Unsupported belief snapshot schema')
        if value.get('source_policy')!=SOURCE_POLICY:raise ValueError('Ordering source policy changed; explicit review and replay required')
        if value.get('ordering_provenance')!=order_provenance():raise ValueError('Ordering implementation provenance changed; explicit review and replay required')
        b=cls(value['model'],battle_id=value['belief_key'][0],instance_id=value['belief_key'][1],stat_epoch=value['belief_key'][2],
            profile=value['profile'],credible_mass=value['credible_mass'])
        for record in value['history']:b.update(record['observation'])
        if encoded(b.summary())!=encoded(value['posterior']):raise ValueError('Saved posterior does not replay under its recorded model; retain old snapshot and review version/evidence')
        return b


class BeliefBank:
    """One belief per established battle/individual/stat epoch, never per species."""
    def __init__(self):self.beliefs={}

    def register(self,model,**kwargs):
        b=SpeedBelief(model,**kwargs)
        if b.key in self.beliefs:raise ValueError('Belief already exists; never reset a tracked individual')
        self.beliefs[b.key]=b;return b

    def update(self,observation):
        try:key=(observation['battle_id'],observation['context']['opponent']['instance_id'],observation['stat_epoch'])
        except (KeyError,TypeError):return dict(status='ineligible',reasons=['established_individual_identity_missing'])
        if key not in self.beliefs:return dict(status='ineligible',reasons=['individual_not_registered; no_species_based_merge'])
        return self.beliefs[key].update(observation)


def infer(*,model,battle_id,instance_id,stat_epoch,observations,profile='champions-evidence-only-v1',credible_mass=.95):
    if not isinstance(observations,list) or len(observations)>10000:raise ValueError('Supply a bounded chronological observation list')
    if len(model['candidates'])*len(observations)>1000000:raise ValueError('Inference work limit exceeded; split reviewed work into incremental checkpoints')
    belief=SpeedBelief(model,battle_id=battle_id,instance_id=instance_id,stat_epoch=stat_epoch,profile=profile,credible_mass=credible_mass)
    for o in observations:belief.update(o)
    return belief.export()
