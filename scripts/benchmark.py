"""Hardware-side benchmark. Never invents NAI token counts or meaning scores."""
import argparse,json,time,urllib.request,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests.test_core import scene
p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8000');p.add_argument('--output',default=str(ROOT/'data/hardware-benchmark.json'));args=p.parse_args()
def request(path,body=None):
 req=urllib.request.Request(args.base_url+path,json.dumps(body).encode() if body is not None else None,{'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=150) as r:return json.load(r)
health=request('/api/health')
if health['mode']!='live':raise SystemExit('Actual LLM benchmark requires explicitly selected live mode.')
rows=[]
for n in [1,2,5]:
 inp=scene(n).model_dump();start=time.perf_counter();job=request('/api/generate',inp)
 while job['status'] in ['queued','running','cancelling']:
  time.sleep(.25);job=request('/api/requests/'+job['request_id'])
 try:gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,memory.total','--format=csv,noheader,nounits'],text=True).strip()
 except (OSError,subprocess.CalledProcessError):gpu=None
 rows.append({'people':n,'status':job['status'],'elapsed_seconds':time.perf_counter()-start,'request_id':job['request_id'],'error':job.get('error'),'budget':job['candidates'][0]['budget'] if job.get('candidates') else None,'gpu_memory_after_generation_mib':gpu,'gpu_peak_memory_mib':None,'semantic_accuracy':None,'nai_image_effect':None})
 print(n,job['status'],flush=True)
out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(out)
