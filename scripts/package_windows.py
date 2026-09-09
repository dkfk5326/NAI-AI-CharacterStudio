"""Build a complete Windows distribution from pinned assets and compiled launchers."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from launcher.manager import download, extract_safe


def main():
    manifest = json.loads((ROOT / 'launcher/assets.json').read_text(encoding='utf-8'))
    stage = ROOT / 'build/windows/NAI-AI-CharacterStudio'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for directory in ['backend', 'config', 'knowledge', 'prompts', 'schemas', 'licenses']:
        shutil.copytree(ROOT / directory, stage / directory, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ['README.md', 'README.en.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'requirements.lock', 'set_up.exe', 'NAI_Studio.exe']:
        shutil.copy2(ROOT / name, stage / name)
    (stage / 'launcher').mkdir()
    for name in ['manager.py', 'assets.json']:
        shutil.copy2(ROOT / 'launcher' / name, stage / 'launcher' / name)
    shutil.copytree(ROOT / 'launcher/licenses', stage / 'launcher/licenses')
    shutil.copytree(ROOT / 'docs', stage / 'docs')
    shutil.copytree(ROOT / 'frontend/dist', stage / 'frontend/dist')
    # Keep paths referenced by attribution documents valid in the release too.
    shutil.copytree(ROOT / 'frontend/public', stage / 'frontend/public')
    cancel = threading.Event()
    cache = ROOT / 'build/downloads'
    python = download(manifest['python'], cache / 'python-embed.zip', cancel, lambda message, *_: print(message))
    extract_safe(python, stage / 'launcher/bootstrap/python')
    for entry in manifest['bootstrap_files']:
        path = stage / 'launcher/bootstrap/python' / entry['path']
        assert path.is_file(), f'Missing bootstrap: {entry["path"]}'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], f'Bootstrap hash: {entry["path"]}'
    for asset in manifest['wheels']:
        path = download(asset, cache / asset['filename'], cancel, lambda message, *_: print(message))
        dest = stage / 'launcher/bootstrap/wheels' / asset['filename']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    assert (stage / 'set_up.exe').read_bytes()[:2] == b'MZ'
    assert (stage / 'NAI_Studio.exe').read_bytes() == (stage / 'set_up.exe').read_bytes()
    assert (stage / 'frontend/dist/THIRD_PARTY_LICENSES.txt').is_file()
    # Smoke-test the shipped interpreter without downloading models.
    check_python = stage / 'launcher/bootstrap/python/python.exe'
    subprocess.run([str(check_python), '-c', 'import ssl, sqlite3, ctypes; print("Embedded Python OK")'], check=True)
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    (stage / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(stage).as_posix() + '\n' for p in files), encoding='utf-8')
    out = ROOT / 'dist/NAI-AI-CharacterStudio-Windows-v1.2.3d.zip'
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(p for p in stage.rglob('*') if p.is_file()):
            archive.write(path, stage.name + '/' + path.relative_to(stage).as_posix())
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None
    (out.parent / 'SHA256SUMS.txt').write_text(hashlib.sha256(out.read_bytes()).hexdigest() + '  ' + out.name + '\n', encoding='utf-8')
    print(f'Complete Windows package: {out.name} ({out.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
