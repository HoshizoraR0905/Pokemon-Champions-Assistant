"""Package an existing review payload using byte-identical, hash-addressed assets.

No recognition, extraction or cache invalidation. Run from any working directory.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'reports/M2.3.6-review'


def package(payload, target=TARGET):
    assets = target / 'assets'
    assets.mkdir(exist_ok=True, parents=True)
    manifest = {}

    def visit(node):
        if isinstance(node, list):
            for value in node:
                visit(value)
        elif isinstance(node, dict):
            if isinstance(node.get('image'), str):
                source = node.get('source_image', node['image'])
                path = (target / node['image']).resolve()
                if not path.is_file():
                    path = (ROOT / node['image']).resolve()
                content = path.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                relative = 'assets/' + digest + path.suffix.lower()
                destination = target / relative
                if not destination.exists():
                    shutil.copyfile(path, destination)
                if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise ValueError(f'Asset hash mismatch: {destination}')
                manifest.setdefault(relative, {'sha256': digest, 'bytes': len(content), 'sources': []})
                if source not in manifest[relative]['sources']:
                    manifest[relative]['sources'].append(source)
                node['source_image'] = source
                node['image'] = relative
            for key, value in node.items():
                if key not in {'image', 'source_image'}:
                    visit(value)
    visit(payload)
    (target / 'assets-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    template = (ROOT / 'scripts/templates/m236_event_review.html').read_text()
    (target / 'review.html').write_text(template.replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')))
    return manifest


if __name__ == '__main__':
    html = (TARGET / 'review.html').read_text()
    payload = json.loads(re.search(r'const DATA=(.*?);\nconst \$', html, re.S)[1])
    manifest = package(payload)
    print(f'Packaged {len(manifest)} byte-identical assets; annotations untouched.')
