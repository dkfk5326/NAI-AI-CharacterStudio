import json,sqlite3,os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone
def prune_result_history(value,deleted):
    result=dict(value)
    result['candidates']=[c for c in value.get('candidates',[]) if c.get('id') not in deleted]
    result['manual_overrides']={k:v for k,v in value.get('manual_overrides',{}).items() if k.split(':')[0] not in deleted}
    if 'history' in value:result['history']=[prune_result_history(h,deleted) for h in value['history']]
    return result

ROOT=Path(__file__).resolve().parents[3]
DATA=Path(os.environ.get('NAI_DATA_DIR',ROOT/'data'))
class Repository:
    def __init__(self,path=None):
        self.path=Path(path or DATA/'projects.sqlite');self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,revision INTEGER,body TEXT,updated TEXT); CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,project_id TEXT,body TEXT,created TEXT); CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,body TEXT,created TEXT);')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL')
        try:
            with c:yield c
        finally:c.close()
    def get(self,key,default=None):
        with self.connect() as c:r=c.execute('SELECT value FROM kv WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else default
    def set(self,key,value):
        with self.connect() as c:c.execute('INSERT INTO kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value,ensure_ascii=False)))
    def save(self,p,expected_revision=None):
        now=datetime.now(timezone.utc).isoformat()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT revision,body FROM projects WHERE id=?',(p['id'],)).fetchone()
            if old and expected_revision is not None and old['revision']!=expected_revision:raise ValueError('REVISION_CONFLICT')
            deleted=set(p.get('legacy',{}).get('deleted_candidate_ids',[]))
            if deleted:
                p=prune_result_history(p,deleted)
                for snapshot in c.execute('SELECT id,body FROM snapshots WHERE project_id=?',(p['id'],)).fetchall():
                    clean=prune_result_history(json.loads(snapshot['body']),deleted)
                    c.execute('UPDATE snapshots SET body=? WHERE id=?',(json.dumps(clean,ensure_ascii=False),snapshot['id']))
            if old:
                previous=prune_result_history(json.loads(old['body']),deleted) if deleted else json.loads(old['body'])
                c.execute('INSERT INTO snapshots(project_id,body,created) VALUES(?,?,?)',(p['id'],json.dumps(previous,ensure_ascii=False),now))
            p['revision']=(old['revision']+1) if old else 1
            c.execute('INSERT INTO projects VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,revision=excluded.revision,body=excluded.body,updated=excluded.updated',(p['id'],p['name'],p['revision'],json.dumps(p,ensure_ascii=False),now))
        return p
    def list_projects(self):
        with self.connect() as c:return [dict(x) for x in c.execute('SELECT id,name,revision,updated FROM projects ORDER BY updated DESC')]
    def open(self,id):
        with self.connect() as c:r=c.execute('SELECT body FROM projects WHERE id=?',(id,)).fetchone()
        return json.loads(r[0]) if r else None
    def run(self,id,value):
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?)',(id,json.dumps(value,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
    def read_run(self,id):
        with self.connect() as c:r=c.execute('SELECT body FROM runs WHERE id=?',(id,)).fetchone()
        return json.loads(r[0]) if r else None
    def history(self,id):
        with self.connect() as c:return [dict(x) for x in c.execute('SELECT id,created,body FROM snapshots WHERE project_id=? ORDER BY id DESC LIMIT 50',(id,))]

    def delete_runs(self,ids):
        with self.connect() as c:
            c.executemany('DELETE FROM runs WHERE id=?',[(id,) for id in ids])
