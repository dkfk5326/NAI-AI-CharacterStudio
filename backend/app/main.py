import json,copy,asyncio,yaml,os,re
from uuid import uuid4
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request,Response
from fastapi.responses import JSONResponse,PlainTextResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .domain.models import GenerationInput,PromptIR,Project,CharacterInput,RelationInput
from .storage.repository import Repository,ROOT
from .services.config import defaults,rules,file_catalog,text_file,validate_file,public_settings
from .services.tag_search import TagService
from .services.character_suggestions import suggestions
from .services.generate import Generator
from .services.guidebook import guidebook, guide_document
from .services.chat import ChatService, ChatRequest, ChatEdit, ChatDelete
from .services.nai_renderer import render
from .services.validator import validate_ir,validate_input,manual_warnings
from .providers.base import ProviderError
repo=Repository();tags=TagService(repo);generator=Generator(repo,tags)
chat=ChatService(generator)
LOCAL_ORIGINS=['http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8000','http://localhost:8000']
if os.environ.get('NAI_PREVIEW_ORIGIN'):LOCAL_ORIGINS.append(os.environ['NAI_PREVIEW_ORIGIN'])
if os.environ.get('NAI_LOCAL_ORIGIN'):LOCAL_ORIGINS.append(os.environ['NAI_LOCAL_ORIGIN'])
app=FastAPI(title='NAI-AI-CharacterStudio',version='1.2.3d')
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','::1','testserver'])
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5173','http://localhost:5173'],allow_methods=['GET','POST','PUT'],allow_headers=['Content-Type'])
def envelope(data=None,revision=0,**kw):return {'request_id':uuid4().hex,'project_revision':revision,'prompt_version':'1.1',**(data or {}),**kw}
@app.exception_handler(HTTPException)
async def http_error(req,e):return JSONResponse(envelope(error={'code':'http_'+str(e.status_code),'message':str(e.detail)}),status_code=e.status_code)
@app.exception_handler(RequestValidationError)
async def schema_error(req,e):return JSONResponse(envelope(error={'code':'input_schema','message':str(e)}),status_code=422)
@app.exception_handler(ValueError)
async def value_error(req,e):return JSONResponse(envelope(error={'code':'validation_error','message':str(e)}),status_code=422)
@app.exception_handler(ProviderError)
async def provider_error(req,e):return JSONResponse(envelope(error={'code':e.code,'message':str(e),'raw':e.raw}),status_code=503)
@app.middleware('http')
async def local_guard(request:Request,call_next):
    origin=request.headers.get('origin')
    if origin and origin not in LOCAL_ORIGINS:return JSONResponse({'error':'허용되지 않은 Origin'},status_code=403)
    response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff';return response
@app.get('/api/health')
def health():return envelope(status='ok',mode=generator.settings()['llm']['mode'])
@app.post('/api/chat',status_code=202)
async def chat_send(body:ChatRequest):return chat.start(body)
@app.get('/api/chat/requests/{id}')
def chat_status(id:str):
    result=chat.get(id)
    if not result:raise HTTPException(404,'대화 요청을 찾을 수 없습니다.')
    return result
@app.post('/api/chat/cancel/{id}')
def chat_cancel(id:str):
    result=chat.cancel(id)
    if not result:raise HTTPException(404,'대화 요청을 찾을 수 없습니다.')
    return result
@app.put('/api/chat/messages/{id}')
def chat_edit_message(id:str,body:ChatEdit):
    if not body.content.strip():raise ValueError('빈 메시지는 저장할 수 없습니다.')
    result=chat.edit_message(id,body.content)
    return envelope(updated=result is not None)
@app.post('/api/chat/history/delete')
def chat_delete_history(body:ChatDelete):return envelope(chat.delete_history(body.request_ids))
@app.get('/api/models/capabilities')
async def capabilities():return envelope(capabilities=await generator.inspect(),profiles=rules(repo)['profiles'])
@app.get('/api/models/manifest')
async def manifest():
    from .services.model_manifest import model_manifest
    return envelope(manifest=await asyncio.to_thread(model_manifest,generator.settings()))
