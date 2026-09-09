from collections import Counter
from .config import rules
from ..domain.models import GROUPS

def term_text(t):
    text=t.text.strip()
    return text if t.weight==1 else f'{t.weight:g}::{text}::'
def join_terms(terms):return ', '.join(dict.fromkeys(term_text(t) for t in terms if t.text.strip()))
def placement(c,profile):
    if c.position is None:return {'character_id':c.id,'label':c.label,'adapter':profile['position_adapter'],'instruction':'위치 미지정','position':None}
    x,y=c.position.x,c.position.y
    if profile['position_adapter']=='grid5':
        col,row=round(x*4)+1,round(y*4)+1;instruction=f'5×5 격자: {col}열 {row}행'
    else:instruction=f'V5 위치 UI에서 수동 배치: 가로 {x:.0%}, 세로 {y:.0%} (앱 상대 좌표)'
    return {'character_id':c.id,'label':c.label,'adapter':profile['position_adapter'],'instruction':instruction,'position':{'x':x,'y':y}}
def render(ir,inp,rulebook=None,prompt_texts=None):
    ir=ir.model_copy(deep=True);prompt_texts=prompt_texts or {}
    for ci,c in enumerate(ir.characters):
        for group,ts in {**c.groups,'undesired':c.undesired}.items():
            for ti,t in enumerate(ts):
                if t.kind=='tag':t.text=prompt_texts.get(f'characters.{ci}.{group}.{ti}',t.text)
    for ti,t in enumerate(ir.shared_terms):
        if t.kind=='tag':t.text=prompt_texts.get(f'shared_terms.{ti}',t.text)
    profile=(rulebook or rules())['profiles'][inp.nai_profile_id];relmap={r.id:r for r in inp.relations};relation_tags={c.id:[] for c in inp.characters};clauses={c.id:[] for c in inp.characters}
    for r in ir.relations:
        spec=relmap.get(r.id) or r
        participants=spec.participant_ids
        if not participants:continue
        if r.action_tag:
            if spec.direction=='directed' and spec.actor_id in relation_tags:
                relation_tags[spec.actor_id].append('source#'+r.action_tag)
                for id in spec.target_ids:
                    if id in relation_tags:relation_tags[id].append('target#'+r.action_tag)
            elif spec.direction=='mutual':
                for id in participants:
                    if id in relation_tags:relation_tags[id].append('mutual#'+r.action_tag)
        for clause in r.character_clauses:
            if clause.character_id in clauses and clause.text_en:clauses[clause.character_id].append(clause.text_en)
    cards=[];inputs={c.id:c for c in inp.characters}
    for c in ir.characters:
        spec=inputs[c.id];allterms=[t for g in GROUPS for t in c.groups[g]]
        tag_terms=[t for t in allterms if t.kind!='natural_language'];natural_terms=[term_text(t) for t in allterms if t.kind=='natural_language']
        chunks=([spec.nai_subject] if spec.nai_subject else [])+[term_text(t) for t in tag_terms]+relation_tags[c.id]
        prompt=', '.join(dict.fromkeys(x for x in chunks if x))
        prose=list(dict.fromkeys(x.strip() for x in natural_terms+clauses[c.id] if x.strip()))
        if prose:prompt=prompt.rstrip('. ')+('. ' if prompt else '')+' '.join(prose)
        cards.append({'id':c.id,'label':spec.label,'prompt':prompt,'uc':join_terms(c.undesired),'terms':[t.model_dump() for t in allterms],'notes_ko':c.notes_ko})
    counts=Counter(c.nai_subject for c in inp.characters if c.nai_subject)
    count_tags=[f'{n}{s}{"s" if n>1 else ""}' for s,n in counts.items()]
    shared=', '.join(count_tags+([join_terms(ir.shared_terms)] if ir.shared_terms else []))
    return {'characters':cards,'shared_fragment':shared if inp.controls.output_scope!='characters_only' else None,'count_status':'complete' if all(c.nai_subject for c in inp.characters) else 'partial','placement':[placement(c,profile) for c in inp.characters],'scope_notice':'인원수는 NAI의 공통 프롬프트에서 별도로 입력하세요.' if inp.controls.output_scope=='characters_only' else None}
