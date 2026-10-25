# SpecGuard

A React frontend and FastAPI backend for checking Python functions against written requirements, reviewing test results, and retesting suggested fixes.

## Project layout

```text
backend/
  ai/                 AI providers, test planning, prompts, and demo fixtures
  api/                API routes
  database/           SQLite persistence
  reports/            Report generation
  runner/             Local and isolated execution
  services/           Verification pipeline
  shared/             Data models
  .env.example        Backend configuration template
  requirements.txt    Locked Python dependencies
  Dockerfile.runner   Isolated runner image
  main.py             API entry point
frontend/
  public/             Static assets
  src/                React application
  package.json        Frontend dependencies and commands
  package-lock.json   Locked npm dependencies
README.md
```

## Setup

Requires **Python 3.11**, **Node.js 22**, and npm. Run commands from the repository root.

```sh
git clone https://github.com/joshuakevin612/SpecGaurd.git
cd SpecGaurd
python -m venv .venv
```

Activate the virtual environment and copy the configuration:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
Copy-Item backend/.env.example backend/.env
```

```sh
# Linux / macOS
source .venv/bin/activate
cp backend/.env.example backend/.env
```

Install dependencies:

```sh
python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

## Run

For a demo using only trusted code on your own computer, set these values in `backend/.env`:

```dotenv
SPECGUARD_RUNNER=local
SPECGUARD_BACKEND_PROVIDER=mock
```

Start the backend from the repository root with the virtual environment activated:

```sh
python -m uvicorn backend.main:app --env-file backend/.env --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```sh
npm --prefix frontend run dev
```

Open [the frontend](http://127.0.0.1:5173). Select **New verification**, then **Load cart demo**, confirm the sharing notice, and run verification. Inspect the results, review a proposed fix, and select **Retest original tests**.

The backend runs at [localhost:8000](http://127.0.0.1:8000), with API documentation at [/docs](http://127.0.0.1:8000/docs). SQLite creates `specguard.db` automatically. Keep `backend/.env` and databases out of Git.

### AI configuration

Mock mode supports the bundled demos without API keys. For arbitrary specifications, set `SPECGUARD_BACKEND_PROVIDER=nvidia` and fill in `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`, and `NVIDIA_CODE_MODEL` in `backend/.env`. Nebius is also supported by explicitly selecting `nebius` and configuring its matching variables. Restart the backend after configuration changes. Live model calls incur provider usage.

Set `SPECGUARD_AUTH_REQUIRED=true` to enable accounts and sign-in locally. Other settings are described in [backend/.env.example](backend/.env.example). Provider keys belong only in the backend configuration.

### Isolated execution

With Docker running, build the runner from the repository root:

```sh
docker build -t specguard-runner:local -f backend/Dockerfile.runner backend
```

Set `SPECGUARD_RUNNER=docker` in `backend/.env` and restart the backend. Local mode executes submissions with your account permissions; use it only for trusted code. Public hosting requires HTTPS, authentication, and a separate private worker with gVisor; the local setup above is intended for development.

### Frontend build

```sh
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

The production frontend is generated in `frontend/dist/` and uses the same-origin `/api` URL. A production web server must serve those assets and proxy `/api` to the backend. To use another API URL, set `VITE_API_URL` when building.

## Supported code

Verification supports synchronous top-level Python functions with JSON inputs and outputs. Class APIs, async functions, arbitrary third-party submission packages, and network-dependent programs are unsupported. Generated tests provide finite behavioral evidence, not formal proof.
