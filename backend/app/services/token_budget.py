import json,math
class BudgetError(ValueError):pass

def estimate_input(messages):
    # This is an LLM-only estimate, never an NAI token count.
    text=json.dumps(messages,ensure_ascii=False)
    return math.ceil(sum(1 if ord(c)>127 else 0.28 for c in text))+16*len(messages)
def budget(messages,settings,exact=None,large=False):
    llm=settings['llm'];n=exact if exact is not None else estimate_input(messages);limit=llm['max_output_tokens_large_scene'] if large else llm['max_output_tokens'];remaining=llm['context_size']-n-llm['context_margin_tokens']
    if remaining<min(limit,512):raise BudgetError('필수 입력과 출력 여유가 컨텍스트를 초과합니다. 인물을 누락시키지 않았습니다. 요청을 명시적으로 나누거나 컨텍스트 설정을 확인하세요.')
    return {'llm_input_tokens':n,'llm_input_measurement':'measured' if exact is not None else 'estimate','llm_output_limit':min(limit,remaining),'context_size':llm['context_size'],'margin':llm['context_margin_tokens'],'nai_prompt_tokens':None,'nai_measurement':'unavailable','nai_note':'NAI 토크나이저와 외부 베이스를 읽지 않아 전체 길이를 계산할 수 없습니다.'}
