"""Timestamp-grid acquisition with independent, resumable per-frame caching."""
from dataclasses import dataclass, asdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess


SAMPLER_VERSION = 3
DEFAULT_SAMPLE_FPS = 2.0


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)


@dataclass(frozen=True)
class SamplingConfig:
    sample_fps: float = DEFAULT_SAMPLE_FPS
    width: int = 1311

    def __post_init__(self):
        if not math.isfinite(self.sample_fps) or self.sample_fps<=0 or type(self.width) is not int or self.width<1:
            raise ValueError('Sampling FPS and width must be positive and finite')
        object.__setattr__(self,'sample_fps',float(self.sample_fps))

    def targets(self,start,end):
        """Half-open interval, anchored to recording zero; no accumulated float drift."""
        if not 0<=start<=end or not math.isfinite(end):raise ValueError('Invalid interval')
        fps=Fraction(str(self.sample_fps));begin=Fraction(str(start));finish=Fraction(str(end))
        first=math.ceil(begin*fps);last=math.ceil(finish*fps)
        return [float(Fraction(i,1)/fps) for i in range(first,last)]

    def identity(self,video):
        return fingerprint(dict(version=SAMPLER_VERSION,video=video,sampling=asdict(self),
                                preprocessing='ffmpeg scale width; lossless PNG; source PTS'))


def selected_pts(log):
    """Read integer PTS/timebase, not the rounded six-digit pts_time display."""
    match=re.search(r'config in time_base:\s*(\d+)/(\d+)',log)
    if not match:raise ValueError('Missing source timebase in extraction log')
    base=Fraction(int(match[1]),int(match[2]))
    return [(int(p),base) for p in re.findall(r'\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:',log)]


