import argparse,sys,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.adapters.danbooru_sqlite import DanbooruSQLiteAdapter
p=argparse.ArgumentParser();p.add_argument('path');p.add_argument('--release',action='store_true');p.add_argument('--apply',action='store_true');args=p.parse_args()
a=DanbooruSQLiteAdapter(args.path,ROOT/'data');s=a.inspect_capabilities();print(json.dumps(s,ensure_ascii=False,indent=2))
if not s['available']:raise SystemExit(1)
if args.release and s['snapshot_sha256']!='392c1528e94cfa1f39838be6a4585718361af884d280f0b0050eab6211c85e38':raise SystemExit('Release hash mismatch')
if args.apply:
 body=json.dumps({'db_path':str(Path(args.path).resolve())}).encode();req=urllib.request.Request('http://127.0.0.1:8000/api/tag-db/config',body,{'Content-Type':'application/json'},method='PUT')
 with urllib.request.urlopen(req) as r:print(r.read().decode())
