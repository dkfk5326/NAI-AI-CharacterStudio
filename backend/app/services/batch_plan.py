"""Explicit component batches: a relation is never split between LLM calls."""
from .prompt_builder import build
from .token_budget import budget,BudgetError
from .validator import ContractError

def subset(inp,ids):
    part=inp.model_copy(deep=True);chosen=set(ids);part.characters=[c for c in part.characters if c.id in chosen];part.relations=[r for r in part.relations if set(r.participant_ids).issubset(chosen)];part.controls.variant_count=1;part.controls.editable_character_ids=[x for x in part.controls.editable_character_ids if x in chosen]
    if part.previous_ir:
        part.previous_ir.characters=[c for c in part.previous_ir.characters if c.id in chosen];part.previous_ir.relations=[r for r in part.previous_ir.relations if r.id in {x.id for x in part.relations}]
    return part

def plan(inp,settings,rulebook,files):
    ids=[c.id for c in inp.characters];neighbors={id:set() for id in ids}
    for relation in inp.relations:
        for a in relation.participant_ids:neighbors[a].update(relation.participant_ids)
    components=[];visited=set()
    for id in ids:
        if id in visited:continue
        todo=[id];component=set()
        while todo:
            node=todo.pop()
            if node in component:continue
            component.add(node);visited.add(node);todo.extend(neighbors[node]-component)
        components.append([x for x in ids if x in component])
    batches=[];current=[]
    def fits(group):
        try:budget(build(subset(inp,group),settings,rulebook,[],files)['messages'],settings,large=len(group)>5);return True
        except BudgetError:return False
    for component in components:
        if not fits(component):raise ContractError('관계로 연결된 '+str(len(component))+'명의 고정 정보가 한 요청의 예산을 초과합니다. 관계를 분리하지 않았습니다. 컨텍스트를 늘리거나 입력을 직접 줄이세요.')
        if current and not fits(current+component):batches.append(current);current=[]
        current+=component
    if current:batches.append(current)
    return batches
