import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.domain.models import GenerationInput,PromptIR,Project
from backend.app.services.guidebook import guidebook
for name,model in [('input',GenerationInput),('prompt-ir',PromptIR),('project',Project)]:
    (ROOT/'schemas'/f'{name}.schema.json').write_text(json.dumps(model.model_json_schema(),indent=2,ensure_ascii=False)+'\n')
(ROOT/'docs/nai-guidebook.md').write_text(guidebook())
print('Exported 3 JSON Schemas and guidebook.')
