"""Bounded, checkpointed team collection; preserve every source record."""
import json
from pathlib import Path
import time
import uuid
from metagame.common import atomic_json,immutable_raw,sha,now
from metagame.fetch import Fetcher
from metagame.store import locked
from .adapters import SOURCES,extract
from .canonical import Canonicalizer
from .store import Teams,prepare


def collect(root,source,*,limit=None,from_file=None,receipt_file=None,force=False,interval=2.):
    policy=SOURCES[source]
    if limit is not None and (type(limit) is not int or not 1<=limit<=policy['max_records']):
        raise ValueError('Limit exceeds audited collection pilot')
    root=prepare(root)
    with locked(root):
        db=Teams(root);path=root/'runs'/(uuid.uuid4().hex+'.json')
        manifest=dict(status='running',source=source,policy=policy,started_at=now(),completed=[],errors=[],network_requests=0)
        atomic_json(path,manifest);started=time.monotonic()
        try:
            if from_file is not None:
                if receipt_file is None:raise ValueError('Original HTTP receipt required for a retained audited page')
                receipt=json.loads(Path(receipt_file).read_text());raw=Path(from_file).read_bytes()
                if receipt['url']!=policy['url'] or receipt.get('status')!=200 or sha(raw)!=receipt['sha256']:
                    raise ValueError('Audited source URL/status/raw hash mismatch')
                raw_path,digest=immutable_raw(root,raw)
                receipt.update(raw_path=str(raw_path),raw_sha256=digest)
            else:
                fetcher=Fetcher(root,interval=interval)
                receipt=fetcher.get(policy['url'],force=force)
                manifest['network_requests']=fetcher.requests
                raw=Path(receipt['raw_path']).read_bytes()
            capture_id=db.capture(source,policy,receipt)
            adapter_path=Path(__file__).parent/'adapters.py'
            adapter_version='published-adapters-v1:'+sha(adapter_path.read_bytes())
            canonicalizer=Canonicalizer()
            rows=extract(source,raw.decode('utf-8'),limit)
            manifest.update(capture_id=capture_id,raw_sha256=receipt['raw_sha256'],adapter_version=adapter_version,
                            discovered_records=len(rows),algorithm_version=canonicalizer.team({'pokemon':[]})['version'])
            atomic_json(path,manifest)
            for record in rows:
                try:
                    canonical=canonicalizer.team(record)
                    result=db.add(source,record,canonical,capture_id,adapter_version)
                    manifest['completed'].append(dict(source_key=record['source_key'],**result))
                    print(f'{source}: {len(manifest["completed"])}/{len(rows)} {canonical["status"]} — {record["title"]}',flush=True)
                except Exception as exc:
                    manifest['errors'].append(dict(source_key=record['source_key'],error=str(exc)))
                atomic_json(path,manifest)
            manifest['status']='complete' if not manifest['errors'] else 'partial'
        except Exception as exc:
            manifest.update(status='failed',error=str(exc))
        finally:
            manifest.update(finished_at=now(),elapsed_seconds=time.monotonic()-started)
            atomic_json(path,manifest);db.close()
        return manifest,path
