"""Explicit deterministic demonstration. It is not a substitute translator or model."""
import re
from ..domain.models import PromptIR,CharacterIR,RelationIR,Term,GROUPS,Unresolved
WORDS={'검은 머리':'black hair','검은 단발':'black hair, short hair','단발':'short hair','갈색 눈':'brown eyes','흰 셔츠':'white shirt','금발':'blonde hair','긴 머리':'long hair','파란 눈':'blue eyes','파란 재킷':'blue jacket','빨간 재킷':'red jacket','놀란 표정':'surprised','미소':'smile','팔을 내린 자세':'arms at sides','컵':'cup','서 있다':'standing','상대를 본다':'looking at another'}
ACTIONS={'껴안는다':'hug','껴안기':'hug','포옹':'hug','hug':'hug','손잡기':'holding hands','악수':'handshake','handshake':'handshake'}
def terms(text):
    result=[];unknown=[]
    for part in re.split(r'[,\n]',text):
        part=part.strip()
        if not part:continue
        value=WORDS.get(part,part)
        if re.search('[가-힣]',value):unknown.append(part);continue
        for x in value.split(','):result.append(Term(text=x.strip(),origin='user',kind='natural_language' if len(x.split())>6 else 'tag'))
    return result,unknown
def mock_ir(inp):
    chars=[];unresolved=[]
    if inp.request_ko:unresolved.append(Unresolved(code='mock_request',message_ko='모의 모드는 자유 상황 설명을 번역하지 않습니다. 카드의 예시 사전과 직접 영어 태그만 처리합니다.'))
    for c in inp.characters:
        groups={}
        for g in GROUPS:
            groups[g],unknown=terms(c.fields[g])
            if unknown:unresolved.append(Unresolved(code='mock_untranslated',character_ids=[c.id],message_ko='모의 사전 미지원: '+', '.join(unknown)))
        for t in c.required_terms:groups['identity'].append(t)
        chars.append(CharacterIR(id=c.id,groups=groups,undesired=c.undesired_terms))
    rels=[]
    for r in inp.relations:
        action=ACTIONS.get(r.action_ko)
        if not action or r.details_ko:unresolved.append(Unresolved(code='mock_relation',character_ids=r.participant_ids,message_ko='모의 모드는 이 관계의 상세 설명을 번역하지 않습니다.'))
        rels.append(RelationIR(id=r.id,action_tag=action,character_clauses=[]))
    return PromptIR(characters=chars,relations=rels,unresolved=unresolved)
