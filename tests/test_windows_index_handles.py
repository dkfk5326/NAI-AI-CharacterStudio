"""Retain connections and emulate Windows refusal to rename open SQLite files."""
import sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.app.adapters import danbooru_sqlite as module

class WindowsIndexHandles(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=self.root/'source.sqlite'
  c=sqlite3.connect(self.db)
  try:
   c.executescript("CREATE TABLE tags(id INTEGER PRIMARY KEY,name TEXT,category_name TEXT,post_count INTEGER,is_deprecated INTEGER);INSERT INTO tags VALUES(1,'black_hair','general',100,0);CREATE TABLE tag_translations(tag_id INTEGER,locale TEXT,translated_name TEXT);INSERT INTO tag_translations VALUES(1,'ko','검은 머리');")
   c.commit()
  finally:c.close()
  self.connections=[];self.real_connect=sqlite3.connect
 def tearDown(self):
  for c in self.connections:c.close()
  self.tmp.cleanup()
 def tracked_connect(self,*args,**kwargs):
  c=self.real_connect(*args,**kwargs);self.connections.append(c);return c
 def assert_closed(self):
  for c in self.connections:
   with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
 def test_rename_after_close_and_persisted_search(self):
  real_replace=Path.replace;renames=[];owner=self
  def windows_replace(source,dest):
   owner.assert_closed();renames.append((source,dest));return real_replace(source,dest)
  with patch.object(module.sqlite3,'connect',side_effect=self.tracked_connect),patch.object(Path,'replace',windows_replace):
   a=module.DanbooruSQLiteAdapter(self.db,self.root/'index')
   self.assertIsNone(a.error);self.assertEqual(len(renames),1)
   self.assertEqual(a.search_tags('검은 머리')['items'][0]['canonical_name'],'black_hair')
   self.assertEqual(a.resolve_terms(['black_hair'])[0]['tag_id'],1);self.assert_closed()
   b=module.DanbooruSQLiteAdapter(self.db,self.root/'index')
   self.assertIsNone(b.error);self.assertEqual(len(renames),1);self.assert_closed()
 def test_build_failure_closes_handles_and_retry_recovers(self):
  with patch.object(module.sqlite3,'connect',side_effect=self.tracked_connect):
   with patch.object(module.DanbooruSQLiteAdapter,'has',side_effect=sqlite3.OperationalError('injected build failure')):
    a=module.DanbooruSQLiteAdapter(self.db,self.root/'index')
   self.assertIn('injected build failure',a.error);self.assert_closed()
   self.assertTrue(list((self.root/'index').glob('*.building')))
   b=module.DanbooruSQLiteAdapter(self.db,self.root/'index')
   self.assertIsNone(b.error);self.assertEqual(b.get_tag(1)['label_ko'],'검은 머리');self.assert_closed()
if __name__=='__main__':unittest.main()
