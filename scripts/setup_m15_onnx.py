"""Explicit pinned ONNX asset download; streaming never downloads models."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

MODELS = {
    'medium': ('50c7eacafc52fa7bcf4194e8cd08e46f8558504b', {
        'inference.onnx':'9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba',
        'inference.yml':'991b700facf5b50a7de193468207d5f4255b538dde0d312ae3b7c7a9b6873129'}),
    'tiny': ('2612ab37152ae0a677521bae4e1e3d4fb4cf7c30', {
        'inference.onnx':'9ef676d6ed3c88256a2d92c640c44f25b0c40947e111b14b8be8f594091563e6',
        'inference.yml':'66170210bad538e83fff3c4a3867e547d6bf20b50d64b20347c4b913f3034ea1'}),
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',choices=MODELS,default='medium')
    parser.add_argument('--directory',type=Path)
    args=parser.parse_args()
    directory=args.directory or Path(f'.cache/m15-onnx-{args.size}')
    directory.mkdir(parents=True,exist_ok=True)
    revision,files=MODELS[args.size]
    source=f'https://huggingface.co/PaddlePaddle/PP-OCRv6_{args.size}_rec_onnx'
    for name,digest in files.items():
        target=directory/name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==digest:
            continue
        partial=directory/(name+'.partial')
        subprocess.run(['curl','-fsSL','--max-time','180',f'{source}/resolve/{revision}/{name}',
                        '-o',str(partial)],check=True)
        if hashlib.sha256(partial.read_bytes()).hexdigest()!=digest:
            partial.unlink()
            raise ValueError(f'Download checksum mismatch: {name}')
        partial.replace(target)
    (directory/'local-manifest.json').write_text(json.dumps({
        'model':f'PP-OCRv6_{args.size}_rec','source':source,'revision':revision,'files':files},indent=2)+'\n')
    print(directory)


if __name__=='__main__':main()