@app.post('/api/models/probe')
async def probe():return envelope(capabilities=await generator.inspect(probe=True))
@app.post('/api/characters/new')
def new_character():return envelope(character=CharacterInput().model_dump())
@app.post('/api/relations/new')
def new_relation(body:dict):return envelope(relation=RelationInput(**body).model_dump())
@app.post('/api/generate',status_code=202)
async def generate(inp:GenerationInput):return copy.deepcopy(generator.start(inp))
@app.post('/api/batch-plan')
def batch_plan(inp:GenerationInput):return envelope(generator.batch_plan(inp),inp.project_revision)
@app.post('/api/generate-batches',status_code=202)
async def generate_batches(inp:GenerationInput):return copy.deepcopy(generator.start_batched(inp))
@app.post('/api/rewrite',status_code=202)
async def rewrite(inp:GenerationInput):
    if not inp.previous_ir:raise ValueError('재작성할 이전 결과가 없습니다.')
    if inp.task=='generate':inp.task='rewrite'
    return copy.deepcopy(generator.start(inp))
@app.get('/api/requests/{id}')
def request_status(id:str):
    result=generator.jobs.get(id) or repo.read_run(id)
    if not result:raise HTTPException(404,'생성 요청이 없습니다.')
    return copy.deepcopy(result)
@app.post('/api/cancel/{id}')
def cancel(id:str):
    job=generator.cancel(id)
    if not job:raise HTTPException(404,'생성 요청이 없습니다.')
    return copy.deepcopy(job)
@app.post('/api/prompt-preview')
async def prompt_preview(inp:GenerationInput):return envelope(await generator.preview(inp),inp.project_revision)
@app.post('/api/render')
def render_api(body:dict):
    inp=GenerationInput.model_validate(body['input']);ir=PromptIR.model_validate(body['ir']);errors=validate_ir(ir,inp,body.get('refs',{}),rules(repo))
    # Rendering a saved IR may contain historical refs; validate IDs separately, no cross-request trust.
    errors=[x for x in errors if 'tag_ref' not in x and '참조 오류' not in x]
    if errors:raise ValueError('; '.join(errors))
    from .services.tag_grounding import after
    adapter=tags.snapshot();evidence=after(ir,adapter,{})
    mapping={e['term_path']:adapter.prompt_text(e['canonical_name'],e['category_name']) for e in evidence if e['canonical_name']}
    return envelope(rendered=render(ir,inp,rules(repo),mapping),revision=inp.project_revision)
@app.post('/api/validate')
def validate_api(body:dict):
    inp=GenerationInput.model_validate(body['input']);validate_input(inp,rules(repo));errors=[]
    if body.get('ir'):errors=validate_ir(PromptIR.model_validate(body['ir']),inp,body.get('refs',{}),rules(repo))
    return envelope(errors=errors,manual_warnings=manual_warnings(body.get('manual_text',''),rules(repo)['profiles'][inp.nai_profile_id]),revision=inp.project_revision)
@app.get('/api/settings')
def get_settings():return envelope(settings=public_settings(generator.settings()),defaults=public_settings(defaults()),nai_profiles=rules(repo)['profiles'])
@app.put('/api/settings')
def set_settings(body:dict):
    s=body.get('settings',body);base=defaults()
    if not isinstance(s,dict) or set(s)!=set(base):raise ValueError('설정의 최상위 항목을 유지하세요.')
    llm=s['llm']
    if llm['mode'] not in ['mock','live'] or llm['provider'] not in ['llama_cpp','lm_studio']:raise ValueError('연결 모드/어댑터가 잘못되었습니다.')
    generator.provider(s)
    if not 1024<=llm['context_size']<=131072 or not 1<=llm['max_output_tokens']<=32768:raise ValueError('토큰 설정 범위 오류입니다.')
    if llm['parallel_requests']!=1 or llm['max_repair_attempts']!=1:raise ValueError('동시 생성은 1, 복구 재시도는 최대 1회입니다.')
    old=generator.settings()
    if old['tag_config']!=s['tag_config']:tags.configure(s['tag_config']['tag_provider'])
    if not llm.get('api_key'):llm['api_key']=old['llm'].get('api_key','')
    repo.set('settings',s)
    repo.set('file:config/content-profile.yaml',yaml.safe_dump({'content_profile':s['content_profile']},allow_unicode=True,sort_keys=False))
    return envelope(settings=public_settings(s),restart_pending=any(old['llm'].get(k)!=llm.get(k) for k in ['context_size']) or old['runtime']!=s['runtime'])
