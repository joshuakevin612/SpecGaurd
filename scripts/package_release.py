"""Create an allowlisted, checksum-addressed deployment archive without secrets."""
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package():
    if not (ROOT / 'frontend/dist/index.html').exists():
        raise RuntimeError('Build the frontend before packaging')
    files = []
    for folder in ['backend', 'shared', 'specguard_ai', 'demos', 'frontend/dist', 'deploy', 'scripts']:
        files.extend(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files.extend(ROOT / p for p in ['requirements.lock', 'requirements-dev.lock', 'requirements.txt',
                                    'requirements-dev.txt', 'pyproject.toml', 'README.md',
                                    'docs/DEPLOYMENT.md'])
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    manifest = json.dumps(hashes, sort_keys=True, indent=2).encode()
    release_id = hashlib.sha256(manifest).hexdigest()[:16]
    out = ROOT / 'artifacts/releases'
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / f'{release_id}.manifest.json'
    manifest_path.write_bytes(manifest)
    archive = out / f'specguard-{release_id}.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for p in sorted(files):
            bundle.add(p, arcname=p.relative_to(ROOT).as_posix())
        bundle.add(manifest_path, arcname='manifest.json')
    (out / f'{archive.name}.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    print(f'Release archive: {archive}')
    return archive


if __name__ == '__main__':
    package()
