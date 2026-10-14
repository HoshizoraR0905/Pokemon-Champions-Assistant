"""Extract one short high-cadence replay interval with FFmpeg input seeking."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--start',type=float,required=True)
    parser.add_argument('--duration',type=float,required=True)
    parser.add_argument('--fps',type=float,default=5.)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.start<0 or args.duration<=0 or args.fps<=0:parser.error('Invalid interval or rate')
    executable=shutil.which('ffmpeg')
    if executable is None:
        import imageio_ffmpeg
        executable=imageio_ffmpeg.get_ffmpeg_exe()
    args.output.mkdir(parents=True,exist_ok=True)
    if any(args.output.glob('*.png')):parser.error('Choose an empty extraction directory; do not decode an existing replay again')
    command=[executable,'-hide_banner','-loglevel','error','-ss',str(args.start),'-i',str(args.video),
             '-t',str(args.duration),'-vf',f'fps={args.fps},scale=1311:-1',str(args.output/'%06d.png')]
    subprocess.run(command,check=True)
    source=f'{args.video}#interval:{args.start}:{args.duration}:fps:{args.fps}'
    rows=[]
    for i,path in enumerate(sorted(args.output.glob('*.png'))):
        rows.append({'source':source,'index':i,'timestamp':args.start+i/args.fps,'image':path.name,
                     'metadata':{'original_source':str(args.video),'sampling_interval_seconds':1/args.fps,
                     'timestamp_method':'ffmpeg_resampled_interval_grid_not_original_frame_pts',
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}})
    (args.output/'frames.json').write_text(json.dumps({'schema_version':1,'extraction_command':command,
        'timestamp_uncertainty_seconds':1/args.fps,'frames':rows},indent=2)+'\n')
    print(f'{len(rows)} cached frames; {args.output}/frames.json')


if __name__=='__main__':main()
