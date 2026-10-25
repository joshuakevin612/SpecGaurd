# SpecGuard

SpecGuard checks Python functions against written requirements. It combines a React workbench, a FastAPI API, NVIDIA/Nebius model integration, deterministic demo fixtures, SQLite persistence, and an isolated execution worker.

Create a project, generate test cases, inspect requirement-level results, review proposed fixes, and retest against the original cases. Accounts, private projects, JSON/HTML reports, execution limits, and production deployment configuration are included.

Generated tests provide finite behavioral evidence, not formal proof. Supported submissions are synchronous top-level Python functions with JSON inputs and outputs; arbitrary dependencies, async functions, and class APIs are unsupported.

## Requirements

- Python 3.11 (the CI-tested version)
- Node.js 22 and npm
- Docker for isolated execution; the local demo below can run without Docker

## Setup

```sh
git clone https://github.com/joshuakevin612/SpecGaurd.git
cd SpecGaurd
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# Linux / macOS
source .venv/bin/activate
```

Install the locked dependencies and create your local configuration:

```sh
python -m pip install -r requirements.txt
npm --prefix frontend ci
```

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```sh
# Linux / macOS
cp .env.example .env
```

Keep `.env` private. Mock mode needs no provider credentials.

## Run locally

For a trusted local demo, start the API in your activated environment:

```powershell
# Windows PowerShell
$env:SPECGUARD_RUNNER = 'local'
$env:SPECGUARD_BACKEND_PROVIDER = 'mock'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```sh
# Linux / macOS
SPECGUARD_RUNNER=local SPECGUARD_BACKEND_PROVIDER=mock python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend:

```sh
npm --prefix frontend run dev
```

Open [the workbench](http://127.0.0.1:5173). Use **New verification**, then **Load cart demo**, confirm the sharing notice, and run verification. Review a proposed fix and select **Retest original tests**. The API is available at [localhost:8000](http://127.0.0.1:8000); development API documentation is at [/docs](http://127.0.0.1:8000/docs).

Mock mode supports the bundled demo specifications only. Projects and reports persist in `specguard.db`, created automatically. Local execution runs submitted code with your account permissions: use it only for trusted code and keep the service bound to localhost.

### Live AI and accounts

For arbitrary specifications, configure `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`, and `NVIDIA_CODE_MODEL` in `.env`, then set `SPECGUARD_BACKEND_PROVIDER=nvidia` before starting the API. Nebius is available by explicitly selecting `nebius` and configuring its matching variables. Providers never fall back to each other; live calls incur provider usage.

Set `SPECGUARD_AUTH_REQUIRED=true` before startup to enable the local account/sign-in flow. See [.env.example](.env.example) for configurable quotas, origins, and database settings. Never put provider keys or worker credentials in frontend `VITE_` variables.

### Docker runner

Docker is the default runner. With Docker running, build its image:

```sh
docker build -t specguard-runner:local -f backend/runner/Dockerfile .
```

Start the API with `SPECGUARD_RUNNER=docker`. The runner disables networking, applies resource/time limits, and uses a nonroot user with a read-only root filesystem. Expected answers stay outside the submission container.

## Checks

In the activated environment:

```sh
python -m pip install -r requirements-dev.txt
python scripts/check.py
```

This runs Python linting/tests, dependency consistency, frontend type checking, and the production build. Standard tests use temporary databases and mock providers; Docker integration tests are opt-in with `SPECGUARD_DOCKER_TESTS=1`.

## Production setup

Follow [the deployment runbook](docs/DEPLOYMENT.md) for HTTPS, separate API/worker accounts, the private authenticated worker, Docker/gVisor, service configuration, backups, and rollback. Public deployment requires these controls and live provider configuration.

After checks and the frontend build, `python scripts/package_release.py` creates a deployment archive and checksums in ignored `artifacts/releases/`.

## Source layout

| Path | Purpose |
| --- | --- |
| `frontend/` | React/TypeScript workbench and Vite build |
| `backend/` | API, accounts, persistence, reports, and execution worker |
| `specguard_ai/` | Model providers, test planning, validation, and repairs |
| `shared/` | Shared data models |
| `configs/`, `demos/` | Provider presets and runnable demo fixtures |
| `deploy/`, `scripts/` | Deployment configuration and operational tools |
| `tests/`, `.github/` | Regression tests and automated checks |

Dependencies, secrets, databases, generated reports, build output, and local tooling are excluded from Git.
