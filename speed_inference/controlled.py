"""Explicitly synthetic inputs; never infer missing battle state from recordings."""
from copy import deepcopy
from .domains import configuration_space
from .likelihood import VERIFICATIONS


def observation(turn=1,*,own_speed=121,first='opponent'):
    actor=dict(identity='Charizard',form='base',instance_id='own:1',actual_speed=own_speed,
        stage=0,tailwind=False,ability='Blaze',ability_active=True,item='none',status='none',
        unburden_active=False,activation_evidence=None,other_effects=[])
    opponent=deepcopy(actor);opponent.update(instance_id='opponent:1',actual_speed=None)
    action=dict(kind='move',move='Flamethrower',effective_priority=0,evidence='Controlled ordinary move')
    return dict(id=f'synthetic:{turn}',battle_id='synthetic',stat_epoch='initial',origin='synthetic',
        evidence_kind='verified_action_order',verification={k:True for k in sorted(VERIFICATIONS)},
        provenance=[dict(source='controlled fixture',verification='synthetic, not an observed game')],
        action_ids=dict(own=f'own-action:{turn}',opponent=f'opponent-action:{turn}'),
        sequence=[first,'own' if first=='opponent' else 'opponent'],
        context=dict(own=actor,opponent=opponent,actions=dict(own=deepcopy(action),opponent=deepcopy(action)),
            field=dict(weather='none',terrain='none',trick_room=False,other_effects=[]),ordering_effects=[],
            timing=dict(turn=turn,decision_id=f'turn:{turn}',state_at='order_decision',modifier_changes=[]),
            comparable=True,evidence='Synthetic ordering snapshot'))


def experiment():
    return dict(model=configuration_space(identity='Charizard',form='base',speed_points=[0,1,2],
            alignments=[dict(increase=None,decrease=None)]),battle_id='synthetic',instance_id='opponent:1',stat_epoch='initial',
        profile='showdown-champions-reference-v1',observations=[observation(),observation(2,own_speed=122)])
