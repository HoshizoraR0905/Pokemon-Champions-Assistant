"""Small fixed-alpha Ridge, with exclusively training-fitted preprocessing."""
import numpy as np
from .features import DESIGN, FEATURES

TARGETS=('speed','attack','bulk')
LIMITS=np.array([32.,32.,66.])


class Encoder:
    def __init__(self, context=(), interaction=None):
        self.context=tuple(context);self.interaction=interaction

    def raw(self, rows):
        result=np.zeros((len(rows),len(self.moves)+len(self.items)+len(self.context)+bool(self.interaction)),float)
        for i,row in enumerate(rows):
            for move in set(row['own']['moves']):
                if move in self.moves:result[i,self.moves.index(move)]=1
            item=row['own'].get('item')
            if item in self.items:result[i,len(self.moves)+self.items.index(item)]=1
            start=len(self.moves)+len(self.items)
            for j,name in enumerate(self.context):
                value=row['context'][name];result[i,start+j]=np.nan if value is None else value
            if self.interaction:
                value=row['interactions'][self.interaction];result[i,-1]=np.nan if value is None else value
        return result

    def fit(self, rows):
        if not rows:raise ValueError('Nonempty training records required')
        self.training_ids=[r['id'] for r in rows]
        self.moves=sorted({m for r in rows for m in r['own']['moves']})
        self.items=sorted({r['own']['item'] for r in rows if r['own'].get('item') is not None})
        self.feature_names=['move:'+m for m in self.moves]+['item:'+i for i in self.items]+list(self.context)+([self.interaction] if self.interaction else [])
        raw=self.raw(rows)
        self.fill=np.array([float(np.median(c[np.isfinite(c)])) if np.isfinite(c).any() else 0. for c in raw.T])
        augmented=self.impute(raw)
        self.mean=augmented.mean(0);self.scale=augmented.std(0);self.scale[self.scale<1e-12]=1.
        return self

    def impute(self, raw):
        # Explicit missingness columns for context/interaction only, always
        # present; never turn unknown raw context into observed absence.
        count=len(self.context)+bool(self.interaction)
        missing=np.isnan(raw[:,-count:]).astype(float) if count else np.empty((len(raw),0))
        return np.column_stack([np.where(np.isnan(raw),self.fill,raw),missing])

    def transform(self, rows):return (self.impute(self.raw(rows))-self.mean)/self.scale

    def receipt(self):
        return dict(training_ids=self.training_ids,moves=self.moves,items=self.items,context=list(self.context),interaction=self.interaction,
                    imputation=self.fill.tolist(),mean=self.mean.tolist(),scale=self.scale.tolist(),
                    all_feature_names=self.feature_names+['missing:'+name for name in list(self.context)+([self.interaction] if self.interaction else [])])


class Ridge:
    def __init__(self, context=(), interaction=None, alpha=None):
        self.encoder=Encoder(context,interaction);self.alpha=DESIGN['ridge_alpha'] if alpha is None else alpha
        if self.alpha<=0:raise ValueError('Positive regularization required')

    def fit(self, rows, targets):
        self.encoder.fit(rows);x=self.encoder.transform(rows);y=np.asarray(targets,float)
        if y.shape!=(len(rows),3):raise ValueError('Independent Speed/Attack/Bulk targets required')
        self.intercept=y.mean(0)
        self.coefficients=np.linalg.solve(x.T@x+self.alpha*np.eye(x.shape[1]),x.T@(y-self.intercept))
        return self

    def predict(self, rows):return np.clip(self.encoder.transform(rows)@self.coefficients+self.intercept,0,LIMITS)

    def receipt(self):return dict(alpha=self.alpha,intercept=self.intercept.tolist(),coefficients=self.coefficients.tolist(),preprocessing=self.encoder.receipt())


def interaction_support(rows, name):
    positive={r['group'] for r in rows if r['interactions'][name] is not None and r['interactions'][name]>0}
    negative={r['group'] for r in rows if r['interactions'][name]==0}
    return dict(positive_groups=len(positive),negative_groups=len(negative),
                fit=len(positive)>=DESIGN['interaction_min_positive_training_groups'] and len(negative)>=DESIGN['interaction_min_negative_training_groups'])
