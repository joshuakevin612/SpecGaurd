"""
SpecGuard Backend - FastAPI Application

Main entry point for the backend API.
"""

import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend.api.routes import router
from backend.auth import production
from backend.auth import router as auth_router
from backend.observability import RequestLog
from backend.security import SecurityBoundary, allowed_origins


def validate_config():
    if not production():
        return
    if os.getenv('SPECGUARD_RUNNER', 'docker') != 'docker':
        raise RuntimeError('Production requires the Docker runner')
    worker = urlsplit(os.getenv('SPECGUARD_WORKER_URL', ''))
    if (worker.scheme != 'http' or worker.hostname != '127.0.0.1' or worker.username
            or not worker.port or worker.query or worker.fragment or worker.path not in {'', '/'}
            or len(os.getenv('SPECGUARD_WORKER_TOKEN', '')) < 32):
        raise RuntimeError('Production requires an authenticated private execution worker')
    hosts = os.getenv('SPECGUARD_ALLOWED_HOSTS', '')
    origins = os.getenv('SPECGUARD_CORS_ORIGINS', '')
    if not hosts or '*' in hosts or not origins or any(
        not x.strip().startswith('https://') for x in origins.split(',')
    ):
        raise RuntimeError('Production requires explicit hosts and HTTPS browser origins')
    if not os.path.isabs(os.getenv('SPECGUARD_DB', '')):
        raise RuntimeError('Production requires an absolute durable database path')
    provider = os.getenv('SPECGUARD_BACKEND_PROVIDER', 'mock')
    if provider not in {'nvidia', 'nebius'}:
        raise RuntimeError('Public production requires a live backend provider')
    prefix = provider.upper()
    if (not os.getenv(prefix + '_API_KEY')
            or not os.getenv(prefix + '_BASE_URL', '').startswith('https://')
            or not os.getenv(prefix + '_MODEL')):
        raise RuntimeError('Configure the selected live provider credentials, HTTPS endpoint and model')


@asynccontextmanager
async def lifespan(app):
    validate_config()
    yield

# Create FastAPI app
app = FastAPI(
    title="SpecGuard",
    description="AI-powered software verification system",
    version="0.2.0",
    lifespan=lifespan,
    docs_url=None if production() else '/docs',
    redoc_url=None if production() else '/redoc',
)

# Origins are checked by the boundary as well as by CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins()),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-SpecGuard-Client"],
)
app.add_middleware(SecurityBoundary)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[host.strip() for host in os.getenv(
        "SPECGUARD_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1],testserver"
    ).split(",") if host.strip()],
)

# Include routes
app.include_router(router)
app.include_router(auth_router)
app.add_middleware(RequestLog)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
