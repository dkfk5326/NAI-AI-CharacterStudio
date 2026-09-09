"""Explicit download only; called manually, never by generation or fallback."""
import sys,argparse,urllib.request,hashlib,yaml,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--profile',default='gemma4-e4b-hauhau-q5km');args=p.parse_args()
config=yaml.safe_load((ROOT/'config/models.yaml').read_text(encoding='utf-8'));profile=config['profiles'][args.profile]
url='https://huggingface.co/'+profile['repository']+'/resolve/'+profile['revision']+'/'+profile['filename']
target=ROOT/'models'/profile['filename'];target.parent.mkdir(exist_ok=True);partial=target.with_suffix('.gguf.part')
print('Downloading explicitly selected profile:',args.profile,flush=True)
h=hashlib.sha256();n=0
with urllib.request.urlopen(url,timeout=120) as response,partial.open('wb') as file:
    while block:=response.read(4*1024*1024):h.update(block);file.write(block);n+=len(block)
if h.hexdigest()!=profile['sha256']:raise SystemExit('SHA-256 mismatch; the .part file was not activated.')
partial.replace(target);profile.update(local_path=str(target),downloaded_bytes=n)
(ROOT/'config/models.yaml').write_text(yaml.safe_dump(config,sort_keys=False,allow_unicode=True));print(json.dumps({'path':str(target),'bytes':n,'sha256':h.hexdigest()},indent=2))
