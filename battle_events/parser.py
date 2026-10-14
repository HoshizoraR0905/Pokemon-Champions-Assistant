"""Conservative Chinese outcome-message parsing using the pinned entity dictionary."""
from dataclasses import dataclass, field
import re
from knowledge import KnowledgeBase, normalize
from .schema import BattleEvent, Evidence, Participant, stable_id

@dataclass
class BattleContext:
    participants: dict = field(default_factory=lambda: {s:Participant(s) for s in ('self','opponent')})
    # Explicit observations, not inferred ownership based on species uniqueness.
    active: dict = field(default_factory=lambda: {'self':set(), 'opponent':set()})
    color_sides: dict = field(default_factory=dict)
    pending_send_side: str = 'unknown'
    previous_move: dict | None = None
    previous_subject: dict | None = None
    # Explicit display-name bindings from independently observed Pokémon icons.
    display_aliases: dict = field(default_factory=dict)

class EventParser:
    def __init__(self, knowledge=None): self.kb = knowledge or KnowledgeBase()

    def identity(self, text, kind):
        found = self.kb.exact[kind].get(normalize(text), [])
        ids = {e.canonical_id for e in found}
        if len(ids)!=1: return None
        e = found[0]
        result = {'canonical_id':e.canonical_id,'kind':kind,'name':e.names.get('zh-hans'),
                  'knowledge_snapshot':self.kb.snapshot_id}
        if kind=='species':result.update(self.kb.identities.for_entity(e))
        return result

    def species_mentions(self, text):
        # Longest exact names first; do not rewrite corrupted OCR or guess a form.
        hits=[]
        for e in self.kb.by_kind['species']:
            name=e.names.get('zh-hans','')
            if name and name in text:
                p=text.index(name)
                if not any(p>=a and p+len(name)<=b for a,b,_ in hits):
                    hits=[h for h in hits if not (h[0]>=p and h[1]<=p+len(name))]
                    hits.append((p,p+len(name),name))
        return [self.identity(n,'species') for _,_,n in sorted(hits)]

    def parse(self, entry, context=None, battle_id='battle'):
        c=context or BattleContext()
        if entry.get('ocr_confidence') is not None and entry['ocr_confidence']<.75:
            from copy import deepcopy
            c=deepcopy(c)  # Low-confidence candidates cannot seed later attribution.
        raw=entry['raw_text'];text=re.sub(r'\s+','',raw)
        subject=None;target=None;refs={};attrs={};unc=[];typ='unknown';basis=[]
        identity_text=text
        for alias,binding in sorted(c.display_aliases.items(),key=lambda kv:-len(kv[0])):
            if alias and alias in identity_text and binding.get('evidence'):
                identity_text=identity_text.replace(alias,binding['identity']['name'])
                attrs.setdefault('display_alias_evidence',[]).append(binding)
        mentions=[m for m in self.species_mentions(identity_text) if m]
        subject=mentions[0] if mentions else None
        hint=entry.get('side_hint','unknown')
        color=c.color_sides.get(entry.get('color'),'unknown')
        explicit='opponent' if text.startswith('对手') else 'unknown'
        if re.search(r'回来[！!]?$',text) or text.startswith('上吧'):explicit='self'
        signals={s for s in (color,explicit,hint) if s!='unknown'}
        side=next(iter(signals)) if len(signals)==1 else 'unknown'
        if len(signals)>1:unc.append('side_evidence_conflict')
        if side!='unknown':
            if explicit!='unknown':basis.append('explicit_text')
            if color!='unknown':basis.append('calibrated_row_color')
            if hint!='unknown':basis.append('adjacent_entry_context')
        name_sides={s for s,p in c.participants.items() if p.display_name and p.display_name!='训练家' and text.startswith(p.display_name)}
        if len(name_sides)>1:
            side='unknown';unc.append('ambiguous_trainer_display_name')
        elif name_sides:
            name_side=next(iter(name_sides))
            if side!='unknown' and side!=name_side:side='unknown';unc.append('trainer_name_conflict')
            else:side=name_side;basis.append('observed_trainer_display_name')
        if '换下了' in text or '回来' in text:typ='switch_out'
        elif '派出了' in text or text.startswith('上吧'):typ='send_out'
        elif '使出了' in text:
            typ='move_execution';move=text.split('使出了',1)[1].rstrip('！!。.')
            refs['move']=self.identity(move,'move')
            if refs['move'] is None:unc.append('unresolved_move')
            c.previous_move={'actor':subject,'side':side,'move':refs['move']}
        elif re.search(r'HP\d+%?[→➡➜>-]+\d+%?',text):
            typ='hp_change';m=re.search(r'HP(\d+)(%?)[→➡➜>-]+(\d+)(%?)',text)
            attrs.update(before=int(m[1]),after=int(m[3]),unit='displayed_percent' if m[2] or m[4] else 'absolute')
            if c.previous_move:attrs['associated_move']=c.previous_move['move']
        elif '倒下了' in text:typ='faint'
        elif '超级进化成了' in text:
            typ='transformation'
            name=text.split('超级进化成了',1)[1].rstrip('！!。.')
            attrs.update(mechanic='mega_evolution',identity=self.identity(name,'species'))
            if not attrs['identity']:unc.append('transformation_identity_unknown')
        elif '摆出了防守的架势' in text:
            typ='move_effect';attrs['effect']='protection_established'
        elif '在攻击中守护住了自己' in text:
            typ='move_effect';attrs['effect']='protected_from_attack'
        elif '没有起到效果' in text:
            typ='move_effect';attrs['effect']='failed_action'
        elif '体力回复了' in text:
            typ='move_effect';attrs['effect']='healing_announcement'
        elif '反作用力造成的伤害' in text:
            typ='move_effect';attrs['effect']='recoil_announcement'
        elif '极光幕使我方' in text:
            typ='side_condition_change';side='self';attrs.update(condition='aurora_veil',change='start')
        elif '我方的极光幕消失' in text:
            typ='side_condition_change';side='self';attrs.update(condition='aurora_veil',change='end')
        elif '脚下青草如茵' in text:
            typ='terrain_change';side='field';attrs.update(terrain='grassy',change='start')
        elif '脚下的青草消失' in text:
            typ='terrain_change';side='field';attrs.update(terrain='grassy',change='end')
        elif '开始下雪' in text:
            typ='weather_change';side='field';attrs.update(weather='snow',change='start')
        elif '吸收了电力' in text:typ='move_effect';attrs['effect']='absorbed_electricity'
        elif '效果不好' in text or '效果绝佳' in text or '没有效果' in text:
            typ='effectiveness';target=subject;subject=None
            attrs['effect']='not_very_effective' if '效果不好' in text else ('super_effective' if '效果绝佳' in text else 'immune')
        elif '击中了要害' in text or '命中要害' in text:typ='critical_hit'
        elif re.search(r'(击中|命中).*[0-9]+次',text):
            typ='multi_hit';attrs['hits']=int(re.search(r'([0-9]+)次',text)[1])
        elif any(s in text for s in ('提高了','降低了','大幅提高','大幅降低')):
            typ='stat_change';stats={'特攻':'special_attack','特防':'special_defense','攻击':'attack','防御':'defense','速度':'speed','命中率':'accuracy','闪避率':'evasion'}
            attrs.update(stats=[v for k,v in stats.items() if k in text], direction='down' if '降低' in text else 'up',stages=None)
        elif any(s in text for s in ('中毒了','麻痹了','睡着了','灼伤了','冰冻了','解除了')):
            typ='status_change';statuses={'中毒':'poison','麻痹':'paralysis','睡着':'sleep','灼伤':'burn','冰冻':'freeze'}
            attrs.update(status=next((v for k,v in statuses.items() if k in text),None),change='remove' if '解除了' in text else 'apply')
        elif '开始下雨' in text:typ='weather_change';side='field';attrs={'weather':'rain','change':'start'}
        elif '奇妙的感觉' in text:
            typ='terrain_change';side='field';attrs={'terrain':None,'change':'start'}
            if c.previous_subject and c.previous_subject.get('ability',{}).get('name')=='精神制造者':
                attrs['terrain']='psychic';basis.append('preceding_psychic_surge')
            else:unc.append('terrain_identity_unknown')
        elif '的' in text:
            suffix=text.split('的',1)[1].rstrip('！!。.')
            for kind,event_type in [('ability','ability_activation'),('item','item_activation')]:
                ref=self.identity(suffix,kind)
                if ref:typ=event_type;refs[kind]=ref;break
        affected=subject or target
        if side=='unknown' and not unc and affected:
            sid=affected['canonical_id'];owners=[s for s,values in c.active.items() if sid in values]
            if len(owners)==1:side=owners[0];basis.append('prior_active_observation')
            elif len(owners)>1:unc.append('species_active_on_both_sides')
            elif typ in {'move_effect','stat_change'} and c.previous_move and c.previous_move['actor'] and sid==c.previous_move['actor']['canonical_id']:
                side=c.previous_move['side'];basis.append('preceding_move_actor')
        if typ=='send_out' and side=='unknown' and c.pending_send_side!='unknown' and not unc:
            side=c.pending_send_side;basis.append('preceding_withdrawal_or_faint')
        if typ in {'switch_out','faint'}:
            c.pending_send_side=side
            if subject and side in c.active:c.active[side].discard(subject['canonical_id'])
        if typ=='send_out':
            if subject and side in c.active:c.active[side].add(subject['canonical_id'])
            c.pending_send_side='unknown'
        if typ=='ability_activation':c.previous_subject=refs
        elif typ!='terrain_change':c.previous_subject=None
        if typ not in {'weather_change','terrain_change'} and side=='unknown':unc.append('side_unknown')
        if typ=='unknown':unc.append('unrecognized_message')
        if subject is None and typ in {'switch_out','send_out','move_execution','hp_change','ability_activation','item_activation','stat_change','faint','transformation'}:unc.append('actor_unresolved')
        # A move announcement alone does not name its target. Later HP messages
        # are separate evidence and do not silently rewrite an earlier candidate.
        if typ=='move_execution':unc.append('target_not_in_entry')
        for role,entity in [('actor',subject),('target',target)]:
            if entity and entity.get('identity_status')=='species_only':unc.append(role+'_variant_unresolved')
        if entry.get('ocr_confidence') is not None and entry['ocr_confidence']<.75:unc.append('low_ocr_confidence')
        attrs['side_basis']=basis
        if entry.get('side_hint_evidence'):attrs['side_hint_evidence']=entry['side_hint_evidence']
        evidence=Evidence('battle_log',entry.get('source_id','unknown'),entry.get('observation_ids',[]),{'turn':entry.get('turn'),'entry_id':entry['entry_id']})
        return BattleEvent(stable_id(battle_id,entry['entry_id']),typ,side,subject,target,raw,refs,
                           entry.get('log_order'),[evidence],entry.get('ocr_confidence'),
                           'uncertain' if unc else 'supported',unc,attrs)


    def parse_sequence(self, entries, context=None, battle_id='battle'):
        """Local message relationships, not a full battle-state reconstruction."""
        c=context or BattleContext();prepared=[dict(e) for e in entries]
        # Generic trainer send-outs can be corroborated by the immediately
        # following same-actor colored ability/item activation. Do not use a
        # globally unique species assumption or a generic display label alone.
        for i,e in enumerate(prepared[:-1]):
            text=compact_text(e['raw_text']);n=prepared[i+1]
            if '派出了' not in text or e.get('turn')!=n.get('turn'):continue
            actor=self.species_mentions(text);following=self.species_mentions(n['raw_text'])
            color_side=c.color_sides.get(n.get('color'),'unknown')
            suffix=compact_text(n['raw_text']).split('的',1)[-1]
            activation=any(self.identity(suffix,k) for k in ('ability','item'))
            if min(e.get('ocr_confidence',0),n.get('ocr_confidence',0))>=.75 and actor and following and actor[0] and following[0] and actor[0]['canonical_id']==following[0]['canonical_id'] and activation and color_side!='unknown':
                e['side_hint']=color_side;e['side_hint_evidence']={'basis':'adjacent_same_actor_activation_color','entry_id':n['entry_id']}
                if i and '换下了' in compact_text(prepared[i-1]['raw_text']):
                    # The paired trainer text must match, including generic label.
                    before=compact_text(prepared[i-1]['raw_text']).split('换下了')[0]
                    trainer=text.split('派出了')[0]
                    if before==trainer:
                        prepared[i-1]['side_hint']=color_side
                        prepared[i-1]['side_hint_evidence']={'basis':'paired_trainer_withdraw_send_activation','entry_id':e['entry_id']}
        events=[];prior_turn=None
        for entry in prepared:
            turn=entry.get('turn')
            if prior_turn is not None and turn!=prior_turn:
                c.previous_move=None;c.previous_subject=None;c.pending_send_side='unknown'
            events.append(self.parse(entry,c,battle_id));prior_turn=turn
        for i,event in enumerate(events):
            if event.event_type!='move_execution' or event.actor is None or event.side=='unknown':continue
            for following in events[i+1:]:
                if following.evidence[0].details.get('turn')!=event.evidence[0].details.get('turn'):break
                if following.event_type in {'move_execution','switch_out','send_out','faint','unknown'}:break
                if following.event_type=='hp_change':
                    if following.actor and following.side in {'self','opponent'} and following.side!=event.side:
                        event.target=following.actor
                        event.attributes['target_side']=following.side
                        event.attributes['target_basis']={'method':'following_opposing_hp_message','event_id':following.event_id}
                        event.uncertainty=[u for u in event.uncertainty if u!='target_not_in_entry']
                        event.uncertainty.append('target_associated_from_sequence')
                        event.parsing_confidence='uncertain'
                    break
        return events


def compact_text(text):return re.sub(r'\s+','',text)
