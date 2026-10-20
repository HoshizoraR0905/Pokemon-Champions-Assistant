"""Pinned, MIT-licensed VGC Multicalc list and detail data, read without executing JS.

The public UI pages the index locally and loads detail blocks on demand. Reading
the same published source blocks avoids hundreds of redundant HTML shell loads.
No submission, analytics, authenticated, or private endpoints are used.
"""
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode

from metagame.common import atomic_json, encode, now, sha
from metagame.fetch import Fetcher
from metagame.store import locked
from .canonical import Canonicalizer
from .store import Teams, prepare

REPOSITORY = 'https://github.com/robsonbittencourt/vgc-multicalc'
DEFAULT_REVISION = 'fd7aa03ea88f09b41ac38280d987c62d15a48094'
DATA = 'src/domain/data/community-teams/'
POLICY = dict(url='https://vgcmulticalc.com/teams/', population='tournament_published',
    attribution='VGC Multicalc / VGCPastes and named team creators',
    terms=REPOSITORY+'/blob/'+DEFAULT_REVISION+'/LICENSE',
    rights='MIT-licensed repository data; retain LICENSE and creator attribution; private research copy',
    scope='Repository-curated VGCPastes teams only; dynamic community submissions not covered by this collector')


def literal(raw, name):
    """Strict JSON-like TS literal subset; reject expressions and layout drift."""
    match = re.search(r'export const '+re.escape(name)+r'\s*:[^=]+=', raw)
    if not match: raise ValueError('Missing exported data declaration: '+name)
    text = raw[match.end():].strip()
    # Tokenize strings before identifiers: never rewrite keys inside strings.
    token = re.compile(r'\s*("(?:[^"\\]|\\.)*"|-?\d+|[A-Za-z_$][\w$]*|[\[\]{},:;])')
    pos = 0; tokens = []
    while pos < len(text):
        if not text[pos:].strip(): break
        m = token.match(text,pos)
        if not m: raise ValueError('Unsupported source data syntax near '+repr(text[pos:pos+40]))
        tokens.append(m[1]); pos = m.end()
    index = 0
    def value():
        nonlocal index
        if index >= len(tokens): raise ValueError('Truncated data literal')
        t=tokens[index]; index+=1
        if t in ('[','{'):
            out=[] if t=='[' else {}; closing=']' if t=='[' else '}'
            while index < len(tokens) and tokens[index]!=closing:
                if t=='[':out.append(value())
                else:
                    key=tokens[index];index+=1
                    key=json.loads(key) if key.startswith('"') else key
                    if key in out:raise ValueError('Duplicate data key')
                    if tokens[index]!=':':raise ValueError('Missing object colon')
                    index+=1;out[key]=value()
                if tokens[index]==',':index+=1
                elif tokens[index]!=closing:raise ValueError('Missing data separator')
            if index>=len(tokens):raise ValueError('Unclosed data literal')
            index+=1;return out
        if t.startswith('"') or re.fullmatch(r'-?\d+',t) or t in ('true','false','null'):
            return json.loads(t)
        raise ValueError('Executable source data is not accepted: '+t)
    try: result=value()
    except IndexError as exc:raise ValueError('Truncated data literal') from exc
    if tokens[index:] not in ([],[';']):raise ValueError('Trailing source expression')
    return result


def discovery(raw, regulation):
    rows=literal(raw,'COMMUNITY_TEAMS')
    if not isinstance(rows,list) or not rows:raise ValueError('Empty/malformed team index')
    ids=set()
    for r in rows:
        if not isinstance(r,dict) or r.get('regulation')!=regulation or not all(k in r for k in
            ('id','description','player','pasteId','hasSps','members','setsBlock','date')):
            raise ValueError('Team index schema/regulation changed')
        if r['id'] in ids:raise ValueError('Duplicate source team identity')
        if len(r['members'])!=6 or type(r['setsBlock']) is not int or r['setsBlock']<0:
            raise ValueError('Invalid roster/detail block')
        ids.add(r['id'])
    return rows


