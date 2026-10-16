"""Prefix-safe, UI-typed temporal message occurrence grouping.

This is observation metadata and an adapter to existing BattleEvent, never a
parallel Battle State. No future frame or review label enters a decision.
"""
from copy import deepcopy
from difflib import SequenceMatcher
import re
from battle_events.parser import EventParser
from battle_events.schema import Evidence,stable_id


def compact(text):return re.sub(r'\s+','',text).casefold()


class MessageOccurrences:
    def __init__(self,battle_id,maximum_gap=1.1,source_occurrence_ids=False):
        self.battle_id=battle_id;self.maximum_gap=maximum_gap;self.current=None;self.groups=[];self.last_timestamp=None
        self.source_occurrence_ids=source_occurrence_ids
        self.parser=EventParser()

    def observe(self,row):
        t=row['timestamp']
        if self.last_timestamp is not None and t<=self.last_timestamp:raise ValueError('Occurrence inputs must be strictly chronological')
        self.last_timestamp=t
        msg=row.get('message') or {};text=msg.get('raw_text','');valid=(msg.get('selected') and msg.get('source_region_type')=='battle_message')
        if not valid or not text.strip():self.current=None;return dict(events=[],occurrence=None,reason='no_visible_live_message')
        entry=dict(entry_id=row['sha256'],source_id=row['source_id'],observation_ids=[row['sha256']],
                   raw_text=text,ocr_confidence=msg['confidence'],source_region_type='battle_message')
        parsed=self.parser.parse(entry,battle_id=self.battle_id)
        move=(parsed.canonical_references.get('move') or {}).get('canonical_id')
        semantic=(parsed.event_type,move,compact(text).split('使出了')[0])
        current=self.current
        related=bool(current and t-current['last_time']<=self.maximum_gap and
            (SequenceMatcher(None,current['last_text'],compact(text)).ratio()>=.57 or
             ('使出了' in compact(text) and '使出了' in current['last_text'] and
              compact(text).split('使出了')[0]==current['last_text'].split('使出了')[0])))
        # Distinct fully resolved move names establish a new occurrence even
        # when their actors and grammar look identical. Ambiguous cases stay raw.
        if related and current.get('canonical_move') and move and current['canonical_move']!=move:related=False
        if not related:
            seed=row['source_id']+':'+row['sha256'] if self.source_occurrence_ids else row['sha256']
            current=dict(id=stable_id(self.battle_id,'occurrence:'+seed),first_time=t,last_time=t,
                         last_text='',observations=[],canonical_move=None,emitted=False,interpretation_time=None,
                         chronology='first supported reading, never backdated')
            self.groups.append(current);self.current=current
        current['last_time']=t;current['last_text']=compact(text)
        current['observations'].append(dict(timestamp=t,source_id=row['source_id'],sha256=row['sha256'],raw_text=text,
            confidence=msg['confidence'],event_type=parsed.event_type,canonical_move=move,rows=deepcopy(msg.get('rows',[]))))
        events=[]
        supported=(msg['confidence']>=.9 and parsed.event_type!='unknown' and (parsed.event_type!='move_execution' or move))
        if supported and not current['emitted']:
            parsed.event_id=stable_id(self.battle_id,current['id']+':semantic')
            parsed.attributes.update(battle_id=self.battle_id,observation_time=t,fusion_context=True,
                                     source_region_type='battle_message',occurrence_id=current['id'])
            parsed.evidence=[Evidence('video_message',row['source_id'],[row['sha256']],dict(timestamp=t,image=row['image'],
                source_region_type='battle_message',occurrence_id=current['id'],row_evidence=deepcopy(msg.get('rows',[]))))]
            events.append(parsed.to_dict());current.update(emitted=True,canonical_move=move,interpretation_time=t)
        return dict(events=events,occurrence=deepcopy(current),reason='supported_now' if events else 'provisional_or_repeat')
