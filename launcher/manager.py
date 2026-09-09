"""Local desktop controller. JSON-lines over inherited pipes; no control TCP port."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['NAI_DATA_DIR'] = str(ROOT / 'data')


class Cancelled(Exception):
    pass


def sha(path, cancel=None):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(4 * 1024 * 1024):
            if cancel and cancel.is_set():
                raise Cancelled('작업을 취소했습니다. 다운로드는 다음 셋업에서 이어집니다.')
            h.update(block)
    return h.hexdigest()


def extract_safe(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target = (destination / item.filename.replace('\\', '/')).resolve()
            if not target.is_relative_to(destination) or ':' in item.filename or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('압축 파일에 허용되지 않은 경로가 있습니다.')
        z.extractall(destination)


def download(asset, target, cancel, report):
    """Pinned hash, atomic promotion, Range resume; never trust size alone."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        report('파일 검사: ' + target.name, 0)
        if sha(target, cancel) == asset['sha256']:
            report('기존 파일 확인: ' + target.name, 100)
            return target
    part = target.with_name(target.name + '.part')
    for attempt in range(3):
        if cancel.is_set():
            raise Cancelled('다운로드를 취소했습니다. 다음 셋업에서 이어받습니다.')
        start = part.stat().st_size if part.exists() else 0
        if start and start == asset.get('size'):
            if sha(part, cancel) == asset['sha256']:
                os.replace(part, target)
                return target
            part.unlink()
            start = 0
        headers = {'User-Agent': 'NAI-Character-Studio/1.2', 'Accept-Encoding': 'identity'}
        if start:
            headers['Range'] = f'bytes={start}-'
        try:
            with urllib.request.urlopen(urllib.request.Request(asset['url'], headers=headers), timeout=30) as response:
                if response.status == 206:
                    if not response.headers.get('Content-Range', '').startswith(f'bytes {start}-'):
                        raise ValueError('이어받기 응답 범위가 일치하지 않습니다.')
                else:
                    start = 0
                total = start + int(response.headers.get('Content-Length', 0))
                done = start
                last = 0
                with part.open('ab' if start else 'wb') as f:
                    while block := response.read(1024 * 1024):
                        if cancel.is_set():
                            raise Cancelled('다운로드를 취소했습니다. 다음 셋업에서 이어받습니다.')
                        f.write(block)
                        done += len(block)
                        if time.monotonic() - last > .35:
                            report(f'{target.name} · {done / 1e9:.2f} / {total / 1e9:.2f} GB', min(99, int(done * 100 / total)) if total else 0)
                            last = time.monotonic()
            report('SHA-256 검사: ' + target.name, 99)
            if sha(part, cancel) != asset['sha256']:
                part.unlink()
                raise ValueError('다운로드 파일 검증 실패: ' + target.name + '. 셋업을 다시 누르면 새로 받습니다.')
            os.replace(part, target)
            report('완료: ' + target.name, 100)
            return target
        except urllib.error.HTTPError as e:
            if e.code == 416 and part.exists():
                part.unlink()
                continue
            if e.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(f'다운로드 HTTP {e.code}: {target.name}. 네트워크/배포 파일 접근을 확인하고 셋업을 다시 누르세요.') from e
            if attempt == 2:
                raise
        except (OSError, TimeoutError) as e:
            if attempt == 2:
                raise RuntimeError(f'다운로드 연결 실패: {target.name}. 셋업을 다시 누르면 이어받습니다. {e}') from e
        if cancel.wait(1 + attempt):
            raise Cancelled('취소했습니다.')
    raise RuntimeError('다운로드를 완료하지 못했습니다. 셋업을 다시 실행하세요.')


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def free_port(preferred):
    with socket.socket() as s:
        try:
            s.bind(('127.0.0.1', preferred))
        except OSError:
            s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def api(url, body=None, method=None, timeout=30):
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Manager:
    def __init__(self, root=ROOT, emit=None):
        self.root = Path(root)
        self.emit = emit or (lambda value: print(json.dumps(value, ensure_ascii=False), flush=True))
        self.manifest = json.loads((self.root / 'launcher/assets.json').read_text(encoding='utf-8'))
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.process_lock = threading.RLock()
        self.children = []
        self.busy = False
        self.url = ''
        self.state_path = self.root / 'data/install.json'
        self.state = json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
        self.prerequisite_done = threading.Event()
        self.prerequisite_code = None

    def report(self, text, percent=0, **extra):
        self.emit({'type': 'status', 'message': text, 'progress': percent, **extra})

    def local_asset(self, asset, subdir):
        return download(asset, self.root / subdir / asset['filename'], self.cancel, self.report)

    def spawn(self, command, log_name, env=None):
        with self.process_lock:
            if self.cancel.is_set():
                raise Cancelled('취소했습니다.')
            logs = self.root / 'data/logs'
            logs.mkdir(parents=True, exist_ok=True)
            with (logs / log_name).open('ab', buffering=0) as log:
                p = subprocess.Popen(command, cwd=self.root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.children.append(p)
            return p

    def stop(self):
        with self.process_lock:
            for p in reversed(self.children):
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait(timeout=5)
            self.children.clear()
            self.url = ''
        self.report('서버를 종료했습니다. 저장한 프로젝트와 모델은 유지됩니다.', running=False, url='')

    def wait_process(self, p, seconds=300):
        end = time.monotonic() + seconds
        while p.poll() is None:
            if self.cancel.wait(.2):
                raise Cancelled('취소했습니다.')
            if time.monotonic() > end:
                p.terminate()
                raise RuntimeError('설치 명령 시간이 초과되었습니다. 로그를 확인하세요.')
        if p.returncode:
            raise RuntimeError('패키지 설치 실패. 로그 폴더의 packages.log를 확인하고 셋업을 다시 누르세요.')

    def setup(self, model, runtime):
        if self.children and any(p.poll() is None for p in self.children):
            raise ValueError('실행 중에는 설치를 바꿀 수 없습니다. 먼저 서버 중지를 누르세요.')
        if model not in self.manifest['models'] or runtime not in self.manifest['runtimes']:
            raise ValueError('설치 프로필이 잘못되었습니다.')
        required = self.manifest['models'][model].get('size', 6_000_000_000) + 4_000_000_000
        model_target = self.root / 'models' / self.manifest['models'][model]['filename']
        for cached in (model_target, model_target.with_name(model_target.name + '.part')):
            if cached.exists():
                required -= cached.stat().st_size
        if shutil.disk_usage(self.root).free < max(required, 2_000_000_000):
            raise ValueError(f'설치 공간이 부족합니다. 이 드라이브에 약 {max(required, 2_000_000_000)/1e9:.1f} GB의 여유 공간이 필요합니다.')
        self.report('1/5 · 포함된 Python 패키지 검사 및 설치')
        wheels = self.root / 'launcher/bootstrap/wheels'
        for asset in self.manifest['wheels']:
            path = wheels / asset['filename']
            if not path.exists() or sha(path, self.cancel) != asset['sha256']:
                download(asset, path, self.cancel, self.report)
        pip = next(a for a in self.manifest['wheels'] if a['name'] == 'pip')
        site = Path(sys.executable).parent / 'Lib/site-packages'
        site.mkdir(parents=True, exist_ok=True)
        extract_safe(wheels / pip['filename'], site)
        self.wait_process(self.spawn([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', '--find-links', str(wheels), '-r', str(self.root / 'requirements.lock')], 'packages.log'))
        importlib.invalidate_caches()
        self.report('2/5 · 추론 엔진 설치')
        runtime_dir = self.root / '.runtime/llama' / runtime / self.manifest['runtime_release']
        for asset in self.manifest['runtimes'][runtime]:
            archive = self.local_asset(asset, '.runtime/downloads')
            extract_safe(archive, runtime_dir)
        if os.name == 'nt':
            self.report('Microsoft 실행 구성 요소를 준비합니다. Windows 권한 창이 나오면 허용하세요.')
            redist = self.local_asset(self.manifest['vcredist'], '.runtime/downloads')
            self.prerequisite_done.clear()
            self.emit({'type':'prerequisite','path':str(redist)})
            while not self.prerequisite_done.wait(.25):
                if self.cancel.is_set():
                    raise Cancelled('셋업을 취소했습니다. 열려 있는 Microsoft 설치 창은 자체적으로 마무리됩니다.')
            if self.prerequisite_code not in (0, 1638, 3010):
                raise RuntimeError(f'Microsoft 구성 요소 설치가 완료되지 않았습니다 (코드 {self.prerequisite_code}). 셋업을 다시 실행하세요.')
            if self.prerequisite_code == 3010:
                self.report('Microsoft 구성 요소가 재부팅을 요청했습니다. 셋업 완료 후 실행 실패 시 Windows를 재시작하세요.')
        exe = next(runtime_dir.rglob('llama-server.exe'), None)
        if exe is None:
            raise ValueError('추론 엔진 압축에 llama-server.exe가 없습니다.')
        self.report('3/5 · 모델 다운로드 (첫 설치에 수 GB가 필요합니다)')
        model_file = self.local_asset(self.manifest['models'][model], 'models')
        self.report('4/5 · 태그 DB 다운로드')
        db_file = self.local_asset(self.manifest['database'], 'data/tag-db')
        self.report('5/5 · DB 검사·검색 인덱스 구성·연결 설정 저장')
        from backend.app.adapters.danbooru_sqlite import DanbooruSQLiteAdapter
        adapter = DanbooruSQLiteAdapter(str(db_file), self.root / 'data')
        status = adapter.inspect_capabilities()
        if not status['available'] or not status['capabilities']['tags']:
            raise ValueError('태그 DB 검사 실패: ' + str(status.get('error')))
        if self.cancel.is_set():
            raise Cancelled('설치 마무리를 취소했습니다. 셋업을 다시 누르세요.')
        new_state = {'model': model, 'runtime': runtime, 'model_file': str(model_file), 'llama_exe': str(exe), 'db_file': str(db_file),
                     'model_sha256': self.manifest['models'][model]['sha256'], 'runtime_release': self.manifest['runtime_release'], 'installed_at': time.time()}
        self.configure(new_state, 8080)
        atomic_json(self.state_path, new_state)
        self.state = new_state
        self.report('설치 완료 · 실행 버튼을 누르세요.', 100, installed=True)

    def configure(self, state, llama_port):
        from backend.app.storage.repository import Repository
        from backend.app.services.config import defaults
        repo = Repository(self.root / 'data/projects.sqlite')
        settings = repo.get('settings', defaults())
        settings['llm'].update(mode='live', provider='llama_cpp', base_url=f'http://127.0.0.1:{llama_port}/v1', model_id='nai-local',
                               api_key='', model_path=state['model_file'], model_profile=state['model'], context_size=8192, parallel_requests=1, thinking=False)
        settings['runtime']['gpu_layers'] = 0 if state['runtime'] == 'cpu' else 99
        settings['tag_config']['tag_provider'].update(db_path=state['db_file'], enabled=True)
        repo.set('settings', settings)

    def wait_http(self, process, url, seconds=360):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.cancel.is_set():
                raise Cancelled('시작을 취소했습니다.')
            if process.poll() is not None:
                raise RuntimeError('서버가 종료되었습니다. 로그 열기에서 오류를 확인하세요. GPU 메모리 또는 드라이버 오류라면 셋업에서 실행 장치를 직접 변경할 수 있습니다.')
            try:
                value = api(url, timeout=2)
                if process.poll() is None:
                    return value
            except (OSError, ValueError):
                pass
            self.cancel.wait(.5)
        raise RuntimeError('서버 시작 제한 시간(6분)을 넘었습니다. 로그 열기에서 상태를 확인하세요.')

    def start(self):
        if self.url and self.children and all(p.poll() is None for p in self.children):
            self.report('이미 실행 중입니다.', 100, running=True, url=self.url)
            return
        if not self.state:
            raise ValueError('먼저 셋업 시작을 눌러 설치하세요.')
        self.stop()
        state = dict(self.state)
        # Rebase portable paths after moving the whole application directory.
        state['model_file'] = str(self.root / 'models' / self.manifest['models'][state['model']]['filename'])
        state['db_file'] = str(self.root / 'data/tag-db' / self.manifest['database']['filename'])
        runtime_root = self.root / '.runtime/llama' / state['runtime'] / state['runtime_release']
        state['llama_exe'] = str(next(runtime_root.rglob('llama-server.exe'), runtime_root / 'llama-server.exe'))
        for key in ('model_file', 'db_file', 'llama_exe'):
            if not Path(state[key]).is_file():
                raise ValueError('설치 파일이 없습니다. 셋업을 다시 누르면 복구합니다: ' + key)
        self.report('모델 무결성 검사 중… (첫 실행은 잠시 걸립니다)')
        if sha(state['model_file'], self.cancel) != state['model_sha256']:
            raise ValueError('모델 검증에 실패했습니다. 셋업을 다시 눌러 복구하세요.')
        exe = state['llama_exe']
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        help_result = subprocess.run([exe, '--help'], capture_output=True, timeout=30, **options)
        help_text = (help_result.stdout + help_result.stderr).decode('utf-8', errors='replace')
        required = ['--jinja', '--chat-template-kwargs', '--parallel', '--alias']
        if help_result.returncode or any(flag not in help_text for flag in required):
            raise RuntimeError('추론 엔진 실행/필수 옵션 검사 실패. 엔진 로그: ' + help_text[-1500:])
        version = subprocess.run([exe, '--version'], capture_output=True, timeout=30, **options)
        if version.returncode:
            raise RuntimeError('추론 엔진 버전 검사 실패')
        llama_port = free_port(8080)
        backend_port = free_port(8000)
        self.configure(state, llama_port)
        cmd = [exe, '-m', state['model_file'], '--alias', 'nai-local', '--jinja', '-c', '8192', '-ngl', '0' if state['runtime'] == 'cpu' else '99',
               '--parallel', '1', '--host', '127.0.0.1', '--port', str(llama_port), '--chat-template-kwargs', '{"enable_thinking":false}']
        self.report('모델을 메모리에 불러오는 중…')
        llama = self.spawn(cmd, 'llama.log')
        self.wait_http(llama, f'http://127.0.0.1:{llama_port}/health')
        env = dict(os.environ, NAI_MODE='live', NAI_DATA_DIR=str(self.root/'data'), NAI_LOCAL_ORIGIN=f'http://127.0.0.1:{backend_port}')
        self.report('편집 화면 서버를 시작하는 중…')
        backend = self.spawn([sys.executable, '-X', 'utf8', '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', str(backend_port)], 'backend.log', env)
        url = f'http://127.0.0.1:{backend_port}'
        health = self.wait_http(backend, url + '/api/health')
        if health.get('mode') != 'live':
            raise RuntimeError('실제 모델 연결 모드가 적용되지 않았습니다.')
        self.url = url
        atomic_json(self.root/'data/runtime-lock.json', {'binary_version': (version.stdout+version.stderr).decode('utf-8',errors='replace'), 'model_sha256':state['model_sha256'], 'command':cmd, 'started_at':time.time()})
        self.report('실행 중 · 편집 화면을 엽니다. 실행확인으로 실제 생성을 시험하세요.', 100, running=True, url=url, open=True)

    def check(self):
        if not self.url or not self.children or any(p.poll() is not None for p in self.children):
            raise ValueError('먼저 실행 버튼을 누르세요.')
        self.report('실행확인 1/3 · 앱과 실제 모델 연결')
        if api(self.url + '/api/health').get('mode') != 'live':
            raise ValueError('실제 모델 모드가 아닙니다.')
        self.report('실행확인 2/3 · 태그 DB 검색')
        db = api(self.url + '/api/tag-db/status', timeout=120)
        if not db.get('available'):
            raise ValueError('태그 DB가 연결되지 않았습니다.')
        found = api(self.url + '/api/tags/search?q=black_hair')
        if not found.get('items'):
            raise ValueError('태그 검색 결과가 없습니다.')
        self.report('실행확인 3/3 · 짧은 프롬프트 실제 생성 (최대 5분)')
        payload = {'rating':'SFW', 'request_ko':'성인 여성 한 명. 검은 머리, 흰 셔츠. 간결하게 작성.',
                   'characters':[{'id':'setup_check','nai_subject':'girl','fields':{'identity':'성인 여성','appearance':'검은 머리','outfit':'흰 셔츠'}}],
                   'controls':{'variant_count':1, 'detail':'short','expansion':'none'}}
        job = api(self.url + '/api/generate', payload, timeout=30)
        end = time.monotonic() + 300
        try:
            while time.monotonic() < end:
                if self.cancel.is_set():
                    raise Cancelled('실행확인을 취소했습니다.')
                job = api(self.url + '/api/requests/' + job['request_id'])
                if job['status'] == 'completed':
                    if not job.get('candidates'):
                        raise ValueError('생성이 완료되었지만 결과가 없습니다.')
                    atomic_json(self.root/'data/execution-check.json', {'checked_at':time.time(), 'passed':True, 'db_snapshot':db.get('snapshot_id'), 'request_id':job['request_id'], 'model':self.state['model']})
                    self.report('실행확인 통과 · 실제 프롬프트 생성과 DB 검색이 정상입니다.', 100, checked=True)
                    return
                if job['status'] not in ('queued', 'running'):
                    raise ValueError('실제 생성 검사 실패: ' + json.dumps(job.get('error',job['status']),ensure_ascii=False))
                self.cancel.wait(.5)
            raise ValueError('실제 생성 검사가 5분을 넘었습니다. 엔진 로그와 메모리를 확인하세요.')
        finally:
            if job.get('status') in ('queued','running'):
                try:
                    api(self.url+'/api/cancel/'+job['request_id'], {})
                except OSError:
                    pass

    def dispatch(self, command):
        action = command.get('action')
        if action == 'prerequisite_result':
            self.prerequisite_code = int(command['code'])
            self.prerequisite_done.set()
            return
        if action == 'cancel':
            self.cancel.set()
            self.report('취소 요청됨 · 진행 중인 파일/요청 정리 후 멈춥니다.')
            return
        with self.lock:
            if self.busy:
                self.report('현재 작업이 끝난 뒤 다시 누르세요.')
                return
            self.busy = True
        self.cancel.clear()
        self.emit({'type':'busy','busy':True})
        def work():
            try:
                if action == 'setup':
                    self.setup(command['model'], command['runtime'])
                elif action == 'start':
                    if self.state and (command.get('model', self.state['model']) != self.state['model'] or command.get('runtime', self.state['runtime']) != self.state['runtime']):
                        raise ValueError('선택한 모델/장치가 설치 기록과 다릅니다. 셋업 시작을 눌러 변경한 구성을 설치하세요.')
                    self.start()
                elif action == 'check':
                    self.check()
                elif action == 'stop':
                    self.stop()
                else:
                    raise ValueError('알 수 없는 작업')
            except Exception as e:
                if action in ('start','setup'):
                    self.stop()
                if action == 'check':
                    atomic_json(self.root/'data/execution-check.json', {'passed':False,'checked_at':time.time(),'error':str(e)})
                self.emit({'type':'error','message':str(e)})
            finally:
                with self.lock:
                    self.busy = False
                self.emit({'type':'busy','busy':False})
        threading.Thread(target=work, daemon=True).start()


def main():
    manager = Manager()
    manager.emit({'type':'ready','installed':bool(manager.state), 'model':manager.state.get('model',''), 'runtime':manager.state.get('runtime','cuda12'), 'message':'설치 기록이 있습니다. 실행을 누르세요.' if manager.state else '설치 준비 완료. 셋업 시작을 누르세요.'})
    def monitor():
        while True:
            time.sleep(2)
            if not manager.busy and manager.url and any(p.poll() is not None for p in manager.children):
                manager.stop()
                manager.emit({'type':'error','message':'실행 중 서버가 종료되었습니다. 로그 열기에서 원인을 확인한 뒤 실행을 다시 누르세요.'})
    threading.Thread(target=monitor, daemon=True).start()
    try:
        for line in sys.stdin:
            command = json.loads(line)
            if command.get('action') == 'quit':
                break
            manager.dispatch(command)
    finally:
        manager.cancel.set()
        manager.stop()


if __name__ == '__main__':
    main()
