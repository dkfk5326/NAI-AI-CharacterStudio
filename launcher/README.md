# Windows launcher build / Windows 런처 빌드

Windows 설치 파일은 [설치 패키지](../installer/)의 전체 ZIP에 포함됩니다. 소스 저장소에는 실행 파일·부트스트랩을 저장하지 않습니다. / Windows setup is included in the full release ZIP. Executables and bootstrap files are distributed as a complete ZIP under `installer/`.

`.github/workflows/windows-release.yml` builds the C++17 launcher with MSVC, builds the frontend, and runs `scripts/package_windows.py` to download and verify pinned Python/wheel files. It packages both `set_up.exe` and `NAI_Studio.exe` with the backend, frontend, bootstrap, and original license notices.

Windows 릴리스 워크플로는 MSVC로 런처를 컴파일하고 화면을 빌드한 뒤, 고정 해시의 Python·wheel을 검증하여 전체 설치 ZIP을 만듭니다. 모델·태그 DB는 사용자 셋업에서 별도로 다운로드합니다.

`launcher/assets.json` records upstream URLs, revisions, sizes, and SHA-256 values. `launcher/manager.py` manages setup, startup, cancellation, and verification over inherited pipes. Original databases are read-only. Closing the launcher terminates its child servers through a Windows Job Object.

런처는 상속 파이프로 설치·실행을 제어하며, 별도의 제어 HTTP 포트를 열지 않습니다. 원본 DB는 읽기 전용이고, 창을 닫으면 자신이 시작한 서버만 종료합니다. 실제 GPU와 모델 응답 품질은 사용자의 실행확인으로 검사합니다.
