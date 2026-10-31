"""Source-bound Life Orb evidence gates, separate from damage arithmetic.

Pinned item/ability callbacks corroborate recoil suppression; protocol messages
are not a verified guarantee of the Champions UI. No missing OCR is exclusion.
"""
import re


def reviewed_message(text, *, actor_name, individual, action_id):
    """Classify reviewed wording only; never identify an actor by co-presence."""
    compact=re.sub(r'\s+', '', text)
    actor=re.escape(actor_name)
    if not individual or not action_id:return None
    prefix=r'(?:对手的)?'+actor
    if re.fullmatch(prefix+r'受到了反作用力造成的伤害[！!]?',compact):
        kind='generic_recoil';confirms=False
    elif re.fullmatch(prefix+r'的生命被少量削减了[！!]?',compact):
        kind='life_orb_hp_loss';confirms=True
    elif re.fullmatch(prefix+r'的生命宝珠[！!]?',compact):
        kind='named_life_orb_popup';confirms=True
    else:return None
    return dict(kind=kind,confirms_life_orb=confirms,individual=individual,
                action_id=action_id,exact_wording=text,
                scope='Reviewed actor/action-bound wording; no HP amount or original ownership inferred')


def expected_recoil(*,ability,move,maximum_hp=None,ability_active=True,successful_hit=None,
                    item_active=None,forced_switch=None,after_move_hook_reached=None):
    if maximum_hp is None or type(maximum_hp) is not int or maximum_hp<=0:return None
    if ability_active is None:return None
    if ability_active and ability=='Magic Guard':return 0
    if ability_active and ability=='Sheer Force':
        if move.get('secondaries') or move.get('hasSheerForceBoost'):return 0
        # An incomplete move definition does not rule out Sheer Force effects.
        if 'secondaries' not in move:return None
    if successful_hit is False or item_active is False or forced_switch is True or after_move_hook_reached is False:return 0
    if any(x is None for x in (successful_hit,item_active,forced_switch,after_move_hook_reached)):return None
    return max(1,maximum_hp//10)


def evidence_allows(evidence,*,item,ability,move,attack_event_id):
    if not evidence or not evidence.get('sources'):return True
    if evidence.get('attack_event_id') not in (None,attack_event_id):raise ValueError('Life Orb evidence belongs to another attack')
    # A positive named item observation is stronger than generic post-hit HP loss.
    if evidence.get('observed') is True:
        specific=evidence.get('basis') in {'reviewed_item_message','reviewed_held_item'}
        if evidence.get('basis')=='attributed_recoil':
            conditions=evidence.get('conditions',{});expected=expected_recoil(ability=ability,move=move,**conditions)
            specific=bool(evidence.get('exclusive_attribution') and expected and evidence.get('hp_before',0)-evidence.get('hp_after',0)==expected)
        if not specific or evidence.get('attack_event_id')!=attack_event_id:return True
        return item=='Life Orb'
    if evidence.get('observed') is False and evidence.get('coverage_complete') and evidence.get('basis')=='reviewed_post_attack_hp_window' and evidence.get('attack_event_id')==attack_event_id and evidence.get('other_hp_changes_excluded'):
        expected=expected_recoil(ability=ability,move=move,**evidence.get('conditions',{}))
        if expected and type(evidence.get('hp_before')) is int and evidence.get('hp_before')==evidence.get('hp_after'):
            return item!='Life Orb'
    return True
