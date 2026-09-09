# 자료 출처 / Source attribution

## Danbooru 태그와 DB / Danbooru tags and database

| 구분 / Item | 출처 / Source |
| --- | --- |
| 원 태그·분류·사용자 기여 / Original tags, categories, community contributions | [Danbooru](https://danbooru.donmai.us/) 및 기여자 / and its contributors |
| SQLite 배포·한국어 번역·분류 구조의 배포 경로 / SQLite distribution, Korean translations, taxonomy distribution | [cksdnfas/danbooru-db-viewer](https://github.com/cksdnfas/danbooru-db-viewer) |
| 고정 DB 배포 / Pinned database release | [26.05.23](https://github.com/cksdnfas/danbooru-db-viewer/releases/tag/26.05.23), `danbooru-taxonomy.release.sqlite` |
| SHA-256 | `392c1528e94cfa1f39838be6a4585718361af884d280f0b0050eab6211c85e38` |
| 기존 구현에서 참고한 뷰어 리비전 / Viewer revision recorded by the implementation | `147e1a605d9e9e35a28482e6a77f2ae840a0ef64` |
| 뷰어 코드 라이선스 출처 / Viewer code license reference | [Upstream LICENSE](https://github.com/cksdnfas/danbooru-db-viewer/blob/147e1a605d9e9e35a28482e6a77f2ae840a0ef64/LICENSE) |

위 고정 리비전·해시는 기존 프로젝트의 배포 기록과 `launcher/assets.json`을 따릅니다. 이번 공개 준비 중 뷰어 저장소와 배포 페이지를 다시 열지 못했으므로, 현재 배포 상태나 DB 재배포 허가를 새로 확인했다고 주장하지 않습니다.

The pinned revision and hash above are retained from the project's existing distribution records and `launcher/assets.json`. The viewer repository and release page could not be retrieved during this preparation; current availability and database redistribution permission have not been independently reconfirmed.

태그 DB는 이 소스 패키지에 포함되지 않습니다. 앱의 SQLite 어댑터는 독립 구현이며 뷰어 소스 파일을 가져오지 않습니다. 기존 고지는 뷰어 코드를 MIT로 기록하지만, 이를 Danbooru 태그·번역·분류 데이터 전체의 라이선스로 간주하지 않습니다. 데이터의 권리는 원 기여자 및 해당 배포자의 조건에 따릅니다. 이 프로젝트의 저작권 고지는 외부 데이터에 적용되지 않습니다.

The database is not included in this source package. The SQLite adapter is independently implemented and does not import viewer source files. Existing notices identify the viewer code as MIT; this is not treated as a license for all Danbooru tags, translations, or taxonomy data. Data rights remain with their contributors and applicable distributors. This project's copyright notice does not cover external data.

## NovelAI 문법 자료 / NovelAI syntax references

LLM 참고 파일 `knowledge/llm-guidebook.json`과 `knowledge/nai-rules.yaml`은 아래 공식 문서를 문법 근거로 연결합니다. 가이드의 설명·모드별 지시문은 이 프로젝트에서 구성한 것이며 공식 가이드북 자체가 아닙니다. / The LLM reference files link to these official syntax sources. Their explanations and mode-specific instructions are assembled for this project; they are not an official NovelAI guidebook.

- [모델 / Models](https://docs.novelai.net/en/image/models/)
- [다중 캐릭터 / Multiple characters](https://docs.novelai.net/en/image/multiplecharacters/)
- [캐릭터 만들기 / Character creation](https://docs.novelai.net/en/image/tutorial-charactercreation/)
- [강조·약화 / Strengthening and weakening](https://docs.novelai.net/en/image/strengthening-weakening/)
- [태그 / Tags](https://docs.novelai.net/en/image/tags/)
- [원치 않는 요소 / Undesired content](https://docs.novelai.net/en/image/undesiredcontent/)
- [텍스트 표현 / Text rendering](https://docs.novelai.net/en/image/textrendering/)

NovelAI 명칭과 관련 상표는 해당 권리자에게 귀속됩니다. 이 프로젝트는 NovelAI의 공식 제품이나 제휴 서비스가 아닙니다. / NovelAI names and marks belong to their respective owners. This project is not an official or affiliated NovelAI product.

## 모델과 추론 도구 / Models and inference tools

모델 파일은 포함하지 않습니다. 실제 모델 선택·사용은 각 저장소와 기본 모델의 조건을 따릅니다. 정확한 리비전·파일명·해시는 `config/models.yaml` 및 `launcher/assets.json`에 있습니다. / Model weights are not included. Model use is governed by each repository's and base model's terms. Exact revisions, filenames, and hashes are in `config/models.yaml` and `launcher/assets.json`.

- Gemma 파생 모델 / Gemma-derived model: [HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive](https://huggingface.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive); [Gemma terms](https://ai.google.dev/gemma/terms)
- Qwen 기본 모델 / Base model: [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- Qwen 양자화 배포 / Quantized distribution: [unsloth/Qwen3-4B-Instruct-2507-GGUF](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)
- 추론 엔진 / Inference engine: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp), [license](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE)
- 선택적 로컬 서버 / Optional local server: [LM Studio](https://lmstudio.ai/)

## 고지의 범위 / Scope of notices

출처 표기는 외부 자료에 대한 소유권이나 재배포 허가를 뜻하지 않습니다. 원문 라이선스는 번역으로 대체하지 않습니다. / Attribution does not establish ownership or redistribution permission for external material. Translations do not replace original license texts.
