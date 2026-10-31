"""Literal outcome grammars, without inferred mechanics, targets or timers."""
import re
from knowledge import normalize

# Shared by side-bearing live actor routing and literal outcome recognition.
ACTOR_OUTCOME = (r'(?:正在呼呼大睡|醒过来了|睡着了|体力回复了|HP回复了|'
                 r'受到了伤害|受到了广域防守的保护|在攻击中守护住了自己|'
                 r'摆出了防守的架势|吸收了电力|HP变成了0|HP降到了0|'
                 r'混乱了|正在混乱中|混乱解除了|从混乱中恢复了|不再混乱了|'
                 r'不知所以地攻击了自己)')


def hp_cause_notice(text, identity):
    """Literal affected subject and explicit cause, never a mechanics deduction.

    Membership in this grammar does not assert Champions availability, damage
    amounts, equipped moves, native abilities, or an effect's effectiveness.
    """
    t=text.rstrip('！!。.')
    recovery=re.fullmatch(r'(对手的)?(.+?)的(?:体力|HP)回复了',t)
    if recovery:
        return recovery[2], 'opponent' if recovery[1] else 'self', dict(
            qualitative_only=True,direction='up',cause=None,explicit_recovery_recipient=True)
    if t=='不知所以地攻击了自己':
        return None, 'unknown', dict(qualitative_only=True,direction='down',
            cause=dict(kind='confusion_self_damage',condition='confusion'),requires_confusion_context=True)
    m=re.fullmatch(r'(对手的)?(.+?)不知所以地攻击了自己',t)
    if m:
        return m[2], 'opponent' if m[1] else 'self', dict(qualitative_only=True,direction='down',
            cause=dict(kind='confusion_self_damage',condition='confusion'))
    # Match named self-cost/recoil before the generic recoil suffix, which
    # otherwise consumes the move clause as part of the affected display name.
    m=re.fullmatch(r'(对手的)?(.+?)因(腹鼓|闪焰冲锋|挣扎)(削减了自己的HP|受到了反作用力造成的伤害)',t)
    if m and (m[3],m[4]) in {('腹鼓','削减了自己的HP'),('闪焰冲锋','受到了反作用力造成的伤害'),('挣扎','受到了反作用力造成的伤害')}:
        return m[2], 'opponent' if m[1] else 'self', dict(qualitative_only=True,direction='down',
            cause=dict(kind={'腹鼓':'self_hp_cost','挣扎':'struggle_recoil'}.get(m[3],'move_recoil'),source=identity(m[3],'move')))
    if t=='受到了反作用力造成的伤害':
        return None, 'unknown', dict(qualitative_only=True,direction='down',
            cause=dict(kind='struggle_recoil'),requires_struggle_context=True)
    m=re.fullmatch(r'(对手的)?(.+?)(?:受到了|因)(灼伤|中毒|毒|沙暴|隐形岩|反作用力)(?:的伤害|造成的伤害|(?:而)?受到了伤害)',t)
    if m:
        label=m[3]
        causes={'灼伤':dict(kind='status',status='burn'),'中毒':dict(kind='status',status='poison'),
            '毒':dict(kind='status',status='poison'),'沙暴':dict(kind='weather',weather='sandstorm'),
            '隐形岩':dict(kind='entry_hazard',hazard='stealth_rock'),'反作用力':dict(kind='move_recoil')}
        return m[2], 'opponent' if m[1] else 'self', dict(qualitative_only=True,direction='down',cause=causes[label])
    m=re.fullmatch(r'(对手的)?(.+?)因(对手的)?(.+?)的(.+?)(受到了伤害|回复了体力)',t)
    if m:
        refs=[(kind,identity(m[5],kind)) for kind in ('item','ability','move')]
        refs=[(kind,ref) for kind,ref in refs if ref]
        holder=identity(m[4],'species')
        if len(refs)==1 and holder:
            kind,ref=refs[0]
            cause=dict(kind=kind,source=ref,holder=holder,holder_side='opponent' if m[3] else 'self')
            return m[2], 'opponent' if m[1] else 'self', dict(qualitative_only=True,
                direction='down' if m[6]=='受到了伤害' else 'up',cause=cause)
    m=re.fullmatch(r'(对手的)?(.+?)的灭亡之歌倒数变成了0',t)
    if m:
        return m[2], 'opponent' if m[1] else 'self', dict(qualitative_only=True,direction='zero',
            cause=dict(kind='instant_faint',source=identity('灭亡之歌','move')))
    return None


def normalize_message(text, kb):
    """Only a canonical stone in a complete reaction grammar licenses 丫 → Y."""
    match = re.fullmatch(r'(.+?进化石)丫(和.+起了反应[！!。.]?)', text)
    if match:
        stone = match[1].split('的')[-1] + 'Y'
        if kb.exact['item'].get(normalize(stone)):
            corrected = match[1] + 'Y' + match[2]
            return corrected, [dict(original='丫', normalized='Y', context='canonical_mega_stone_reaction', canonical_name=stone)]
    return text, []


def outcome(text):
    t = text.rstrip('！!。.')
    m=re.fullmatch(r'(?:对手的)?.+?(混乱了|正在混乱中|混乱解除了|从混乱中恢复了|不再混乱了)',t)
    if m:
        return 'volatile_change', None, dict(condition='confusion',
            change={'混乱了':'start','正在混乱中':'observe'}.get(m[1],'end'))
    weather = {'日照变强了':'sun', '阳光变得强烈了':'sun', '刮起了沙暴':'sandstorm',
               '沙暴刮起来了':'sandstorm', '开始下雨了':'rain', '开始下雪了':'snow'}
    if t in weather:
        return 'weather_change', 'field', dict(weather=weather[t], change='start')
    m = re.fullmatch(r'从(我方|对手|对方)(?:的)?身后吹起了顺风', t)
    if m:
        return 'side_condition_change', 'self' if m[1]=='我方' else 'opponent', dict(condition='tailwind', change='start')
    m = re.fullmatch(r'(我方|对手|对方)周围正受到广域防守的保护', t)
    if m:
        return 'side_condition_change', 'self' if m[1]=='我方' else 'opponent', dict(condition='wide_guard', change='start')
    m = re.fullmatch(r'(?:对手的)?.+?' + ACTOR_OUTCOME, t)
    if not m:
        return None
    if t.endswith('正在呼呼大睡'):
        return 'status_change', None, dict(status='sleep', change='observe', reason='continued_sleep')
    if t.endswith('醒过来了'):
        return 'status_change', None, dict(status='sleep', change='remove', reason='woke_up')
    if t.endswith(('体力回复了','HP回复了')):
        return 'hp_change', None, dict(qualitative_only=True, direction='up', cause=None)
    if t.endswith('受到了伤害'):
        return 'hp_change', None, dict(qualitative_only=True, direction='down', cause=None)
    if t.endswith(('HP变成了0','HP降到了0')):
        # A zero without a unit/max does not establish an absolute HP series.
        return 'hp_change', None, dict(qualitative_only=True, direction='zero', cause=None)
    effects={'受到了广域防守的保护':'wide_guard_received', '在攻击中守护住了自己':'protected_from_attack',
             '摆出了防守的架势':'protection_established', '吸收了电力':'absorbed_electricity'}
    for suffix, effect in effects.items():
        if t.endswith(suffix):
            return 'move_effect', None, dict(effect=effect, recipient_observation=True, scope='per_action')
    return None
