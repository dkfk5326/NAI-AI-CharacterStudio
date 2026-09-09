import re
from .config import rules
from ..domain.models import GROUPS
class ContractError(ValueError):pass
def validate_input(inp,rulebook=None):
    profiles=(rulebook or rules())['profiles']
    if inp.nai_profile_id not in profiles:raise ContractError('알 수 없는 NAI 프로필입니다.')
    if len(inp.characters)>profiles[inp.nai_profile_id]['max_characters']:raise ContractError('대상 NAI 모델의 캐릭터 한도를 초과했습니다.')
    ids=[c.id for c in inp.characters]
    if len(ids)!=len(set(ids)):raise ContractError('캐릭터 ID가 중복됩니다.')
    rids=[r.id for r in inp.relations]
    if len(rids)!=len(set(rids)):raise ContractError('관계 ID가 중복됩니다.')
    if set(inp.controls.editable_character_ids)-set(ids):raise ContractError('수정 대상 ID가 없습니다.')
    for r in inp.relations:
        refs=set(r.participant_ids+r.target_ids+([r.actor_id] if r.actor_id else []))
        if refs-set(ids):raise ContractError('삭제되었거나 없는 인물의 관계입니다.')
        if len(set(r.participant_ids))!=len(r.participant_ids):raise ContractError('관계 참여자가 중복됩니다.')
        if r.direction=='directed' and (r.actor_id is None or not r.target_ids or r.actor_id in r.target_ids):raise ContractError('주체와 서로 다른 대상이 필요합니다.')
        if not set(r.target_ids+([r.actor_id] if r.actor_id else [])).issubset(r.participant_ids):raise ContractError('관계 주체/대상이 참여자에 없습니다.')
    if inp.previous_ir and set(c.id for c in inp.previous_ir.characters)!=set(ids):raise ContractError('이전 결과와 현재 카드가 다릅니다. 전체 생성을 실행하세요.')
def validate_ir(ir,inp,refs=None,rulebook=None,syntax_enabled=True):
    validate_input(inp,rulebook);errors=[];refs=refs or {};ids=[c.id for c in inp.characters]
    if [c.id for c in ir.characters]!=ids:errors.append('캐릭터 ID·순서·인원이 입력과 다릅니다.')
    ri={r.id:r for r in inp.relations};seen_rel=set()
    for r in ir.relations:
        if r.id in seen_rel:errors.append('관계 ID가 중복됩니다.')
        seen_rel.add(r.id)
    missing=set(ri)-seen_rel
    if missing:errors.append('입력한 관계가 결과에서 누락되었습니다.')
    inferred=[r for r in ir.relations if r.id not in ri]
    for r in inferred:
        if not r.id.startswith('auto_'):errors.append('추론 관계 ID는 auto_ 접두사를 사용해야 합니다.')
        participants=list(dict.fromkeys(r.participant_ids))
        if len(participants)<2 or set(participants)-set(ids):errors.append('추론 관계의 참여 인물이 잘못되었습니다.')
        if len(participants)!=len(r.participant_ids):errors.append('추론 관계 참여자가 중복됩니다.')
        if r.direction=='directed' and (r.actor_id is None or not r.target_ids or r.actor_id in r.target_ids):errors.append('추론 관계에는 서로 다른 주체와 대상이 필요합니다.')
        if not set(r.target_ids+([r.actor_id] if r.actor_id else [])).issubset(set(participants)):errors.append('추론 관계의 주체/대상이 참여자에 없습니다.')
    negative=(rulebook or rules())['profiles'][inp.nai_profile_id]['negative_weight']
    excluded=(rulebook or rules()).get('scope',{}).get('auto_generated_excluded_tags',[])
    def termcheck(t,cid):
        if syntax_enabled and t.origin=='model' and t.text.lower().replace('_',' ') in excluded:errors.append('출력 범위 밖의 배경·화풍·품질 태그입니다.')
        if t.tag_ref and (t.tag_ref not in refs or refs[t.tag_ref]['character_id']!=cid):errors.append('다른 인물 또는 존재하지 않는 tag_ref입니다.')
        elif t.tag_ref and t.text not in (refs[t.tag_ref]['canonical_name'],refs[t.tag_ref]['prompt_text']):errors.append('tag_ref와 반환 표현이 다릅니다.')
        if syntax_enabled and t.kind!='user_literal' and (re.search(r'\d+(?:girls?|boys?|others?)\b|(?:source|target|mutual)#|::|\(.*:\d',t.text) or any(x in t.text for x in '{}[]|')):errors.append('Term에는 인원수·가중치·관계 문법을 넣을 수 없습니다.')
        if syntax_enabled and t.weight<0 and not negative:errors.append('이 모델에서 음수 강조를 사용하지 않습니다.')
    for c in ir.characters:
        for terms in list(c.groups.values())+[c.undesired]:
            for t in terms:termcheck(t,c.id)
    for t in ir.shared_terms:termcheck(t,None)
    for r in ir.relations:
        source=ri.get(r.id)
        participants=source.participant_ids if source else r.participant_ids
        if r.action_tag and (any(x in r.action_tag for x in '#@|{}[]:') or re.search(r'\bc[_\d]',r.action_tag)):errors.append('잘못된 관계 행동 태그입니다.')
        for clause in r.character_clauses:
            if clause.character_id not in participants:errors.append('관계 문장이 참여자 밖의 인물을 참조합니다.')
            if any(re.search(r'(?<!\w)'+re.escape(cid)+r'(?!\w)',clause.text_en) for cid in ids):errors.append('관계 문장에 앱 내부 ID를 출력할 수 없습니다.')
        if r.action_tag_ref and (r.action_tag_ref not in refs or refs[r.action_tag_ref]['character_id'] not in participants):errors.append('관계 태그 참조 오류입니다.')
    return list(dict.fromkeys(errors))

