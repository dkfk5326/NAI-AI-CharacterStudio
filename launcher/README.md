# Desktop launcher source

소스 저장소에는 실행 파일과 `launcher/bootstrap`이 포함되지 않습니다. 아래 내용은 전체 Windows 배포를 구성하는 개발자를 위한 설명입니다. / This source repository excludes executables and `launcher/bootstrap`. The following describes building the full Windows distribution.

사용자는 루트의 set_up.exe / NAI_Studio.exe를 실행합니다. 이 문서는 개발용입니다.

StudioLauncher.cpp는 Windows API만 사용하는 C++17 GUI입니다. 제어 프로그램과 JSON-lines를 상속 파이프로 주고받으며, 별도 HTTP 제어 포트를 열지 않습니다. Windows Job Object가 Python 컨트롤러와 그 자식 서버를 관리합니다. 창을 닫거나 프로세스가 끝나면 소유한 자식만 종료합니다. Microsoft 공용 구성 요소 설치는 Windows의 정상 권한 요청으로 별도 실행합니다.

manager.py는 포함된 CPython으로 실행합니다. 셋업은 포함된 wheel 파일 및 원격 배포 파일의 SHA-256을 확인하고, Python 패키지·llama.cpp·VC++ 구성 요소·GGUF·태그 DB를 준비합니다. 설치 완료 기록은 마지막에 저장합니다. DB 원본은 읽기 전용이며 인덱스는 별도로 작성합니다. 모델은 자동 대체하지 않습니다.

assets.json은 다운로드 URL·리비전·바이트·SHA-256의 배포 잠금 파일입니다. 셋업은 latest URL이나 변경 가능한 모델 main 브랜치를 사용하지 않습니다. llama.cpp는 v0.4.0에서 지시한 b10809 배포 자산을 고정했습니다. CUDA 12.4 바이너리와 대응 cudart ZIP을 함께 설치합니다.

## 재빌드

MinGW-w64 C++17 컴파일러와 windres가 있는 개발 환경에서 프로젝트 루트 기준:

```sh
x86_64-w64-mingw32-windres launcher/launcher.rc -I launcher -o launcher-resource.o
x86_64-w64-mingw32-g++ -std=c++17 -O2 -static -municode -mwindows launcher/StudioLauncher.cpp launcher-resource.o -I launcher -o NAI_Studio.exe -lcomctl32 -lshell32 -lbcrypt -lgdi32 -luser32 -Wl,--major-subsystem-version,6,--minor-subsystem-version,0
```

출력 파일을 set_up.exe에도 복사합니다. 두 진입점은 같은 제어 GUI입니다. 컴파일러 런타임은 정적으로 연결되어 사용자가 MinGW나 .NET을 설치할 필요가 없습니다. 실행 파일에는 asInvoker 매니페스트가 포함됩니다.

## 검증 범위

다운로드의 이어받기/검증/취소, 설정 보존, 설치 기록, 실제 생성 검사 상태와 소유 프로세스 종료는 tests/test_launcher.py에서 검증합니다. 로컬 HTTP 서버, 작은 fixture DB와 테스트 프로세스 대역을 사용합니다. 실제 Windows GPU 실행 결과를 대체하지 않습니다. 실행확인 결과는 data/execution-check.json에 시간·모델·요청 ID와 함께 저장됩니다.
