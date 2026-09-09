# NAI-AI-CharacterStudio

[한국어](README.md) · [English](README.en.md)

**A local workspace for discussing characters and scenes with an LLM and writing, editing, and organizing character prompts for NovelAI.** Describe scenes and characters in Korean, generate English prompt candidates, and edit/copy each character's output. Chat stays alongside the editing workspace.

This is not an image generator. Copy finished prompts into NovelAI yourself. The app does not log in to NovelAI or call its billing or image-generation API. It is not an official or affiliated NovelAI product.

Repository: [dkfk5326/NAI-AI-CharacterStudio](https://github.com/dkfk5326/NAI-AI-CharacterStudio)

## Features

- **Character prompts:** describe appearance, outfits, expressions, poses, actions, and relationships; compare and edit candidates.
- **Workspace chat:** discuss everyday topics, character design, stories, composition, lighting, and poses, with optional current-project context.
- **History editing:** edit/delete user and model messages, rename/delete conversations, and rename/delete individual or all generated results.
- **Editable chat instructions:** change the conversation model's role, tone, and response style in the browser.
- **NAI guide for the LLM:** select relevant syntax and model constraints for generation, rewriting, and chat.
- **Optional tag database:** connect a Danbooru-based SQLite database for lookup, completion, and tag grounding.
- **Local projects:** save projects, results, overrides, and settings; import/export project JSON.

The UI and default conversation language are Korean. English documentation does not imply an English UI.

## Installation

### Requirements

- Python **3.12 or 3.13**
- Node.js **22.12 or later** and npm
- Git, or GitHub's **Code → Download ZIP**
- For real generation/chat: a **local llama.cpp or LM Studio API server** with a model loaded

Mock mode allows trying example generation and editing without weights or a tag database. Real model memory requirements and speed depend on the model, quantization, and hardware.

This is a **source distribution**. Windows executables, the Python bootstrap, model weights, and tag databases are not included. Follow the steps below; there is no `set_up.exe` to run in the source ZIP.

### 1. Get the source

```sh
git clone https://github.com/dkfk5326/NAI-AI-CharacterStudio.git
cd NAI-AI-CharacterStudio
```

If using a ZIP, extract it and open a terminal in the directory containing `README.md`.

### 2. Create a Python environment

```sh
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```sh
source .venv/bin/activate
```

### 3. Install dependencies and build the UI

```sh
python -m pip install -r requirements.lock
npm --prefix frontend ci
npm --prefix frontend run build
```

### 4. Start the app

```sh
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Keep the server terminal open; press `Ctrl+C` there to stop. On later runs, activate the environment and repeat step 4. Repeat the npm install/build commands after frontend source updates.

## Connect a real LLM

1. Load a model in llama.cpp or LM Studio and start its local API server.
2. In **설정** (Settings), select **실제 로컬 모델** (Live local model).
3. Select the matching **추론 어댑터** (Inference adapter) and enter the server address including `/v1`, for example `http://127.0.0.1:8080/v1`. Match the port to your server.
4. Enter a model ID and local API key if needed. Click **설정 저장** (Save settings), then **저장된 연결 확인** (Check saved connection).
5. Prompt generation requires structured JSON output. Use **JSON 제약 출력 시험** (Test JSON constraint) to check support. Chat uses ordinary text responses.

Bundled profile sources, filenames, and pinned revisions are in [config/models.yaml](config/models.yaml). Changing app connection settings does not automatically load a model into an external server. Mock mode does not produce real chat responses.

## Usage

### Create character prompts

1. In **작업 공간** (Workspace), click **2인 예제 불러오기** (Load two-character example), or write a scene and fill in character cards.
2. Select the target NAI model and describe each character's appearance, outfit, and action. Add a relationship when you need to fix its subject and target.
3. Click **프롬프트 생성** (Generate prompts) and wait for candidates. Use **묶음 생성** (Batch generation) when many characters exceed the context budget.
4. Edit Character Prompt and Undesired Content (UC) directly, then use the corresponding copy buttons. Copying uses the current edited text.
5. Paste into the appropriate character-prompt and UC fields in NovelAI. Set the base prompt and image-generation parameters separately in NovelAI.

### Chat while editing

Send messages in **작업 채팅** (Workspace chat). Enable **현재 캐릭터·장면·선택 결과 참고** to include the current characters, scene, and selected result. Disable it to chat without project context.

Use **이 결과를 채팅에서 검토** (Review this result in chat) to discuss revisions, and **장면 입력에 추가** (Add to scene input) on an answer to bring text into your scene. Conversation alone does not automatically change the project.

Use each message's **수정 / 삭제** (Edit / Delete) buttons and **대화 관리** (Conversation management) to organize history. Edits affect subsequent requests. Wait for a running response or its cancellation to finish before editing that conversation. Use **생성 기록 관리** (Generated history management) to rename/delete results; saving the project also cleans its stored history.

### Change the conversation model's instructions

Open **작업 채팅 → 대화 프롬프트** (Workspace chat → Chat prompt), edit the role/tone/response instructions, and click **프롬프트 저장** (Save prompt). Changes apply to subsequent requests across conversations; queued/running requests retain their original instructions. **기본값 불러오기** (Load defaults) also requires saving before it takes effect.

Default text: [prompts/chat-system.md](prompts/chat-system.md). This is separate from generation prompts.

### LLM reference guide and optional tags

[knowledge/llm-guidebook.json](knowledge/llm-guidebook.json) is an **NAI reference guide for the LLM**. Edit it under **LLM 프롬프트·참고 자료** in Settings. Relevant sections are selected automatically; reference material does not guarantee a model's behavior.

Tag lookup is optional. Obtain the SQLite file separately from the [database source](docs/SOURCES.md), enter its absolute path under **설정 → 태그 데이터베이스** (Settings → Tag database), then click **해시·스키마 확인 후 연결** (Verify hash/schema and connect). The original database is read-only. It is not redistributed in this repository.

### Save and reopen

Input drafts and conversations are kept in the same browser's local storage. **프로젝트 저장** (Save project) persists the project in the server's `data` directory. Reopen it through **프로젝트** (Projects), or use **내보내기** (Export) to save project JSON. Clearing browser storage can remove local conversations and drafts.

The server is intended for local use; the default bind address is `127.0.0.1`.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| UI does not open | Check that the server is running and inspect terminal errors. Run `npm --prefix frontend run build` and reload. |
| Blank screen after update | Reload with `Ctrl+F5` to fetch current frontend assets. |
| Cannot send chat | Check live mode, server address, and whether a model is loaded. |
| Generation JSON errors | Check the model/server's structured-output support. |
| Context limit exceeded | Reduce request/reference size or use batch generation. Match app settings to the server's actual context limit. |
| No tag results | Check the database path and connection. General editing works without the DB. |

## Development and tests

```sh
python -m pip install -r requirements-test.lock
python -m unittest discover -s tests
npm --prefix frontend test
npm --prefix frontend run build
```

Build the frontend once before Python tests. For frontend development, run `npm --prefix frontend run dev` and start the backend separately. Automated tests do not replace real Windows GPU or model-quality testing.

[API reference](docs/api.md) · [Launcher source build](launcher/README.md) · [Contributing](CONTRIBUTING.md)

## Attribution and copyright

[Third-party notices](THIRD_PARTY_NOTICES.md) · [Danbooru, model, and NovelAI sources](docs/SOURCES.md) · [Dependency inventory](docs/DEPENDENCIES.md)

**Unauthorized copying and commercial use are prohibited.** See [LICENSE](LICENSE) for its scope and permission to make copies required for personal, non-commercial operation. Third-party components retain their original licenses. This is a source-available project with a commercial-use restriction, not an open-source-licensed project.
