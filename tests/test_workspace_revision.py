import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from backend.app.services.chat import ChatService, ChatRequest, CHAT_SYSTEM_PATH
from backend.app.services.config import defaults,rules,file_catalog,text_file,validate_file
from backend.app.services.generate import Generator
from backend.app.services.guidebook import GUIDE_PATH,guide_document,select_reference
from backend.app.services.prompt_builder import build
from backend.app.storage.repository import Repository
from backend.app.domain.models import Project
from backend.app.providers.base import BaseProvider
from tests.test_core import scene

class LLMReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.repo=Repository(Path(self.temp.name)/'p.sqlite')
    def tearDown(self):self.temp.cleanup()
    def test_generation_and_rewrite_receive_mode_specific_reference(self):
        inp=scene();inp.request_ko='구도와 카메라 시점을 정리해 줘'
        result=build(inp,defaults(),rules(),[],self.repo)
        source=next(s for s in result['sources'] if s['file']==GUIDE_PATH)
        self.assertIn('composition',source['section_ids'])
        self.assertIn('[NAI LLM reference]',result['messages'][0]['content'])
        self.assertIn('Return PromptIR JSON only',result['messages'][0]['content'])
        inp.task='rewrite';inp.request_ko='B의 의상만 수정'
        source=next(s for s in build(inp,defaults(),rules(),[],self.repo)['sources'] if s['file']==GUIDE_PATH)
        self.assertIn('editing',source['section_ids'])
    def test_saved_guide_edits_change_prompt_and_frozen_jobs_keep_old_revision(self):
        before=build(scene(),defaults(),rules(),[],self.repo)
        frozen={'file:'+p:text_file(p,self.repo) for p in file_catalog()}
        doc=guide_document();doc['version']='test-edited';doc['sections'][0]['generation'].append('TEST_REFERENCE_MARKER')
        content=json.dumps(doc);validate_file(GUIDE_PATH,content);self.repo.set('file:'+GUIDE_PATH,content)
        after=build(scene(),defaults(),rules(),[],self.repo)
        self.assertIn('TEST_REFERENCE_MARKER',after['messages'][0]['content'])
        self.assertNotEqual(before['prompt_version'],after['prompt_version'])
        self.assertNotIn('TEST_REFERENCE_MARKER',build(scene(),defaults(),rules(),[],frozen)['messages'][0]['content'])
    def test_guide_validation_rejects_invalid_data(self):
        self.assertIn(GUIDE_PATH,file_catalog())
        for value in [{}, {'version':'bad','sections':[]}, {'version':'bad','sections':[{'id':'core','generation':'not a list'}]}]:
            with self.assertRaises(ValueError):validate_file(GUIDE_PATH,json.dumps(value))
    def test_selection_is_bounded_and_casual_chat_stays_conversational(self):
        r=select_reference('구도 카메라 전신 시선','chat',max_chars=3000)
        self.assertIn('composition',r['source']['section_ids']);self.assertLessEqual(len(r['text']),3000)
        self.assertNotIn('Return PromptIR JSON only',r['text'])
        self.assertIn('Casual conversation',select_reference('안녕하세요','chat')['text'])
    def test_result_deletion_cleans_saved_and_undo_history(self):
        p=Project(input=scene()).model_dump();p['candidates']=[{'id':'one','title':'old'},{'id':'two','title':'keep'}];p['manual_overrides']={'one:c0:prompt':'edited one','two:c0:prompt':'keep'}
        p=self.repo.save(p,0)
        p=self.repo.save(p,p['revision'])
        p['legacy']['deleted_candidate_ids']=['one']
        p['history']=[{'candidates':copy.deepcopy(p['candidates']),'manual_overrides':copy.deepcopy(p['manual_overrides'])}]
        p=self.repo.save(p,p['revision'])
        self.assertEqual([c['id'] for c in p['candidates']],['two'])
        self.assertNotIn('one:c0:prompt',p['manual_overrides'])
        for snap in self.repo.history(p['id']):
            body=json.loads(snap['body']);self.assertEqual([c['id'] for c in body['candidates']],['two'])
        self.assertEqual(p['history'][0]['candidates'][0]['id'],'two')

class ChatEditingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.repo=Repository(Path(self.temp.name)/'p.sqlite')
        self.settings=defaults();self.settings['llm']['mode']='live';self.repo.set('settings',self.settings)
        self.generator=Generator(self.repo,None);self.service=ChatService(self.generator)
        self.provider=BaseProvider(self.settings)
        self.provider.inspect=AsyncMock(return_value={'models':[{'id':'stub'}], 'samplers':{}})
        self.provider.complete=AsyncMock(return_value=('old answer',{'choices':[{}]}))
        self.generator.provider=lambda _:self.provider
    async def asyncTearDown(self):
        if self.service.tasks:await asyncio.gather(*self.service.tasks)
        self.temp.cleanup()
    async def test_chat_receives_guide_and_edits_delete_reach_durable_record(self):
        job=self.service.start(ChatRequest(messages=[{'role':'user','content':'구도와 시선을 정해 주세요'}]))
        await asyncio.gather(*self.service.tasks)
        payload=self.provider.complete.call_args.args[0]
        self.assertIn('[composition]',payload['messages'][0]['content'])
        self.assertNotIn('response_format',payload)
        self.assertTrue(self.service.get(job['request_id'])['reference_sources'])
        self.service.edit_message(job['request_id'],'new answer')
        self.assertEqual(self.repo.read_run(job['request_id'])['content'],'new answer')
        self.service.delete_history([job['request_id']])
        self.assertIsNone(self.repo.read_run(job['request_id']));self.assertIsNone(self.service.get(job['request_id']))
    async def test_bulk_delete_protects_pending_and_other_kinds(self):
        self.repo.run('done',{'request_id':'done','kind':'chat','status':'completed','content':'x'})
        self.repo.run('generation',{'request_id':'generation','kind':'generation','status':'completed'})
        with self.assertRaises(ValueError):self.service.delete_history(['done','generation'])
        self.assertIsNotNone(self.repo.read_run('done'))
        await self.generator.lock.acquire()
        job=self.service.start(ChatRequest(messages=[{'role':'user','content':'hello'}]))
        with self.assertRaises(ValueError):self.service.edit_message(job['request_id'],'bad')
        with self.assertRaises(ValueError):self.service.delete_history([job['request_id']])
        self.service.cancel(job['request_id']);self.generator.lock.release()
    async def test_invalid_guide_does_not_leave_chat_queue_busy(self):
        self.repo.set('file:'+GUIDE_PATH,'{}')
        with self.assertRaises(ValueError):self.service.start(ChatRequest(messages=[{'role':'user','content':'hello'}]))
        self.assertFalse(self.service.jobs)
    async def test_custom_chat_prompt_is_frozen_at_submission_and_applied_next_time(self):
        self.repo.set('file:'+CHAT_SYSTEM_PATH,'OLD_CUSTOM_CHAT_PROMPT')
        await self.generator.lock.acquire()
        job=self.service.start(ChatRequest(messages=[{'role':'user','content':'hello'}]))
        self.repo.set('file:'+CHAT_SYSTEM_PATH,'NEW_CUSTOM_CHAT_PROMPT {{red scarf}}')
        self.generator.lock.release()
        await asyncio.gather(*self.service.tasks)
        sent=self.provider.complete.call_args.args[0]['messages'][0]['content']
        self.assertTrue(sent.startswith('OLD_CUSTOM_CHAT_PROMPT'))
        self.assertNotIn('NEW_CUSTOM_CHAT_PROMPT',sent)
        next_job=self.service.start(ChatRequest(messages=[{'role':'user','content':'hello again'}]))
        await asyncio.gather(*self.service.tasks)
        sent=self.provider.complete.call_args.args[0]['messages'][0]['content']
        self.assertTrue(sent.startswith('NEW_CUSTOM_CHAT_PROMPT {{red scarf}}'))
        self.assertIn('[NAI LLM reference]',sent)
        self.assertNotEqual(job['system_prompt_source']['hash'],next_job['system_prompt_source']['hash'])
        generation=build(scene(),defaults(),rules(),[],self.repo)
        self.assertNotIn('NEW_CUSTOM_CHAT_PROMPT',generation['messages'][0]['content'])
