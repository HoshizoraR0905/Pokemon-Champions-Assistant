"""Replay drift is evidence quality metadata, never a silent state repair."""
from .snapshots import project
from tracking.battle_state import from_dict


def replay_validation(saved,last_projection,stage):
    expected=project(from_dict(saved['state']));paths=[]
    def visit(a,b,path=''):
        if isinstance(a,dict) and isinstance(b,dict):
            for key in sorted(set(a)|set(b)):
                if key not in a or key not in b:paths.append(path+'/'+key)
                else:visit(a[key],b[key],path+'/'+key)
        elif a!=b:paths.append(path)
    visit(expected,last_projection)
    return dict(saved_final_hash=stage['saved_final_hash'],replayed_final_hash=stage['replayed_final_hash'],
        full_final_state_matches=stage['saved_final_hash']==stage['replayed_final_hash'],
        projected_final_state_matches=not paths,projected_difference_paths=paths,
        scope='Current-code replay prefixes; final projected agreement does not independently validate every earlier prefix or recognition result',
        caution='Saved/current observable projections differ; historical instance/status bindings need review' if paths else 'Full-state hash drift, if present, is outside this compact projection')
