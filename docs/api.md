# 앱 API 계약

기본 주소는 `http://127.0.0.1:8000`입니다. 모든 JSON 응답에는 요청 ID·프로젝트 리비전·프롬프트 버전 봉투를 사용합니다. 입력·HTTP 오류도 오류 코드가 포함된 JSON 봉투로 반환하며, 파일 내보내기는 파일 본문입니다.

| 경로 | 기능 |
|---|---|
| GET /api/health | 백엔드 및 모드 상태 |
| GET /api/models/capabilities | 로컬 서버 기능 탐지 |
| GET /api/models/manifest | 선택 프로필 및 실제 로컬 GGUF 해시 |
| POST /api/models/probe | 명시적 JSON 제약 출력 시험 |
| POST /api/characters/new | 안정적인 새 카드 ID 발급 |
| POST /api/relations/new | 관계 생성과 ID 발급 |
| POST /api/generate | GenerationInput을 받아 202+작업 ID 반환 |
| POST /api/rewrite | 이전 IR과 수정 범위로 생성 |
| POST /api/batch-plan | 관계를 보존하는 명시적 묶음 계획 |
| POST /api/generate-batches | 확인한 입력을 묶음별로 순차 생성 후 병합 |
| GET /api/requests/{request_id} | 진행 상태·완료 후보·원본 요청/응답 |
| POST /api/cancel/{request_id} | 중단 요청 |
| POST /api/prompt-preview | 실제 요청 조립 미리보기 |
| POST /api/validate | `{input, ir?, manual_text?, refs?}` 검증 |
| POST /api/render | `{input, ir}`을 개별 복사 문자열로 렌더링 |
| GET/PUT /api/settings | 초기값·현재값·공개 설정 |
| GET /api/projects | 저장 프로젝트 목록 |
| GET/PUT /api/projects/{id} | 프로젝트 읽기/저장, revision 충돌 검출 |
| GET /api/projects/{id}/export?format=json\|text | 전체 프로젝트 내보내기 |
| GET /api/projects/{id}/history | 저장본 변경 이력 |
| POST /api/projects/import | JSON 가져오기, 새 프로젝트 ID 발급 |
| GET/PUT /api/files | 허용된 프롬프트·규칙 원문 편집 |
| GET /api/guide | 규칙 원본에서 생성한 가이드 |
| GET /api/tag-db/status | 해시·스키마·기능·인덱스 상태 |
| PUT /api/tag-db/config | `{db_path, expected_sha256?, verify_release_hash?}` 연결 |
| GET /api/tags/search | q·locale·category·taxonomy_node_id·limit·cursor |
| POST /api/tags/resolve | `{terms:[...]}` 일괄 exact 대조 |
| GET /api/tags/{tag_id} | 개별 태그와 번역 |
| GET /api/characters/search | q·copyright·limit |
| GET /api/characters/{tag_id}/related-tags | category·score_min·score_max·limit |
| GET /api/taxonomy/nodes | parent_id·limit, 별도 트리 구분 |
| GET/PUT /api/tag-overrides | 사용자 검증 별칭·즐겨찾기·표현 매핑 |

생성 상태는 queued → running → completed/failed/cancelled이며 중단 대기 시 cancelling을 표시합니다. 실패 코드에는 unreachable, loading, timeout, oom, invalid_json, model_mismatch, budget_conflict가 있습니다. 입력과 이전 결과는 오류로 삭제하지 않습니다.

스키마 원본은 Pydantic 모델이며 `scripts/export_contracts.py`가 배포용 `schemas/*.schema.json`을 만듭니다. 로컬 Swagger UI `/docs`에서 경로의 실제 파라미터와 계약을 확인할 수 있습니다.

SQLite DB 선택 API는 앱 백엔드가 읽을 수 있는 사용자가 명시한 로컬 파일만 엽니다. 원본 DB에 쓰지 않습니다. 기본 바인딩은 로컬호스트이며 외부 Origin과 Host를 제한합니다.

## 작업 채팅 / Workspace chat

| 경로 / Endpoint | 기능 / Purpose |
| --- | --- |
| POST /api/chat | 대화 요청 / Submit chat |
| GET /api/chat/requests/{id} | 응답 상태 / Response status |
| POST /api/chat/cancel/{id} | 중단 / Cancel |
| PUT /api/chat/messages/{id} | 모델 답변 편집 / Edit stored model response |
| POST /api/chat/history/delete | 완료된 대화 응답 삭제 / Delete finalized chat responses |
| GET /api/files | 편집 가능한 지시문·자료 / Editable prompts and references |
| PUT /api/files | 원문 검사·저장 / Validate and save text |

대화 지시문은 `prompts/chat-system.md`, LLM 가이드북은 `knowledge/llm-guidebook.json`입니다. / Chat instructions are in `prompts/chat-system.md`; the LLM reference guide is `knowledge/llm-guidebook.json`.
