"""Explicit stat ownership for damage; category alone is insufficient."""


def select_stats(move_name, category):
    if category not in {'Physical', 'Special'}:
        raise ValueError('A damaging category is required')
    offense = 'attack' if category == 'Physical' else 'special_attack'
    defense = 'defense' if category == 'Physical' else 'special_defense'
    owner = 'attacker'
    if move_name == 'Body Press':
        offense, defense = 'defense', 'defense'
    elif move_name in {'Psyshock', 'Psystrike'}:
        offense, defense = 'special_attack', 'defense'
    elif move_name == 'Foul Play':
        owner, offense, defense = 'defender', 'attack', 'defense'
    return dict(offensive_owner=owner, offensive_stat=offense,
                defensive_owner='defender', defensive_stat=defense,
                constrains_opponent_offensive_stat=owner == 'attacker')
