import asyncio,json,re,time,copy
from uuid import uuid4
from pydantic import ValidationError
from ..domain.models import PromptIR
from ..providers.mock import mock_ir
from ..providers.llama_cpp import LlamaCppProvider
from ..providers.lm_studio import LMStudioProvider
from ..providers.base import ProviderError
from .config import defaults,rules,public_settings,digest,file_catalog,text_file
from .validator import validate_input,validate_ir,preserve_fixed,warnings,ContractError
from .prompt_builder import build
from .token_budget import budget,BudgetError
from .nai_renderer import render
from .tag_grounding import before,after
from .model_manifest import model_manifest

class Generator:
    def __init__(self,repo,tags):self.repo=repo;self.tags=tags;self.lock=asyncio.Lock();self.jobs={};self.capabilities={}
    def settings(self):return self.repo.get('settings',defaults())
    def provider(self,settings):return (LMStudioProvider if settings['llm']['provider']=='lm_studio' else LlamaCppProvider)(settings)
    async def inspect(self,probe=False):
        s=self.settings()
        if s['llm']['mode']=='mock':return {'mode':'mock','connected':False,'message':'명시적 모의 모드. 실제 모델이 연결되지 않았습니다.','structured_output':'not_applicable','thinking_control':'not_applicable','tokenize':False,'samplers':{}}
        p=self.provider(s);caps=await p.inspect()
        caps['model_manifest']=await asyncio.to_thread(model_manifest,s)
        if probe and hasattr(p,'probe_schema'):
            async with self.lock: caps=await p.probe_schema()
        self.capabilities[digest(s['llm'])]=caps;return caps
    async def preview(self,inp):
        s=copy.deepcopy(self.settings());r=rules(self.repo);validate_input(inp,r);adapter=self.tags.snapshot();bundles,refs=before(inp,adapter);b=build(inp,s,r,bundles,self.repo);p=None
        if s['llm']['mode']=='live':
            p=self.provider(s);p.caps=self.capabilities.get(digest(s['llm']),{})
        b['budget']=budget(b['messages'],s,large=len(inp.characters)>5);b['applied_request']=p.payload(b['messages'],b['schema'],b['budget']['llm_output_limit']) if p else {'mode':'mock','messages':b['messages']};b['settings']=public_settings(s);b['mode']=s['llm']['mode'];return b
    def start(self,inp):
        rulebook=copy.deepcopy(rules(self.repo));validate_input(inp,rulebook)
        id=uuid4().hex;s=copy.deepcopy(self.settings());adapter=self.tags.snapshot()
        job={'request_id':id,'project_revision':inp.project_revision,'prompt_version':'1.1','status':'queued','candidates':[],'cancel_requested':False,'input':inp.model_dump(),'settings':public_settings(s),'db_snapshot':adapter.inspect_capabilities()}
        self.jobs[id]=job;self.repo.run(id,job)
        frozen_files={'file:'+path:text_file(path,self.repo) for path in file_catalog()}
        asyncio.create_task(self.run(id,inp.model_copy(deep=True),s,rulebook,adapter,frozen_files));return job
    def cancel(self,id):
        job=self.jobs.get(id)
        if job and job['status'] in ('queued','running'):
            job['cancel_requested']=True;job['status']='cancelling';self.repo.run(id,job)
            if job.get('active_child_request_id'):self.cancel(job['active_child_request_id'])
        return job or self.repo.read_run(id)
    async def run(self,id,inp,s,rulebook,adapter,frozen_files):
        job=self.jobs[id];started=time.perf_counter();attempts=[]
        try:
            async with self.lock:
                if job['cancel_requested']:job['status']='cancelled';return
                job['status']='running';self.repo.run(id,job)
                bundles,refs=await asyncio.to_thread(before,inp,adapter)
                p=None
                if s['llm']['mode']=='live':
                    p=self.provider(s);p.caps=self.capabilities.get(digest(s['llm'])) or await p.inspect()
                    if not p.caps.get('models'):raise ProviderError('loading','서버에 로드된 모델이 없습니다.')
                    p.caps['model_manifest']=await asyncio.to_thread(model_manifest,s)
                    if p.caps['model_manifest']['status']=='hash_mismatch':raise ProviderError('model_mismatch','선택한 프로필과 로컬 GGUF 해시가 다릅니다.')
                for n in range(inp.controls.variant_count):
                    if job['cancel_requested']:break
                    b=build(inp,s,rulebook,bundles,frozen_files)
                    exact=await p.input_tokens(b['messages']) if p else None
                    try:measure=budget(b['messages'],s,exact,large=len(inp.characters)>5)
                    except BudgetError:
                        # Drop optional retrieval first; do not truncate a character or user's required terms.
                        bundles=[];refs={};b=build(inp,s,rulebook,bundles,frozen_files);exact=await p.input_tokens(b['messages']) if p else None;measure=budget(b['messages'],s,exact,large=len(inp.characters)>5)
                    raw='';response={};repair=None;automatic=[]
                    for attempt in range(2):
                        if job['cancel_requested']:break
                        if repair:
                            b=build(inp,s,rulebook,bundles,frozen_files,repair);exact=await p.input_tokens(b['messages']) if p else None;measure=budget(b['messages'],s,exact,large=len(inp.characters)>5)
                        if p:
                            payload=p.payload(b['messages'],b['schema'],measure['llm_output_limit'],s['generation']['repair_temperature'] if attempt else s['generation']['creativity_temperature'] if inp.task=='vary' else None)
                            if payload.get('seed') is not None:payload['seed']+=n
                            raw,response=await p.complete(payload)
                        else:
                            payload={'mode':'mock','messages':b['messages']};raw=mock_ir(inp).model_dump_json();await asyncio.sleep(0)
                        record={'variant':n+1,'attempt':attempt,'applied_request':payload,'raw_response':raw,'raw_server_response':response,'sources':b['sources'],'repair_reason':repair['errors'] if repair else None};attempts.append(record)
                        try:
                            cleaned=raw.strip()
                            if cleaned.startswith('```') and cleaned.endswith('```'):
                                cleaned=re.sub(r'^```(?:json)?\s*|\s*```$','',cleaned);automatic.append({'reason':'JSON 코드펜스 제거','before':raw,'after':cleaned})
                            ir=PromptIR.model_validate_json(cleaned)
                            errors=validate_ir(ir,inp,refs,rulebook,syntax_enabled=s.get('validation',{}).get('enabled',True))
                            # Structural ID/ref checks are invariant data contract checks, never content filters.
                            if errors:raise ContractError('; '.join(errors))
                            ir,changes=preserve_fixed(ir,inp);automatic+=changes
                            break
                        except (ValidationError,ValueError) as e:
                            repair={'raw':raw,'errors':[str(e)]}
                            if attempt==1 or not p:raise ProviderError('invalid_json','출력 계약 검증에 실패했습니다.',raw)
                    if job['cancel_requested']:break
                    evidence=await asyncio.to_thread(after,ir,adapter,refs)
                    prompt_texts={e['term_path']:adapter.prompt_text(e['canonical_name'],e['category_name']) for e in evidence if e['canonical_name']}
                    rendered=render(ir,inp,rulebook,prompt_texts)
                    automatic.extend({'path':k,'reason':'검증된 태그 단위의 표시 표현 매핑','rendered_text':v} for k,v in prompt_texts.items())
                    candidate={'id':uuid4().hex,'ir':ir.model_dump(),'rendered':rendered,'tag_evidence':evidence,'db_snapshot':adapter.inspect_capabilities(),'settings_hash':b['settings_hash'],'rules_version':rulebook['version'],'prompt_version':b['prompt_version'],'model_profile':s['llm']['model_profile'],'seed':payload.get('seed'),'capabilities':p.caps if p else {'mode':'mock'},'budget':{**measure,'external_base_reserved_tokens':inp.controls.external_base_reserved_tokens if 'v4' in inp.nai_profile_id else None,'nai_combined_budget':rulebook['profiles'][inp.nai_profile_id]['combined_t5_budget'],'llm_output_tokens':response.get('usage',{}).get('completion_tokens'),'usage':response.get('usage',{})},'warnings':warnings(ir),'automatic_changes':automatic,'mode':s['llm']['mode'],'validation_status':'validated' if s.get('validation',{}).get('enabled',True) else 'unverified','elapsed_seconds':round(time.perf_counter()-started,3),'source_revision':inp.project_revision}
                    job['candidates'].append(candidate);job['attempts']=attempts;job['prompt_version']=b['prompt_version'];self.repo.run(id,job)
                job['status']='cancelled' if job['cancel_requested'] else 'completed'
        except (ProviderError,BudgetError,ValueError) as e:
            job['status']='cancelled' if job['cancel_requested'] else 'failed';job['error']={'code':getattr(e,'code','budget_conflict' if isinstance(e,BudgetError) else 'validation_error'),'message':str(e),'raw':getattr(e,'raw',None)}
        except Exception as e:
            job['status']='failed';job['error']={'code':'internal_error','message':str(e)}
        finally:
            job['attempts']=attempts;job['elapsed_seconds']=round(time.perf_counter()-started,3);self.repo.run(id,job)

    def batch_plan(self,inp):
        from .batch_plan import plan
        s=copy.deepcopy(self.settings());r=copy.deepcopy(rules(self.repo));validate_input(inp,r);files={'file:'+path:text_file(path,self.repo) for path in file_catalog()}
        batches=plan(inp,s,r,files)
        return {'batches':[{'character_ids':ids,'labels':[c.label for c in inp.characters if c.id in ids]} for ids in batches],'measurement':'estimate','notice':'연결된 관계는 같은 묶음에 보존합니다. 묶음 안의 실제 토큰 예산도 전송 전에 다시 검사합니다.'}

    def start_batched(self,inp):
        from .batch_plan import plan
        s=copy.deepcopy(self.settings());r=copy.deepcopy(rules(self.repo));validate_input(inp,r);files={'file:'+path:text_file(path,self.repo) for path in file_catalog()};adapter=self.tags.snapshot();batches=plan(inp,s,r,files)
        id=uuid4().hex;job={'request_id':id,'project_revision':inp.project_revision,'prompt_version':'1.1','status':'queued','candidates':[],'cancel_requested':False,'input':inp.model_dump(),'settings':public_settings(s),'db_snapshot':adapter.inspect_capabilities(),'batch_plan':batches}
        self.jobs[id]=job;self.repo.run(id,job);asyncio.create_task(self.run_batched(id,inp.model_copy(deep=True),s,r,adapter,files,batches));return job

    async def run_batched(self,id,inp,s,rulebook,adapter,files,batches):
        from .batch_plan import subset
        from ..domain.models import Unresolved
        parent=self.jobs[id];started=time.perf_counter();traces=[]
        try:
            parent['status']='running'
            for variant in range(inp.controls.variant_count):
                results=[]
                for ids in batches:
                    if parent['cancel_requested']:break
                    child_id=uuid4().hex;part=subset(inp,ids);child={'request_id':child_id,'project_revision':inp.project_revision,'prompt_version':'1.1','status':'queued','candidates':[],'cancel_requested':False};self.jobs[child_id]=child;parent['active_child_request_id']=child_id
                    await self.run(child_id,part,s,rulebook,adapter,files)
                    traces.append({'batch_character_ids':ids,'attempts':child.get('attempts',[])})
                    if child['status']=='failed':raise ProviderError(child['error']['code'],child['error']['message'],child['error'].get('raw'))
                    if child['status']=='cancelled':break
                    results.append(child['candidates'][0])
                if parent['cancel_requested']:break
                if len(results)!=len(batches):raise ProviderError('cancelled','묶음 생성이 완료되지 않았습니다.')
                chars={c['id']:c for result in results for c in result['ir']['characters']};rels={r['id']:r for result in results for r in result['ir']['relations']}
                merged=PromptIR.model_validate({'schema_version':'1.1','characters':[chars[c.id] for c in inp.characters],'relations':[rels[r.id] for r in inp.relations],'shared_terms':[t for result in results for t in result['ir']['shared_terms']],'unresolved':[u for result in results for u in result['ir']['unresolved']]})
                # Candidate refs are request-local. Evidence is re-resolved on the original frozen snapshot.
                for c in merged.characters:
                    for ts in list(c.groups.values())+[c.undesired]:
                        for t in ts:t.tag_ref=None
                for r in merged.relations:r.action_tag_ref=None
                for t in merged.shared_terms:t.tag_ref=None
                errors=validate_ir(merged,inp,{},rulebook)
                if errors:raise ContractError('; '.join(errors))
                evidence=after(merged,adapter,{})
                mapping={e['term_path']:adapter.prompt_text(e['canonical_name'],e['category_name']) for e in evidence if e['canonical_name']}
                out=copy.deepcopy(results[0]);out.update(id=uuid4().hex,ir=merged.model_dump(),rendered=render(merged,inp,rulebook,mapping),tag_evidence=evidence,budget={'batches':[c['budget'] for c in results],'nai_prompt_tokens':None,'nai_measurement':'unavailable'},batch_plan=batches,source_revision=inp.project_revision)
                parent['candidates'].append(out);parent['attempts']=traces;self.repo.run(id,parent)
            parent['status']='cancelled' if parent['cancel_requested'] else 'completed'
        except Exception as e:parent['status']='failed';parent['error']={'code':getattr(e,'code','batch_error'),'message':str(e),'raw':getattr(e,'raw',None)}
        finally:
            parent['attempts']=traces;parent['elapsed_seconds']=round(time.perf_counter()-started,3);self.repo.run(id,parent)
