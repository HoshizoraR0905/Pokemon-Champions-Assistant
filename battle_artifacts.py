"""Recording-owned artifact namespaces and immutable legacy provenance aliases."""
from dataclasses import dataclass
import os
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
ALIASES={'sample_battle':'sample_battle_0'}


def canonical_id(value):
    value=ALIASES.get(value,value)
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',value):
        raise ValueError('battle_id must be a recording stem, without paths or extensions')
    return value


@dataclass(frozen=True)
class BattleArtifacts:
    battle_id: str
    root: Path = ROOT

    def __post_init__(self):
        object.__setattr__(self,'battle_id',canonical_id(self.battle_id))
        object.__setattr__(self,'root',Path(self.root).resolve())

    @classmethod
    def select(cls, battle_id=None, video=None, *, default=None, root=ROOT):
        stem=canonical_id(Path(video).stem) if video else None
        selected=canonical_id(battle_id or stem or default)
        if stem and stem!=selected:raise ValueError('--battle-id differs from --video stem')
        registered=Path(root)/'tests/fixtures'/f'{selected}.mp4'
        provided=Path(video) if video else None
        if provided and provided.is_file() and registered.is_file() and not provided.samefile(registered):raise ValueError('A different video is already registered for this battle_id')
        return cls(selected,root)

    @property
    def cache_dir(self):return self.root/'.cache/battles'/self.battle_id
    @property
    def report_dir(self):return self.root/'reports/battles'/self.battle_id

    def _path(self,base,name):
        if base.is_symlink():raise ValueError('Battle namespace cannot be a symlink')
        name=Path(name)
        if name.is_absolute() or '..' in name.parts:raise ValueError('Artifact path must stay in its battle namespace')
        path=base/name
        # A stale or malicious symlink must not redirect into a different recording.
        if not path.resolve().is_relative_to(base.resolve()):raise ValueError('Artifact symlink escapes battle namespace')
        return path

    def cache(self,name):return self._path(self.cache_dir,name)
    def report(self,name):return self._path(self.report_dir,name)
    def input(self,name):return self.report(Path('inputs')/name)

    def video(self):
        path=self.root/'tests/fixtures'/f'{self.battle_id}.mp4'
        if path.is_file():return path
        raise FileNotFoundError(f'Recording not found: {path}')

    def prepare(self):
        self.cache_dir.mkdir(parents=True,exist_ok=True);self.report_dir.mkdir(parents=True,exist_ok=True)
        return self

    def check_identity(self,value):
        if canonical_id(value)!=self.battle_id:raise ValueError(f'Input belongs to {value}, requested {self.battle_id}')

    def guard_output(self,path):
        path=Path(path).absolute();resolved=path.resolve()
        for base in (self.root/'reports/battles',self.root/'.cache/battles'):
            if resolved.is_relative_to(base):
                owner=resolved.relative_to(base).parts[0]
                if owner!=self.battle_id:raise ValueError(f'Output belongs to another recording: {owner}')
        if (path.is_relative_to(self.root/'reports') and not resolved.is_relative_to(self.report_dir.resolve())) or (path.is_relative_to(self.root/'.cache') and not resolved.is_relative_to(self.cache_dir.resolve())):
            raise ValueError('Battle output must use its own canonical report directory')
        path.parent.mkdir(parents=True,exist_ok=True)
        if not resolved.is_relative_to(self.report_dir.resolve()) and not resolved.is_relative_to(self.cache_dir.resolve()):
            # Explicit external destinations retain per-file ownership too.
            import fcntl
            registry=path.parent/'.battle-artifact-owners.json'
            with registry.open('a+') as stream:
                fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0);raw=stream.read();owners=json.loads(raw) if raw else {}
                prior=owners.get(path.name)
                if prior and prior!=self.battle_id:raise ValueError('External output is owned by another battle')
                owners[path.name]=self.battle_id;stream.seek(0);stream.truncate();json.dump(owners,stream,sort_keys=True)
        return path


def add_arguments(parser, *, default=None, video=True):
    parser.add_argument('--battle-id',default=default,help='Recording stem; outputs are isolated by battle')
    if video:parser.add_argument('--video',type=Path,help='Recording path; stem determines battle_id')


def legacy_video(path):
    """Resolve an old filename without rewriting historical source/event IDs."""
    path=Path(path)
    return path.with_name('sample_battle_0.mp4') if path.name=='sample_battle.mp4' else path


def check_event_ownership(paths,payload):
    """Validate explicit evidence ownership without changing opaque event IDs."""
    if payload.get('battle_id'):paths.check_identity(payload['battle_id'])
    for event in payload.get('event_candidates',[]):
        for evidence in event.get('evidence',[]):
            source=evidence.get('source_id','')
            for match in re.findall(r'(sample_battle(?:_[0-9]+)?)\.mp4',source):paths.check_identity(match)
        pid=event.get('attributes',{}).get('actor_instance_id')
        if pid and pid.startswith('sample_battle'):paths.check_identity(pid.split(':',1)[0])



def manifest_battle(path):
    """Read cached metadata only; never inspect or decode video frames."""
    value=json.loads(Path(path).read_text());sources=[]
    if value.get('battle_id'):sources.append(canonical_id(value['battle_id']))
    for key in ('video','source'):
        text=value.get(key,'')
        if isinstance(text,str):sources.extend(canonical_id(m) for m in re.findall(r'(sample_battle(?:_[0-9]+)?)\.mp4',text))
    for key in ('command','extraction_command'):
        for part in value.get(key,[]):sources.extend(canonical_id(m) for m in re.findall(r'(sample_battle(?:_[0-9]+)?)\.mp4',str(part)))
    for row in value.get('frames',[]):
        sources.extend(canonical_id(m) for m in re.findall(r'(sample_battle(?:_[0-9]+)?)\.mp4',row.get('source','')))
    if len(set(sources))!=1:raise ValueError('Cannot establish one recording owner from cache metadata')
    return sources[0]


def historical_reference(path, *, root=ROOT):
    """Keep an archived evidence address stable when its compatibility alias exists."""
    path=Path(path).absolute();root=Path(root).resolve();manifest=root/'reports/battle-artifact-migration.json'
    if manifest.exists():
        for record in json.loads(manifest.read_text())['moves']:
            canonical=root/record['canonical']
            if path==canonical or path.is_relative_to(canonical):
                old=root/record['legacy']/path.relative_to(canonical) if path!=canonical else root/record['legacy']
                if old.exists() and old.resolve()==path.resolve():return str(old.relative_to(root))
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
