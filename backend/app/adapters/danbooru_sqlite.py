"""Read-only original DB; a small SQLite sidecar owns searchable labels and aliases."""
import sqlite3,hashlib,json,time,copy
from collections import OrderedDict
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

def literal_like(s):return s.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
def hash_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
class DanbooruSQLiteAdapter:
    def __init__(self,path=None,index_dir=None,overrides=None):
        self.path=Path(path).expanduser().resolve() if path else None
        self.overrides=overrides or {};self.index_dir=Path(index_dir or './data');self.error=None;self.schema={};self.snapshot=None;self.index_path=None;self.cache=OrderedDict();self.cache_entries=512
        if not self.path:return
        try:
            self.snapshot=hash_file(self.path)
            with closing(self.connect()) as c:
                if c.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('SQLite 무결성 검사 실패')
                for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                    n=row[0]
                    if not n.replace('_','').isalnum():continue
                    self.schema[n]=[x[1] for x in c.execute('PRAGMA table_info("'+n+'")')]
                if not {'id','name'}.issubset(self.schema.get('tags',[])):raise ValueError('tags.id/name이 없습니다.')
                self.indexes=[dict(x) for x in c.execute("SELECT name,tbl_name FROM sqlite_master WHERE type='index'")]
                self.build_info=[dict(x) for x in c.execute('SELECT * FROM build_info LIMIT 30')] if 'build_info' in self.schema else []
            self.prepare_index()
        except (OSError,ValueError,sqlite3.Error) as e:self.error=str(e)
    def connect(self):
        c=sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');return c
    def has(self,table,*cols):return set(cols).issubset(self.schema.get(table,[]))
    def inspect_capabilities(self):
        available=bool(self.path and not self.error)
        return {'available':available,'path':str(self.path) if self.path else None,'snapshot_id':self.snapshot,'source_id':'danbooru_sqlite','snapshot_sha256':self.snapshot,'error':self.error,'schema':self.schema,'build_info':getattr(self,'build_info',[]),'indexes':getattr(self,'indexes',[]),'index_status':'ready' if self.index_path else 'unavailable','capabilities':{k:available and self.has(t,*cs) for k,t,cs in [('tags','tags',['id','name']),('translations','tag_translations',['tag_id','locale','translated_name']),('characters','characters',['tag_id']),('copyrights','character_copyright_links',['character_tag_id','copyright_tag_id']),('related_tags','character_related_tags',['character_tag_id','related_tag_id','score']),('taxonomy','taxonomy_nodes',['id','node_key','title']),('taxonomy_edges','taxonomy_edges',['parent_node_id','child_node_id']),('memberships','taxonomy_tag_memberships',['taxonomy_node_id','tag_id'])]}}
    def prepare_index(self):
        self.index_dir.mkdir(parents=True,exist_ok=True);ovhash=hashlib.sha256(json.dumps(self.overrides,sort_keys=True).encode()).hexdigest()[:12]
        dest=self.index_dir/('tag-search-'+self.snapshot+'-'+ovhash+'.sqlite')
        if not dest.exists():
            temp=dest.with_suffix('.building');temp.unlink(missing_ok=True)
            # SQLite context managers commit/rollback but do not close file handles.
            # Commit first, then close both handles before renaming on Windows.
            with closing(sqlite3.connect(temp)) as idx,closing(self.connect()) as src,idx:
                idx.executescript('CREATE TABLE terms(id INTEGER, canonical TEXT, label TEXT, locale TEXT, kind INTEGER, category TEXT, post_count INTEGER, deprecated INTEGER);')
                cols=self.schema['tags'];expr=lambda n,d:n if n in cols else d
                query='SELECT id,name,'+expr('category_name',"'unknown'")+','+expr('post_count','0')+','+expr('is_deprecated','0')+' FROM tags'
                cursor=src.execute(query)
                while rows:=cursor.fetchmany(2000):idx.executemany('INSERT INTO terms VALUES(?,?,?,?,?,?,?,?)',[(r[0],r[1],r[1],'en',0,r[2],r[3],r[4]) for r in rows])
                idx.executescript('CREATE INDEX canonical_idx ON terms(canonical); CREATE INDEX tag_id_idx ON terms(id);')
                for col in ['normalized_name','display_name']:
                    if col in cols:
                        for r in src.execute('SELECT id,name,"'+col+'" FROM tags WHERE "'+col+'" IS NOT NULL'):
                            idx.execute('INSERT INTO terms SELECT id,canonical,?,\'en\',2,category,post_count,deprecated FROM terms WHERE id=? AND kind=0',(r[2],r[0]))
                if self.has('tag_translations','tag_id','locale','translated_name'):
                    for r in src.execute('SELECT tag_id,locale,translated_name FROM tag_translations'):
                        idx.execute('INSERT INTO terms SELECT id,canonical,?,?,1,category,post_count,deprecated FROM terms WHERE id=? AND kind=0',(r[2],r[1],r[0]))
                for alias in self.overrides.get('aliases',[]):
                    if alias.get('verified'):
                        idx.execute('INSERT INTO terms SELECT id,canonical,?,\'ko\',1,category,post_count,deprecated FROM terms WHERE canonical=? AND kind=0',(alias['alias'],alias['canonical_name']))
                idx.executescript('CREATE INDEX label_idx ON terms(label COLLATE NOCASE);')
            temp.replace(dest)
        self.index_path=dest
    def envelope(self,items=None,next_cursor=None,**extra):return {'items':items or [],'next_cursor':next_cursor,'snapshot_id':self.snapshot,'capabilities':self.inspect_capabilities()['capabilities'],**extra}
    def get_tag(self,id,locale='ko'):
        if not self.index_path:return None
        with closing(sqlite3.connect(self.index_path)) as c:
            c.row_factory=sqlite3.Row;r=c.execute('SELECT * FROM terms WHERE id=? AND kind=0',(id,)).fetchone()
            if not r:return None
            labels=c.execute('SELECT label FROM terms WHERE id=? AND locale=? AND kind=1',(id,locale)).fetchall()
        result={'tag_id':r['id'],'canonical_name':r['canonical'],'prompt_text':self.prompt_text(r['canonical'],r['category']),'label_ko':labels[0][0] if labels else r['canonical'],'category_name':r['category'],'post_count':r['post_count'],'is_deprecated':bool(r['deprecated']),'danbooru_status':'deprecated' if r['deprecated'] else 'matched','nai_evidence':'unknown'}
        return result
    def prompt_text(self,name,category='general'):
        mapping=self.overrides.get('prompt_mappings',{}).get(name)
        return mapping or (name if category in ['character','copyright'] else name.replace('_',' '))
    def search_tags(self,*args,**kwargs):
        started=time.perf_counter();key=json.dumps([args,kwargs],sort_keys=True,ensure_ascii=False)
        if key in self.cache:
            self.cache.move_to_end(key);result=copy.deepcopy(self.cache[key]);result['cache_hit']=True;result['elapsed_ms']=round((time.perf_counter()-started)*1000,3);return result
        result=self._search_tags(*args,**kwargs);result['cache_hit']=False
        if self.index_path:
            self.cache[key]=copy.deepcopy(result)
            while len(self.cache)>self.cache_entries:self.cache.popitem(last=False)
        return result
    def _search_tags(self,q='',locale='ko',category=None,taxonomy_node_id=None,limit=20,cursor=None,exclude_deprecated=False,**kwargs):
        if not self.index_path:return self.envelope(error=self.error or 'DB 미연결')
        started=time.perf_counter();limit=max(1,min(int(limit),100));offset=max(0,int(cursor or 0));q=q[:200];escaped=literal_like(q)
        where=['(label LIKE ? ESCAPE \'\\\' OR canonical = ?)','locale IN (?,\'en\')'];args=['%'+escaped+'%',q,locale]
        if category:where.append('category=?');args.append(category)
        if exclude_deprecated:where.append('deprecated=0')
        if taxonomy_node_id is not None:
            if not self.has('taxonomy_tag_memberships','taxonomy_node_id','tag_id'):return self.envelope()
            with closing(self.connect()) as original:ids=[r[0] for r in original.execute('SELECT tag_id FROM taxonomy_tag_memberships WHERE taxonomy_node_id=?',(taxonomy_node_id,))]
            if not ids:return self.envelope()
            where.append('id IN ('+','.join('?' for _ in ids)+')');args+=ids
        sql='SELECT id,MIN(CASE WHEN canonical=? THEN 0 WHEN label=? AND kind=1 THEN 1 WHEN label LIKE ? ESCAPE \'\\\' THEN 2 ELSE 3 END) rank,MAX(post_count) n FROM terms WHERE '+' AND '.join(where)+' GROUP BY id ORDER BY rank,n DESC,id LIMIT ? OFFSET ?'
        with closing(sqlite3.connect(self.index_path)) as c:rows=c.execute(sql,[q,q,escaped+'%']+args+[limit+1,offset]).fetchall()
        items=[]
        for id,rank,n in rows[:limit]:
            item=self.get_tag(id,locale);item['match_reason']=['canonical_exact','translation_or_verified_alias_exact','prefix','substring'][rank];items.append(item)
        return self.envelope(items,str(offset+limit) if len(rows)>limit else None,elapsed_ms=round((time.perf_counter()-started)*1000,3),measurement='measured',target_p95_ms=150)
    def resolve_terms(self,terms):
        if not self.index_path:return [{'text':t,'danbooru_status':'unavailable'} for t in terms]
        out=[]
        with closing(sqlite3.connect(self.index_path)) as c:
            for text in terms:
                # Exact canonical or verified display expression; never fuzzy replace.
                r=c.execute('SELECT id FROM terms WHERE canonical=? ORDER BY kind LIMIT 1',(text,)).fetchone()
                if not r:r=c.execute('SELECT id FROM terms WHERE label=? AND kind IN (1,2) LIMIT 1',(text,)).fetchone()
                if not r and '_' not in text and '(' not in text:r=c.execute('SELECT id FROM terms WHERE canonical=? AND category NOT IN (\'character\',\'copyright\') LIMIT 1',(text.replace(' ','_'),)).fetchone()
                out.append({'text':text,**(self.get_tag(r[0]) if r else {'danbooru_status':'not_found'})})
        return out
    def copyrights(self,id):
        if not self.has('character_copyright_links','character_tag_id','copyright_tag_id'):return []
        with closing(self.connect()) as c:rows=c.execute('SELECT * FROM character_copyright_links WHERE character_tag_id=?',(id,)).fetchall()
        return [{**dict(r),'tag':self.get_tag(r['copyright_tag_id'])} for r in rows]
    def search_characters(self,q='',copyright=None,limit=20,**kwargs):
        result=self.search_tags(q,category='character',limit=100)
        for x in result['items']:x['copyrights']=self.copyrights(x['tag_id'])
        if copyright:
            result['items']=[x for x in result['items'] if any(copyright.lower() in json.dumps(y,ensure_ascii=False).lower() for y in x['copyrights'])]
            # A work-only query should find connected character names too.
            if not q and not result['items'] and self.has('character_copyright_links','character_tag_id','copyright_tag_id'):
                works=self.search_tags(copyright,category='copyright',limit=100)['items']
                with closing(self.connect()) as c:
                    for work in works:
                        for row in c.execute('SELECT character_tag_id FROM character_copyright_links WHERE copyright_tag_id=? LIMIT ?',(work['tag_id'],limit)):
                            item=self.get_tag(row[0]);item and result['items'].append({**item,'copyrights':self.copyrights(row[0]),'match_reason':'copyright'})
        result['items']=result['items'][:limit];return result
    def get_character_related_tags(self,ids,category='general',score_min=0.05,score_max=None,limit=30):
        result={str(x):[] for x in ids}
        if not self.has('character_related_tags','character_tag_id','related_tag_id','score') or not ids:return result
        # Window function limits each character inside SQL before Python materialization.
        where=['r.character_tag_id IN ('+','.join('?' for _ in ids)+')','r.score>=?'];args=list(ids)+[score_min]
        if score_max is not None:where.append('r.score<=?');args.append(score_max)
        if category and self.has('tags','category_name'):where.append('t.category_name=?');args.append(category)
        with closing(self.connect()) as c:
            rows=c.execute('SELECT * FROM (SELECT r.*,row_number() OVER(PARTITION BY character_tag_id ORDER BY score DESC) rn FROM character_related_tags r JOIN tags t ON t.id=r.related_tag_id WHERE '+' AND '.join(where)+') WHERE rn<=?',args+[max(1,min(limit,100))]).fetchall()
        for row in rows:
            item=self.get_tag(row['related_tag_id'])
            if item:result[str(row['character_tag_id'])].append({**item,'score':row['score'],'score_label':'연관 점수(원본 DB)','field':'unclassified'})
        return result
    def get_taxonomy_nodes(self,parent_id=None,limit=100):
        if not self.has('taxonomy_nodes','id','node_key','title'):return self.envelope()
        with closing(self.connect()) as c:
            if parent_id is not None and self.has('taxonomy_edges','parent_node_id','child_node_id'):
                rows=c.execute('SELECT DISTINCT n.*,e.parent_node_id FROM taxonomy_nodes n JOIN taxonomy_edges e ON e.child_node_id=n.id WHERE e.parent_node_id=? AND n.id!=? LIMIT ?',(parent_id,parent_id,limit)).fetchall()
            else:rows=c.execute('SELECT * FROM taxonomy_nodes LIMIT ?',(limit,)).fetchall()
        return self.envelope([{**dict(r),'derived':False,'tree_kind':'manual_group' if r['node_key'].startswith('manual_group') else 'taxonomy'} for r in rows])
