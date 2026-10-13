"""Offline PaddleOCR line recognizer with the existing OCR.read contract.

Downloads are an explicit setup step. No detector is needed for known UI regions.
"""
from pathlib import Path
import hashlib
import json
import re
import time
import cv2
import numpy as np
from models import Observation, RawOCR
from recognition.ocr import OCR

MODELS = {'paddle-v6':'PP-OCRv6_medium_rec', 'paddle-v5':'PP-OCRv5_server_rec'}


def model_path(backend='paddle-v6'):
    return Path.home()/'.paddlex/official_models'/MODELS[backend]


class PaddleOCRBackend:
    def __init__(self, backend='paddle-v6', *, directory=None, threshold=.75,
                 numeric_backend=None, cpu_threads=4):
        if backend not in MODELS or not 0 <= threshold <= 1:
            raise ValueError('Invalid Paddle OCR backend or threshold')
        self.model_name=MODELS[backend]
        self.directory=Path(directory) if directory else model_path(backend)
        if not (self.directory/'inference.json').exists():
            raise ValueError(f'OCR model missing: {self.directory}; run scripts/setup_ocr.py first')
        model_manifest=self.directory/'local-manifest.json'
        if model_manifest.exists():
            pinned=json.loads(model_manifest.read_text())
            if pinned.get('model')!=self.model_name:
                raise ValueError('OCR model provenance does not match selected backend')
            for name,digest in pinned.get('files',{}).items():
                path=self.directory/name
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    raise ValueError(f'OCR model checksum mismatch: {name}')
        from paddleocr import TextRecognition
        self.model=TextRecognition(model_name=self.model_name,model_dir=str(self.directory),
                                   device='cpu',enable_mkldnn=False,cpu_threads=cpu_threads)
        self.threshold=threshold
        self.language='zh-Hans+en'
        self.warnings=[]
        self.numeric_backend=numeric_backend
        self.last_latency_ms=0.0

    def read(self,image,box,numeric=False,multiline=False,italic=False):
        if numeric and self.numeric_backend:
            # Explicit hybrid policy: the evaluated numeric Tesseract adapter.
            result=self.numeric_backend.read(image,box,numeric,multiline,italic)
            self.warnings=list(self.numeric_backend.warnings)
            return result
        x1,y1,x2,y2=box
        crop=image[y1:y2,x1:x2]
        if crop.size==0:return Observation(region=box)
        if multiline:
            # Known message regions may span lines; do not flatten a paragraph.
            gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            white=(gray>190).astype('uint8')
            projection=white.sum(axis=1)
            active=projection>max(2,crop.shape[1]*.012)
            transitions=np.diff(np.r_[False,active,False].astype('int8'))
            segments=[(a,b) for a,b in zip(np.where(transitions==1)[0],np.where(transitions==-1)[0]) if b-a>=5]
            crops=[crop[max(0,a-2):min(crop.shape[0],b+2)] for a,b in segments] or [crop]
        else:crops=[crop]
        start=time.perf_counter()
        try:
            results=list(self.model.predict(crops,batch_size=1))
        except (RuntimeError,ValueError) as exc:
            self.warnings.append(f'Paddle OCR failed: {exc}')
            return Observation(region=box)
        self.last_latency_ms=(time.perf_counter()-start)*1000
        tokens=[{'text':r['rec_text'],'confidence':float(r['rec_score'])} for r in results]
        text='\n'.join(t['text'] for t in tokens)
        text=re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])','',text)
        confidence=sum(len(t['text'])*t['confidence'] for t in tokens)/max(1,sum(len(t['text']) for t in tokens))
        return Observation(text if text and confidence>=self.threshold else None,
                           round(confidence,3),box,text,raw_ocr=RawOCR(text,round(confidence,3),box,
                           self.language,engine=self.model_name,tokens=tokens))


def create_ocr(backend='auto',language='chi_sim+eng',*,directory=None):
    if backend=='tesseract':return OCR(language)
    if backend=='auto':
        try:
            if (model_path()/'inference.json').exists():
                return PaddleOCRBackend()
        except (ImportError,ValueError,RuntimeError):
            pass
        ocr=OCR(language)
        ocr.warnings.append('PP-OCRv6 unavailable locally; using Tesseract. Run scripts/setup_ocr.py for improved Chinese OCR.')
        return ocr
    return PaddleOCRBackend(backend,directory=directory)
