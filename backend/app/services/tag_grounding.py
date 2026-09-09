import re

_SPLIT=re.compile(r'[,;\n.!?]+')
_WORD=re.compile(r"[A-Za-z0-9_()'-]{3,}|[가-힣]{2,}")

def _queries(text,limit=16):
    """Small lexical probes for the local tag dictionary; never a prompt parser."""
    if not text:return []
    out=[]
    def add(v):
        v=' '.join(v.strip().split())[:120]
        if v and v not in out:out.append(v)
    for chunk in _SPLIT.split(text):
        add(chunk)
        words=_WORD.findall(chunk)
        for w in words:add(w)
        for i in range(len(words)-1):add(words[i]+' '+words[i+1])
        if len(out)>=limit:break
    return out[:limit]

def _items(adapter,query,limit=2,exact_only=False):
    result=adapter.search_tags(query,limit=limit,exclude_deprecated=True)
    items=[]
    for item in result.get('items',[]):
        if exact_only and item.get('match_reason') not in ('canonical_exact','translation_or_verified_alias_exact'):continue
        items.append(item)
    return items

def before(inp,adapter):
    """Retrieve optional dictionary clues. Card fields are consistency hints, not a fill-every-field contract."""
    bundles=[];refs={};extra_total=0

    # Character-scoped hints may carry refs because a returned term can safely point back to that character.
    for c in inp.characters:
        character_total=0
        for field,text in c.fields.items():
            if not text:continue
            candidates=[];seen=set()
            for query in _queries(text,10):
                for item in _items(adapter,query,limit=2):
                    key=item.get('tag_id') or item.get('canonical_name')
                    if key in seen:continue
                    if character_total>=10 or extra_total>=44:break
                    seen.add(key);ref=f'{c.id}-{field}-{len(candidates)+1}'
                    item={**item,'ref':ref,'character_id':c.id,'field':field,'snapshot_id':adapter.snapshot,'db_match_reason':item.get('match_reason'),'match_reason':'consistency_hint','source':'danbooru_sqlite'}
                    refs[ref]=item;candidates.append(item);extra_total+=1;character_total+=1
                if character_total>=10 or extra_total>=44:break
            if candidates:bundles.append({'scope':'character_hint','app_character_id':c.id,'field':field,'candidates':candidates})

    # The main scene is primary input. These are unscoped lookup clues only and deliberately have no tag_ref.
    scene=[];seen=set()
    for query in _queries(inp.request_ko,20):
        for item in _items(adapter,query,limit=2):
            key=item.get('tag_id') or item.get('canonical_name')
            if key in seen:continue
            seen.add(key);scene.append({**item,'query':query,'source':'scene_lookup','ref':None})
            if len(scene)>=16:break
        if len(scene)>=16:break
    if scene:bundles.append({'scope':'scene_lookup','candidates':scene})

    # Explicit relation cards are optional guardrails, but their DB hits can safely ground action_tag_ref.
    for relation in inp.relations:
        candidates=[];seen=set();owner=relation.actor_id or (relation.participant_ids[0] if relation.participant_ids else None)
        for query in _queries('\n'.join(x for x in [relation.action_ko,relation.details_ko] if x),12):
            for item in _items(adapter,query,limit=2):
                key=item.get('tag_id') or item.get('canonical_name')
                if key in seen or owner is None:continue
                seen.add(key);ref=f'{relation.id}-action-{len(candidates)+1}'
                item={**item,'ref':ref,'character_id':owner,'relation_id':relation.id,'query':query,'snapshot_id':adapter.snapshot,'source':'relation_lookup'}
                refs[ref]=item;candidates.append(item)
                if len(candidates)>=8:break
            if len(candidates)>=8:break
        if candidates:bundles.append({'scope':'relation_hint','relation_id':relation.id,'participant_ids':relation.participant_ids,'candidates':candidates})
    return bundles,refs

def after(ir,adapter,refs):
    paths=[];terms=[]
    for ci,c in enumerate(ir.characters):
        for g,ts in {**c.groups,'undesired':c.undesired}.items():
            for i,t in enumerate(ts):paths.append(f'characters.{ci}.{g}.{i}');terms.append(t)
    for i,t in enumerate(ir.shared_terms):paths.append(f'shared_terms.{i}');terms.append(t)
    lookups=[t.text for t in terms if t.kind=='tag'];resolved=iter(adapter.resolve_terms(lookups));evidence=[]
    for path,t in zip(paths,terms):
        item=next(resolved) if t.kind=='tag' else {'danbooru_status':'not_applicable'}
        evidence.append({'term_path':path,'source_id':'danbooru_sqlite' if adapter.snapshot else None,'snapshot_sha256':adapter.snapshot,'tag_id':item.get('tag_id'),'canonical_name':item.get('canonical_name'),'label_ko':item.get('label_ko'),'category_name':item.get('category_name'),'post_count':item.get('post_count'),'danbooru_status':item['danbooru_status'],'nai_evidence':'unknown','nai_profile_id':None,'observation_id':None})
    return evidence
