import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.services.chat import ChatRequest, ChatService, prepare_messages
from backend.app.services.config import defaults
from backend.app.services.generate import Generator
from backend.app.services.guidebook import guide_document, guidebook
from backend.app.storage.repository import Repository
from backend.app.providers.base import BaseProvider, ProviderError
import backend.app.main as main


def request(text='안녕하세요', context=''):
    return ChatRequest(messages=[{'role':'user','content':text}], context=context)

class ChatTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.temp.name)/'projects.sqlite')
        self.settings = defaults()
        self.settings['llm']['mode'] = 'live'
        self.repo.set('settings',self.settings)
        self.generator = Generator(self.repo,None)
        self.provider = BaseProvider(self.settings)
        caps = {'models':[{'id':'test-model'}], 'structured_output':'supported', 'samplers':{}}
        self.provider.inspect = AsyncMock(return_value=caps)
        self.provider.complete = AsyncMock(return_value=('함께 이야기해 봐요.',{'choices':[{'finish_reason':'stop'}]}))
        self.generator.provider = lambda _:self.provider
        self.chat = ChatService(self.generator)

    async def asyncTearDown(self):
        if self.chat.tasks: await asyncio.gather(*self.chat.tasks)
        self.temp.cleanup()

    async def finish(self, job):
        if self.chat.tasks: await asyncio.gather(*self.chat.tasks)
        return self.chat.get(job['request_id'])

    async def test_free_text_and_context_without_json_schema(self):
        job = self.chat.start(request(context='{"scene":"서점"}'))
        result = await self.finish(job)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['content'],'함께 이야기해 봐요.')
        payload = self.provider.complete.call_args.args[0]
        self.assertNotIn('response_format',payload)
        self.assertEqual(payload['model'],'test-model')
        self.assertIn('서점',payload['messages'][0]['content'])
        self.assertEqual(payload['messages'][-1]['content'],'안녕하세요')
        self.assertEqual(self.repo.read_run(job['request_id'])['kind'],'chat')

    async def test_shared_lock_and_queued_cancel(self):
        await self.generator.lock.acquire()
        job = self.chat.start(request())
        await asyncio.sleep(0)
        self.provider.complete.assert_not_awaited()
        self.assertEqual(self.chat.get(job['request_id'])['status'],'queued')
        self.chat.cancel(job['request_id'])
        self.generator.lock.release()
        self.assertEqual((await self.finish(job))['status'],'cancelled')
        self.provider.complete.assert_not_awaited()

    async def test_running_cancel_keeps_lock_until_http_finishes(self):
        entered,release=asyncio.Event(),asyncio.Event()
        async def complete(payload):
            entered.set();await release.wait()
            return 'discard this answer',{'choices':[{}]}
        self.provider.complete=AsyncMock(side_effect=complete)
        job=self.chat.start(request())
        await entered.wait()
        self.chat.cancel(job['request_id'])
        self.assertTrue(self.generator.lock.locked())
        with self.assertRaises(ProviderError):self.chat.start(request())
        release.set()
        result=await self.finish(job)
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(result['content'],'')
        self.assertFalse(self.generator.lock.locked())

    async def test_history_trimming_keeps_latest_and_pairs(self):
        self.settings['llm']['context_size']=2500
        self.provider.input_tokens=AsyncMock(side_effect=lambda messages:3000 if len(messages)>2 else 1000)
        inp=ChatRequest(messages=[{'role':'user','content':'old'}, {'role':'assistant','content':'old answer'}, {'role':'user','content':'latest'}])
        messages,output,dropped=await prepare_messages(inp,self.settings,self.provider)
        self.assertEqual([m['role'] for m in messages],['system','user'])
        self.assertEqual(messages[-1]['content'],'latest')
        self.assertEqual(dropped,2)
        self.assertGreater(output,0)
        self.provider.input_tokens=AsyncMock(return_value=10000)
        with self.assertRaises(ProviderError):await prepare_messages(inp,self.settings,self.provider)

    async def test_error_and_restart_recovery(self):
        self.provider.complete=AsyncMock(side_effect=ProviderError('unreachable','연결 실패'))
        result=await self.finish(self.chat.start(request()))
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['error']['code'],'unreachable')
        self.repo.run('interrupted',{'request_id':'interrupted','kind':'chat','status':'running'})
        self.assertEqual(self.chat.get('interrupted')['error']['code'],'server_restarted')
        self.repo.run('generation',{'request_id':'generation','status':'running'})
        self.assertIsNone(self.chat.get('generation'))

    async def test_mock_is_not_presented_as_real_chat(self):
        self.settings['llm']['mode']='mock';self.repo.set('settings',self.settings)
        with self.assertRaises(ProviderError):self.chat.start(request())
        self.provider.complete.assert_not_awaited()

    async def test_invalid_turns_rejected(self):
        for messages in [[],[{'role':'system','content':'x'}],[{'role':'user','content':' '}],[{'role':'assistant','content':'x'}],[{'role':'user','content':'x'},{'role':'user','content':'y'}]]:
            with self.assertRaises(ValidationError):ChatRequest(messages=messages)

class ChatAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.repo=Repository(Path(self.temp.name)/'p.sqlite')
        settings=defaults();settings['llm']['mode']='live';self.repo.set('settings',settings)
        self.generator=Generator(self.repo,None)
        provider=BaseProvider(settings)
        provider.inspect=AsyncMock(return_value={'models':[{'id':'stub'}], 'samplers':{}})
        provider.complete=AsyncMock(return_value=('안녕하세요.',{'choices':[{'finish_reason':'stop'}]}))
        self.generator.provider=lambda _:provider
        self.service=ChatService(self.generator)
        self.patcher=patch.object(main,'chat',self.service);self.patcher.start()
        self.context=TestClient(main.app);self.client=self.context.__enter__()
    def tearDown(self):
        self.context.__exit__(None,None,None);self.patcher.stop();self.temp.cleanup()
    def test_routes_complete_and_validate(self):
        result=self.client.post('/api/chat',json={'messages':[{'role':'user','content':'안녕'}]})
        self.assertEqual(result.status_code,202)
        rid=result.json()['request_id']
        for _ in range(20):
            status=self.client.get('/api/chat/requests/'+rid).json()
            if status['status']=='completed':break
        self.assertEqual(status['content'],'안녕하세요.')
        self.assertEqual(self.client.post('/api/chat',json={'messages':[]}).status_code,422)
        self.assertEqual(self.client.get('/api/chat/requests/missing').status_code,404)
        self.assertEqual(self.client.post('/api/chat/cancel/missing',json={}).status_code,404)
    def test_browser_prompt_file_edit_persists_and_validates_literal_text(self):
        path='prompts/chat-system.md'
        with patch.object(main,'repo',self.repo):
            before=next(f for f in self.client.get('/api/files').json()['items'] if f['path']==path)
            content='간결하게 답하세요. {{red scarf}}'
            self.assertEqual(self.client.put('/api/files',json={'path':path,'content':content}).status_code,200)
            after=next(f for f in self.client.get('/api/files').json()['items'] if f['path']==path)
            self.assertEqual(after['content'],content)
            self.assertEqual(after['default'],before['default'])
            for invalid in ['  ','x'*16001]:
                self.assertEqual(self.client.put('/api/files',json={'path':path,'content':invalid}).status_code,422)
            self.assertEqual(Repository(self.repo.path).get('file:'+path),content)
    def test_guide_is_machine_reference_with_output_modes(self):
        response=self.client.get('/api/guide')
        self.assertEqual(response.status_code,200)
        body=response.json();doc=body['document']
        self.assertIn('LLM reference',doc['purpose'])
        self.assertEqual(len({s['id'] for s in doc['sections']}),len(doc['sections']))
        self.assertEqual(body['markdown'],guidebook())
        for section in doc['sections']:
            self.assertIn('common',section)
            self.assertIn('generation',section)
            self.assertIn('chat',section)
            for source in section['sources']:
                self.assertTrue(source.startswith('https://docs.novelai.net/'))
