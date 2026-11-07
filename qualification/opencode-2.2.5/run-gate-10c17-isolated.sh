#!/usr/bin/env bash
# Gate 10C.17 — disposable runtime qualification only.
# No production mounts, GitHub tokens, providers, outbound network or published ports.
# Usage: bash run-gate-10c17-isolated.sh path/to/compose.isolated-review.yml path/to/validate-isolated-compose.py
set -euo pipefail
umask 077

COMPOSE_FILE="${1:?manifest path required}"
VALIDATOR="${2:?validator path required}"
EXPECTED_IMAGE="sha256:4accab77deb837737d073b6499147ff61ac6aae2161ebb3c1a0bc0a7b8e8c268"
EXPECTED_MANIFEST_BLOB="049e6ddff130d61fa7ec73c888e381dcac56e9bf"
EXPECTED_VALIDATOR_BLOB="a82db1d67fff7ecf3c5b342a46fffc83b859e1bb"
PROJECT="tsinjoops-gate10c17-$$"
CID=""
STARTED=0
PRE_PROD=""
PRE_OVERLAY=""

stop() {
  rc=$?
  trap - EXIT INT TERM
  if (( STARTED )); then
    echo "===== OWNED CANDIDATE CLEANUP ====="
    sudo -n docker compose --project-name "$PROJECT" \
      --profile manual-qualification-only -f "$COMPOSE_FILE" \
      down --remove-orphans --timeout 5 || { echo "CANDIDATE_CLEANUP=FAIL"; rc=1; }
    if sudo -n docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | grep -q .; then
      echo "CANDIDATE_RESIDUE=FAIL"
      rc=1
    else
      echo "CANDIDATE_RESIDUE=PASS"
    fi
  else
    echo "CANDIDATE_START=NOT_ATTEMPTED_OR_FAILED"
  fi
  now_prod="$(sudo -n docker inspect opencode-lab --format '{{.Id}}' 2>/dev/null || true)"
  now_overlay="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}' 2>/dev/null || true)"
  if [[ -n "$PRE_PROD" && "$PRE_PROD" == "$now_prod" && -n "$PRE_OVERLAY" && "$PRE_OVERLAY" == "$now_overlay" ]]; then
    echo "PRODUCTION_CONTAINER_IDS=UNCHANGED"
  else
    echo "PRODUCTION_CONTAINER_IDS=NV_OR_CHANGED"
    rc=1
  fi
  echo "GATE_10C17_EXIT_CODE=$rc"
  exit "$rc"
}
trap stop EXIT

echo "===== GATE 10C.17 PREFLIGHT ====="
test "$(git hash-object "$COMPOSE_FILE")" = "$EXPECTED_MANIFEST_BLOB"
test "$(git hash-object "$VALIDATOR")" = "$EXPECTED_VALIDATOR_BLOB"
echo "SOURCE_INTEGRITY=PASS"

# Validate the actual resolved config, including all security/credential boundaries.
sudo -n docker compose --project-name "$PROJECT" \
  --profile manual-qualification-only -f "$COMPOSE_FILE" \
  config --format json | python3 "$VALIDATOR"

image="$(sudo -n docker image inspect local/tsinjoops-opencode:2.2.5-candidate --format '{{.Id}}')"
test "$image" = "$EXPECTED_IMAGE"
echo "IMAGE_ID=PASS"

PRE_PROD="$(sudo -n docker inspect opencode-lab --format '{{.Id}}')"
PRE_OVERLAY="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}')"
test -n "$PRE_PROD"
test -n "$PRE_OVERLAY"
test -z "$(sudo -n docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")"
echo "BASELINE_CONTAINER_IDS=RECORDED"

echo "===== START OWNED CANDIDATE ONLY ====="
# No build, no image pull, and no other services in this uniquely named Compose project.
# STARTED is set before invoking up so partial creation still gets cleaned.
STARTED=1
sudo -n docker compose --project-name "$PROJECT" \
  --profile manual-qualification-only -f "$COMPOSE_FILE" \
  up -d --no-deps --no-build --pull never opencode-review

