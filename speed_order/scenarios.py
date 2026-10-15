"""Finite shared/local assignment enumeration for Speed APIs."""
from copy import deepcopy
from itertools import product
from math import prod
from .core import need, shape, text


def assignments(contexts,variables,max_assignments):
    need(isinstance(variables,list),'Explicit finite variable list required')
    dimensions=[];seen=set();occupied=set()
    for variable in variables:
        required={'id','scope','observation_ids','path','values'}
        need(isinstance(variable,dict) and required<=set(variable)<=required|{'change_evidence'},'Invalid finite variable fields')
        name=variable['id'];scope=variable['scope'];targets=variable['observation_ids'];path=variable['path'];values=variable['values']
        need(text(name) and name not in seen,'Unique variable IDs required');seen.add(name)
        need(scope in ('shared','observation'),'Scope must be shared or observation')
        need(isinstance(targets,list) and targets and all(text(t) and t in contexts for t in targets) and len(set(targets))==len(targets),'Invalid observation bindings')
        need(isinstance(values,list) and 1<=len(values)<=max_assignments,'Finite alternatives required')
        need(text(path) and path.split('.')[0] in ('own','opponent','field'),'Only participant/field leaf variables supported')
        need(path not in ('opponent.actual_speed','opponent.identity','opponent.form','opponent.instance_id','own.identity','own.form','own.instance_id'),'Cannot change inferred subject or participant identity')
        if scope=='observation' and len(targets)>1 and path in ('own.item','opponent.item','own.ability','opponent.ability'):
            need(text(variable.get('change_evidence')),'Independent persistent item/ability changes require explicit change_evidence')
        for target in targets:
            need((target,path) not in occupied,'Overlapping scenario bindings');occupied.add((target,path))
            patch(deepcopy(contexts[target]),path,values[0])
        if scope=='shared':dimensions.append((name,targets,path,values))
        else:dimensions.extend((name+':'+target,[target],path,values) for target in targets)
    need(len({x[0] for x in dimensions})==len(dimensions),'Expanded variable IDs collide')
    count=prod(len(d[3]) for d in dimensions);need(count<=max_assignments,'Scenario assignment limit exceeded')
    def generate():
        for choices in product(*(d[3] for d in dimensions)):
            result=deepcopy(contexts);values={}
            for (name,targets,path,_),value in zip(dimensions,choices):
                values[name]=value
                for target in targets:patch(result[target],path,value)
            yield values,result
    return count,generate()


def patch(context,path,value):
    parts=path.split('.');obj=context
    for part in parts[:-1]:
        need(isinstance(obj,dict) and part in obj,'Scenario path does not exist');obj=obj[part]
    need(isinstance(obj,dict) and parts[-1] in obj and not isinstance(obj[parts[-1]],(dict,list)),'Only existing leaf scenario paths supported')
    obj[parts[-1]]=deepcopy(value)
