"""Execute each generated test in an isolated directory, with bounded retries."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from backend.shared.schemas import GeneratedTest, TestResult

from .cases import extract, matches


class PytestRunner:
    def __init__(self, use_docker=True, docker_image="specguard-runner:local"):
        self.use_docker = use_docker
        self.docker_image = docker_image
        self.runtime = os.getenv('SPECGUARD_DOCKER_RUNTIME', '')

    def run_tests(self, tests: list[GeneratedTest], code: str,
                  timeout_sec: int = 30, retry_count: int = 0,
                  deadline: float | None = None) -> list[TestResult]:
        if len(tests) > 128 or not 0 < timeout_sec <= 30 or not 0 <= retry_count <= 2:
            raise ValueError("Runner limits exceeded")
        results = []
        run_started = time.monotonic()
        deadline = min(deadline or float('inf'), run_started + 120)
        for test in tests:
            outcomes = []
            try:
                cases = extract(test.pytest_code)
            except (ValueError, SyntaxError, TypeError, RecursionError, KeyError):
                results.append(TestResult(test_id=test.id, requirement_id=test.requirement_id,
                                          status='error', output='Unsupported test plan; no source executed',
                                          duration_ms=0))
                continue
            for _ in range(retry_count + 1):
                start = time.monotonic()
                if start >= deadline:
                    outcomes.append(({'status': 'timeout', 'output': 'Verification time budget exceeded'}, 0))
                    break
                # IDs never become filesystem paths; every attempt starts clean.
                with tempfile.TemporaryDirectory(prefix='specguard-') as tmpdir:
                    root = Path(tmpdir)
                    (root / 'submission.py').write_text(code, encoding='utf-8')
                    (root / 'invoke.py').write_bytes(Path(__file__).with_name('invoke.py').read_bytes())
                    (root / 'inputs.json').write_text(json.dumps([
                        {'function': c.function, 'args': c.args, 'kwargs': c.kwargs}
                        for c in cases]), encoding='utf-8')
                    if self.use_docker:
                        # The worker service has a private umask; the nonroot
                        # container still needs read permission on this mount.
                        root.chmod(0o755)
                        for child in root.iterdir():
                            child.chmod(0o444)
                    outcome = self._execute(tmpdir, min(timeout_sec, deadline - start), cases)
                outcomes.append((outcome, int((time.monotonic() - start) * 1000)))
            statuses = {item[0]['status'] for item in outcomes}
            results.append(TestResult(
                test_id=test.id, requirement_id=test.requirement_id,
                status=next(iter(statuses)) if len(statuses) == 1 else 'flaky',
                output=outcomes[-1][0]['output'],
                duration_ms=sum(item[1] for item in outcomes) // len(outcomes)))
        return results

    def _execute(self, tmpdir, timeout_sec, cases):
        name = f'specguard-{uuid.uuid4().hex}'
        args = ['python', '-I', '-B', 'invoke.py']
        if self.use_docker:
            command = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
                       '--label', 'app=specguard-job',
                       '--memory', '256m', '--cpus', '1', '--pids-limit', '64',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                       '--read-only', '--log-driver', 'none',
                       '--ulimit', 'nofile=128:128', '--ulimit', 'fsize=1048576:1048576',
                       '--tmpfs', '/tmp:rw,nosuid,size=64m',
                       '-e', 'PYTHONDONTWRITEBYTECODE=1',
                       '-e', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
                       '-v', f'{tmpdir}:/work:ro', '-w', '/work', self.docker_image, *args]
            if self.runtime:
                command[2:2] = ['--runtime', self.runtime]
        else:
            command = [sys.executable, *args[1:]]
        env = ({**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
               if self.use_docker else
               {key: value for key, value in os.environ.items()
                if key.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH'}})
        env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        try:
            # Read incrementally: capture_output previously buffered unbounded child output.
            process = subprocess.Popen(command, cwd=tmpdir, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=env,
                                       start_new_session=os.name != 'nt')
            chunks = bytearray()
            errors = bytearray()
            overflow = threading.Event()

            def read_output(stream, target):
                total = 0
                while stream is not None:
                    block = stream.read(4096)
                    if not block:
                        break
                    total += len(block)
                    target.extend(block)
                    del target[:-60000]
                    if total > 1024 * 1024:
                        overflow.set()
                        process.kill()
                        break

            reader = threading.Thread(target=read_output, args=(process.stdout, chunks), daemon=True)
            err_reader = threading.Thread(target=read_output, args=(process.stderr, errors), daemon=True)
            reader.start()
            err_reader.start()
            try:
                returncode = process.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise
            finally:
                reader.join(timeout=1)
                err_reader.join(timeout=1)
            output = bytes(chunks).decode('utf-8', errors='replace')
            if overflow.is_set():
                return {'status': 'error', 'output': 'Test exceeded the 1 MB output limit'}
            if returncode != 0:
                return {'status': 'error', 'output': 'Submission process did not complete normally'}
            try:
                observations = json.loads(output)
                if not isinstance(observations, list) or len(observations) != len(cases):
                    raise ValueError('Incomplete evidence')
                failures = []
                for i, (case, observed) in enumerate(zip(cases, observations, strict=True), 1):
                    if not isinstance(observed, dict):
                        raise ValueError('Invalid observation')
                    if observed.get('kind') == 'raise' and set(observed) == {'kind', 'type'}:
                        passed = case.exception == observed['type']
                    elif observed.get('kind') == 'return' and set(observed) == {'kind', 'value'}:
                        passed = case.exception is None and matches(
                            observed['value'], case.expected, case.approximate)
                    elif observed == {'kind': 'invalid'}:
                        passed = False
                    else:
                        raise ValueError('Invalid observation')
                    if not passed:
                        failures.append(f'Case {i}: observed {str(observed)[:500]}; expected '
                                        f'{case.exception or repr(case.expected)[:500]}')
                return {'status': 'failed' if failures else 'passed',
                        'output': '\n'.join(failures) or f'{len(cases)} cases passed supervisor comparisons'}
            except (ValueError, TypeError, RecursionError):
                return {'status': 'error', 'output': 'Missing, invalid or incomplete execution evidence'}
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'output': f'Test timed out after {timeout_sec}s'}
        except OSError as exc:
            return {'status': 'error', 'output': str(exc)}
        finally:
            if self.use_docker:
                try:
                    subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
