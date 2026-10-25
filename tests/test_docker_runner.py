"""Real sandbox gates, opt in explicitly on hosts with a Docker engine."""
import os
import subprocess

import pytest

from backend.runner.pytest_runner import PytestRunner
from shared.schemas import GeneratedTest
from specguard_ai.demo_assets import load_demo

pytestmark = pytest.mark.skipif(os.getenv('SPECGUARD_DOCKER_TESTS') != '1', reason='Docker checks are opt-in')


@pytest.mark.parametrize('demo', ['add', 'divide', 'cart'])
def test_real_docker_good_bad_and_original_retest(demo):
    fixture = load_demo(demo)
    tests = [GeneratedTest.model_validate(t) for t in fixture['tests']]
    runner = PytestRunner()
    assert all(r.status == 'passed' for r in runner.run_tests(tests, fixture['good_code']))
    assert any(r.status == 'failed' for r in runner.run_tests(tests, fixture['bad_code']))


def test_docker_constraints_and_secret_absence(monkeypatch):
    monkeypatch.setenv('NVIDIA_API_KEY', 'this-host-secret-must-not-enter-container')
    source = '''import os, socket
def isolated():
    assert os.getuid() == 10001
    assert 'NVIDIA_API_KEY' not in os.environ
    assert open('/sys/fs/cgroup/memory.max').read().strip() == '268435456'
    assert open('/sys/fs/cgroup/pids.max').read().strip() == '64'
    for filename in ['/root-escape', '/work/submission.py']:
        try:
            open(filename, 'w')
            return False
        except OSError:
            pass
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(('1.1.1.1', 53))
        return False
    except OSError:
        return True
    finally:
        s.close()
'''
    test = GeneratedTest(id='TEST-001', requirement_id='REQ-001', description='Isolation',
                         pytest_code='from submission import isolated\ndef test_isolation():\n    assert isolated() == True\n')
    result = PytestRunner().run_tests([test], source)[0]
    assert result.status == 'passed', result.output


def test_docker_early_exit_timeout_and_orphan_cleanup():
    test = GeneratedTest(id='TEST-001', requirement_id='REQ-001', description='Call',
                         pytest_code='from submission import call\ndef test_call():\n    assert call() == 1\n')
    runner = PytestRunner()
    assert runner.run_tests([test], 'import os\nos._exit(0)\ndef call(): return 0')[0].status == 'error'
    assert runner.run_tests([test], 'def call():\n    while True: pass', timeout_sec=2)[0].status == 'timeout'
    containers = subprocess.run(['docker', 'ps', '-aq', '--filter', 'label=app=specguard-job'],
                                 check=True, capture_output=True, text=True)
    assert not containers.stdout.strip(), 'A test container was left behind'