def pages(rows, size=20):
    if type(size) is not int or size<1:raise ValueError('Positive page size required')
    for offset in range(0,len(rows),size):yield rows[offset:offset+size]


def pilot(rows, limit):
    """Deterministic coverage sample, not a random/statistically weighted sample."""
    if limit>=len(rows):return rows
    selected=rows[:min(4,limit)];seen=set()
    for r in selected:seen.add((r.get('event'),bool(r.get('replicaCode')),r['hasSps']))
    for r in rows:
        stratum=(r.get('event'),bool(r.get('replicaCode')),r['hasSps'])
        if len(selected)>=limit:break
        if stratum not in seen:selected.append(r);seen.add(stratum)
    for r in rows:
        if len(selected)>=limit:break
        if r not in selected:selected.append(r)
    return selected


def detail(summary, block, revision):
    sets=literal(block,'COMMUNITY_TEAM_SETS')
    members=sets.get(summary['id'])
    if not isinstance(members,list) or len(members)!=6:raise ValueError('Missing six-member detail block')
    pokemon=[]
    for species,build in zip(summary['members'],members):
        if not isinstance(build,dict) or set(build)-{'ability','nature','sps','moves'}:
            raise ValueError('Detail fields changed; review new gameplay fields')
        moves=build.get('moves',[])
        if not isinstance(moves,list) or any(not isinstance(m,str) for m in moves):raise ValueError('Malformed moves')
        points=build.get('sps')
        if points is not None and (not isinstance(points,dict) or set(points)-{'hp','atk','def','spa','spd','spe'}):
            raise ValueError('SP layout changed')
        values=[points.get(k) for k in ('hp','atk','def','spa','spd','spe')] if points is not None else [None]*6
        if any(v is not None and type(v) is not int for v in values):raise ValueError('Noninteger SP')
        pokemon.append(dict(species=species['name'],item=species.get('item'),
            ability=build.get('ability'),nature=build.get('nature'),moves=moves,
            sp=dict(kind='champions_sp' if points is not None else 'unknown',values=values),
            evidence=dict(sp_semantics='Source CommunityTeamSet.sps; UI explicitly uses SP mode; missing components stay unknown',
                          original_set=build)))
    reg=summary['regulation']
    return dict(source_key=summary['id'],title=summary['description'],
        source_url='https://vgcmulticalc.com/teams/?'+urlencode(dict(reg=reg,paste=summary['pasteId'])),
        population='tournament_published',regulation=reg,format='Doubles',pokemon=pokemon,
        metadata=dict(attribution='VGC Multicalc / VGCPastes; '+summary['player'],
            creator=summary['player'],handle=summary.get('handle'),event=summary.get('event'),
            placement=summary.get('placement'),source_date=summary['date'],
            date_semantics='Source date field; publication versus event date not independently established',
            replica_code=summary.get('replicaCode'),paste_id=summary['pasteId'],source_id=summary['id'],
            repository=REPOSITORY,revision=revision,license='MIT',original_summary=summary,
            source_scope='repository_curated_vgcpastes',
            form_semantics='Named species/form as displayed; pre-Mega ability may describe the base form. No legality assertion'))


