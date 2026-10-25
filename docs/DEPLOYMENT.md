# Deploying SpecGuard on one Linux server

This runbook describes public deployment behind HTTPS. Replace configuration
placeholders and complete the server-specific gates before opening signup.

## Architecture and supported contract

```text
Browser -> Caddy :443 -> public API 127.0.0.1:8000 (specguard-api OS user)
                              |-> SQLite /var/lib/specguard
                              |-> NVIDIA/Nebius (provider credentials)
                              `-> private worker 127.0.0.1:8001 (specguard-worker OS user)
                                          `-> Docker + gVisor runsc jobs
```

Only the worker account belongs to the Docker group. The API account must have
no Docker socket access; worker configuration must have no model-provider keys.
The shared worker credential belongs to these two local services only. Neither
upstream port is exposed publicly. Browser authentication uses random opaque
sessions in HttpOnly/Secure/SameSite=Strict cookies and per-session CSRF values.
Passwords use salted scrypt (N=32768, r=8, p=3); recovery codes are single-use and
hashed. Signup, login, mutations and verification attempts have durable quotas.

The runner supports synchronous top-level Python functions with JSON arguments
and JSON return values, plus the documented exception types. It parses a limited
deterministic test language without executing test source. Expected answers stay
in the supervisor, outside the submission container. Incomplete observations,
early exits and unsupported plans are errors. Generated cases are finite evidence,
not formal proof or an attestation that deliberately hostile code followed a
particular internal execution path. No network-dependent programs, class APIs,
async functions, arbitrary fixtures or third-party submission packages are supported.

## Build and verify on a development/CI machine

Use Python 3.11 and Node 22. Install the checked-in environments:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
npm --prefix frontend ci
.venv/Scripts/python.exe scripts/check.py
.venv/Scripts/python.exe scripts/security_scan.py
npm --prefix frontend audit --audit-level=high --include=dev
docker build -t specguard-runner:local -f backend/runner/Dockerfile .
$env:SPECGUARD_DOCKER_TESTS='1'
.venv/Scripts/python.exe -m pytest tests/test_docker_runner.py -q
.venv/Scripts/python.exe scripts/package_release.py
```

On Linux use `.venv/bin/python` and `SPECGUARD_DOCKER_TESTS=1 python ...`.
The package command creates an allowlisted archive, its checksum, and a per-file
manifest in `artifacts/releases/`. It excludes `.env`, databases, local artifacts,
dependencies, Git metadata, and caches. Do not upload the workspace wholesale.
The release ID is a content hash, independent of whether the folder has Git metadata.

The GitHub workflow uses pinned official actions and runs the same check command,
advisory/secret-pattern gates and actual Docker tests. Require `verify` on pull requests before enabling merge.
Enable repository secret scanning and review in GitHub settings.

## Host prerequisites

- A supported, patched Linux system on an architecture supported by gVisor.
- Docker Engine, gVisor `runsc`, Python 3.11/venv, Caddy, age, curl, and systemd.
- DNS for the chosen domain and inbound TCP 80/443; restrict SSH to operator
  access. Keep 8000, 8001 and the Docker daemon off the public network.
- Encrypted persistent storage, backups copied to a separate failure domain, and
  an operator/support address published to users. Provision capacity from measured
  load; public signup defaults to a maximum of 500 accounts and 100 jobs/day.

Install gVisor using its [official installation instructions](https://gvisor.dev/docs/user_guide/install/)
and [Docker integration](https://gvisor.dev/docs/user_guide/quick_start/docker/).
Install it as `runsc`; do not weaken the runtime requirement to get a public
deployment past readiness. Review its production guidance and syscall compatibility.

Create separate system users and directories (run once as an operator):

```bash
sudo groupadd --system specguard-release
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid specguard-release specguard-api
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid specguard-release specguard-worker
sudo usermod -aG docker specguard-worker
sudo install -d -m 0755 /opt/specguard/releases /etc/specguard
sudo install -d -m 0700 -o specguard-api -g specguard-release /var/lib/specguard
sudo install -d -m 0700 -o specguard-worker -g specguard-release /var/lib/specguard-worker/jobs
sudo install -d -m 0700 /var/backups/specguard
```

Do not rerun account creation blindly if those users/groups already exist.
Keep release files root-owned and readable/executable by the service users and
Caddy. The database and usage log belong only to the API account.

## Prepare a release

Transfer the archive and checksum. Verify `sha256sum -c`, unpack it into
`/opt/specguard/releases/RELEASE_ID`, and create that release's virtual environment:

```bash
cd /opt/specguard/releases/RELEASE_ID
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip uninstall --yes pip setuptools wheel
```

Build the runner from the pinned Dockerfile on the chosen architecture. Push it
to your controlled registry and set the worker image to its immutable digest;
alternatively load a prebuilt image and use its immutable image ID. The API and
worker are promoted from the same release archive; do not rebuild the frontend
per environment. The production frontend uses the same-origin `/api` prefix.

Copy `deploy/api.env.example` to `/etc/specguard/api.env` and
`deploy/worker.env.example` to `/etc/specguard/worker.env`. Replace the domain,
provider key, shared worker token and runner image. Generate the worker token
with `python3 -c "import secrets; print(secrets.token_hex(32))"` and store it only
in those environment files. Set their owner to root and mode to 0600; systemd
reads them before dropping privileges. Never add them to the archive or Git.

Set `SPECGUARD_SIGNUP_ENABLED=false` until the smoke checks pass. Choose the actual
per-user and global daily job limits based on provider pricing and your budget;
the application has an aggregate call/token bound, not a currency billing engine.
Set a provider-side account spending limit too. Configured model names must be
available to your provider account; run the reviewed live smoke before opening.

Copy the API, worker, backup service and backup timer files to `/etc/systemd/system/`.
Set `SPECGUARD_DOMAIN=your.domain` in Caddy's service environment, install
`deploy/Caddyfile` as its configuration, and run `caddy validate` before reload.
The file provides TLS, same-origin API routing, security headers and asset caching.
An additional CDN/proxy requires an explicit trusted-forwarding review.

Create the first `current` symlink to the release, reload systemd and start the
services. Subsequent releases use `deploy/activate.sh RELEASE_ID`, which verifies
the manifest, switches the release and restores the previous symlink on failed
liveness. Startup fails on unsafe production settings; worker readiness fails
when Docker, the image or required sandbox runtime is unavailable.

## Deployment smoke and opening signup

1. Confirm only Caddy and SSH are listening publicly; verify the API user cannot
   access Docker and cannot read the worker's job directory.
2. With the production runtime configured, run the Docker test suite on the host:
   install dev locks into a separate verification environment and run
   `SPECGUARD_DOCKER_RUNTIME=runsc SPECGUARD_DOCKER_TESTS=1 python -m pytest tests/test_docker_runner.py -q`
   from the full reviewed source checkout. Do not add dev packages to the running
   API environment. CI's ordinary Docker tests do not replace this gVisor gate.
3. Run the API account tests over HTTPS: sign up a controlled test account during
   the maintenance window, save its recovery code, sign out/in, and attempt
   cross-account reads/retests. Temporarily enable signup for this check, then
   close it again until verification is complete.
4. Run authenticated readiness with a controlled account. Set
   `SPECGUARD_SMOKE_URL=https://your.domain/api`, `SPECGUARD_SMOKE_USER`, and
   `SPECGUARD_SMOKE_PASSWORD`; run `python scripts/smoke.py`. Keep credentials out
   of shell history by setting them interactively or through your secret tooling.
