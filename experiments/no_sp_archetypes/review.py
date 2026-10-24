"""Loopback-only review server with durable, versioned SQLite annotations."""
import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlparse

ASSESSMENTS = ('reasonable','another_cluster','ambiguous','insufficient','source_issue')
ROOT=Path(__file__).resolve().parents[2]
ASSETS=Path(__file__).parent/'assets'
FIGURES=ROOT/'milestone_reports/M3.5.2_Midterm_Research_Report/figures'
FIGURE_NAMES={'incineroar-sp-only-heatmap.png','incineroar-sp-only-projection.png','incineroar-sp-only-boxplots.png'}


class ReviewStore:
    def __init__(self, path, payload):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.fingerprint=payload['model_fingerprint']
        self.records={r['empirical_record_id']:r for r in payload['records']}
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS reviews(
                revision INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL,
                observation_id TEXT NOT NULL, assessment TEXT NOT NULL, preferred_cluster INTEGER,
                notes TEXT NOT NULL, reviewed_at TEXT NOT NULL, suggested_weights TEXT NOT NULL,
                interpretation TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS review_lookup ON reviews(fingerprint,observation_id,revision);
                CREATE TABLE IF NOT EXISTS session(fingerprint TEXT PRIMARY KEY,state TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:yield db
        finally:db.close()

    def save(self, value):
        rid=value.get('observation_id');assessment=value.get('assessment')
        preferred=value.get('preferred_cluster');notes=value.get('notes','')
        if value.get('model_fingerprint')!=self.fingerprint:raise ValueError('Model fingerprint mismatch; reload the page')
        if rid not in self.records:raise ValueError('Unknown observation ID')
        if assessment not in ASSESSMENTS:raise ValueError('Select a human assessment')
        if preferred is not None and (type(preferred) is not int or preferred not in range(3)):raise ValueError('Invalid preferred cluster')
        if not isinstance(notes,str) or len(notes)>20000:raise ValueError('Notes must contain at most 20000 characters')
        prediction=self.records[rid]['prediction']
        suggested={k:prediction[k] for k in ('moves_only','moves_item')}
        with self.connect() as db:
            db.execute('INSERT INTO reviews(fingerprint,observation_id,assessment,preferred_cluster,notes,reviewed_at,suggested_weights,interpretation) VALUES(?,?,?,?,?,?,?,?)',
                       (self.fingerprint,rid,assessment,preferred,notes,datetime.now(timezone.utc).isoformat(),json.dumps(suggested),
                        'Interpretive human review, not verified true SP or a training label'))
        return next(r for r in self.latest() if r['observation_id']==rid)

    def latest(self):
        with self.connect() as db:
            rows=db.execute('SELECT * FROM reviews WHERE revision IN (SELECT MAX(revision) FROM reviews WHERE fingerprint=? GROUP BY observation_id) ORDER BY revision',(self.fingerprint,)).fetchall()
        result=[]
        for row in rows:
            r=dict(row);r['suggested_weights']=json.loads(r['suggested_weights']);result.append(r)
        return result

    def session(self, state=None):
        with self.connect() as db:
            if state is not None:
                if not isinstance(state,dict) or len(json.dumps(state))>10000:raise ValueError('Invalid session state')
                db.execute('INSERT INTO session VALUES(?,?) ON CONFLICT(fingerprint) DO UPDATE SET state=excluded.state',(self.fingerprint,json.dumps(state)))
            row=db.execute('SELECT state FROM session WHERE fingerprint=?',(self.fingerprint,)).fetchone()
        return json.loads(row[0]) if row else {}

    def csv(self):
        stream=io.StringIO();fields=['revision','fingerprint','observation_id','assessment','preferred_cluster','notes','reviewed_at','suggested_weights','interpretation']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in self.latest():
            row['suggested_weights']=json.dumps(row['suggested_weights'],sort_keys=True)
            # Escape spreadsheet formula prefixes without changing stored notes.
            for key in ('notes',):
                if row[key].lstrip().startswith(('=','+','-','@')):row[key]="'"+row[key]
            writer.writerow(row)
        return stream.getvalue()


def handler_for(payload, store):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not self.path.startswith('/api/session'):super().log_message(fmt,*args)

        def send(self, data, content='application/json; charset=utf-8', status=200, attachment=None):
            if isinstance(data,(dict,list)):data=json.dumps(data,ensure_ascii=False,allow_nan=False)
            if isinstance(data,str):data=data.encode()
            self.send_response(status);self.send_header('Content-Type',content)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            if attachment:self.send_header('Content-Disposition',f'attachment; filename="{attachment}"')
            self.end_headers();self.wfile.write(data)

        def valid_host(self):
            host=self.headers.get('Host','')
            return host in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.valid_host():return self.send({'error':'Loopback Host required'},status=403)
            route=urlparse(self.path).path
            if route=='/api/data':return self.send(payload)
            if route=='/api/reviews':return self.send(store.latest())
            if route=='/api/session':return self.send(store.session())
            if route=='/api/export.json':return self.send(dict(model_fingerprint=store.fingerprint,reviews=store.latest(),interpretation='Interpretive reviews; true SP unknown'),attachment='m353-reviews.json')
            if route=='/api/export.csv':return self.send(store.csv(),'text/csv; charset=utf-8',attachment='m353-reviews.csv')
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if route in files:
                f,mime=files[route];return self.send((ASSETS/f).read_bytes(),mime)
            if route.startswith('/figures/') and route[9:] in FIGURE_NAMES:
                return self.send((FIGURES/route[9:]).read_bytes(),'image/png')
            return self.send({'error':'Not found'},status=404)

        def do_PUT(self):
            if not self.valid_host():return self.send({'error':'Loopback Host required'},status=403)
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:
                return self.send({'error':'Same-origin request required'},status=403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=100000:raise ValueError('Invalid request length')
                if self.headers.get_content_type()!='application/json':raise ValueError('JSON required')
                value=json.loads(self.rfile.read(length))
                if not isinstance(value,dict):raise ValueError('JSON object required')
                if self.path=='/api/reviews':return self.send(store.save(value))
                if self.path=='/api/session':return self.send(store.session(value))
                return self.send({'error':'Not found'},status=404)
            except (ValueError,TypeError) as exc:return self.send({'error':str(exc)},status=400)
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,help='Fingerprint directory; default latest completed run')
    parser.add_argument('--port',type=int,default=8353)
    parser.add_argument('--annotations',type=Path,default=ROOT/'.cache/research/m353/reviews.sqlite3')
    args=parser.parse_args()
    run=args.run or Path(json.loads((ROOT/'.cache/research/m353/latest.json').read_text())['path'])
    manifest=json.loads((run/'manifest.json').read_text())
    raw=(run/'review-data.json').read_bytes()
    if manifest.get('status')!='complete' or hashlib.sha256(raw).hexdigest()!=manifest['stages']['review-data']['sha256']:
        raise ValueError('Review requires a completed run with intact prediction data')
    payload=json.loads(raw)
    if payload['model_fingerprint']!=manifest['fingerprint']:raise ValueError('Review model identity mismatch')
    payload['annotation_location']=str(args.annotations.resolve())
    store=ReviewStore(args.annotations,payload)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(payload,store))
    print(f'Review: http://127.0.0.1:{server.server_port}\nAnnotations: {args.annotations.resolve()}\nModel: {store.fingerprint}\nHuman review pending; interpretive judgments are not true SP labels.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
