"""Secret-pattern and installed runtime advisory gates; values are never printed."""
import concurrent.futures
import importlib.metadata
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [r'\bAKIA[0-9A-Z]{16}\b', r'\bgh[pousr]_[A-Za-z0-9]{36,}\b',
            r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            r'\bnvapi-[A-Za-z0-9_-]{20,}\b', r'\bsk_live_[A-Za-z0-9]{24,}\b']


def check_package(pin):
    name, version = pin.split('==')
    if importlib.metadata.version(name) != version:
        raise RuntimeError(f'Installed runtime differs from lock: {name}')
    with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=20) as response:
        metadata = json.load(response)
    return name, [v['id'] for v in metadata.get('vulnerabilities', [])]


def main():
    problems = []
    for directory in ['backend', 'specguard_ai', 'shared', 'frontend/src', 'scripts', '.github', 'deploy']:
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.ts', '.tsx', '.js', '.json', '.yml', '.sh', '.env'}:
                text = path.read_text(encoding='utf-8')
                if any(re.search(pattern, text) for pattern in PATTERNS):
                    problems.append('Credential pattern: ' + str(path.relative_to(ROOT)))
    pins = [line for line in (ROOT / 'requirements.lock').read_text().splitlines() if '==' in line]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for name, advisories in pool.map(check_package, pins):
            if advisories:
                problems.append(name + ': ' + ', '.join(advisories))
    print('\n'.join(problems) if problems else f'Secret patterns and {len(pins)} runtime advisory checks passed')
    return bool(problems)


if __name__ == '__main__':
    sys.exit(main())
