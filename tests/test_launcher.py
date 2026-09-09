import hashlib,json,tempfile,threading,unittest,zipfile,socket
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from launcher.manager import download,extract_safe,Cancelled,Manager,free_port
from backend.app.services.config import defaults
from backend.app.storage.repository import Repository
class DownloadTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.data=b'verified payload'*200;self.requests=[];owner=self
  class Handler(BaseHTTPRequestHandler):
   def do_GET(self):
    start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0]);owner.requests.append(start)
    if self.path=='/no-range':start=0
    self.send_response(206 if start else 200)
    if start:self.send_header('Content-Range',f'bytes {start}-{len(owner.data)-1}/{len(owner.data)}')
    self.send_header('Content-Length',str(len(owner.data)-start));self.end_headers();self.wfile.write(owner.data[start:])
   def log_message(self,*args):pass
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.server.serve_forever,daemon=True).start()
  self.asset={'url':f'http://127.0.0.1:{self.server.server_port}/file','size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()};self.target=self.root/'file.bin';self.cancel=threading.Event()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
 def fetch(self):return download(self.asset,self.target,self.cancel,lambda *a:None)
 def test_verified_reuse(self):
  self.fetch();self.fetch();self.assertEqual(self.requests,[0]);self.assertEqual(self.target.read_bytes(),self.data)
 def test_range_resume(self):
  self.target.with_suffix('.bin.part').write_bytes(self.data[:50]);self.fetch();self.assertEqual(self.requests,[50]);self.assertEqual(self.target.read_bytes(),self.data)
 def test_ignored_range(self):
  self.asset['url']=self.asset['url'].replace('/file','/no-range');self.target.with_suffix('.bin.part').write_bytes(self.data[:50]);self.fetch();self.assertEqual(self.target.read_bytes(),self.data)
 def test_corrupt_preserves_existing(self):
  self.target.write_bytes(b'old');self.asset['sha256']='0'*64
  with self.assertRaises(ValueError):self.fetch()
  self.assertEqual(self.target.read_bytes(),b'old');self.assertFalse(self.target.with_suffix('.bin.part').exists())
 def test_cancel_preserves_partial(self):
  self.target.with_suffix('.bin.part').write_bytes(b'partial');self.cancel.set()
  with self.assertRaises(Cancelled):self.fetch()
  self.assertEqual(self.target.with_suffix('.bin.part').read_bytes(),b'partial')
class ControllerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'launcher').mkdir();(self.root/'launcher/assets.json').write_text('{}');self.events=[];self.m=Manager(self.root,self.events.append)
 def tearDown(self):self.tmp.cleanup()
 def test_zip_traversal(self):
  for name in ['../outside','..\\outside','C:/outside']:
   with zipfile.ZipFile(self.root/'bad.zip','w') as z:z.writestr(name,'bad')
   with self.assertRaises(ValueError):extract_safe(self.root/'bad.zip',self.root/'output')
  self.assertFalse((self.root/'outside').exists())
 def test_config_preservation(self):
  repo=Repository(self.root/'data/projects.sqlite');s=defaults();s['llm']['temperature']=.77;s['content_profile']['custom_preference_rules']=['keep'];repo.set('settings',s);repo.set('unrelated',{'saved':True})
  self.m.configure({'runtime':'cpu','model':'example','model_file':'a.gguf','db_file':'db.sqlite'},9876);actual=repo.get('settings')
  self.assertEqual(actual['llm']['temperature'],.77);self.assertEqual(actual['content_profile']['custom_preference_rules'],['keep']);self.assertEqual(actual['llm']['base_url'],'http://127.0.0.1:9876/v1');self.assertEqual(actual['llm']['mode'],'live');self.assertEqual(repo.get('unrelated'),{'saved':True})
 def test_busy_blocks(self):
  self.m.busy=True
  with patch.object(self.m,'start') as f:self.m.dispatch({'action':'start'});f.assert_not_called()
 def test_uninstalled_start(self):
  with self.assertRaisesRegex(ValueError,'셋업'):self.m.start()
 def test_busy_port(self):
  with socket.socket() as s:s.bind(('127.0.0.1',0));self.assertNotEqual(free_port(s.getsockname()[1]),s.getsockname()[1])
 def test_check_requires_generation(self):
  class Process:
   def poll(self):return None
  self.m.children=[Process()];self.m.url='http://127.0.0.1:1111';self.m.state={'model':'test'}
  responses=[{'mode':'live'},{'available':True,'snapshot_id':'db'},{'items':[{}]},{'request_id':'job','status':'queued'},{'request_id':'job','status':'completed','candidates':[{'id':'result'}]}]
  with patch('launcher.manager.api',side_effect=responses):self.m.check()
  self.assertTrue(json.loads((self.root/'data/execution-check.json').read_text())['passed'])
 def test_check_rejects_mock(self):
  class Process:
   def poll(self):return None
  self.m.children=[Process()];self.m.url='http://127.0.0.1:1111'
  with patch('launcher.manager.api',return_value={'mode':'mock'}):
   with self.assertRaisesRegex(ValueError,'실제 모델'):self.m.check()
 def test_stop_owned_only(self):
  class Process:
   stopped=False
   def poll(self):return None if not self.stopped else 0
   def terminate(self):self.stopped=True
   def wait(self,timeout):return 0
  owned=Process();unrelated=Process();self.m.children=[owned];self.m.stop();self.assertTrue(owned.stopped);self.assertFalse(unrelated.stopped)
 def test_full_setup_and_repeat_preserve_settings(self):
  from tests.test_core import fixture
  from types import SimpleNamespace
  fixtures=self.root/'fixtures';fixtures.mkdir();fixture(fixtures/'db.sqlite')
  (fixtures/'model.gguf').write_bytes(b'test-model')
  with zipfile.ZipFile(fixtures/'runtime.zip','w') as z:z.writestr('llama-server.exe',b'test-executable')
  with zipfile.ZipFile(fixtures/'pip.whl','w') as z:z.writestr('pip/__init__.py','')
  def asset(name):return {'filename':name,'sha256':hashlib.sha256((fixtures/name).read_bytes()).hexdigest(),'size':(fixtures/name).stat().st_size,'url':'https://unused.invalid/'+name}
  pip=dict(asset('pip.whl'),name='pip');self.m.manifest={'models':{'test':asset('model.gguf')},'runtimes':{'cpu':[asset('runtime.zip')]},'wheels':[pip],'database':asset('db.sqlite'),'runtime_release':'test'}
  wheels=self.root/'launcher/bootstrap/wheels';wheels.mkdir(parents=True);(wheels/'pip.whl').write_bytes((fixtures/'pip.whl').read_bytes())
  class Process:
   returncode=0
   def poll(self):return 0
  def local(a,subdir):
   out=self.root/subdir/a['filename'];out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((fixtures/a['filename']).read_bytes());return out
  with patch('launcher.manager.sys.executable',str(self.root/'python/python.exe')),patch.object(self.m,'spawn',return_value=Process()),patch.object(self.m,'local_asset',side_effect=local),patch('launcher.manager.shutil.disk_usage',return_value=SimpleNamespace(free=30_000_000_000)):
   self.m.setup('test','cpu');self.assertTrue(self.m.state_path.exists());self.assertTrue(self.events[-1]['installed'])
   repo=Repository(self.root/'data/projects.sqlite');s=repo.get('settings');s['llm']['temperature']=.81;repo.set('settings',s)
   self.m.setup('test','cpu');self.assertEqual(repo.get('settings')['llm']['temperature'],.81);self.assertEqual(repo.get('settings')['llm']['mode'],'live')
