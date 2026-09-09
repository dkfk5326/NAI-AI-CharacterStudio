import asyncio,json,urllib.request,urllib.error,socket
from urllib.parse import urlparse
class ProviderError(RuntimeError):
    def __init__(self,code,message,raw=None):self.code=code;self.raw=raw;super().__init__(message)
class BaseProvider:
    def __init__(self,settings):
        self.settings=settings;self.config=settings['llm'];self.base=self.config['base_url'].rstrip('/');self.root=self.base.removesuffix('/v1');self.caps={}
        u=urlparse(self.base)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1'):raise ProviderError('invalid_endpoint','로컬 HTTP 추론 서버 주소를 사용하세요.')
    async def http(self,url,body=None,timeout=None):
        # HTTP in a worker thread. Await the actual task on cancel: never start a second GPU call while it still runs.
        def request():
            headers={'Content-Type':'application/json'}
            if self.config.get('api_key'):headers['Authorization']='Bearer '+self.config['api_key']
            req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with urllib.request.urlopen(req,timeout=timeout or self.config['timeout_seconds']) as response:return json.load(response)
            except urllib.error.HTTPError as e:
                raw=e.read().decode(errors='replace');low=raw.lower();code='oom' if 'out of memory' in low or 'cuda out' in low else 'loading' if e.code==503 else 'server_error'
                raise ProviderError(code,f'추론 서버 오류 ({e.code})',raw)
            except (TimeoutError,socket.timeout):raise ProviderError('timeout','추론 서버 응답 시간이 초과되었습니다.')
            except urllib.error.URLError as e:raise ProviderError('unreachable','추론 서버에 연결할 수 없습니다.',str(e.reason))
            except json.JSONDecodeError as e:raise ProviderError('invalid_json','서버 응답이 JSON이 아닙니다.',str(e))
        return await asyncio.to_thread(request)
    async def inspect(self):
        result=await self.http(self.base+'/models',timeout=5)
        self.caps={'connected':True,'models':result.get('data',[]),'structured_output':'unknown','thinking_control':'unknown','tokenize':False,'samplers':{x:'unknown' for x in ['temperature','top_p','top_k','min_p','repeat_penalty','frequency_penalty','presence_penalty','seed','stop']},'template':None,'model_hash':None,'runtime_version':None}
        return self.caps
    async def input_tokens(self,messages):return None
    def payload(self,messages,schema,max_tokens,temperature=None):
        c=self.config;p={'model':c.get('model_id') or (self.caps.get('models') or [{}])[0].get('id',''),'messages':messages,'max_tokens':max_tokens,'stream':False}
        for key in ['temperature','top_p','top_k','min_p','repeat_penalty','frequency_penalty','presence_penalty','seed','stop']:
            if self.caps.get('samplers',{}).get(key)=='supported' and c.get(key) is not None:p[key]=c[key]
        if temperature is not None and 'temperature' in p:p['temperature']=temperature
        if self.caps.get('structured_output')=='supported' and c.get('structured_output')!='off':p['response_format']={'type':'json_schema','json_schema':{'name':'PromptIR','strict':True,'schema':schema}}
        if self.caps.get('thinking_control')=='supported':p['chat_template_kwargs']={'enable_thinking':bool(c['thinking'])}
        return p
    async def complete(self,payload):
        response=await self.http(self.base+'/chat/completions',payload)
        try:content=response['choices'][0]['message']['content']
        except (KeyError,IndexError,TypeError):raise ProviderError('invalid_response','최종 메시지를 찾을 수 없습니다.',response)
        if not content:raise ProviderError('empty_response','모델이 최종 결과를 반환하지 않았습니다.',response)
        return content,response
