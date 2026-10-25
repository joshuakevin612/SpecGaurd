"""The same local and CI verification command; fails on the first broken gate."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NPM = 'npm.cmd' if os.name == 'nt' else 'npm'
commands = [
    [sys.executable, '-m', 'ruff', 'check', 'shared', 'specguard_ai', 'backend', 'tests', 'scripts'],
    [sys.executable, '-m', 'pytest', '-q'],
    [sys.executable, '-m', 'pip', 'check'],
    [NPM, '--prefix', 'frontend', 'run', 'typecheck'],
    [NPM, '--prefix', 'frontend', 'run', 'build'],
]
if __name__ == '__main__':
    environment = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True, env=environment, timeout=180)
