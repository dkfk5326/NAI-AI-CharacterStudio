import json,subprocess,sys,tempfile,unittest
from pathlib import Path

class LauncherDefault(unittest.TestCase):
 def ready(self,state=None):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'launcher').mkdir();(root/'launcher/assets.json').write_text('{}')
   source=Path(__file__).resolve().parents[1]/'launcher/manager.py'
   (root/'launcher/manager.py').write_bytes(source.read_bytes())
   if state:
    (root/'data').mkdir();(root/'data/install.json').write_text(json.dumps(state))
   r=subprocess.run([sys.executable,'-X','utf8',str(root/'launcher/manager.py')],input='{"action":"quit"}\n',text=True,capture_output=True,timeout=10)
   self.assertEqual(r.returncode,0,r.stderr)
   return json.loads(r.stdout.splitlines()[0])
 def test_clean_install_defaults_to_cuda(self):
  self.assertEqual(self.ready()['runtime'],'cuda12')
 def test_explicit_saved_selection_is_preserved(self):
  self.assertEqual(self.ready({'model':'test','runtime':'cpu'})['runtime'],'cpu')
if __name__=='__main__':unittest.main()