CID="$(sudo -n docker compose --project-name "$PROJECT" \
  --profile manual-qualification-only -f "$COMPOSE_FILE" ps -q opencode-review)"
test -n "$CID"
test "$(sudo -n docker inspect "$CID" --format '{{.Image}}')" = "$EXPECTED_IMAGE"

sudo -n docker inspect "$CID" --format \
  'RUNNING={{.State.Running}}
UID_GID={{.Config.User}}
ROOTFS_READONLY={{.HostConfig.ReadonlyRootfs}}
NETWORK_MODE={{.HostConfig.NetworkMode}}
PRIVILEGED={{.HostConfig.Privileged}}
CAP_DROP={{json .HostConfig.CapDrop}}
SECURITY_OPTIONS={{json .HostConfig.SecurityOpt}}
MEMORY_BYTES={{.HostConfig.Memory}}
PID_LIMIT={{.HostConfig.PidsLimit}}
PUBLISHED_PORTS={{json .HostConfig.PortBindings}}
BIND_MOUNT_COUNT={{len .Mounts}}
TMPFS_MOUNTS={{json .HostConfig.Tmpfs}}'

# Read effective facts, not only source declarations. This in-process check
# never prints Docker inspection JSON (which might contain sensitive metadata).
sudo -n docker inspect "$CID" | python3 -c '
import json, sys
data = json.load(sys.stdin)
assert len(data) == 1
o = data[0]
h = o["HostConfig"]
cfg = o["Config"]
assert o["State"]["Running"] is True, "not running"
assert cfg["User"] == "10001:10001", "uid"
assert h["ReadonlyRootfs"] is True, "rootfs"
assert h["NetworkMode"] == "none", "network"
assert h["Privileged"] is False, "privileged"
assert "ALL" in (h.get("CapDrop") or []), "capabilities"
assert "no-new-privileges:true" in (h.get("SecurityOpt") or []), "privilege escalation"
assert not o.get("Mounts"), "bind or volume mount"
assert not h.get("PortBindings"), "published port"
assert h.get("Memory") == 1073741824, "memory cap"
assert h.get("PidsLimit") == 256, "pid cap"
assert h.get("NanoCpus") == 1000000000, "cpu cap"
tmp = h.get("Tmpfs") or {}
expected = {
    "/tmp", "/workspace",
    "/home/opencode/.local/share/opencode",
    "/home/opencode/.local/state/opencode",
    "/home/opencode/.config/opencode",
    "/home/opencode/.config/gh",
    "/home/opencode/.config/git",
}
assert set(tmp) == expected, "tmpfs destinations"
for key, opts in tmp.items():
    if key != "/tmp":
        assert "uid=10001" in opts and "gid=10001" in opts, "tmpfs owner"
print("RUNTIME_ISOLATION_CORE=PASS")
'

echo "===== LOCAL LOOPBACK API CHECK (NO INFERENCE) ====="
# The image previously included Python. HTTP is local *inside* the network-disabled container.
# No cookies, tokens, credentials, GitHub calls or model requests.
sudo -n docker exec -i "$CID" python3 - <<'PY'
import json
import time
from urllib.request import urlopen

for attempt in range(15):
    try:
        with urlopen("http://127.0.0.1:4096/api/info", timeout=2) as response:
            payload = json.load(response)
            if response.status != 200:
                raise RuntimeError("HTTP status")
            # Do not log the payload: only the expected version and status.
            if not isinstance(payload, dict) or payload.get("version") != "2.2.5":
                raise RuntimeError("unexpected version")
            print("LOCAL_API_INFO=PASS")
            print("EXPECTED_VERSION=2.2.5")
            break
    except Exception:
        if attempt == 14:
            print("LOCAL_API_INFO=FAIL")
            raise
        time.sleep(1)
PY

echo "NO_MODEL_CALL=YES"
echo "NO_GITHUB_CREDENTIAL=YES"
echo "GATE_10C17_RUNTIME=PASS"