5. Run a reviewed bad demo with the live provider, inspect failures, retest the
   reviewed good code against the original cases and inspect the stored report.
   This incurs bounded provider usage. Verify errors, limits, deletion and refresh.
6. Rehearse rollback and backup restore as below, configure external uptime and
   error alerts, publish support/privacy/retention details, then enable signup.

## Rollback and schema compatibility

Keep at least two verified releases. From the current release run:
`sudo bash deploy/activate.sh PREVIOUS_RELEASE_ID`. Confirm authenticated readiness
and one representative workflow. Current schema changes are expand-only and keep
pre-account projects owned by `local`; they never become public user data. Future
schema changes must remain compatible with the previous application during rollback.
Never restore an old database automatically during an application rollback.

No actual Linux activation/rollback has been executed in this Windows workspace.
The scripts are prepared and syntax-checked; their systemd/TLS/gVisor integration
must be rehearsed on the future host before opening the service.

## Backups, restore and deletion

`scripts/database.py backup SOURCE NEW_DESTINATION` uses SQLite's online backup
API and verifies integrity. `restore` creates a new file and refuses to overwrite
an existing destination. Automated tests exercise both and the no-overwrite guard.

Create an age key pair in your secure operations environment; keep the private
identity off the application host. Put the public recipient into
`/etc/specguard/backup.env` as `SPECGUARD_BACKUP_RECIPIENT=age1...`. Install age,
enable `specguard-backup.timer`, and monitor its result. The job takes an encrypted
daily copy and expires local encrypted backups after 30 days. Copy verified
encrypted backups off-server and apply the same retention policy there; a local
backup alone does not protect against host loss. A terminated backup may leave a
root-only plaintext temp file; inspect that directory after backup failures.

For a restore rehearsal, decrypt a copy using the off-host age identity, then run
the restore command into a new database file and check representative accounts,
projects and reports. To restore production, close signup, stop the API, retain
the damaged database for recovery, place the verified restored copy at the configured
path with API ownership/mode 0600, and restart. Force sign-in again after restoring:
delete restored sessions using a controlled maintenance transaction. Replay all
account/project deletion requests received since the backup before opening access.
Do not assume data deleted from active storage vanished from older backups.

## Monitoring and incident response

Initial objective: 99.5% monthly availability for authenticated reads and at least
95% of accepted verifications ending within 150 seconds. Busy rejections are tracked
separately; provider-quality success is not the same as HTTP availability.

- Configure an external probe for `https://your.domain/api/health` every minute;
  alert after three consecutive failures. Use a controlled account to monitor
  `/ready` and alert on worker/storage failures. Liveness alone is insufficient.
- Collect Caddy JSON access logs, API JSON request metadata (request ID, status,
  duration), run IDs/status and usage metadata. Never log credentials or source.
- Alert on elevated 5xx, long verification times, sustained 409/429, resource
  saturation, disk usage above 80%, backup failures, and provider spending limits.
- Publish a support contact and assign an operator before opening signup. On an
  incident close signup, preserve logs, inspect `journalctl -u specguard-api -u
  specguard-worker`, check `/ready`, Docker/gVisor and provider health, then roll
  back or restore only with the corresponding recovery steps. Record the cause
  and add a regression test after recovery.
