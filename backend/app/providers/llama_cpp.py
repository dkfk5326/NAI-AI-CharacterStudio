from .base import BaseProvider,ProviderError
class LlamaCppProvider(BaseProvider):
    async def inspect(self):
        await super().inspect()
        try:
            props=await self.http(self.root+'/props',timeout=5);template=props.get('chat_template','');defaults=props.get('default_generation_settings',{});params=defaults.get('params',defaults)
            self.caps['template']=template;self.caps['runtime_version']=props.get('build_info');self.caps['context_size']=params.get('n_ctx')
            for k in self.caps['samplers']:
                if k in params:self.caps['samplers'][k]='supported'
            if 'enable_thinking' in template:
                probe_messages=[{'role':'user','content':'Return a JSON object.'}]
                on=await self.http(self.root+'/apply-template',{'messages':probe_messages,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':True}},timeout=5)
                off=await self.http(self.root+'/apply-template',{'messages':probe_messages,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}},timeout=5)
                self.caps['thinking_control']='supported' if on.get('prompt') and on.get('prompt')!=off.get('prompt') else 'unverified'
                self.caps['thinking_template_probe']={'changes_generation_prompt':on.get('prompt')!=off.get('prompt')}
            # Merely accepting a property is not evidence that structured generation honors it.
            self.caps['structured_output']='unverified'
            check=await self.http(self.root+'/tokenize',{'content':'test','add_special':False},timeout=5)
            self.caps['tokenize']=isinstance(check.get('tokens'),list)
        except ProviderError as e:self.caps['inspection_note']=str(e)
        return self.caps
    async def input_tokens(self,messages):
        if not self.caps.get('tokenize'):return None
        try:
            formatted=await self.http(self.root+'/apply-template',{'messages':messages,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':bool(self.config['thinking'])}},timeout=5)
            if not isinstance(formatted.get('prompt'),str):return None
            result=await self.http(self.root+'/tokenize',{'content':formatted['prompt'],'add_special':True},timeout=5)
            return len(result['tokens'])
        except (ProviderError,KeyError):return None
    async def probe_schema(self):
        # Explicit connection-check action, not an automatic extra inference per generation.
        p={'model':self.config.get('model_id') or self.caps['models'][0]['id'],'messages':[{'role':'user','content':'Return exactly {"ok":true}.'}],'max_tokens':32,'response_format':{'type':'json_schema','schema':{'type':'object','properties':{'ok':{'type':'boolean','const':True}},'required':['ok'],'additionalProperties':False}},'temperature':0}
        import json
        try:
            content,_=await self.complete(p)
            self.caps['structured_output']='supported' if json.loads(content)=={'ok':True} else 'unsupported'
        except (ProviderError,ValueError):self.caps['structured_output']='unsupported'
        return self.caps
    def payload(self,*args,**kwargs):
        p=super().payload(*args,**kwargs)
        if 'response_format' in p:p['response_format']={'type':'json_schema','schema':p['response_format']['json_schema']['schema']}
        return p
