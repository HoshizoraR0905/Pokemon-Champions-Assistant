"""Prefix-safe, UI-typed message grouping with evidence-preserving row overlap."""
from copy import deepcopy
from difflib import SequenceMatcher
import re
from battle_events.parser import EventParser
from battle_events.schema import Evidence,stable_id


def compact(text):return re.sub(r'\s+','',text).casefold()


def row_key(text):
    # Punctuation variation alone is not a new visible row. Names are exact.
    return compact(text).translate(str.maketrans({'！':'!','。':'.'}))


def semantic_key(events):
    return tuple((e.event_type,e.side,(e.actor or {}).get('canonical_id'),
                  (e.target or {}).get('canonical_id'),
                  (e.canonical_references.get('move') or {}).get('canonical_id'),
                  row_key(e.attributes.get('semantic_text',e.original_text)).rstrip('!.')) for e in events)


class MessageOccurrences:
    def __init__(self,battle_id,maximum_gap=1.1,source_occurrence_ids=False):
        self.battle_id=battle_id;self.maximum_gap=maximum_gap;self.current=None;self.groups=[];self.last_timestamp=None
        self.source_occurrence_ids=source_occurrence_ids
        self.parser=EventParser()

    def observe(self,row):
        t=row['timestamp']
        if self.last_timestamp is not None and t<=self.last_timestamp:raise ValueError('Occurrence inputs must be strictly chronological')
        self.last_timestamp=t
        msg=row.get('message') or {};text=msg.get('raw_text','')
        valid=msg.get('selected') and msg.get('source_region_type')=='battle_message'
        if not valid or not text.strip():
            # Partial visibility has no new reading and cannot supply overlap.
            # Keep dedup context across animation, but never assemble through it.
            if msg.get('visibility')=='partial' and self.current:
                self.current['scroll_continuous']=False
            else:self.current=None
            return dict(events=[],occurrence=None,reason='no_visible_live_message')
        visible=[r['text'] for r in msg.get('rows',[]) if r.get('text','').strip()] or text.splitlines()
        entry=dict(entry_id=row['sha256'],source_id=row['source_id'],observation_ids=[row['sha256']],
                   raw_text=text,ocr_confidence=msg['confidence'],source_region_type='battle_message')
        current=self.current;continuous=bool(current and t-current['last_time']<=self.maximum_gap)
        logical=visible;overlap=0
        if continuous and current.get('scroll_continuous',True) and msg['confidence']>=.9 and all(o['confidence']>=.9 for o in current['observations']):
            prior=current.get('logical_rows',[])
            # Append only an exact suffix/prefix overlap to an unfinished message,
            # or recognize its repeated scrolled tail after completion.
            for n in range(min(len(prior),len(visible)),0,-1):
                if list(map(row_key,prior[-n:]))==list(map(row_key,visible[:n])):
                    if not current['emitted'] and re.search(r'(?:和|的)$',compact(''.join(prior))):
                        logical=prior+visible[n:];overlap=n
                    elif current['emitted'] and list(map(row_key,visible))==list(map(row_key,prior[-len(visible):])):
                        logical=prior;overlap=n
                    break
        entry['raw_text']='\n'.join(logical)
        parsed=self.parser.parse_many(entry,battle_id=self.battle_id)
        supported=(msg['confidence']>=.9 and all(e.event_type!='unknown' and
            (e.event_type!='move_execution' or e.canonical_references.get('move')) for e in parsed))
        semantic=semantic_key(parsed)
        related=bool(continuous and (overlap or SequenceMatcher(None,current['last_text'],compact(text)).ratio()>=.57))
        # A recognized semantic transition beats visual similarity. Unknown OCR
        # fragments may refine an un-emitted candidate but cannot replace events.
        if related and current['emitted'] and supported and current.get('semantic')!=semantic:related=False
        if related and current['emitted'] and not supported and compact(text).endswith(('和','的')):related=False
        if not related:
            seed=row['source_id']+':'+row['sha256'] if self.source_occurrence_ids else row['sha256']
            current=dict(id=stable_id(self.battle_id,'occurrence:'+seed),first_time=t,last_time=t,
                last_text='',observations=[],canonical_move=None,emitted=False,interpretation_time=None,
                chronology='first supported complete reading, never backdated',scroll_continuous=True)
            self.groups.append(current);self.current=current
        current.update(last_time=t,last_text=compact(text),logical_rows=logical,scroll_continuous=True)
        current['observations'].append(dict(timestamp=t,source_id=row['source_id'],sha256=row['sha256'],image=row['image'],
            raw_text=text,confidence=msg['confidence'],event_type=parsed[0].event_type,
            canonical_move=(parsed[0].canonical_references.get('move') or {}).get('canonical_id'),rows=deepcopy(msg.get('rows',[]))))
        events=[]
        if supported and not current['emitted']:
            for i,event in enumerate(parsed):
                suffix=':semantic' if len(parsed)==1 else ':recipient:'+str(i)
                event.event_id=stable_id(self.battle_id,current['id']+suffix)
                event.attributes.update(battle_id=self.battle_id,observation_time=t,fusion_context=True,
                    source_region_type='battle_message',occurrence_id=current['id'],
                    reconstructed_logical_message='\n'.join(logical),row_overlap=overlap)
                observations=current['observations'] if overlap else current['observations'][-1:]
                event.evidence=[Evidence('video_message',o['source_id'],[o['sha256']],dict(timestamp=o['timestamp'],
                    image=o['image'],source_region_type='battle_message',occurrence_id=current['id'],row_evidence=deepcopy(o['rows'])))
                    for o in observations]
                events.append(event.to_dict())
            current.update(emitted=True,semantic=semantic,canonical_move=(parsed[0].canonical_references.get('move') or {}).get('canonical_id'),interpretation_time=t)
        return dict(events=events,occurrence=deepcopy(current),reason='supported_now' if events else 'provisional_or_repeat',
            semantic_candidates=[e.to_dict() for e in parsed] if not supported else [],
            semantic_admission='emitted' if events else 'repeat' if supported else
                'below_occurrence_confidence' if msg['confidence']<.9 else 'unsupported_semantics')
