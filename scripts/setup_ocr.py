"""Explicitly retrieve official Paddle recognition weights for offline use."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recognition.paddle_ocr import MODELS, model_path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',choices=list(MODELS)+['all'],default='all')
    a=p.parse_args()
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
    os.environ['PADDLE_PDX_MODEL_SOURCE']='BOS'
    from paddleocr import TextRecognition
    for backend in MODELS if a.backend=='all' else [a.backend]:
        TextRecognition(model_name=MODELS[backend],device='cpu',enable_mkldnn=False,cpu_threads=4)
        root=model_path(backend)
        manifest={'model':MODELS[backend],'package':'paddleocr==3.7.0',
            'source':f'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/{MODELS[backend]}_infer.tar',
            'license':'PaddleOCR Apache-2.0; weights retrieved from official model distribution',
            'files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in root.rglob('*') if p.is_file() and p.name!='local-manifest.json'}}
        (root/'local-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(f'{backend}: ready at {root}')


if __name__=='__main__':main()
