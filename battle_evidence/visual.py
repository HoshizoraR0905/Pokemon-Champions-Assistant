"""Temporal normal-screen phase evidence; no Battle Log input or sole-cue counter."""
from copy import deepcopy
from speed_inference.domains import digest

PHASES=('PRE_BATTLE','INITIAL_SENDOUT','NORMAL_COMMAND','COMMAND_SUBMENU','TURN_RESOLUTION','FORCED_SELECTION','POST_TURN_TRANSITION','UNKNOWN')


def normal_command_support(signals,*,established=False,pending=False):
    """Context-dependent native command evidence; HUD cardinality is not a quorum."""
    result=dict(qualified=False,strength='unknown',reasons=[],required_samples=3)
    if pending or signals.get('faint') or signals.get('pivot_action'):
        result['reasons']=['pending_replacement_or_pivot'];return result
    if signals.get('menu') or signals.get('pre_battle') or signals.get('battle_end'):
        result['reasons']=['selection_or_nonbattle_phase'];return result
    if signals.get('overlay') not in (None,'status_overlay'):
        result['reasons']=['overlay_excluded'];return result
    native=signals.get('native_dual_controls') or signals.get('normal_controls')
    if not native:
        result['reasons']=['native_dual_controls_missing'];return result
    slots=set(signals.get('hud_slots',[]));count=signals.get('hud_cards',len(slots))
    ordinary=signals.get('battle_view') or signals.get('cached_phase')=='battle_screen'
    timer=signals.get('command_timer');timer_known=type(timer) is int and 0<=timer<=90
    own=any(x.startswith('own_active_') for x in slots);opponent=any(x.startswith('opponent_active_') for x in slots)
    occupancy=signals.get('active_slot_occupancy') or {};verified=signals.get('occupancy_verified') is True
    sides={side:bool([x for x in (occupancy.get(side) or {}).values() if x]) for side in ('self','opponent')}
    conflict=verified and ((own and not sides['self']) or (opponent and not sides['opponent']))
    if conflict:
        result['reasons']=['verified_occupancy_conflicts_with_HUD'];return result
    if count>=4 and ordinary:
        result.update(qualified=True,strength='strong_four_card_support',required_samples=2,
            reasons=['two_native_controls_and_ordinary_four_card_layout']);return result
    side_support=(own and opponent) or (verified and all(sides.values()) and count>=1)
    if ordinary and timer_known and established and side_support:
        result.update(qualified=True,strength='context_supported_variable_HUD',
            reasons=['two_native_controls','range_checked_recognized_command_timer','ordinary_battle_geometry',
                'established_phase_history','both_sides_visible_or_verified_occupancy'])
    else:result['reasons']=['variable_HUD_context_insufficient']
    return result


