from pathlib import Path
from .config import read_yaml
from ..adapters.danbooru_sqlite import hash_file
_cache={}
def model_manifest(settings):
    profiles=read_yaml('config/models.yaml')['profiles'];selected=profiles.get(settings['llm']['model_profile'],{})
    path=settings['llm'].get('model_path') or selected.get('local_path')
    result={'selected_profile':settings['llm']['model_profile'],'expected':selected,'local_path':path,'actual_sha256':None,'actual_bytes':None,'status':'not_configured','gpu_vram_gb':None,'tokens_per_second':None}
    if path:
        p=Path(path).expanduser()
        if not p.is_file():return {**result,'status':'missing'}
        stat=p.stat();key=(str(p.resolve()),stat.st_size,stat.st_mtime_ns)
        if key not in _cache:_cache[key]=hash_file(p)
        result.update(actual_sha256=_cache[key],actual_bytes=stat.st_size,status='hash_matched' if _cache[key]==selected.get('sha256') else 'hash_mismatch')
    return result
