import unittest,os,tempfile,json,asyncio
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.test_core import scene,fixture
from backend.app.domain.models import Project
from backend.app.services.config import defaults
from backend.app.services.generate import Generator
from backend.app.services.tag_search import TagService
from backend.app.storage.repository import Repository
import backend.app.main as main
class APITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.repo=Repository(self.path/'p.sqlite');s=defaults();s['llm']['mode']='mock';self.repo.set('settings',s);self.tags=TagService(self.repo);self.engine=Generator(self.repo,self.tags)
  self.patches=[patch.object(main,'repo',self.repo),patch.object(main,'tags',self.tags),patch.object(main,'generator',self.engine)]
  for p in self.patches:p.start()
  self.context=TestClient(main.app);self.client=self.context.__enter__()
 def tearDown(self):
  self.context.__exit__(None,None,None)
  for p in self.patches:p.stop()
  self.tmp.cleanup()
 def test_health_and_built_frontend(self):
  self.assertEqual(self.client.get('/api/health').json()['mode'],'mock');self.assertEqual(self.client.get('/').status_code,200)
 def test_new_ids_generated_server_side(self):
  a=self.client.post('/api/characters/new',json={}).json()['character'];b=self.client.post('/api/characters/new',json={}).json()['character'];self.assertNotEqual(a['id'],b['id'])
 def test_generate_poll_edit_save_export_open(self):
  response=self.client.post('/api/generate',json=scene().model_dump());self.assertEqual(response.status_code,202,response.text);j=response.json()
  import time
  for _ in range(200):
   j=self.client.get('/api/requests/'+j['request_id']).json()
   if j['status'] not in ['queued','running']:break
   time.sleep(.01)
  self.assertEqual(j['status'],'completed',j.get('error'));c=j['candidates'][0]
  project=Project(input=scene(),candidates=[c]);project.manual_overrides[c['id']+':c0:prompt']='girl, user edited'
  saved=self.client.put('/api/projects/'+project.id,json=project.model_dump());self.assertEqual(saved.status_code,200,saved.text)
  opened=self.client.get('/api/projects/'+project.id).json()['project'];self.assertEqual(opened['manual_overrides'][c['id']+':c0:prompt'],'girl, user edited');text=self.client.get('/api/projects/'+project.id+'/export?format=text').text;self.assertIn('girl, user edited',text)
  conflict=self.client.put('/api/projects/'+project.id,json=project.model_dump());self.assertEqual(conflict.status_code,409)
 def test_actual_request_preview(self):
  r=self.client.post('/api/prompt-preview',json=scene().model_dump());self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['messages'][0]['role'],'system');self.assertNotIn('Authorization',r.text)
 def test_settings_and_content_editor(self):
  r=self.client.get('/api/settings').json();s=r['settings'];s['content_profile']['custom_preference_rules']=['test preference'];r=self.client.put('/api/settings',json={'settings':s});self.assertEqual(r.status_code,200,r.text)
  preview=self.client.post('/api/prompt-preview',json=scene().model_dump()).json();self.assertIn('test preference',preview['messages'][0]['content'])
 def test_file_validation_and_no_path_traversal(self):
  r=self.client.put('/api/files',json={'path':'../../etc/passwd','content':'x'});self.assertEqual(r.status_code,422)
  r=self.client.put('/api/files',json={'path':'prompts/rewrite.md','content':'{{unknown}}'});self.assertEqual(r.status_code,422)
 def test_tag_route_order_and_korean_search(self):
  fixture(self.path/'db.sqlite');r=self.client.put('/api/tag-db/config',json={'db_path':str(self.path/'db.sqlite')});self.assertEqual(r.status_code,200,r.text)
  r=self.client.get('/api/tags/search',params={'q':'검은 머리'});self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['items'][0]['canonical_name'],'black_hair');self.assertEqual(self.client.get('/api/tags/1').json()['item']['tag_id'],1)
 def test_bad_db_preserves_previous_snapshot(self):
  fixture(self.path/'db.sqlite');self.client.put('/api/tag-db/config',json={'db_path':str(self.path/'db.sqlite')});old=self.client.get('/api/tag-db/status').json()['snapshot_id'];r=self.client.put('/api/tag-db/config',json={'db_path':str(self.path/'missing.sqlite')});self.assertEqual(r.status_code,422);self.assertEqual(self.client.get('/api/tag-db/status').json()['snapshot_id'],old)
 def test_slot_overflow_is_clear(self):
  inp=scene(7);inp.nai_profile_id='nai-v4';r=self.client.post('/api/generate',json=inp.model_dump());self.assertEqual(r.status_code,422);self.assertIn('한도',r.text)
 def test_origin_protection(self):
  r=self.client.put('/api/settings',headers={'Origin':'https://evil.example'},json={'settings':defaults()});self.assertEqual(r.status_code,403)
