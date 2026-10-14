"""Recreate available historical aliases without media processing or broken links."""
import argparse
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def setup(root=ROOT):
    root = Path(root).resolve()
    aliases = json.loads((root / 'data/battle_artifact_aliases.json').read_text())['aliases']
    aliases += [{'legacy': 'tests/fixtures/sample_battle.mp4', 'canonical': 'tests/fixtures/sample_battle_0.mp4'}]
    created, unavailable = [], []
    for pair in aliases:
        source, target = (root / pair[k] for k in ('legacy', 'canonical'))
        if not source.absolute().is_relative_to(root) or not target.resolve().is_relative_to(root):
            raise ValueError('Alias escapes repository')
        if not target.exists():
            unavailable.append(pair['canonical'])
            continue  # Never manufacture dangling links in a clean clone.
        if source.is_symlink():
            if source.resolve() != target.resolve():
                raise ValueError(f'Conflicting alias: {source}')
            continue
        if source.exists():
            raise FileExistsError(f'Existing legacy data needs explicit migration: {source}')
        source.parent.mkdir(parents=True, exist_ok=True)
        source.symlink_to(os.path.relpath(target, source.parent), target_is_directory=target.is_dir())
        created.append(pair['legacy'])
    return {'created': created, 'unavailable_local_artifacts': unavailable}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(setup(), indent=2))
