"""Integer arithmetic for the pinned Champions-reference direct-hit sequence.

Algorithm adapted from @smogon/calc 0.12.0 (MIT); see data/LICENSE.smogon.txt.
"""
from collections import Counter
from fractions import Fraction

def poke_round(numerator,denominator=4096):
    q,r=divmod(numerator,denominator)
    return q+(2*r>denominator)

def chain_mods(mods):
    value=4096
    for mod in mods:value=(value*mod+2048)//4096
    return max(41,min(value,131072))

def stage_stat(value,stage):
    if stage==0:return value
    numerator,denominator=(2+stage,2) if stage>0 else (2,2-stage)
    return (value*numerator%65536)//denominator

def base_damage(level,power,attack,defense):
    # Inputs are bounded upstream, but retain the reference's overflow semantics.
    return ((((2*level//5+2)*power*attack)%(2**32))//defense)//50+2

def rolls(base,stab,effectiveness,burn,final_mod):
    output=[];trace=[]
    for random in range(85,101):
        randomized=(base*random%(2**32))//100
        with_stab=randomized if stab==4096 else poke_round(randomized*stab%(2**32))
        typed=(with_stab*effectiveness.numerator)//effectiveness.denominator
        after_burn=typed//2 if burn else typed
        damage=poke_round(max(4096,after_burn*final_mod%(2**32)))%65536
        output.append(damage);trace.append(dict(random=random,randomized=randomized,after_stab=with_stab,after_type=typed,after_burn=after_burn,damage=damage))
    return output,trace

def distribution(values,maximum_hp,current_hp):
    counts=Counter(values);den=len(values)
    def ratio(n,d):return dict(numerator=n,denominator=d)
    return dict(rolls=values,frequencies=[dict(damage=n,count=c,probability=ratio(c,den)) for n,c in sorted(counts.items())],
        outcome_count=den,hp_loss_rolls=[min(n,current_hp) for n in values] if current_hp is not None else None,minimum=min(values),maximum=max(values),
        percent_max_hp=[ratio(n*100,maximum_hp) for n in values] if maximum_hp else None,
        ko_probability=ratio(sum(n>=current_hp for n in values),den) if current_hp is not None else None)
