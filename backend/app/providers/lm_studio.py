from .base import BaseProvider,ProviderError
class LMStudioProvider(BaseProvider):
    async def inspect(self):
        await super().inspect()
        try:self.caps['native_metadata']=await self.http(self.root+'/api/v0/models',timeout=5)
        except ProviderError:pass
        # OpenAI-compatible standard parameters only; no unverified top_k/min_p pretending.
        for k in ['temperature','top_p','frequency_penalty','presence_penalty','seed','stop']:self.caps['samplers'][k]='supported'
        return self.caps
