import json,re
from .config import text_file,digest
from .guidebook import select_reference
from ..domain.models import PromptIR

def substitute(template,values):
    return re.sub(r'{{\s*(\w+)\s*}}',lambda m:values.get(m[1],m[0]),template)
def build(inp,settings,rulebook,bundles,repo=None,repair=None):
    schema=PromptIR.model_json_schema();profile=rulebook['profiles'][inp.nai_profile_id]
    values={'nai_rules_excerpt':json.dumps({'version':rulebook['version'],'syntax':rulebook['syntax'],'profile':profile,'scope':rulebook.get('scope',{})},ensure_ascii=False),'prompt_ir_schema':json.dumps(schema,ensure_ascii=False),'retrieved_knowledge':json.dumps({'tag_candidates':bundles,'aliases':json.loads(text_file('knowledge/tag-aliases.json',repo)),'examples':[json.loads(x) for x in text_file('knowledge/examples.jsonl',repo).splitlines() if x.strip()][:2]},ensure_ascii=False),'content_profile':json.dumps(settings['content_profile'],ensure_ascii=False),'generation_input_json':inp.model_dump_json()}
    template='repair' if repair else 'user-request' if inp.task=='generate' else 'rewrite'
    if repair:values.update(previous_output=repair['raw'],validation_errors_json=json.dumps(repair['errors'],ensure_ascii=False))
    files=['prompts/main-system.md','prompts/'+template+'.md'];texts=[text_file(f,repo) for f in files]
    messages=[{'role':role,'content':substitute(t,values)} for role,t in zip(['system','user'],texts)]
    required=['interactions'] if inp.relations or len(inp.characters)>1 else ['characters']
    if inp.task!='generate':required.insert(0,'editing')
    reference=select_reference(inp.request_ko,repo=repo,required=required)
    messages[0]['content']+='\n\n[NAI LLM reference]\n'+reference['text']
    return {'messages':messages,'schema':schema,'sources':[reference['source']]+[{'file':f,'sha256':digest(t)} for f,t in zip(files,texts)]+[{'file':'knowledge/nai-rules.yaml','version':rulebook['version'],'sha256':digest(rulebook)},{'file':'config/content-profile.yaml','sha256':digest(settings['content_profile'])}],'settings_hash':digest(settings),'retrieved_knowledge':bundles,'prompt_version':digest([*texts,reference['source']])[:12]}
