"""Public VGC Multicalc submissions; collection requires a recorded authorization.

Website navigation establishes endpoints, not a license for submitted content.
The licensed repository collector remains independent of this optional path.
"""
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode

from metagame.common import atomic_json,now,sha
from metagame.fetch import Fetcher
from metagame.store import locked
from .adapters import parse_export,points
from .canonical import Canonicalizer
from .population import exclusion
from .store import Teams,prepare
from .vgcmulticalc import pages,pilot

HOST='https://vgcmulticalc.com'
POLICY=dict(url=HOST+'/teams/',population='tournament_published',terms=None,
    attribution='VGC Multicalc public submissions and named team creators',
    rights='Submission reuse license unpublished; authorization must be recorded; private factual research only',
    scope='Public index and unprotected GET paste data only; no unlock, login, submission or analytics requests')


def discovery(raw,regulation):
    rows=json.loads(raw)
    if not isinstance(rows,list):raise ValueError('Public index is not an array')
    ids=set()
    for r in rows:
        if not isinstance(r,dict) or r.get('regulation')!=regulation or r.get('source')!='community':
            raise ValueError('Public index source/regulation changed')
        if not all(k in r for k in ('id','pasteId','description','player','date','members','hasSps')) or len(r['members'])!=6:
            raise ValueError('Public index schema changed')
        if not re.fullmatch('[A-Za-z0-9_-]{1,80}',r['pasteId']) or r['id'] in ids:raise ValueError('Unsafe/duplicate public paste ID')
        ids.add(r['id'])
    return rows


def detail(summary,raw):
    payload=json.loads(raw)
    if not isinstance(payload,dict) or payload.get('kind')!='team' or payload.get('version')!=1:
        raise ValueError('Protected/unsupported paste schema; never unlock or guess credentials')
    if set(payload)-{'kind','version','useSpsMode','showdown','name','source','createdAt','replicaCode'}:
        raise ValueError('Paste fields changed; review possible gameplay fields')
    if type(payload.get('useSpsMode')) is not bool or not isinstance(payload.get('showdown'),str):
        raise ValueError('Paste allocation mode/export missing')
    members=parse_export(payload['showdown'])
    if len(members)!=6:raise ValueError('Not a six-member public export')
    for m,s in zip(members,summary['members']):
        if m['species']!=s['name']:m['conflicts'].append('species_summary_export_disagreement')
        if m['item']!=s.get('item'):m['conflicts'].append('item_summary_export_disagreement')
        allocation=m['evidence'].get('untyped_allocation')
        if allocation:
            values,deductions=points(allocation)
            if not payload['useSpsMode']:
                for i in deductions:values[i]=None
                deductions=[]
            m['sp']=dict(kind='champions_sp' if payload['useSpsMode'] else 'legacy_ev',values=values)
            m['evidence'].update(sp_semantics='Public paste useSpsMode flag; EVs is export syntax, not assumed traditional EV units',
                zero_components_deduced_from_66_budget=deductions)
    return dict(source_key=summary['id'],title=summary['description'],
        source_url=HOST+'/teams/?'+urlencode(dict(reg=summary['regulation'],paste=summary['pasteId'])),
        population='tournament_published',regulation=summary['regulation'],format='Doubles',pokemon=members,
        metadata=dict(attribution='VGC Multicalc public submission; '+summary['player'],
            creator=summary['player'],handle=summary.get('handle'),event=summary.get('event'),
            placement=summary.get('placement'),source_date=summary['date'],published_date=payload.get('createdAt'),
            date_semantics='Index date versus paste createdAt retained separately; event independence unverified',
            replica_code=summary.get('replicaCode'),paste_id=summary['pasteId'],
            original_summary=summary,original_payload=payload,source_scope='public_submissions',
            provenance_status='Third-party claimed Champions published team; no independent in-game validation'))


