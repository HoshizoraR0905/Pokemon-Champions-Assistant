"""Reproducible OCR/icon/fusion benchmark on manually annotated game captures."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from knowledge import KnowledgeBase
from models import Observation
from recognition.ocr import OCR
from recognition.paddle_ocr import PaddleOCRBackend
from recognition.icons import IconRecognizer
from recognition.entities import EntityResolver
from recognition.identity import combine_identity


def levenshtein(a,b):
    prior=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        current=[i]
        for j,y in enumerate(b,1):current.append(min(current[-1]+1,prior[j]+1,prior[j-1]+(x!=y)))
        prior=current
    return prior[-1]


def evaluate(backend,truth,images,kb,icons):
    ocr=OCR() if backend=='tesseract' else PaddleOCRBackend(backend,numeric_backend=None)
    resolver=EntityResolver(kb)
    rows=[];icon_cache={};start=time.perf_counter()
    for n,r in enumerate(truth['regions']):
        image=images[r['image']];box=tuple(r['box']);key=(r['image'],r['region'])
        if r['kind']=='icon':
            if key not in icon_cache:icon_cache[key]=icons.identify(image,box) if icons else None
            icon=icon_cache[key]
            got=icon.species_id if icon and icon.status=='resolved' else None
            row={**r,'predicted':got,'predicted_form_id':icon.form_id if icon else None,
                 'icon_status':icon.status if icon else 'unavailable',
                 'candidates':[{'asset':c.asset,'species_id':c.species_id,'form_id':c.form_id,'similarity':c.similarity}
                               for c in icon.candidates[:3]] if icon else [],
                 'latency_ms':icon.latency_ms if icon else 0}
        else:
            numeric=r['kind']=='numeric'
            t=time.perf_counter()
            obs=ocr.read(image,box,numeric=numeric,italic=(r['region'].startswith('own_name') or r['region'].startswith('opponent_name')))
            elapsed=(time.perf_counter()-t)*1000
            row={**r,'predicted':obs.raw_text,'confidence':obs.confidence,'latency_ms':round(elapsed,2)}
            if r['kind']=='species_text':
                result=resolver.resolve(obs,'species',region_kind='species')
                row['text_species_id']=result.resolution.species_id if result.resolution.status=='resolved' else None
                row['text_form_id']=result.resolution.form_id if result.resolution.status=='resolved' else None
                region=r['region']
                icon_region=(region.replace('team_name_','own_icon_').replace('config_name_','config_icon_')
                             .replace('own_name_','own_icon_').replace('opponent_name_','opponent_icon_'))
                if r['image'].startswith(('team_','m12_video_')) and region.startswith('config_name_'):
                    icon_region=region.replace('config_name_','config_icon_')
                ikey=(r['image'],icon_region)
                if ikey not in icon_cache:
                    related=next((x for x in truth['regions'] if x['image']==r['image'] and x['region']==icon_region),None)
                    icon_cache[ikey]=icons.identify(image,tuple(related['box'])) if related and icons else None
                combined=combine_identity(result,icon_cache[ikey],kb)
                row['combined_species_id']=combined.resolution.species_id if combined.resolution.status=='resolved' else None
                row['combined_form_id']=combined.resolution.form_id if combined.resolution.status=='resolved' else None
                row['combined_status']=combined.resolution.status
                row['combined_method']=combined.resolution.method
        rows.append(row)
        if (n+1)%25==0:print(backend,n+1,'/',len(truth['regions']),flush=True)
    metrics={}
    for split in sorted(set(r['split'] for r in rows)):
        subset=[r for r in rows if r['split']==split];metrics[split]={}
        for kind in sorted(set(r['kind'] for r in subset)):
            group=[r for r in subset if r['kind']==kind]
            if kind=='icon':
                metrics[split][kind]=({'count':len(group),'evaluated':False} if icons is None else
                    {'count':len(group),'evaluated':True,
                     'species_accuracy':sum(r['predicted']==r['species_id'] for r in group)/len(group),
                     'false_id_rate':sum(r['predicted'] is not None and r['predicted']!=r['species_id'] for r in group)/len(group),
                     'unresolved_rate':sum(r['predicted'] is None for r in group)/len(group)})
                forms=[r for r in group if r['form_id'] is not None]
                if forms and icons is not None:
                    metrics[split][kind]['form_count']=len(forms)
                    metrics[split][kind]['species_and_form_accuracy']=sum(
                        r['predicted']==r['species_id'] and r['predicted_form_id']==r['form_id'] for r in forms)/len(forms)
            else:
                metrics[split][kind]={'count':len(group),
                    'exact_accuracy':sum(r['predicted']==r['expected'] for r in group)/len(group),
                    'cer':sum(levenshtein(r['expected'],r['predicted']) for r in group)/sum(len(r['expected']) for r in group)}
                if kind=='species_text':
                    for label,key in [('text','text_species_id'),('combined','combined_species_id')]:
                        metrics[split][kind][label+'_species_accuracy']=sum(r[key]==r['species_id'] for r in group)/len(group)
                        metrics[split][kind][label+'_false_id_rate']=sum(r[key] is not None and r[key]!=r['species_id'] for r in group)/len(group)
                        metrics[split][kind][label+'_unresolved_rate']=sum(r[key] is None for r in group)/len(group)
                    forms=[r for r in group if r['form_id'] is not None]
                    if forms and icons is not None:
                        metrics[split][kind]['form_count']=len(forms)
                        metrics[split][kind]['combined_species_and_form_accuracy']=sum(
                            r['combined_species_id']==r['species_id'] and
                            r['combined_form_id']==r['form_id'] for r in forms)/len(forms)
        metrics[split]['latency_ms_per_region_median']=round(statistics.median(r['latency_ms'] for r in subset),2)
        metrics[split]['latency_ms_per_region_mean']=round(statistics.mean(r['latency_ms'] for r in subset),2)
    return {'backend':backend,'metrics':metrics,'rows':rows,'elapsed_s':round(time.perf_counter()-start,2),
            'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576,1),
            'ocr_model':getattr(ocr,'model_name','tesseract'), 'warnings':ocr.warnings}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=['tesseract','paddle-v5','paddle-v6'],required=True)
    p.add_argument('--truth',type=Path,default=Path('tests/fixtures/m12_ground_truth.json'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--no-icons',action='store_true')
    a=p.parse_args();truth=json.loads(a.truth.read_text());images={}
    for name,meta in truth['images'].items():
        path=a.truth.parent/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('Fixture checksum mismatch: '+name)
        images[name]=cv2.imread(str(path))
    kb=KnowledgeBase();icons=None if a.no_icons else IconRecognizer()
    data={'platform':{'machine':platform.machine(),'processor':platform.processor(),'python':platform.python_version()},
          'ground_truth_sha256':hashlib.sha256(a.truth.read_bytes()).hexdigest(),
          **evaluate(a.backend,truth,images,kb,icons)}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(a.output,'elapsed',data['elapsed_s'],'seconds',flush=True)


if __name__=='__main__':main()