def preserve_fixed(ir,inp):
    ir=ir.model_copy(deep=True);changes=[]
    old={c.id:c for c in inp.previous_ir.characters} if inp.previous_ir else {}
    byid={c.id:c for c in ir.characters}
    editable=set(inp.controls.editable_character_ids or [c.id for c in inp.characters])
    for c in inp.characters:
        if c.id not in byid:continue
        out=byid[c.id]
        for g in GROUPS:
            if c.id in old and (g in c.locked_groups or (inp.task!='generate' and (c.id not in editable or g not in inp.controls.editable_groups))):
                if out.groups[g]!=old[c.id].groups[g]:changes.append({'path':f'{c.id}.{g}','reason':'잠금/수정 범위 보존'})
                out.groups[g]=old[c.id].groups[g]
        if c.id in old and inp.task!='generate' and c.id not in editable:out.undesired=old[c.id].undesired
        for term in c.required_terms:
            if not any(t.text==term.text for ts in out.groups.values() for t in ts):
                # Required input takes effect only in an editable group; no mutation of frozen groups.
                allowed=[g for g in GROUPS if g not in c.locked_groups and (inp.task=='generate' or (c.id in editable and g in inp.controls.editable_groups))]
                if allowed:out.groups[allowed[0]].append(term);changes.append({'path':c.id,'reason':'사용자 필수 태그 복원','text':term.text})
                else:raise ContractError('필수 태그와 잠금이 충돌합니다.')
        for term in c.undesired_terms:
            if not any(t.text==term.text for t in out.undesired):out.undesired.append(term)
    if inp.previous_ir:
        oldrel={r.id:r for r in inp.previous_ir.relations}
        for idx,r in enumerate(ir.relations):
            spec=next((x for x in inp.relations if x.id==r.id),None)
            frozen=spec and (spec.locked or any('action' in c.locked_groups or (inp.task!='generate' and (c.id not in editable or 'action' not in inp.controls.editable_groups)) for c in inp.characters if c.id in spec.participant_ids))
            if frozen and r.id in oldrel and r!=oldrel[r.id]:
                ir.relations[idx]=oldrel[r.id];changes.append({'path':r.id,'reason':'영향받는 잠긴 인물의 관계 보존'})
        if inp.task!='generate':ir.shared_terms=inp.previous_ir.shared_terms
    return ir,changes
def warnings(ir):
    shared={t.text.lower().replace('_',' ') for t in ir.shared_terms};out=[]
    for c in ir.characters:
        positive={t.text.lower().replace('_',' ') for v in c.groups.values() for t in v}|shared
        for t in c.undesired:
            if t.text.lower().replace('_',' ') in positive:out.append({'character_id':c.id,'code':'literal_uc_conflict','message_ko':t.text+'가 positive와 UC에 함께 있습니다. 의미 충돌 여부를 확인하세요.'})
    return out
def manual_warnings(text,profile):
    out=[]
    if re.search(r'\([^()]+:[-\d.]+\)',text):out.append('Stable Diffusion식 가중치입니다. NAI 숫자 강조는 1.2::text:: 형식입니다.')
    if '|' in text:out.append('독립 캐릭터 칸과 | 분리 방식을 혼용하지 마세요.')
    if not profile['negative_weight'] and re.search(r'-\d+(?:\.\d+)?::',text):out.append('이 모델에서는 음수 강조를 사용하지 않습니다.')
    return out
