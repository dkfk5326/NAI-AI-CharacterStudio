from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator

Group = Literal['identity','appearance','outfit','expression','pose','gaze','prop','action']
GROUPS = ['identity','appearance','outfit','expression','pose','gaze','prop','action']
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
class Term(Strict):
    text: str = Field(min_length=1,max_length=1000)
    weight: float = Field(default=1,ge=-10,le=10)
    origin: Literal['user','preset','reference','model'] = 'user'
    kind: Literal['tag','natural_language','user_literal'] = 'tag'
    tag_ref: str | None = None
class Position(Strict):
    x: float = Field(ge=0,le=1)
    y: float = Field(ge=0,le=1)
class CharacterInput(Strict):
    id: str = Field(default_factory=lambda:'c_'+uuid4().hex,min_length=1,max_length=100)
    label: str = Field(default='',max_length=200)
    identity_tag_id: int | None = None
    copyright_tag_ids: list[int] = Field(default_factory=list,max_length=30)
    nai_subject: Literal['girl','boy','other'] | None = None
    fields: dict[Group,str] = Field(default_factory=lambda:dict.fromkeys(GROUPS,''))
    locked_groups: list[Group] = Field(default_factory=list)
    required_terms: list[Term] = Field(default_factory=list,max_length=100)
    undesired_terms: list[Term] = Field(default_factory=list,max_length=100)
    position: Position | None = None
    @field_validator('fields')
    @classmethod
    def fields_size(cls,v):
        if any(len(x)>4000 for x in v.values()): raise ValueError('카드 필드가 너무 깁니다.')
        return {**dict.fromkeys(GROUPS,''),**v}
class RelationInput(Strict):
    id: str = Field(default_factory=lambda:'r_'+uuid4().hex,max_length=100)
    participant_ids: list[str] = Field(min_length=2,max_length=22)
    actor_id: str | None = None
    target_ids: list[str] = Field(default_factory=list,max_length=21)
    direction: Literal['directed','mutual','group'] = 'directed'
    action_ko: str = Field(default='',max_length=500)
    details_ko: str = Field(default='',max_length=2000)
    locked: bool = False
class Controls(Strict):
    format: Literal['tags','hybrid'] = 'hybrid'
    detail: Literal['short','standard','detailed'] = 'standard'
    expansion: Literal['none','minimal','creative'] = 'minimal'
    output_scope: Literal['characters_only','characters_with_shared_fragment'] = 'characters_with_shared_fragment'
    variant_count: int = Field(default=1,ge=1,le=3)
    editable_character_ids: list[str] = Field(default_factory=list,max_length=22)
    editable_groups: list[Group] = Field(default_factory=lambda:list(GROUPS))
    external_base_reserved_tokens: int | None = Field(default=128,ge=0,le=10000)
class CharacterIR(Strict):
    id: str = Field(max_length=100)
    groups: dict[Group,list[Term]]
    undesired: list[Term] = Field(default_factory=list,max_length=100)
    notes_ko: list[str] = Field(default_factory=list,max_length=20)
    @field_validator('groups')
    @classmethod
    def all_groups(cls,v):
        if set(v)!=set(GROUPS) or any(len(x)>100 for x in v.values()): raise ValueError('8개 그룹이 필요합니다. 그룹당 최대 100개입니다.')
        return v
class Clause(Strict):
    character_id: str = Field(max_length=100)
    text_en: str = Field(max_length=1200)
class RelationIR(Strict):
    id: str = Field(max_length=100)
    participant_ids: list[str] = Field(default_factory=list,max_length=22)
    actor_id: str | None = Field(default=None,max_length=100)
    target_ids: list[str] = Field(default_factory=list,max_length=21)
    direction: Literal['directed','mutual','group'] = 'directed'
    action_tag: str | None = Field(default=None,max_length=300)
    action_tag_ref: str | None = None
    character_clauses: list[Clause] = Field(default_factory=list,max_length=22)
class Unresolved(Strict):
    code: str = Field(max_length=100)
    character_ids: list[str] = Field(default_factory=list,max_length=22)
    message_ko: str = Field(max_length=2000)
class PromptIR(Strict):
    schema_version: Literal['1.1'] = '1.1'
    characters: list[CharacterIR] = Field(min_length=1,max_length=22)
    relations: list[RelationIR] = Field(default_factory=list,max_length=100)
    shared_terms: list[Term] = Field(default_factory=list,max_length=100)
    unresolved: list[Unresolved] = Field(default_factory=list,max_length=100)
class GenerationInput(Strict):
    project_revision: int = Field(default=0,ge=0)
    task: Literal['generate','rewrite','shorten','vary'] = 'generate'
    request_ko: str = Field(default='',max_length=20000)
    rating: Literal['SFW','NSFW'] = 'NSFW'
    nai_profile_id: str = 'nai-v5-full'
    characters: list[CharacterInput] = Field(min_length=1,max_length=22)
    relations: list[RelationInput] = Field(default_factory=list,max_length=100)
    controls: Controls = Field(default_factory=Controls)
    previous_ir: PromptIR | None = None
class Project(Strict):
    schema_version: Literal['1.1'] = '1.1'
    id: str = Field(default_factory=lambda:uuid4().hex,max_length=100)
    name: str = Field(default='새 프로젝트',min_length=1,max_length=200)
    revision: int = Field(default=0,ge=0)
    input: GenerationInput
    candidates: list[dict] = Field(default_factory=list,max_length=100)
    manual_overrides: dict[str,str] = Field(default_factory=dict)
    settings: dict = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list,max_length=200)
    tag_db_snapshot: dict | None = None
    legacy: dict = Field(default_factory=dict)
