from pathlib import Path
import yaml,hashlib,json,os,re
ROOT=Path(__file__).resolve().parents[3]
def read_yaml(path):return yaml.safe_load((ROOT/path).read_text(encoding='utf-8'))
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def defaults():
    c=read_yaml('config/app.yaml');c['llm']['mode']=os.environ.get('NAI_MODE','mock')
    c['llm']['model_id']='';c['llm']['api_key']='';c['llm']['model_path']=None
    c['validation']={'enabled':True};c['content_profile']=read_yaml('config/content-profile.yaml')['content_profile'];c['tag_config']=read_yaml('config/tag-provider.yaml');return c
def rules(repo=None):return repo.get('file:knowledge/nai-rules.yaml') and yaml.safe_load(repo.get('file:knowledge/nai-rules.yaml')) if repo and repo.get('file:knowledge/nai-rules.yaml') else read_yaml('knowledge/nai-rules.yaml')
def text_file(path,repo=None):
    # Project/config text files are UTF-8 regardless of the Windows ANSI code page.
    disk_text=(ROOT/path).read_text(encoding='utf-8')
    return repo.get('file:'+path,disk_text) if repo else disk_text
def public_settings(s):
    import copy
    c=copy.deepcopy(s);c['llm']['api_key']='';return c
def file_catalog():return ['prompts/'+x for x in ['main-system.md','chat-system.md','user-request.md','rewrite.md','repair.md','reference-extract.md']]+['knowledge/nai-rules.yaml','knowledge/llm-guidebook.json','knowledge/tag-aliases.json','knowledge/examples.jsonl','knowledge/field-taxonomy-map.yaml','config/content-profile.yaml']
def validate_file(path,text):
    if path not in file_catalog():raise ValueError('편집할 수 없는 파일입니다.')
    if len(text)>200000:raise ValueError('파일이 너무 큽니다.')
    if path=='prompts/chat-system.md':
        if not text.strip():raise ValueError('대화 프롬프트를 입력해 주세요.')
        if len(text)>16000:raise ValueError('대화 프롬프트는 16,000자 이내로 입력해 주세요.')
        return True  # Literal text, not a generation template. NAI braces are allowed.
    if path.endswith('.yaml'):
        v=yaml.safe_load(text)
        if not isinstance(v,dict):raise ValueError('YAML 객체가 필요합니다.')
        if path.endswith('nai-rules.yaml'):
            for p in v['profiles'].values():
                if not 1<=p['max_characters']<=22:raise ValueError('슬롯 범위가 잘못되었습니다.')
        if path.endswith('content-profile.yaml') and 'content_profile' not in v:raise ValueError('content_profile이 필요합니다.')
    elif path.endswith('.json'):
        value=json.loads(text)
        if path=='knowledge/llm-guidebook.json':
            from .guidebook import validate_guide
            validate_guide(value)
    elif path.endswith('.jsonl'):
        for line in text.splitlines():
            if line.strip():json.loads(line)
    else:
        known={'nai_rules_excerpt','prompt_ir_schema','retrieved_knowledge','content_profile','generation_input_json','previous_output','validation_errors_json','reference_extraction_schema','reference_request_json'}
        if set(re.findall(r'{{\s*(\w+)\s*}}',text))-known:raise ValueError('알 수 없는 템플릿 변수입니다.')
        if text.count('{{')!=text.count('}}'):raise ValueError('템플릿 괄호가 닫히지 않았습니다.')
    return True
