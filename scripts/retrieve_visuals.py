"""Explicit cache retrieval from the audited visual manifest (never at runtime)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=Path('knowledge/data/visual_assets.json'))
    p.add_argument('--cache',type=Path,default=Path('.cache/champions-icons'))
    a=p.parse_args();manifest=json.loads(a.manifest.read_text());a.cache.mkdir(parents=True,exist_ok=True)
    def get(ref):
        target=a.cache/ref['file']
        if target.name!=ref['file']:raise ValueError('Unsafe asset path')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==ref['sha256']:return
        with urllib.request.urlopen(ref['url'],timeout=30) as response:raw=response.read()
        if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('Asset checksum mismatch: '+ref['file'])
        target.write_bytes(raw)
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(get,manifest['assets']))
    shutil.copyfile(a.manifest,a.cache/'index.json')
    print(f'Icon cache ready: {len(manifest["assets"])} pinned assets in {a.cache}')


if __name__=='__main__':main()