def collect(root, *, regulation='M-C', revision=DEFAULT_REVISION, limit=None, interval=2., fetcher=None):
    if regulation not in ('M-A','M-B','M-C'):raise ValueError('Unaudited Champions regulation')
    if not re.fullmatch('[0-9a-f]{40}',revision):raise ValueError('Pinned source commit required')
    if limit is not None and (type(limit) is not int or limit<1):raise ValueError('Positive detail limit required')
    root=prepare(root)
    with locked(root):
        db=Teams(root);f=fetcher or Fetcher(root,interval=interval)
        base='https://raw.githubusercontent.com/robsonbittencourt/vgc-multicalc/'+revision+'/'
        run=root/'runs'/('vgcmulticalc-'+regulation+'-'+revision+'.json')
        previous=json.loads(run.read_text()) if run.exists() else {}
        manifest=dict(source='vgcmulticalc',revision=revision,regulation=regulation,
            status='running',started_at=now(),completed=previous.get('completed',{}),errors={},
            attempts=previous.get('attempts',[]),
            scope=POLICY['scope'],requested_limit=limit)
        atomic_json(run,manifest);started=time.monotonic();canon=Canonicalizer()
        adapter='vgcmulticalc-licensed-detail-v1:'+sha(Path(__file__).read_bytes())
        try:
            license_receipt=f.get(base+'LICENSE',refresh_seconds=10**12)
            license_text=Path(license_receipt['raw_path']).read_text()
            if not license_text.startswith('MIT License') or 'Robson Bittencourt' not in license_text:
                raise ValueError('Source license changed; collection stopped')
            db.capture('vgcmulticalc',POLICY,license_receipt)
            directory=DATA+regulation.lower()+'/'
            receipt=f.get(base+directory+'community-teams-'+regulation.lower()+'.ts',refresh_seconds=10**12)
            index_capture=db.capture('vgcmulticalc',POLICY,receipt)
            rows=discovery(Path(receipt['raw_path']).read_text(),regulation)
            manifest.update(discovered=len(rows),replica_code_teams=sum(bool(r.get('replicaCode')) for r in rows),
                source_reports_sp=sum(bool(r['hasSps']) for r in rows),index_capture=index_capture,
                source_pages=(len(rows)+19)//20,license_receipt=license_receipt)
            atomic_json(run,manifest)
            chosen=pilot(rows,limit) if limit else rows
            manifest['selected_ids']=[r['id'] for r in chosen]
            for page_number,page in enumerate(pages(chosen),1):
                manifest['current_page']=page_number;atomic_json(run,manifest)
                for summary in page:
                    key=summary['id']
                    old=manifest['completed'].get(key)
                    if old and old.get('adapter_version')==adapter:continue
                    try:
                        block=summary['setsBlock']+1
                        path=directory+'community-team-sets-'+regulation.lower()+f'-{block:03}.ts'
                        detail_receipt=f.get(base+path,refresh_seconds=10**12)
                        capture=db.capture('vgcmulticalc',POLICY,detail_receipt)
                        record=detail(summary,Path(detail_receipt['raw_path']).read_text(),revision)
                        canonical=canon.team(record)
                        result=db.add('vgcmulticalc',record,canonical,capture,adapter)
                        # The index supplies species/items/metadata; both captures are essential.
                        with db.db:
                            db.db.execute('INSERT OR IGNORE INTO publication_captures VALUES(?,?)',(result['publication_id'],index_capture))
                            # Replace only the known old card summary, preserving it as evidence.
                            for prior in db.db.execute("SELECT id,original FROM publications WHERE source_id='vgcmulticalc' AND title=?",(record['title'],)).fetchall():
                                old_record=json.loads(prior['original'])
                                if prior['id']!=result['publication_id'] and old_record.get('metadata',{}).get('locator'):
                                    db.db.execute('INSERT OR IGNORE INTO publication_supersessions VALUES(?,?,?,?)',
                                        (prior['id'],result['publication_id'],'Detail record identifies the same titled pilot card',now()))
                        manifest['completed'][key]=dict(**result,adapter_version=adapter,
                            replica_code=summary.get('replicaCode'),detail_capture=capture)
                    except Exception as exc:
                        manifest['errors'][key]=str(exc)
                    atomic_json(run,manifest)
                done=sum(r['id'] in manifest['completed'] for r in chosen)
                print(f'VGC Multicalc {regulation}: {done}/{len(chosen)} selected details, {len(manifest["errors"])} errors',flush=True)
            manifest['status']='partial' if manifest['errors'] else 'complete'
        except Exception as exc:manifest.update(status='failed',error=str(exc))
        finally:
            manifest.update(finished_at=now(),elapsed_seconds=time.monotonic()-started,
                network_requests=f.requests,cache_hits=f.cache_hits)
            manifest['attempts'].append({k:manifest[k] for k in ('started_at','finished_at','elapsed_seconds','network_requests','cache_hits','status')})
            atomic_json(run,manifest);db.close()
        return manifest,run
