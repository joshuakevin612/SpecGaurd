"""API-to-worker boundary. The public API has no Docker daemon privileges."""
import os
import time

import httpx

from shared.schemas import TestResult


class RemoteRunner:
    use_docker = True

    def __init__(self):
        self.url = os.environ['SPECGUARD_WORKER_URL'].rstrip('/')

    def _headers(self):
        return {'Authorization': 'Bearer ' + os.environ['SPECGUARD_WORKER_TOKEN']}

    def ready(self):
        response = httpx.get(self.url + '/ready', headers=self._headers(), timeout=5, trust_env=False)
        response.raise_for_status()

    def run_tests(self, tests, code, deadline=None):
        remaining = min(120, (deadline - time.monotonic()) if deadline else 120)
        if remaining <= 0:
            return [TestResult(test_id=t.id, requirement_id=t.requirement_id, status='timeout',
                               output='Run time budget exhausted', duration_ms=0) for t in tests]
        try:
            response = httpx.post(self.url + '/run', headers=self._headers(), timeout=remaining + 10,
                                  trust_env=False,
                                  json={'tests': [t.model_dump() for t in tests], 'code': code,
                                        'seconds': remaining})
            response.raise_for_status()
            values = response.json()['results']
            return [TestResult.model_validate(x) for x in values]
        except (httpx.HTTPError, ValueError, KeyError):
            return [TestResult(test_id=t.id, requirement_id=t.requirement_id, status='error',
                               output='Execution worker unavailable or returned invalid evidence',
                               duration_ms=0) for t in tests]
