"""Free-form local LLM chat, sharing the generation queue and GPU lock."""
import asyncio
import copy
import json
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator
from ..providers.base import ProviderError
from .config import digest, text_file, validate_file
from .guidebook import select_reference, GUIDE_PATH
from .token_budget import estimate_input

CHAT_SYSTEM_PATH = 'prompts/chat-system.md'

class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=16000)

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=81)
    context: str = Field(default='', max_length=24000)

    @model_validator(mode='after')
    def validate_turns(self):
        if any(not m.content.strip() for m in self.messages):
            raise ValueError('빈 메시지는 보낼 수 없습니다.')
        if self.messages[-1].role != 'user':
            raise ValueError('마지막 메시지는 사용자 메시지여야 합니다.')
        for i, message in enumerate(self.messages):
            if message.role != ('user' if i % 2 == 0 else 'assistant'):
                raise ValueError('사용자와 모델 메시지는 순서대로 번갈아 보내세요.')
        return self

async def prepare_messages(request, settings, provider, reference=None, system_prompt=None):
    system = text_file(CHAT_SYSTEM_PATH) if system_prompt is None else system_prompt
    if reference: system += "\n\n[NAI LLM reference]\n" + reference["text"]
    if request.context:
        system += '\n\nOptional project reference (JSON data):\n' + request.context
    turns = [m.model_dump() for m in request.messages]
    dropped = 0
    llm = settings['llm']
    output = min(llm['max_output_tokens'], 2048)
    while True:
        messages = [{'role':'system', 'content':system}, *turns]
        exact = await provider.input_tokens(messages)
        count = exact if exact is not None else estimate_input(messages)
        available = llm['context_size'] - llm['context_margin_tokens'] - count
        if available >= min(output, 512):
            return messages, min(output, available), dropped
        if len(turns) <= 1:
            raise ProviderError('chat_context_full', '현재 메시지와 참고 정보가 모델 문맥 한도를 넘습니다. 메시지를 줄이거나 현재 프로젝트 참고를 꺼 주세요.')
        turns = turns[2:]
        dropped += 2

class ChatService:
    def __init__(self, generator):
        self.generator = generator
        self.jobs = {}
        self.tasks = set()

    def persist(self, job):
        self.generator.repo.run(job['request_id'], job)

    def start(self, request):
        settings = copy.deepcopy(self.generator.settings())
        if settings['llm']['mode'] != 'live':
            raise ProviderError('chat_requires_model', '채팅에는 실제 LLM 연결이 필요합니다. 설정에서 로컬 모델 모드를 선택하고 연결을 확인해 주세요.')
        if any(j['status'] in ('queued','running','cancelling') for j in self.jobs.values()):
            raise ProviderError('chat_busy', '이전 대화의 응답이 끝난 뒤 다시 보내 주세요.')
        reference=select_reference(request.messages[-1].content+' '+request.context,mode='chat',repo=self.generator.repo,max_chars=3000)
        system_prompt=text_file(CHAT_SYSTEM_PATH,self.generator.repo)
        validate_file(CHAT_SYSTEM_PATH,system_prompt)
        job = {'request_id':uuid4().hex, 'kind':'chat', 'status':'queued', 'content':'', 'cancel_requested':False, 'dropped_messages':0}
        self.jobs[job['request_id']] = job
        job['reference_sources']=[reference['source']]
        job['system_prompt_source']={'file':CHAT_SYSTEM_PATH,'hash':digest(system_prompt)}
        self.persist(job)
        task = asyncio.create_task(self.run(job, request.model_copy(deep=True), settings, reference, system_prompt))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        # Finished jobs are durable; do not retain an unbounded second copy.
        for key in list(self.jobs):
            if len(self.jobs) <= 50: break
            if self.jobs[key]['status'] in ('completed','failed','cancelled'): del self.jobs[key]
        return copy.deepcopy(job)

    def get(self, request_id):
        job = self.jobs.get(request_id) or self.generator.repo.read_run(request_id)
        if not job or job.get('kind') != 'chat': return None
        if request_id not in self.jobs and job['status'] in ('queued','running','cancelling'):
            job.update(status='failed', error={'code':'server_restarted', 'message':'서버가 재시작되어 응답이 중단되었습니다. 다시 보내 주세요.'})
            self.persist(job)
        return copy.deepcopy(job)

    def cancel(self, request_id):
        job = self.jobs.get(request_id)
        if job and job['status'] in ('queued','running'):
            job['cancel_requested'] = True
            job['status'] = 'cancelling'
            self.persist(job)
        return self.get(request_id)

    def edit_message(self, request_id, content):
        job=self.get(request_id)
        if not job:return None
        if job['status'] in ('queued','running','cancelling'):
            raise ValueError('응답 중인 대화는 중단이 끝난 뒤 수정하세요.')
        job.update(content=content,edited=True)
        if request_id in self.jobs:self.jobs[request_id]=job
        self.persist(job)
        return job

    def delete_history(self, request_ids):
        ids=set(request_ids)
        for request_id in ids:
            job=self.get(request_id)
            if job and job['status'] in ('queued','running','cancelling'):
                raise ValueError('응답 중인 대화는 중단이 끝난 뒤 삭제하세요.')
            stored=self.generator.repo.read_run(request_id)
            if stored and stored.get('kind')!='chat':
                raise ValueError('채팅 기록이 아닌 요청은 삭제할 수 없습니다.')
        self.generator.repo.delete_runs(ids)
        for request_id in ids:self.jobs.pop(request_id,None)
        return {'deleted':len(ids)}

    async def run(self, job, request, settings, reference=None, system_prompt=None):
        try:
            async with self.generator.lock:
                if job['cancel_requested']:
                    job['status'] = 'cancelled'
                    return
                job['status'] = 'running'
                self.persist(job)
                provider = self.generator.provider(settings)
                provider.caps = self.generator.capabilities.get(digest(settings['llm'])) or await provider.inspect()
                if not provider.caps.get('models'):
                    raise ProviderError('loading', '서버에 로드된 모델이 없습니다.')
                messages, output, dropped = await prepare_messages(request, settings, provider, reference, system_prompt)
                if job['cancel_requested']:
                    job['status'] = 'cancelled'
                    return
                payload = provider.payload(messages, {}, output)
                payload.pop('response_format', None)  # Chat must never inherit PromptIR's JSON constraint.
                content, response = await provider.complete(payload)
                if job['cancel_requested']:
                    job['status'] = 'cancelled'
                else:
                    job.update(status='completed', content=content, dropped_messages=dropped,
                               model=payload.get('model',''), finish_reason=response.get('choices',[{}])[0].get('finish_reason'),
                               usage=response.get('usage',{}))
        except Exception as error:
            job.update(status='cancelled' if job['cancel_requested'] else 'failed',
                       error={'code':getattr(error,'code','chat_error'), 'message':str(error)})
        finally:
            self.persist(job)

class ChatEdit(BaseModel):
    content: str = Field(min_length=1,max_length=16000)

class ChatDelete(BaseModel):
    request_ids: list[str] = Field(default_factory=list,max_length=10000)
