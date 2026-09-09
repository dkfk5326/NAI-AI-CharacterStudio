import argparse,subprocess,sys,json,yaml,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--llama-server',required=True);p.add_argument('--profile',default='gemma4-e4b-hauhau-q5km');p.add_argument('--check-only',action='store_true');args=p.parse_args()
config=yaml.safe_load((ROOT/'config/models.yaml').read_text(encoding='utf-8'));profile=config['profiles'][args.profile]
exe=str(Path(args.llama_server).expanduser().resolve());help_text=subprocess.run([exe,'--help'],capture_output=True,text=True,check=True).stdout
version=subprocess.run([exe,'--version'],capture_output=True,text=True,check=True);version=(version.stdout+version.stderr).strip()
required=['--jinja','--parallel','--host','--port','--chat-template-kwargs']
missing=[x for x in required if x not in help_text]
if missing:raise SystemExit('This binary lacks required options: '+', '.join(missing))
model=Path(profile.get('local_path') or ROOT/'models'/profile['filename'])
if not model.is_file():raise SystemExit('Download the selected profile first with scripts/download_model.py.')
with model.open('rb') as f:actual_hash=hashlib.file_digest(f,'sha256').hexdigest()
if actual_hash!=profile['sha256']:raise SystemExit('Selected GGUF hash does not match the verified model profile.')
cmd=[exe,'-m',str(model),'--jinja','-c','8192','-ngl','99','--parallel','1','--host','127.0.0.1','--port','8080','--chat-template-kwargs','{"enable_thinking":false}']
record={'executable':exe,'version':version,'command':cmd,'model_profile':args.profile,'model_sha256':actual_hash,'model_bytes':model.stat().st_size,'help_verified':True,'gpu_tested':False,'thinking_behavior':'verify via /api/models/capabilities template probe'}
(ROOT/'data').mkdir(exist_ok=True);(ROOT/'data/runtime-lock.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));(ROOT/'data/llama-server-help.txt').write_text(help_text)
print(json.dumps(record,ensure_ascii=False,indent=2))
if not args.check_only:raise SystemExit(subprocess.call(cmd))