@app.get('/api/projects')
def project_list():return envelope(items=repo.list_projects())
@app.put('/api/projects/{id}')
def project_save(id:str,project:Project):
    if id!=project.id:raise ValueError('프로젝트 ID가 다릅니다.')
    p=project.model_dump();p['settings'].get('llm',{}).pop('api_key',None)
    try:result=repo.save(p,project.revision)
    except ValueError:raise HTTPException(409,'다른 저장본이 있습니다. 다시 열어 주세요.')
    return envelope(project=result,revision=result['revision'])
@app.get('/api/projects/{id}/history')
def project_history(id:str):return envelope(items=repo.history(id))
@app.get('/api/projects/{id}/export')
def project_export(id:str,format:str='json'):
    p=repo.open(id)
    if not p:raise HTTPException(404)
    if format=='text':
        lines=[p['name'],'읽기용 프로젝트 내보내기 — NAI 한 칸에 붙이는 완성 프롬프트가 아닙니다.']
        for candidate in p['candidates']:
            for c in candidate['rendered']['characters']:
                lines.extend([c['label'],p['manual_overrides'].get(candidate['id']+':'+c['id']+':prompt',c['prompt']),'UC',p['manual_overrides'].get(candidate['id']+':'+c['id']+':uc',c['uc'])])
        return PlainTextResponse('\n\n'.join(lines))
    return JSONResponse(p)
@app.get('/api/projects/{id}')
def project_open(id:str):
    p=repo.open(id)
    if not p:raise HTTPException(404)
    return envelope(project=p,revision=p['revision'])
@app.post('/api/projects/import')
def project_import(body:dict):
    if body.get('schema_version')=='1.0':
        body['legacy']=copy.deepcopy(body);body['schema_version']='1.1'
        for candidate in body.get('candidates',[]):
            ir=candidate.get('ir',{});ir['schema_version']='1.1'
            for c in ir.get('characters',[]):
                for ts in list(c.get('groups',{}).values())+[c.get('undesired',[])]:
                    for term in ts:term.pop('verification',None);term.setdefault('kind','user_literal' if term.get('origin')=='user' else 'natural_language' if len(term['text'].split())>5 else 'tag');term['tag_ref']=None
            for r in ir.get('relations',[]):r.pop('confidence',None);r.setdefault('action_tag_ref',None)
            candidate['tag_evidence']=[]
    p=Project.model_validate(body);p.id=uuid4().hex;p.revision=0
    return envelope(project=repo.save(p.model_dump()))
@app.get('/api/files')
def files():return envelope(items=[{'path':p,'content':text_file(p,repo),'default':text_file(p)} for p in file_catalog()])
@app.put('/api/files')
def edit_file(body:dict):
    path,content=body['path'],body['content'];validate_file(path,content)
    if body.get('check_only'):return envelope(valid=True)
    repo.set('file:'+path,content)
    if path=='config/content-profile.yaml':
        s=generator.settings();s['content_profile']=yaml.safe_load(content)['content_profile'];repo.set('settings',s)
    return envelope(valid=True)
@app.get('/api/guide')
def guide():return envelope(markdown=guidebook(rules(repo),repo),document=guide_document(repo),rules=rules(repo))
@app.get('/api/tag-db/status')
def db_status():return envelope(tags.snapshot().inspect_capabilities())
@app.put('/api/tag-db/config')
async def db_config(body:dict):
    status=await asyncio.to_thread(tags.configure,body);s=generator.settings();s['tag_config']['tag_provider']['db_path']=body.get('db_path');repo.set('settings',s);return envelope(status)
