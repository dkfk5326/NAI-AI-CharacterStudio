"""Select bounded LLM reference sections and record the exact supplied revision."""
import json
from .config import text_file, digest

GUIDE_PATH = 'knowledge/llm-guidebook.json'

def validate_guide(doc):
    if not isinstance(doc,dict) or not isinstance(doc.get('version'),str) or not isinstance(doc.get('sections'),list):
        raise ValueError('LLM 가이드북에는 version과 sections 목록이 필요합니다.')
    seen=set()
    for section in doc['sections']:
        if not isinstance(section,dict) or not isinstance(section.get('id'),str) or section['id'] in seen:
            raise ValueError('LLM 가이드북 항목 ID는 고유한 문자열이어야 합니다.')
        seen.add(section['id'])
        for field in ('common','generation','chat','keywords','sources'):
            values=section.get(field,[])
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values):raise ValueError('LLM 가이드북 항목은 문자열 목록이어야 합니다: '+field)
        if len('\n'.join(section.get('common',[])+section.get('generation',[])+section.get('chat',[])))>3200:
            raise ValueError('가이드북의 개별 항목이 너무 깁니다.')
    if 'core' not in seen:raise ValueError('LLM 가이드북 core 항목이 필요합니다.')
    if len(doc['sections'])>50:raise ValueError('LLM 가이드북은 최대 50개 항목을 지원합니다.')
    return doc

def guide_document(repo=None):
    return validate_guide(json.loads(text_file(GUIDE_PATH,repo)))

def select_reference(query,mode='generation',repo=None,required=(),max_chars=2600):
    doc=guide_document(repo)
    lower=query.lower()
    indexed=list(enumerate(doc['sections']))
    scored=[]
    for order,section in indexed:
        score=sum(1 for word in section.get('keywords',[]) if word.lower() in lower)
        if section['id']=='core':score=10000
        elif section['id'] in required:score+=1000+100*(len(required)-list(required).index(section['id']))
        if score:scored.append((-score,order,section))
    lines=[];ids=[]
    for _,_,section in sorted(scored):
        content=section.get('common',[])+section.get(mode,[])
        block='['+section['id']+']\n'+'\n'.join('- '+v for v in content)
        if lines and len('\n\n'.join(lines+[block]))>max_chars:continue
        lines.append(block);ids.append(section['id'])
    text='\n\n'.join(lines)
    return {'text':text,'source':{'file':GUIDE_PATH,'version':doc['version'],'sha256':digest(doc),'section_ids':ids,'excerpt_sha256':digest(text)}}

def guidebook(rulebook=None,repo=None):
    # Backward-compatible export endpoint, now exporting reference data.
    return json.dumps(guide_document(repo),ensure_ascii=False,indent=2)
