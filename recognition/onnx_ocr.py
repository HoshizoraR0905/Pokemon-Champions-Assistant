"""Opt-in PP-OCR ONNX experiment; never silently selects an execution provider.

The published Paddle model's BGR resize/normalization and CTC dictionary are
used directly. Provider assignment and Core ML compute plans require separate
profiling; requesting Core ML does not prove GPU/ANE execution.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import time

import cv2
import numpy as np
from models import Observation, RawOCR


class ONNXOCRBackend:
    def __init__(self, directory, *, provider='cpu', batch_size=1,
                 compute_units='ALL', profile_prefix=None):
        import onnxruntime as ort
        import yaml
        if provider not in {'cpu','coreml'} or batch_size < 1:
            raise ValueError('Invalid ONNX provider/batch size')
        directory = Path(directory)
        manifest = json.loads((directory/'local-manifest.json').read_text())
        for name,digest in manifest['files'].items():
            if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:
                raise ValueError(f'ONNX asset checksum mismatch: {name}')
        config = yaml.safe_load((directory/'inference.yml').read_text())
        self.model_name = config['Global']['model_name']+'-onnx-'+provider
        self.characters = ['blank']+config['PostProcess']['character_dict']+[' ']
        self.batch_size, self.threshold = batch_size, .75
        self.language, self.warnings = 'zh-Hans+en', []
        self.requested_provider, self.compute_units = provider, compute_units
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        if profile_prefix:
            options.enable_profiling = True
            options.profile_file_prefix = str(profile_prefix)
        providers = ['CPUExecutionProvider']
        if provider=='coreml':
            if 'CoreMLExecutionProvider' not in ort.get_available_providers():
                raise ValueError('This ONNX Runtime build has no CoreML provider')
            options.log_severity_level = 0
            providers.insert(0, ('CoreMLExecutionProvider', {
                'ModelFormat':'MLProgram', 'MLComputeUnits':compute_units,
                'RequireStaticInputShapes':'0', 'EnableOnSubgraphs':'0',
                'ProfileComputePlan':'1',
                'ModelCacheDirectory':str(directory/'coreml-cache'/manifest['files']['inference.onnx'][:16]),
            }))
        self.session = ort.InferenceSession(str(directory/'inference.onnx'),
                                            sess_options=options, providers=providers)
        self.active_providers = self.session.get_providers()
        if provider=='coreml' and 'CoreMLExecutionProvider' not in self.active_providers:
            raise RuntimeError('CoreML session fell back during initialization')
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, crops):
        results = []
        for start in range(0,len(crops),self.batch_size):
            group = crops[start:start+self.batch_size]
            width = min(3200,max(320,max(int(48*c.shape[1]/c.shape[0]) for c in group)))
            batch = np.zeros((len(group),3,48,width),dtype=np.float32)
            for i,crop in enumerate(group):
                resized_w = min(width,math.ceil(48*crop.shape[1]/crop.shape[0]))
                normalized = cv2.resize(crop,(resized_w,48)).astype(np.float32).transpose(2,0,1)/127.5-1
                batch[i,:,:,:resized_w] = normalized
            output = self.session.run(None,{self.input_name:batch})[0]
            if output.shape[-1] != len(self.characters):
                raise ValueError('CTC dictionary does not match ONNX output')
            for probabilities in output:
                ids = probabilities.argmax(axis=-1)
                scores = probabilities.max(axis=-1)
                selected = np.r_[True,ids[1:]!=ids[:-1]] & (ids!=0)
                text = ''.join(self.characters[i] for i in ids[selected])
                results.append({'text':text,'confidence':float(scores[selected].mean()) if selected.any() else 0.})
        return results

    def read(self,image,box,numeric=False,multiline=False,italic=False):
        x1,y1,x2,y2 = box
        crop = image[y1:y2,x1:x2]
        if crop.size==0:
            return Observation(region=box)
        # Same multiline preprocessing as the existing Paddle CPU adapter.
        if multiline:
            gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            active = (gray>190).sum(axis=1)>max(2,crop.shape[1]*.012)
            transitions = np.diff(np.r_[False,active,False].astype('int8'))
            segments = [(a,b) for a,b in zip(np.where(transitions==1)[0],np.where(transitions==-1)[0]) if b-a>=5]
            crops = [crop[max(0,a-2):min(crop.shape[0],b+2)] for a,b in segments] or [crop]
        else:
            crops = [crop]
        started = time.perf_counter()
        tokens = self.predict(crops)
        self.last_latency_ms = (time.perf_counter()-started)*1000
        text = '\n'.join(t['text'] for t in tokens)
        text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])','',text)
        confidence = sum(len(t['text'])*t['confidence'] for t in tokens)/max(1,sum(len(t['text']) for t in tokens))
        return Observation(text if text and confidence>=self.threshold else None,
                           round(confidence,3),box,text,
                           raw_ocr=RawOCR(text,round(confidence,3),box,self.language,
                                          engine=self.model_name,tokens=tokens))

    def end_profile(self):
        return self.session.end_profiling()