@app.get('/api/tags/search')
def tag_search(q:str='',locale:str='ko',category:str|None=None,taxonomy_node_id:int|None=None,limit:int=20,cursor:str|None=None):return envelope(tags.snapshot().search_tags(q,locale,category,taxonomy_node_id,limit,cursor,exclude_deprecated=generator.settings()['tag_config']['search']['exclude_deprecated_from_suggestions']))
@app.post('/api/tags/resolve')
def resolve(body:dict):return envelope(items=tags.snapshot().resolve_terms(body['terms']))
@app.get('/api/tags/{tag_id}')
def tag_get(tag_id:int):
    item=tags.snapshot().get_tag(tag_id)
    if not item:raise HTTPException(404)
    return envelope(item=item)
@app.get('/api/characters/search')
def character_search(q:str='',copyright:str|None=None,limit:int=20):return envelope(tags.snapshot().search_characters(q,copyright,limit))
@app.get('/api/characters/{tag_id}/related-tags')
def related(tag_id:int,category:str='general',score_min:float=0.05,score_max:float|None=None,limit:int=30):return envelope(items=suggestions(tags.snapshot(),[tag_id],mapping=yaml.safe_load(text_file('knowledge/field-taxonomy-map.yaml',repo))['mapping'],category=category,score_min=score_min,score_max=score_max,limit=limit)[str(tag_id)])
@app.get('/api/taxonomy/nodes')
def taxonomy(parent_id:int|None=None,limit:int=100):return envelope(tags.snapshot().get_taxonomy_nodes(parent_id,max(1,min(limit,100))))
@app.get('/api/tag-overrides')
def overrides():return envelope(overrides=tags.overrides.get('tag_overrides',{'aliases':[],'favorites':[],'prompt_mappings':{},'observations':[],'revision':0}))
@app.put('/api/tag-overrides')
async def set_overrides(body:dict):
    old=tags.overrides.get('tag_overrides',{})
    aliases=body.get('aliases',[])
    if not isinstance(aliases,list) or len(aliases)>10000:raise ValueError('별칭은 최대 10000개의 목록입니다.')
    for a in aliases:
        if not isinstance(a,dict) or not isinstance(a.get('alias'),str) or not isinstance(a.get('canonical_name'),str) or not isinstance(a.get('verified',False),bool):raise ValueError('별칭에는 alias, canonical_name, verified가 필요합니다.')
    mappings=body.get('prompt_mappings',{})
    if not isinstance(mappings,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in mappings.items()):raise ValueError('표현 매핑은 문자열 객체입니다.')
    body['revision']=old.get('revision',0)+1
    config=generator.settings()['tag_config']['tag_provider'];await asyncio.to_thread(tags.configure,config,body)
    tags.overrides.set('tag_overrides',body)
    return envelope(overrides=body)
# Built frontend is served by the same localhost process; no external hosting needed.
DIST=ROOT/'frontend/dist'

class FrontendStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # Windows registry MIME associations must not decide whether browsers
        # can execute our modules when X-Content-Type-Options is nosniff.
        media_types = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css'}
        media_type = media_types.get(Path(path).suffix.lower())
        if response.status_code == 200 and media_type:
            response.headers['Content-Type'] = media_type + '; charset=utf-8'
        return response

if DIST.exists():
    # A partial patch must never open a blank browser window. Verify every hashed
    # bundle referenced by index.html before reporting the backend as healthy.
    index_path=DIST/'index.html'
    if not index_path.is_file():
        raise RuntimeError('프런트엔드 index.html이 없습니다. 누적 패치를 다시 덮어써 주세요.')
    index_html=index_path.read_text(encoding='utf-8')
    asset_refs=re.findall(r'(?:src|href)=[\"\'](/assets/[^\"\']+)[\"\']',index_html)
    missing=[ref for ref in asset_refs if not (DIST/ref.lstrip('/')).is_file()]
    if missing:
        raise RuntimeError('프런트엔드 파일이 누락되었습니다: '+', '.join(missing)+'. v1.2.3d 풀 패키지를 새 폴더에 다시 압축 해제해 주세요.')
    app.mount('/assets',FrontendStaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/')
    def index():return FileResponse(index_path,media_type='text/html',headers={'Cache-Control':'no-cache'})
