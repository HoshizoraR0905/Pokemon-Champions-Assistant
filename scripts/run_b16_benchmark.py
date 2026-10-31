"""Time the normal production CLI without call-profiler instrumentation."""
import json,os,platform,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from battle_artifacts import BattleArtifacts
from recognition.video_sampling import atomic_json
from recognition.fast_video import digest
RUN='b16-semantic-state-20261027-v1'

def main():
 owner=BattleArtifacts('sample_battle_16').prepare();out=owner.cache('evaluation/'+RUN);out.mkdir(parents=True,exist_ok=True)
 if (out/'normal-process.json').exists():raise ValueError('Measurement exists; do not launch duplicate benchmark')
 command=[str(ROOT/'.venv/bin/python'),str(ROOT/'main.py'),'--video',str(owner.video()),'--profile','event-driven','--identity-mode','lightweight','--sample-fps','2','--run-id',RUN]
 data=dict(status='running',command=command,started_at=datetime.now(timezone.utc).isoformat(),driver_pid=os.getpid(),
  platform=platform.platform(),machine=platform.machine(),python=sys.version,logical_cpus=os.cpu_count(),profiler_enabled=False,
  cache_policy='no imported frames/recognition/reconstruction; shared pinned model/icon assets only',video_sha256=digest(owner.video()))
 atomic_json(out/'normal-process.json',data)
 with (out/'normal-pipeline.log').open('w') as stream:
  began=time.perf_counter();p=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
  data['child_pid']=p.pid;atomic_json(out/'normal-process.json',data)
  rc=p.wait();data.update(status='complete' if rc==0 else 'failed',returncode=rc,normal_cli_wall_seconds=time.perf_counter()-began,finished_at=datetime.now(timezone.utc).isoformat())
 atomic_json(out/'normal-process.json',data)
 if rc:raise SystemExit(rc)
 m=json.loads(owner.cache('event-driven/'+RUN+'/manifest.json').read_text());duration=m['decoder']['container_duration_seconds']
 data.update(video_seconds=duration,PTR=data['normal_cli_wall_seconds']/duration,internal_seconds=m['cold_end_to_end_wall_seconds'],manifest_sha256=digest(owner.cache('event-driven/'+RUN+'/manifest.json')))
 atomic_json(out/'normal-process.json',data);print(json.dumps(data,indent=2))
if __name__=='__main__':main()