def collect(root,*,authorization_note=None,regulation='M-C',limit=None,interval=2.,fetcher=None):
    authorization_path=Path(root)/'source-authorizations.json'
    if authorization_note is None and authorization_path.exists():
        authorization_note=json.loads(authorization_path.read_text()).get('vgcmulticalc_public_submissions',{}).get('note')
    if not authorization_note or not authorization_note.strip():raise ValueError('Public submission collection authorization is required')
    if regulation not in ('M-A','M-B','M-C'):raise ValueError('Unaudited regulation')
    if limit is not None and (type(limit) is not int or limit<1):raise ValueError('Positive detail limit required')
    root=prepare(root)
    with locked(root):
        authorizations=json.loads(authorization_path.read_text()) if authorization_path.exists() else {}
        authorizations['vgcmulticalc_public_submissions']=dict(note=authorization_note,
            scope='Public unprotected source records, private non-commercial research cache',recorded_at=now())
        atomic_json(authorization_path,authorizations)
        db=Teams(root);f=fetcher or Fetcher(root,interval=interval)
        run=root/'runs'/('vgcmulticalc-public-'+regulation+'.json')
        old=json.loads(run.read_text()) if run.exists() else {}
        manifest=dict(status='running',source='vgcmulticalc',origin='public_submissions',regulation=regulation,
            authorization_note=authorization_note,started_at=now(),completed=old.get('completed',{}),errors={},
            exclusions={},attempts=old.get('attempts',[]))
        atomic_json(run,manifest);started=time.monotonic();canon=Canonicalizer()
        adapter='vgcmulticalc-public-detail-v1:'+sha(Path(__file__).read_bytes())
        try:
            receipt=f.get(HOST+'/api/teams/index/'+regulation.lower()+'.json')
            capture=db.capture('vgcmulticalc',POLICY,receipt)
            rows=discovery(Path(receipt['raw_path']).read_text(),regulation)
            selected=pilot(rows,limit) if limit else rows
            manifest.update(discovered=len(rows),replica_code_teams=sum(bool(r.get('replicaCode')) for r in rows),
                selected_ids=[r['id'] for r in selected],index_capture=capture)
            atomic_json(run,manifest)
            for page_number,page in enumerate(pages(selected),1):
                manifest['current_page']=page_number
                for summary in page:
                    key=summary['id'];prior=manifest['completed'].get(key)
                    # Re-evaluate when the current index changes: a saved checkpoint
                    # is not proof that a later source revision has identical fields.
                    identity=sha(json.dumps(summary,sort_keys=True).encode())
                    if prior and prior.get('adapter_version')==adapter and prior.get('index_identity')==identity and time.time()-prior.get('checked_epoch',0)<86400:continue
                    try:
                        reason=exclusion(dict(title=summary['description'],metadata=summary))
                        if reason:manifest['exclusions'][key]=reason;continue
                        receipt=f.get(HOST+'/api/pastes/'+summary['pasteId'])
                        cid=db.capture('vgcmulticalc',POLICY,receipt)
                        record=detail(summary,Path(receipt['raw_path']).read_text())
                        result=db.add('vgcmulticalc',record,canon.team(record),cid,adapter)
                        with db.db:db.db.execute('INSERT OR IGNORE INTO publication_captures VALUES(?,?)',(result['publication_id'],capture))
                        manifest['completed'][key]=dict(**result,adapter_version=adapter,index_identity=identity,checked_epoch=time.time())
                    except Exception as exc:manifest['errors'][key]=str(exc)
                    atomic_json(run,manifest)
                print(f'VGC Multicalc public {regulation}: {len(manifest["completed"])}/{len(selected)} details; {len(manifest["errors"])} errors',flush=True)
            manifest['status']='partial' if manifest['errors'] else 'complete'
        except Exception as exc:manifest.update(status='failed',error=str(exc))
        finally:
            manifest.update(finished_at=now(),elapsed_seconds=time.monotonic()-started,network_requests=f.requests,cache_hits=f.cache_hits)
            manifest['attempts'].append({k:manifest[k] for k in ('status','started_at','finished_at','elapsed_seconds','network_requests','cache_hits')})
            atomic_json(run,manifest);db.close()
        return manifest,run
