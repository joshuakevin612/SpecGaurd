#!/usr/bin/env bash
# Activate an already unpacked/tested release, or roll back to a previous one.
set -euo pipefail
release_id="${1:?Usage: activate.sh RELEASE_ID}"
[[ "$release_id" =~ ^[a-f0-9]{16}$ ]] || { echo 'Invalid release ID' >&2; exit 1; }
release_dir="/opt/specguard/releases/$release_id"
[[ -d "$release_dir" && -f "$release_dir/manifest.json" && -x "$release_dir/.venv/bin/python" ]] || exit 1
"$release_dir/.venv/bin/python" - "$release_dir" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
for name,digest in json.loads((root/'manifest.json').read_text()).items():
    path=(root/name).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise SystemExit('Release manifest mismatch')
PY
previous="$(readlink -f /opt/specguard/current || true)"
systemctl stop specguard-api specguard-worker
ln -s "$release_dir" /opt/specguard/next
mv -Tf /opt/specguard/next /opt/specguard/current
systemctl start specguard-worker specguard-api
healthy=false
for attempt in {1..15}; do
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then healthy=true; break; fi
    sleep 1
done
if [[ "$healthy" != true ]]; then
    if [[ "$previous" == /opt/specguard/releases/* && -d "$previous" ]]; then
        systemctl stop specguard-api specguard-worker
        ln -s "$previous" /opt/specguard/rollback
        mv -Tf /opt/specguard/rollback /opt/specguard/current
        systemctl start specguard-worker specguard-api
    fi
    echo 'Activation failed; prior release restored when available. Inspect journalctl.' >&2
    exit 1
fi
echo 'Liveness passed. Run the authenticated readiness and end-to-end smoke gate before opening signup.'
