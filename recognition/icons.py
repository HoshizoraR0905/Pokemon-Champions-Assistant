"""Independent Champions UI sprite recognition; no text or roster filtering."""
import hashlib
import json
from pathlib import Path
import time
import cv2
import numpy as np
from models import IconCandidate, IconEvidence

DEFAULT_CACHE=Path(__file__).resolve().parents[1]/'.cache/champions-icons'


class IconRecognizer:
    def __init__(self,directory=None,*,minimum=.80,margin=.10,max_height=64):
        self.directory=Path(directory) if directory else DEFAULT_CACHE
        self.minimum,self.margin,self.max_height=minimum,margin,max_height
        index_path=self.directory/'index.json'
        if not index_path.exists():raise ValueError('Icon cache missing; see scripts/retrieve_visuals.py')
        index=json.loads(index_path.read_text());self.source=index['source']
        self.templates=[];self.banks={};self.warnings=[]
        for ref in index['assets']:
            path=self.directory/ref['file']
            if not path.exists():
                self.warnings.append(f'Missing visual asset: {ref["file"]}');continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
                raise ValueError(f'Visual asset checksum mismatch: {ref["file"]}')
            rgba=cv2.imread(str(path),cv2.IMREAD_UNCHANGED)
            if rgba is None or rgba.ndim!=3 or rgba.shape[2]!=4:
                raise ValueError(f'Expected transparent RGBA PNG: {path}')
            x,y,w,h=cv2.boundingRect((rgba[:,:,3]>32).astype('uint8'))
            if w and h:self.templates.append((ref,rgba[y:y+h,x:x+w]))

    def _bank(self,height,width):
        key=(height,width)
        if key not in self.banks:
            bank=[]
            for ref,rgba in self.templates:
                variants=[]
                for scale in (.50,.62,.74,.86,.98):
                    th=round(height*scale);tw=round(rgba.shape[1]*th/rgba.shape[0])
                    if tw>width or tw<8 or th>height:continue
                    template=cv2.resize(rgba,(tw,th),interpolation=cv2.INTER_AREA)
                    if (template[:,:,3]>200).sum()<20:continue
                    variants.append((template,float(scale)))
                bank.append((ref,variants))
            self.banks[key]=bank
        return self.banks[key]

    def identify(self,image,region):
        start=time.perf_counter();x1,y1,x2,y2=region
        result=IconEvidence(region=region,source_commit=self.source['commit'])
        crop=image[y1:y2,x1:x2]
        if not crop.size or crop.shape[0]<12 or crop.shape[1]<12:
            result.reason='crop_too_small';return result
        scale=min(1,self.max_height/crop.shape[0])
        query=cv2.resize(crop,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA).astype('float32')
        if float(np.std(query,axis=(0,1)).max())<8:
            result.reason='insufficient_visual_detail';return result
        ranked=[]
        background=np.median(query.reshape(-1,3),axis=0)
        for ref,variants in self._bank(*query.shape[:2]):
            best=(-1.0,0.0,(0,0))
            for template,template_scale in variants:
                alpha=template[:,:,3:4].astype('float32')/255
                rendered=(template[:,:,:3].astype('float32')*alpha+background*(1-alpha)).astype('uint8')
                # Fast complete-library pass renders transparency against the
                # observed panel color; the shortlist gets masked refinement.
                scores=cv2.matchTemplate(query.astype('uint8'),rendered,cv2.TM_CCOEFF_NORMED)
                scores=np.nan_to_num(scores,nan=-1,posinf=-1,neginf=-1)
                _,value,_,loc=cv2.minMaxLoc(scores)
                if value>best[0]:best=(value,template_scale,loc)
            ranked.append(IconCandidate(ref['canonical_id'],ref['species_id'],ref['form_id'],
                                       ref['file'],round(best[0],5),round(best[1],3),best[2]))
        ranked.sort(key=lambda c:c.similarity,reverse=True)
        # A coarse pass searches the complete library. Refine its shortlist at
        # capture resolution so dark/thin sprites aren't penalized by downsampling.
        shortlist={c.asset for c in ranked[:12]}
        fine_scale=min(1,128/crop.shape[0])
        fine=cv2.resize(crop,None,fx=fine_scale,fy=fine_scale,interpolation=cv2.INTER_AREA).astype('float32')
        refined=[]
        for ref,rgba in self.templates:
            if ref['file'] not in shortlist:continue
            best=(-1.0,0.0,(0,0))
            for template_scale in np.arange(.35,1.001,.025):
                th=round(fine.shape[0]*template_scale)
                tw=round(rgba.shape[1]*th/rgba.shape[0])
                if tw>fine.shape[1] or tw<8:continue
                template=cv2.resize(rgba,(tw,th),interpolation=cv2.INTER_AREA)
                mask=(template[:,:,3]>200).astype('uint8')
                scores=cv2.matchTemplate(fine,template[:,:,:3].astype('float32'),cv2.TM_CCOEFF_NORMED,mask=mask)
                scores=np.nan_to_num(scores,nan=-1,posinf=-1,neginf=-1)
                _,value,_,loc=cv2.minMaxLoc(scores)
                if value>best[0]:best=(value,float(template_scale),loc)
            refined.append(IconCandidate(ref['canonical_id'],ref['species_id'],ref['form_id'],
                          ref['file'],round(best[0],5),round(best[1],3),best[2]))
        ranked=sorted(refined,key=lambda c:c.similarity,reverse=True)
        result.candidates=ranked[:5]
        result.latency_ms=round((time.perf_counter()-start)*1000,2)
        if not ranked or ranked[0].similarity<self.minimum:
            result.reason='below_similarity_threshold';return result
        winner=ranked[0]
        near=[c for c in ranked if winner.similarity-c.similarity<self.margin]
        if not winner.canonical_id or any(c.species_id is None for c in near):
            result.reason='unmapped_visual_identity';return result
        if len({c.species_id for c in near})!=1:
            result.status='ambiguous';result.reason='small_species_margin';return result
        result.species_id=winner.species_id
        if len({c.form_id for c in near})==1:
            result.form_id=winner.form_id;result.canonical_id=winner.canonical_id
        else:
            result.canonical_id=f'pokeapi:species:{winner.species_id}'
            result.reason='species_only_forms_visually_ambiguous'
        result.status='resolved'
        return result


def default_icons():
    if (DEFAULT_CACHE/'index.json').exists():return IconRecognizer()
    return None