def acquire(paths,video_identity,config,start,end,*,chunk_seconds=10):
    """Decode only missing short chunks. Cached known frames can serve exact targets.

    FFmpeg's selected source PTS is retained; desired grid time is a separate field.
    Chunk boundaries own [start,end), and every target is selected exactly once.
    """
    import imageio_ffmpeg
    duration=video_identity['metadata']['duration_seconds'];end=min(end,duration)
    if not 0<=start<end:raise ValueError('Empty/out-of-range acquisition interval')
    root=paths.root;cache=paths.cache('m233b1/sampling/'+config.identity(video_identity)[:24]);rows=[]
    existing=[]
    b1_existing=[]
    for prior_path in paths.cache('m233b1/sampling').glob('*/*/frames.json'):
        prior=json.loads(prior_path.read_text())
        prior_version=prior.get('sampler_version')
        # Early B1 manifests encoded the sampler version in their directory hash.
        legacy_key=fingerprint(dict(version=SAMPLER_VERSION,video=video_identity,sampling=prior.get('sampling'),
            preprocessing='ffmpeg scale width; lossless PNG; source PTS'))[:24]
        version_matches=prior_version==SAMPLER_VERSION or (prior_version is None and prior_path.parents[1].name==legacy_key)
        if (prior.get('video_fingerprint')==video_identity and version_matches
                and prior.get('sampling',{}).get('width')==config.width):
            b1_existing+=prior['frames']
    # Only exact PTS matches with compatible known width can be borrowed from legacy surveys.
    for manifest in [paths.cache('m232/survey.json')]:
        if manifest.exists():
            prior=json.loads(manifest.read_text())
            if prior.get('video_fingerprint')==video_identity:existing+=prior['frames']
    for offset in range(math.floor(start/chunk_seconds),math.ceil(end/chunk_seconds)):
        left=max(start,offset*chunk_seconds);right=min(end,(offset+1)*chunk_seconds)
        targets=config.targets(left,right)
        if not targets:continue
        key=fingerprint(dict(left=float(left),right=float(right),targets=targets))[:24]
        folder=cache/key;manifest=folder/'frames.json'
        if manifest.exists():
            value=json.loads(manifest.read_text())
            if (value['video_fingerprint']==video_identity and value['sampling']==asdict(config)
                    and all((root/r['image']).is_file() and hashlib.sha256((root/r['image']).read_bytes()).hexdigest()==r['sha256'] for r in value['frames'])):
                rows+=value['frames'];continue
        folder.mkdir(parents=True,exist_ok=True)
        borrowed={}
        if config.width==1311:
            for target in targets:
                matches=[r for r in existing if abs(r['timestamp']-target)<1e-7 and (root/r['image']).is_file()]
                if matches:
                    r=matches[0]
                    if hashlib.sha256((root/r['image']).read_bytes()).hexdigest()==r['sha256']:borrowed[target]=r
        for target in targets:
            if target in borrowed:continue
            matches=[r for r in b1_existing if abs(r['target_timestamp']-target)<1e-7
                and target<=r['timestamp']<min(target+1/config.sample_fps,right) and (root/r['image']).is_file()]
            if matches:
                r=matches[0]
                if hashlib.sha256((root/r['image']).read_bytes()).hexdigest()==r['sha256']:
                    borrowed[target]=dict(r,reused_from='compatible_b1_sampling')
        missing=[t for t in targets if t not in borrowed]
        frames=[]
        if missing:
            # Use global grid cells, not average frame-rate windows: recordings
            # have variable source PTS. Empty cells stay explicit gaps, never duplicates.
            grid=f'floor((t+{left:.10f})*{config.sample_fps:.10f}+0.000000001)'
            prior_grid=f'floor((prev_selected_t+{left:.10f})*{config.sample_fps:.10f}+0.000000001)'
            expr=f'gte(t+{left:.10f},{targets[0]:.10f})*lt(t+{left:.10f},{right:.10f})*(isnan(prev_selected_t)+gt({grid},{prior_grid}))'
            if borrowed:
                exclusions='+'.join(f'eq({grid},{round(t*config.sample_fps)})' for t in borrowed)
                expr+=f'*not({exclusions})'
            command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','info','-y',
                '-ss',str(left),'-t',str(right-left),'-i',str(paths.video()),'-an',
                '-vf',f"select='{expr}',scale={config.width}:-1,showinfo",'-fps_mode','vfr',str(folder/'%06d.png')]
            with (folder/'extraction.log').open('w') as log:
                subprocess.run(command,stderr=log,stdout=subprocess.DEVNULL,check=True)
            pts=selected_pts((folder/'extraction.log').read_text())
            files=sorted(folder.glob('[0-9][0-9][0-9][0-9][0-9][0-9].png'))
            if len(files)<len(pts):raise ValueError('Decoded file/PTS mismatch')
            for (ticks,base),p in zip(pts,files):
                exact=Fraction(str(left))+ticks*base
                timestamp=float(exact)
                target=float(Fraction(math.floor(exact*Fraction(str(config.sample_fps))),1)/Fraction(str(config.sample_fps)))
                if not any(abs(target-t)<1e-7 for t in missing):raise ValueError('PTS outside requested sampling grid')
                frames.append(dict(image=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                    timestamp=timestamp,target_timestamp=target,source_id=video_identity['path']+'#'+str(timestamp),
                    timestamp_uncertainty_seconds=None,source_pts=ticks,source_time_base=str(base),reused_legacy=False))
        for target,r in borrowed.items():frames.append(dict(r,target_timestamp=target,reused_legacy=r.get('reused_from')!='compatible_b1_sampling'))
        frames.sort(key=lambda r:r['target_timestamp'])
        atomic_json(manifest,dict(video_fingerprint=video_identity,sampler_version=SAMPLER_VERSION,sampling=asdict(config),frames=frames,
            missing_target_cells=[t for t in targets if not any(abs(t-r['target_timestamp'])<1e-7 for r in frames)],
            boundary='half-open; global grid; first available source PTS in each cell; empty VFR cells skipped'))
        print(f'{paths.battle_id}: sampling checkpoint [{left:g},{right:g}) {len(frames)} frames',flush=True)
        rows+=frames
    if len({r['target_timestamp'] for r in rows})!=len(rows):raise ValueError('Duplicate boundary samples')
    return sorted(rows,key=lambda r:r['target_timestamp'])