class VisualPhaseEstimator:
    def __init__(self,battle_id,*,max_gap=1.6,profile='v1'):
        if profile not in ('v1','v2'):raise ValueError('Unknown visual profile')
        self.profile=profile;self.initial_observed=False
        self.battle_id=battle_id;self.max_gap=max_gap;self.history=[];self.segments=[];self.open=None
        self.terminal=False;self.phase='UNKNOWN';self.last=None;self.candidate=[];self.candidate_bound=None;self.seen={};self.resolution=[]
        self.gaps=[];self.interruptions=[];self.pending=False;self.resumed=False;self.prebattle=False;self.initial_sides=set()

    def consume(self,observation):
        o=deepcopy(observation);oid=o['id'];fp=digest(o)
        if oid in self.seen:
            if self.seen[oid]!=fp:raise ValueError('Visual evidence revision requires replay')
            return dict(status='duplicate_ignored')
        if o['battle_id']!=self.battle_id:raise ValueError('Cross-battle observation')
        if self.last and o['timestamp']<=self.last['timestamp']:raise ValueError('Visual observations require chronological order')
        self.seen[oid]=fp;t=o['timestamp'];signals=o.get('signals',{});actions=o.get('actions',[])
        gap=None
        if self.last and (t-self.last['timestamp']>self.max_gap or signals.get('missing_image')):
            gap=dict(before=self.last['id'],after=oid,bounds=[self.last['timestamp'],t],reason='missing_cached_frame' if signals.get('missing_image') else 'sampling_gap_exceeds_validated_cadence')
            self.gaps.append(gap);self.candidate=[]
            if self.open:self.open['gaps'].append(gap)
        old=self.phase;phase='UNKNOWN';reasons=[]
        if self.terminal:
            record=dict(frame_id=oid,timestamp=t,phase='POST_TURN_TRANSITION',previous_phase=old,
                reasons=['post_battle_evidence; no further turn inference'],signals=signals,source_id=o.get('source_id'),gap=gap,
                possible_phases=['POST_TURN_TRANSITION'])
            self.history.append(record);self.last=o;return deepcopy(record)
        if signals.get('pre_battle'):
            phase='PRE_BATTLE';self.prebattle=True
        elif signals.get('initial_sendout') and not self.open:
            phase='INITIAL_SENDOUT';self.initial_observed=True;self.initial_sides.update(signals.get('sendout_sides',[]))
        main=(signals.get('normal_controls') is True and signals.get('hud_cards',0)>=4 and not signals.get('overlay'))
        support=normal_command_support(signals,established=bool(self.open or self.resolution or self.initial_observed),pending=self.pending) if self.profile=='v2' else None
        if support is not None:main=support['qualified'];o['command_support']=support
        menu=signals.get('menu')
        # A native-button anchor can be followed immediately by ordinary move-menu
        # navigation. This corroborates command persistence; it is not a new cue
        # based solely on COMMAND or a menu classification.
        anchored_command=(self.candidate and not self.pending and not signals.get('overlay')
            and t-self.candidate[-1]['timestamp']<=self.max_gap
            and signals.get('command_label') and not actions
            and (signals.get('hud_cards',0)>=4 or menu in ('move_selection','move_target_selection')))
        if self.profile=='v2':
            context=(menu in ('move_selection','move_target_selection') or signals.get('overlay')=='status_overlay' or signals.get('command_panel')=='status_overlay'
                or (signals.get('command_label') and (signals.get('battle_view') or signals.get('hud_cards',0)>=4 or (any(x.startswith('own_active_') for x in signals.get('hud_slots',[])) and any(x.startswith('opponent_active_') for x in signals.get('hud_slots',[]))))))
            anchored_command=bool(self.candidate and not self.pending and not actions and not signals.get('faint')
                and not signals.get('pivot_action') and context and not signals.get('battle_end')
                and menu not in ('pokemon_selection','switch_selection')
                and signals.get('overlay') in (None,'status_overlay')
                and t-self.candidate[-1]['timestamp']<=self.max_gap)
        if anchored_command:
            main=True;menu=None;reasons.append('native_command_anchor_persisted_into_command_context')
            if self.profile=='v2':
                o['command_support']['required_samples']=max((c.get('command_support') or {}).get('required_samples',2) for c in self.candidate)
                o['command_support']['anchor_frames']=[c['id'] for c in self.candidate]
        actual_actions=[a for a in actions if a.get('live_execution') and a.get('event_id')]
        if signals.get('faint') or signals.get('pivot_action'):self.pending=True
        if menu:
            self.candidate=[]
            if self.open and not self.resolution and not self.pending:
                phase='COMMAND_SUBMENU';reasons.append('menu_navigation_within_existing_command')
            elif self.open and self.resolution and not self.pending and menu in ('move_selection','move_target_selection'):
                phase='POST_TURN_TRANSITION';reasons.append('ordinary_move_menu_without_observed_next_native_anchor')
                self.open.setdefault('unanchored_command_menus',[]).append(dict(frame_id=oid,
                    bounds=[self.last['timestamp'] if self.last else t,t]))
            else:
                phase='FORCED_SELECTION';self.interruptions.append(oid);self.candidate=[]
                if self.open:self.open['interruptions'].append(oid)
        elif actual_actions and not main and not signals.get('overlay'):
            phase='TURN_RESOLUTION';self.candidate=[]
            if self.open:
                self.resolution.extend(dict(a,frame_id=oid,timestamp=t) for a in actual_actions)
                if self.interruptions:self.resumed=True
            else:reasons.append('resolution_without_observed_command_anchor')
        elif signals.get('sendout') and self.resolution:
            phase='TURN_RESOLUTION';self.pending=False;self.resumed=True
        elif main:
            if not self.candidate:self.candidate_bound=[self.last['timestamp'] if self.last else t,t]
            self.candidate.append(o)
            required=max((c.get('command_support') or {}).get('required_samples',2) for c in self.candidate) if self.profile=='v2' else 2
            if len(self.candidate)>required:self.candidate=self.candidate[-required:]
            stable=len(self.candidate)>=required and t-self.candidate[-2]['timestamp']<=self.max_gap
            phase='POST_TURN_TRANSITION' if self.resolution else 'NORMAL_COMMAND'
            if stable:
                phase='NORMAL_COMMAND'
                if self.open and self.resolution:
                    first=self.candidate[0];issues=[]
                    if self.open['gaps']:issues.append('observation_gap')
                    if self.open.get('unanchored_command_menus'):issues.append('unanchored_command_menu_before_native_return')
                    if self.pending:issues.append('unresolved_faint_or_pivot_selection')
                    if self.interruptions and not self.resumed:issues.append('forced_selection_return_without_resumed_resolution')
                    if len({a['event_id'] for a in self.resolution})<2:issues.append('insufficient_distinct_resolution_actions')
                    if len({a['event_id'] for a in self.resolution})>4:issues.append('possible_unobserved_command_phase_or_extra_execution_mechanic')
                    start=self.open;segment=dict(id='visual-turn:'+digest([self.battle_id,start['frames'],first['id']]),
                        battle_id=self.battle_id,local_index=len(self.segments)+1,game_turn_number=None,start=start['bounds'],end=deepcopy(self.candidate_bound),
                        command_start_time=start['first_time'],next_command_time=first['timestamp'],
                        status='ambiguous' if 'possible_unobserved_command_phase_or_extra_execution_mechanic' in issues else 'confirmed' if not issues else 'supported_but_incomplete',reasons=issues,
                        frames=start['frames']+[a['frame_id'] for a in self.resolution]+[first['id'],oid],
                        actions=deepcopy(self.resolution),gaps=deepcopy(start['gaps']),interruptions=deepcopy(start['interruptions']),
                        transition_sequence=['NORMAL_COMMAND','TURN_RESOLUTION','NORMAL_COMMAND'],
                        excluded_interpretations=['submenu_return: live move executions intervened while normal controls were absent',
                            'isolated COMMAND/message visibility: native controls and sustained context-dependent evidence required'],
                        numbering_scope='local observed segment; no unseen turns or absolute game number invented',counter_evidence=[])
                    if start.get('unanchored_command_menus'):
                        segment['end'][0]=min(segment['end'][0],start['unanchored_command_menus'][0]['bounds'][0])
                        segment['unanchored_command_menus']=deepcopy(start['unanchored_command_menus'])
                    self.segments.append(segment);self.open=None;self.resolution=[];self.interruptions=[];self.pending=False;self.resumed=False
                if self.open is None:
                    self.pending=False;self.interruptions=[];self.resumed=False
                    first=self.candidate[0];self.open=dict(frames=[first['id'],oid],first_time=first['timestamp'],
                        bounds=deepcopy(self.candidate_bound),gaps=[],interruptions=[])
        elif self.resolution and signals.get('battle_view'):
            phase='TURN_RESOLUTION';self.candidate=[]
        elif self.open and not self.resolution and signals.get('command_label') and not signals.get('overlay'):
            phase='COMMAND_SUBMENU';reasons.append('command_label_support_only; no new turn')
        elif signals.get('battle_end'):
            phase='POST_TURN_TRANSITION'
            if self.open:reasons.append('battle_ended_without_next_normal_command; terminal_segment_incomplete')
        else:self.candidate=[]
        if signals.get('battle_end'):
            self.terminal=True;phase='POST_TURN_TRANSITION';self.candidate=[]
            reasons.append('battle_ended_without_next_normal_command; terminal_segment_incomplete')
        if self.profile=='v2' and anchored_command and not (support or {}).get('qualified') and phase=='NORMAL_COMMAND':phase='COMMAND_SUBMENU'
        # Message geometry or animation alone does not create resolution evidence.
        self.phase=phase;record=dict(frame_id=oid,timestamp=t,phase=phase,previous_phase=old,reasons=reasons,
            signals=signals,command_support=support,source_id=o.get('source_id'),gap=gap,possible_phases=[phase] if phase!='UNKNOWN' else ['UNKNOWN','TURN_RESOLUTION' if self.resolution else 'COMMAND_SUBMENU'])
        self.history.append(record);self.last=o;return deepcopy(record)

    def export(self):
        return dict(battle_id=self.battle_id,profile=self.profile,phase_history=deepcopy(self.history),segments=deepcopy(self.segments),gaps=deepcopy(self.gaps),
            incomplete_tail=deepcopy(self.open),unclosed_resolution_actions=deepcopy(self.resolution),uses_battle_log=False,terminal_observed=self.terminal)
