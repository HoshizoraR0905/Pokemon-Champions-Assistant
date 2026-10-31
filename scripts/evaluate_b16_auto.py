"""Sealed live predictions versus independent automatic Battle Log evidence.
No annotations, prediction edits, UI or shared live state in the reference pass.
"""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
import platform
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.fast_video import CachedOCR, digest
from recognition.event_report import verify_seal
from recognition.battle_log import detect_log,extract_view,assemble_views
from recognition.log_comparison import align,compact
from battle_events.parser import EventParser

TYPES={'move_execution','switch_out','send_out','faint','status_change','weather_change','terrain_change','transformation','stat_change','ability_activation','item_activation','move_effect','critical_hit','multi_hit','effectiveness','side_condition_change','trick_room_change','item_change','position_change'}

def read(path):return json.loads(path.read_text())
def csv_write(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def reference(owner,run):
    source=owner.cache('event-driven/'+run);verify_seal(source)
    out=owner.cache('evaluation/'+run+'/auto-reference');out.mkdir(parents=True,exist_ok=True)
    identity={p:digest(ROOT/p) for p in ['scripts/evaluate_b16_auto.py','recognition/battle_log.py','battle_events/parser.py','recognition/log_comparison.py']}
    identity['observations']=digest(source/'observations.json')
    manifest=out/'manifest.json'
    if manifest.exists():
        old=read(manifest)
        if old['identity']!=identity:raise ValueError('Reference identity changed; preserve existing run')
        if old['status']=='complete':return read(out/'reference.json')
    start=time.perf_counter();atomic_json(manifest,dict(identity=identity,status='running'))
    import cv2
    counts=Counter();ocr=CachedOCR(out,counts);views=[];timings=[]
    rows=read(source/'observations.json')['observations']
    for i,row in enumerate(rows):
        began=time.perf_counter();cache=out/'views'/f'{i:06d}.json'
        if cache.exists():view=read(cache)
        else:
            image=cv2.imread(str(ROOT/row['image']))
            if image is None:raise FileNotFoundError(row['image'])
            # Independent geometric detection; do not rely on Pass A overlay labels.
            geometry=detect_log(image)
            view=None
            if geometry:
                ocr.source=row['source_id'];ocr.timestamp=row['timestamp']
                from recognition.fast_profile import RegionGate
                ocr.gate=RegionGate(.004)
                view=extract_view(image,ocr,row['source_id'],row['timestamp'],row['sha256'])
                view['image']=row['image']
            atomic_json(cache,view)
        timings.append(dict(timestamp=row['timestamp'],seconds=time.perf_counter()-began))
        if view:views.append(view)
        if i%100==0:
            atomic_json(manifest,dict(identity=identity,status='running',completed_frames=i+1,views=len(views)))
            print('Independent log scan',i+1,'views',len(views),flush=True)
    entries,issues=assemble_views(views,ignore_partial_overlap=True)
    observations={r['observation_id']:r for v in views for r in v['observations']}
    parser=EventParser();events=[]
    for entry in entries:
        selected=observations[entry['selected_observation_id']]
        entry.update(partial=selected['partial'],inspection_timestamp=selected['timestamp'],original_event_time=None)
        events.append(parser.parse(entry,battle_id=owner.battle_id).to_dict())
    result=dict(entries=entries,event_candidates=events,views=views,assembly_issues=issues,timings=timings,
                wall_seconds=time.perf_counter()-start,counts=dict(counts),coverage='saved inspected frames only; no whole-log completeness claim')
    atomic_json(out/'reference.json',result);atomic_json(manifest,dict(identity=identity,status='complete',sha256=digest(out/'reference.json')))
    verify_seal(source);return result


def validate_reference(entry,event,raw):
    reasons=[]
    if entry.get('partial'):reasons.append('partial_log_row')
    if entry.get('ocr_confidence',0)<.95:reasons.append('low_log_ocr_confidence')
    if not isinstance(entry.get('turn'),int) or entry['turn']<1:reasons.append('invalid_turn')
    if event['event_type'] not in TYPES:reasons.append('unsupported_log_semantics')
    if event['event_type'] in {'move_execution','switch_out','send_out','faint','status_change','transformation','stat_change'}:
        if not (event.get('actor') or {}).get('species_id'):reasons.append('unresolved_log_actor')
    if event['event_type']=='move_execution' and not event.get('canonical_references',{}).get('move'):reasons.append('unresolved_log_move')
    if any(u not in {'actor_variant_unresolved','target_not_in_entry','target_unresolved','side_unknown'} for u in event.get('uncertainty',[])):
        reasons.append('log_semantic_uncertainty')
    variants={compact(t) for t in entry.get('text_variants',[])}
    if len(variants)>1:reasons.append('log_ocr_variants_disagree')
    sources={v['source_id'] for v in raw['views'] if v.get('turn')==entry['turn']}
    if any(i['source_id'] in sources for i in raw['assembly_issues']):reasons.append('turn_scroll_assembly_uncertain')
    return reasons


def evaluate(owner,run,ref):
    source=owner.cache('event-driven/'+run);evaluation=owner.cache('evaluation/'+run)
    out=owner.report('evaluation/'+run);out.mkdir(parents=True,exist_ok=True)
    replay=read(source/'replay.json');pred=[r['bindings'].get('resolved_event') or r['event'] for r in replay['history']]
    gameplay=[e for e in pred if e['event_type'] in TYPES or e['event_type']=='unknown']
    comparison=align(ref['entries'],ref['event_candidates'],gameplay)
    rows=[];used=set();counts=defaultdict(Counter)
    for entry,event,c in zip(ref['entries'],ref['event_candidates'],comparison['comparisons']):
        reasons=validate_reference(entry,event,ref);p=c['prediction'];status='uncertain';reason=';'.join(reasons)
        if not reasons:
            if c['status']=='provisional_match':
                missing=[role for role in ['actor','target'] if event.get(role) and not p.get(role)]
                if missing:reason='unverified_prediction_roles:'+','.join(missing)
                elif event['side'] not in {'unknown','field'} and p['side']=='unknown':reason='unverified_prediction_side'
                else:status='TP';reason='ordered_semantic_agreement_on_observed_fields'
            elif c['status']=='missing_logged_event':status='FN';reason='no_supported_ordered_prediction_match; possible_live_miss_or_reference_error'
            else:reason=c['status']+'; alignment_or_attribution_uncertain'
        if p:used.add(p['event_id'])
        counts[event['event_type']][status]+=1
        rows.append(dict(prediction_id=p['event_id'] if p else '',reference_id=entry['entry_id'],event_type=event['event_type'],
            video_timestamp=p['attributes'].get('observation_time','') if p else '',log_inspection_timestamp=entry['inspection_timestamp'],
            turn=entry.get('turn'),validation_status=status,mismatch_reason=reason,reference_source=entry['source_id'],
            live_ocr=p['original_text'] if p else '',log_ocr=entry['raw_text'],
            prediction=json.dumps(p,ensure_ascii=False),reference=json.dumps(event,ensure_ascii=False),
            unverified_fields='exact_hp;instance_slot;original_log_action_time'+(';live_turn' if not p or p['attributes'].get('turn') is None else '')+
              (';target' if not event.get('target') else '')+(';side' if event['side']=='unknown' else '')))
    for p in gameplay:
        if p['event_id'] in used:continue
        rows.append(dict(prediction_id=p['event_id'],reference_id='',event_type=p['event_type'],video_timestamp=p['attributes'].get('observation_time',''),
            log_inspection_timestamp='',turn='',validation_status='unverified',mismatch_reason='log_coverage_or_alignment_not_established; cannot_count_FP',
            reference_source='',live_ocr=p['original_text'],log_ocr='',prediction=json.dumps(p,ensure_ascii=False),reference='',unverified_fields='all'))
    fields=['prediction_id','reference_id','event_type','video_timestamp','log_inspection_timestamp','turn','validation_status','mismatch_reason','reference_source','live_ocr','log_ocr','prediction','reference','unverified_fields']
    csv_write(out/'event_validation.csv',rows,fields)
    metrics={}
    for typ in sorted(TYPES|set(counts)):
        c=counts[typ];n=c['TP']+c['FN'];metrics[typ]=dict(TP=c['TP'],FN=c['FN'],FP=None,uncertain=c['uncertain'],precision=None,recall=c['TP']/n if n else None,F1=None)
    total=Counter()
    for c in counts.values():total.update(c)
    n=total['TP']+total['FN']
    result=dict(metrics=metrics,total=dict(TP=total['TP'],FN=total['FN'],FP=None,precision=None,recall=total['TP']/n if n else None,F1=None),
        reference_entries=len(ref['entries']),reference_eligible=n,reference_uncertain=total['uncertain'],
        live_gameplay_candidates=len(gameplay),live_matched=sum(r['validation_status']=='TP' for r in rows),
        live_unverified=sum(r['validation_status'] in {'uncertain','unverified'} and bool(r['prediction_id']) for r in rows),
        coverage=total['TP']/len(gameplay) if gameplay else None,
        limitation='No proven exhaustive Battle Log coverage or independent original event times: FP, precision and F1 unavailable. TP/FN are automatic reference comparisons, not human-labelled accuracy.')
    atomic_json(out/'validation.json',result)
    return out,rows,result


def performance(owner,run,out,validation_rows,result,ref):
    source=owner.cache('event-driven/'+run);evaluation=owner.cache('evaluation/'+run)
    manifest=read(source/'manifest.json');duration=manifest['decoder']['container_duration_seconds']
    segment=evaluation/'profiler/segment-0000';profile=read(segment/'profiler.json')
    operations=[json.loads(s) for s in (segment/'operations.jsonl').read_text().splitlines()]
    frames=[json.loads(s) for s in (segment/'frames.jsonl').read_text().splitlines()]
    pipeline=next(o for o in operations if o['module']=='pipeline');wall=pipeline['inclusive_seconds']
    bins=[dict(start=i*10,end=min(duration,(i+1)*10),attributed_seconds=0.,shared_seconds=0.,sampled_frames=0,events=[],issues=[]) for i in range(math.ceil(duration/10))]
    modules=defaultdict(list);shared=0.
    for op in operations:
        sec=op['exclusive_seconds'];modules[op['module']].append(sec)
        t=(op.get('source') or {}).get('timestamp')
        if isinstance(t,(int,float)) and 0<=t<duration:bins[min(len(bins)-1,int(t//10))]['attributed_seconds']+=sec
        else:shared+=sec
    # Exclusive spans remove child instrumentation costs. Reconcile the measured
    # pipeline wall once; shared startup/export/overhead has no true source time.
    attributed=sum(b['attributed_seconds'] for b in bins)
    shared=wall-attributed
    if shared<0:raise ValueError('Exclusive timing exceeds pipeline wall')
    for b in bins:b['shared_seconds']=shared*(b['end']-b['start'])/duration
    for f in frames:
        bins[min(len(bins)-1,int(f['timestamp']//10))]['sampled_frames']+=1
    replay=read(source/'replay.json')
    for r in replay['history']:
        e=r['event'];t=e['attributes'].get('observation_time')
        if e['event_type'] in TYPES and t is not None:bins[min(len(bins)-1,int(t//10))]['events'].append(e['event_type'])
    for r in validation_rows:
        if r['validation_status']=='TP':continue
        t=r['video_timestamp']
        if isinstance(t,(int,float)):bins[min(len(bins)-1,int(t//10))]['issues'].append(r['validation_status']+':'+r['mismatch_reason'])
    export=[]
    for b in bins:
        seconds=b['attributed_seconds']+b['shared_seconds']
        export.append(dict(video_start=b['start'],video_end=b['end'],processing_seconds=seconds,PTR=seconds/(b['end']-b['start']),
            source_attributed_seconds=b['attributed_seconds'],allocated_shared_seconds=b['shared_seconds'],sampled_frames=b['sampled_frames'],
            event_count=len(b['events']),major_events=json.dumps(dict(Counter(b['events'])),ensure_ascii=False),
            uncertain_or_errors=json.dumps(dict(Counter(b['issues'])),ensure_ascii=False)))
    csv_write(out/'processing_per_10s.csv',export,list(export[0]))
    import numpy as np,cv2
    cap=cv2.VideoCapture(str(owner.video()));fps=cap.get(cv2.CAP_PROP_FPS);source_count=cap.get(cv2.CAP_PROP_FRAME_COUNT);cap.release()
    ptrs=[r['PTR'] for r in export]
    perf=dict(video_seconds=duration,pipeline_wall_seconds=wall,PTR=wall/duration,P50=float(np.percentile(ptrs,50)),P95=float(np.percentile(ptrs,95)),maximum=max(ptrs),
        sampled_frames=len(frames),actual_sample_fps=len(frames)/duration,source_fps=fps,source_frames=source_count,
        shared_seconds=shared,profiler_overhead=profile['measured_recording_overhead_seconds'],reference_wall_seconds=ref['wall_seconds'],
        stages={k:dict(total=sum(v),P50=float(np.percentile(v,50)),P95=float(np.percentile(v,95)),maximum=max(v),calls=len(v)) for k,v in modules.items()})
    atomic_json(out/'performance.json',perf)
    env=read(evaluation/'environment.json');top=sorted(export,key=lambda b:b['PTR'],reverse=True)[:5]
    lines=['# B16 自动事件交叉核验与处理性能评测','',
        '**原始冻结版本；Battle Log 自动交叉核验结果。没有人工标注或人工核验。**','',
        f"录像 {duration:.2f}s，原始 {fps:.3f} FPS / {int(source_count)} 帧；采样 {len(frames)} 帧，实际 {len(frames)/duration:.3f} FPS。运行 ID `{run}`。",
        f"环境：Apple M1 Pro / 16 GiB RAM；{env['platform']}；Python {env['python'].split()[0]}；PP-OCRv6 ONNX CPU。完整依赖与工作树版本保存在 execution/environment/frozen-source。评测期间另运行了0.94秒的41项工具测试，系统负载和文件缓存未隔离；这是单次测量，不给性能提升或置信区间。",'',
        f"正常解析、状态重建和产物导出实测 {wall:.3f}s；总体 PTR **{wall/duration:.4f} 秒/视频秒**。10秒区间 PTR：P50 **{perf['P50']:.4f}**，P95 **{perf['P95']:.4f}**，最大 **{perf['maximum']:.4f}**。",
        f"Battle Log 独立提取另耗时 {ref['wall_seconds']:.3f}s，不计入正常管线 PTR。",'',
        '计时使用 time.perf_counter。任务按输入帧/事件的原始时间戳归属一个区间，跨界任务整体归入输入区间；递归调用只累计 exclusive 时间。无唯一源时间的初始化、批处理、导出及计时开销按区间视频时长分摊，CSV 单列给出，不能视作当地事件的实际耗时。各区间之和等于正常管线 wall。FFmpeg 并发解码仅计主线程等待，不重复加解码 CPU 时间。PTR 为离线吞吐指标，不代表实时端到端延迟。','',
        f"日志提取 {len(ref['views'])} 个候选画面，{len(ref['entries'])} 条合并记录；可核验参考 {result['reference_eligible']}，uncertain {result['reference_uncertain']}。正常管线主要事件候选 {result['live_gameplay_candidates']}，匹配 {result['live_matched']}，未核验 {result['live_unverified']}；自动匹配覆盖率 {result['coverage'] if result['coverage'] is not None else 'N/A'}。精确 HP、未显示的目标/角色、原事件时间及未观测回合不纳入字段准确率。",'',
        '参考有效性检查：完整行、OCR≥0.95、合法回合、规范名称与事件类型、结构化不确定字段、跨画面文字一致性及滚动拼接冲突。不能确认的记录保留 uncertain；时间戳是日志查看时间，不作为原行动时间。共享 OCR 模型、词典及解析器可产生相关错误，双方一致不构成独立真值。','',
        '| 类别 | TP | FN | FP | Precision | Recall | F1 | uncertain |','|---|---:|---:|---|---|---|---|---:|']
    def fmt(v):return 'N/A' if v is None else f'{v:.4f}'
    for typ,m in [('总体',dict(result['total'],uncertain=result['reference_uncertain'])),*result['metrics'].items()]:
        lines.append(f"| {typ} | {m['TP']} | {m['FN']} | N/A | N/A | {fmt(m['recall'])} | N/A | {m['uncertain']} |")
    lines+=['','未证明日志全覆盖，也没有独立的原事件时间边界，因此未匹配预测不能直接算 FP，Precision/F1 无法可靠估计。FN 是可靠日志行没有有序预测匹配的自动候选，仍可能源于日志自身错误。不得据此宣称整体绝对识别准确率。','',
        '| 高 PTR 区间 | 秒 | PTR | 采样帧 | 事件 |','|---|---:|---:|---:|---|']
    for b in top:lines.append(f"| {b['video_start']:.0f}–{b['video_end']:.2f} | {b['processing_seconds']:.3f} | {b['PTR']:.4f} | {b['sampled_frames']} | {b['major_events']} |")
    lines+=['','复杂事件依据识别到的 faint/send_out/switch_out/transformation/status_change 记录定位，详见逐10秒 CSV；未核验不能解释为无错误。高耗时与事件共现不证明因果。','',
        '模块独占耗时（嵌套子调用单独列出，不应把父级 inclusive 时间相加）：','']
    for k,v in sorted(perf['stages'].items(),key=lambda kv:kv[1]['total'],reverse=True)[:12]:lines.append(f"- {k}: {v['total']:.3f}s，调用P50/P95 {v['P50']:.6f}/{v['P95']:.6f}s，最大 {v['maximum']:.6f}s。")
    lines+=['','简历可用表述：',f"- 构建可复现的视频解析与状态追踪自动评测流程，在新增 {duration/60:.2f} 分钟录像上实测处理时间比 PTR 为 {wall/duration:.3f} 秒/视频秒，并输出逐10秒性能与事件核验记录。",
        '- 结合独立 Battle Log 提取、参考有效性检查和有序事件匹配，自动区分可核验、歧义与覆盖不足的记录，保留原始预测及完整证据链。','',
        '产物：[事件明细](event_validation.csv) · [逐10秒性能](processing_per_10s.csv) · [分类核验JSON](validation.json) · [模块性能JSON](performance.json)。']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    verify_seal(source)
    print(json.dumps(dict(output=str(out),validation=result,performance={k:v for k,v in perf.items() if k!='stages'}),ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--battle',default='sample_battle_16');p.add_argument('--run-id',required=True);a=p.parse_args()
    owner=BattleArtifacts(a.battle);ref=reference(owner,a.run_id);out,rows,result=evaluate(owner,a.run_id,ref);performance(owner,a.run_id,out,rows,result,ref)
if __name__=='__main__':main()
