"""
Test runner: executes generated tests against submitted code.

Supports both local (for dev) and Docker (for production) execution.
"""

import os
import sys
import tempfile
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from shared_schemas import GeneratedTest, TestResult


class PytestRunner:
    """Runs generated tests locally or in Docker."""

    def __init__(self, use_docker: bool = False, docker_image: str = "python:3.11-slim"):
        """
        Initialize the test runner.
        
        Args:
            use_docker: If True, run tests in Docker. If False, run locally.
            docker_image: Docker image to use for execution.
        """
        self.use_docker = use_docker
        self.docker_image = docker_image

    def run_tests(
        self,
        tests: List[GeneratedTest],
        code: str,
        timeout_sec: int = 30,
        retry_count: int = 2,
    ) -> List[TestResult]:
        """
        Run a list of generated tests against the provided code.
        
        Args:
            tests: List of GeneratedTest objects
            code: Source code to test against
            timeout_sec: Timeout per test execution
            retry_count: Number of retries to detect flakiness
        
        Returns:
            List of TestResult objects
        """
        results = []

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write the code to a file in the temporary directory
            code_file = Path(tmpdir) / "implementation.py"
            code_file.write_text(code)

            # Write each test to a file
            test_files = {}
            for test in tests:
                test_file = Path(tmpdir) / f"test_{test.id}.py"
                test_file.write_text(test.pytest_code)
                test_files[test.id] = test_file

            # Run each test
            for test in tests:
                result = self._run_single_test(
                    test,
                    tmpdir,
                    timeout_sec=timeout_sec,
                    retry_count=retry_count,
                )
                results.append(result)

        return results

    def _run_single_test(
        self,
        test: GeneratedTest,
        tmpdir: str,
        timeout_sec: int = 30,
        retry_count: int = 2,
    ) -> TestResult:
        """
        Run a single test, optionally retrying to detect flakiness.
        
        Args:
            test: The test to run
            tmpdir: Temporary directory with code and test files
            timeout_sec: Execution timeout
            retry_count: Number of retries
        
        Returns:
            TestResult with status and output
        """
        outcomes = []

        for attempt in range(retry_count + 1):
            start_time = time.time()
            
            if self.use_docker:
                outcome = self._run_in_docker(test, tmpdir, timeout_sec)
            else:
                outcome = self._run_locally(test, tmpdir, timeout_sec)
            
            duration_ms = int((time.time() - start_time) * 1000)
            outcomes.append((outcome, duration_ms))

        # Analyze outcomes for flakiness
        status, output, duration_ms = self._determine_status(outcomes)

        return TestResult(
            test_id=test.id,
            requirement_id=test.requirement_id,
            status=status,
            output=output,
            duration_ms=duration_ms,
        )

    def _run_locally(self, test: GeneratedTest, tmpdir: str, timeout_sec: int) -> Dict[str, Any]:
        """
        Run test locally (no Docker).
        
        Returns:
            Dict with 'status' and 'output' keys
        """
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", f"test_{test.id}.py", "-v"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )

            if result.returncode == 0:
                return {"status": "passed", "output": result.stdout}
            else:
                return {"status": "failed", "output": result.stdout + "\n" + result.stderr}

        except subprocess.TimeoutExpired:
            return {"status": "timeout", "output": f"Test timed out after {timeout_sec}s"}
        except Exception as e:
            return {"status": "error", "output": f"Execution error: {str(e)}"}

    def _run_in_docker(self, test: GeneratedTest, tmpdir: str, timeout_sec: int) -> Dict[str, Any]:
        """
        Run test in Docker sandbox.
        
        Returns:
            Dict with 'status' and 'output' keys
        """
        try:
            # Build the docker run command
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--network", "none",  # Disable network
                "--memory", "256m",  # Memory limit
                "--cpus", "1.0",  # CPU limit
                "--timeout", str(timeout_sec),
                "-v", f"{tmpdir}:/work",
                "-w", "/work",
                self.docker_image,
                "python", "-m", "pytest", f"test_{test.id}.py", "-v",
            ]

            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec + 5,  # Give docker some extra time
            )

            if result.returncode == 0:
                return {"status": "passed", "output": result.stdout}
            else:
                return {"status": "failed", "output": result.stdout + "\n" + result.stderr}

        except subprocess.TimeoutExpired:
            return {"status": "timeout", "output": f"Test timed out after {timeout_sec}s"}
        except Exception as e:
            return {"status": "error", "output": f"Docker execution error: {str(e)}"}

    def _determine_status(self, outcomes: List[tuple]) -> tuple:
        """
        Analyze outcomes from multiple runs to determine final status.
        
        If results are inconsistent, mark as "flaky".
        
        Returns:
            Tuple of (status, output, duration_ms)
        """
        statuses = [outcome[0]["status"] for outcome in outcomes]
        output = outcomes[-1][0]["output"]  # Last output
        duration_ms = int(sum(outcome[1] for outcome in outcomes) / len(outcomes))

        # Check for flakiness
        if len(set(statuses)) > 1:
            return "flaky", f"Inconsistent results: {statuses}\n{output}", duration_ms

        # All same status
        final_status = statuses[0]
        return final_status, output, duration_ms
