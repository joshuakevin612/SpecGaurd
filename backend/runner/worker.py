"""Private worker service. Run as a different OS user from the public API."""
import asyncio
import hmac
import json
import os
import subprocess
import time
from threading import BoundedSemaphore

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from backend.runner.pytest_runner import PytestRunner
from backend.shared.schemas import GeneratedTest

inner = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
slot = BoundedSemaphore(1)


class WorkerBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        token = os.getenv('SPECGUARD_WORKER_TOKEN', '')
        if len(token) < 32 or not hmac.compare_digest(
            headers.get(b'authorization', b''), ('Bearer ' + token).encode()
        ):
            return await JSONResponse({'detail': 'Unauthorized worker request'}, status_code=401)(scope, receive, send)
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    msg = await receive()
                    if msg['type'] == 'http.disconnect':
                        return
                    body.extend(msg.get('body', b''))
                    if len(body) > 512 * 1024:
                        return await JSONResponse({'detail': 'Worker input too large'}, status_code=413)(scope, receive, send)
                    if not msg.get('more_body'):
                        break
        except TimeoutError:
            return await JSONResponse({'detail': 'Upload timeout'}, status_code=408)(scope, receive, send)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {'type': 'http.request', 'body': bytes(body)}
            return await receive()
        return await self.app(scope, replay, send)


def runner():
    if os.getenv('SPECGUARD_ENV') == 'production' and os.getenv('SPECGUARD_DOCKER_RUNTIME') != 'runsc':
        raise HTTPException(503, 'Production requires the configured gVisor sandbox runtime')
    return PytestRunner(use_docker=True, docker_image=os.getenv('SPECGUARD_RUNNER_IMAGE', 'specguard-runner:local'))


class Job(BaseModel):
    code: str = Field(min_length=1, max_length=60000)
    tests: list[GeneratedTest] = Field(min_length=1, max_length=32)
    seconds: float = Field(gt=0, le=120)


@inner.get('/ready')
def ready():
    current = runner()
    try:
        subprocess.run(['docker', 'image', 'inspect', current.docker_image],
                       timeout=5, check=True, capture_output=True)
        info = subprocess.run(['docker', 'info', '--format', '{{json .Runtimes}}'],
                              timeout=5, check=True, capture_output=True, text=True)
        if current.runtime and current.runtime not in json.loads(info.stdout):
            raise ValueError('Required sandbox runtime missing')
    except (OSError, subprocess.SubprocessError, ValueError):
        raise HTTPException(503, 'Worker runner is unavailable') from None
    return {'status': 'ready'}


@inner.post('/run')
def run(job: Job, request: Request):
    if not slot.acquire(blocking=False):
        raise HTTPException(409, 'Execution worker is busy')
    try:
        results = runner().run_tests(job.tests, job.code, deadline=time.monotonic() + job.seconds)
        return {'results': [r.model_dump() for r in results]}
    finally:
        slot.release()


app = WorkerBoundary(inner)
