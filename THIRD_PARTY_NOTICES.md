# 서드파티 고지 / Third-party notices

이 프로젝트의 무단 복제·상업 이용 금지 고지는 아래 서드파티 구성 요소에 적용되지 않습니다. 각 원저작자의 저작권·라이선스·고지는 그대로 유지됩니다. / This project's restriction on unauthorized copying and commercial use does not apply to third-party components below. Their original copyrights, licenses, and notices remain in effect.

## 앱 의존성 / Application dependencies

| 구성 요소 / Component | 출처 / Source | 라이선스 / License |
| --- | --- | --- |
| React, React DOM, Scheduler | [facebook/react](https://github.com/facebook/react) | MIT |
| Vite | [vitejs/vite](https://github.com/vitejs/vite) | MIT; bundled dependencies have separate notices |
| TypeScript | [microsoft/TypeScript](https://github.com/microsoft/TypeScript) | Apache-2.0 |
| FastAPI | [fastapi/fastapi](https://github.com/fastapi/fastapi) | MIT |
| Starlette | [encode/starlette](https://github.com/encode/starlette) | BSD-3-Clause |
| Uvicorn | [encode/uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause |
| Pydantic, pydantic-core | [pydantic/pydantic](https://github.com/pydantic/pydantic), [pydantic-core](https://github.com/pydantic/pydantic-core) | MIT |
| PyYAML | [yaml/pyyaml](https://github.com/yaml/pyyaml) | MIT |

전이 의존성을 포함한 버전·라이선스·원문 경로는 [의존성 목록](docs/DEPENDENCIES.md) 및 [JSON 목록](docs/dependencies.json)에 있습니다. npm·Python 잠금 파일의 고정 버전을 기준으로 하며, 원문은 [licenses](licenses/)에 보관합니다. / Versions, licenses, and retained text paths, including transitive dependencies, are in the [inventory](docs/DEPENDENCIES.md) and [JSON inventory](docs/dependencies.json). They are based on pinned npm/Python distributions; original texts are retained under [licenses](licenses/).

프런트엔드에 포함되는 React 계열 원문 고지는 [frontend/public/THIRD_PARTY_LICENSES.txt](frontend/public/THIRD_PARTY_LICENSES.txt)에 있으며 Vite 빌드 때 `dist`로 복사됩니다. 소스 저장소에는 `node_modules`, wheel, 빌드 결과를 포함하지 않습니다. / React-family notices shipped with the frontend are in [frontend/public/THIRD_PARTY_LICENSES.txt](frontend/public/THIRD_PARTY_LICENSES.txt), copied into `dist` by Vite. The source repository does not include `node_modules`, wheels, or built output.

## 포함된 C++ 코드 / Included C++ code

[JSON for Modern C++](https://github.com/nlohmann/json) 3.12.0 — Niels Lohmann 및 기여자 / and contributors, MIT. `launcher/json.hpp`의 원문 고지와 [라이선스 파일](launcher/licenses/nlohmann-json-MIT.txt)을 유지합니다. / Original notices in `launcher/json.hpp` and the [license file](launcher/licenses/nlohmann-json-MIT.txt) are retained.

## Windows 배포 구성 요소 / Windows distribution components

아래 바이너리는 소스 ZIP에 포함하지 않습니다. 기존 전체 Windows 배포 또는 런처에서 사용하는 구성 요소의 출처입니다. / These binaries are not included in the source ZIP. They are used by the existing full Windows distribution or launcher.

- CPython 3.13.15 — Python Software Foundation, [source](https://www.python.org/), [retained original license](licenses/CPython-3.13.15.txt). 전체 실행 패키지의 부트스트랩에도 원문이 포함됩니다. / The full runtime package also retains the original bootstrap license.
- MinGW-w64 / GCC runtimes — [MinGW-w64](https://www.mingw-w64.org/), [GCC](https://gcc.gnu.org/). [MinGW notices](launcher/licenses/mingw-w64-common-copyright.txt), [GCC runtime notices and exception](launcher/licenses/gcc-mingw-w64-base-copyright.txt).
- Microsoft Visual C++ Redistributable — [official distribution and deployment terms](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). 런처가 공식 경로에서 다운로드하며 Microsoft 조건을 따릅니다. / Downloaded by the launcher from the official source, subject to Microsoft's terms.
- llama.cpp 및 CUDA 런타임 / and CUDA runtime companion files — [official llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases). 고정 다운로드는 `launcher/assets.json`에 있습니다. 각 파일의 upstream 고지를 보존해야 합니다. / Pinned downloads are in `launcher/assets.json`; upstream notices must accompany their files.

## 태그 데이터·모델·문서 / Tag data, models, and documentation

Danbooru 원 기여자, DB 배포자 `cksdnfas/danbooru-db-viewer`, 모델 배포자, NovelAI 문서 출처는 [SOURCES.md](docs/SOURCES.md)에 기록했습니다. 뷰어 코드의 MIT 표기를 태그 DB 전체에 적용하지 않습니다. 모델 가중치와 원본 DB는 포함하지 않습니다. / [SOURCES.md](docs/SOURCES.md) credits Danbooru contributors, the `cksdnfas/danbooru-db-viewer` database distributor, model distributors, and NovelAI documentation. The viewer code's MIT designation is not applied to the entire tag database. Model weights and the original database are not bundled.

## CI 도구 / CI tools

GitHub Actions에서 [actions/checkout](https://github.com/actions/checkout), [actions/setup-node](https://github.com/actions/setup-node), [actions/setup-python](https://github.com/actions/setup-python)을 참조합니다. 각 액션은 MIT 라이선스를 사용하며 액션 코드를 이 저장소에 동봉하지 않습니다. / CI references these MIT-licensed actions; their code is not bundled in this repository.
