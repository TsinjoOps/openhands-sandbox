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
command -v nsenter >/dev/null
command -v curl >/dev/null
command -v python3 >/dev/null
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

CID="$(sudo -n docker ps -aq \
  --filter "label=com.docker.compose.project=$PROJECT" \
  --filter "label=com.docker.compose.service=opencode-review")"
test -n "$CID"
test "$(sudo -n docker inspect "$CID" --format '{{.Image}}')" = "$EXPECTED_IMAGE"

# A stopped process is not an isolation bypass. Capture only bounded,
# redacted diagnostics before cleanup. This candidate has no credentials
# or production state and cannot access the network.
if [[ "$(sudo -n docker inspect "$CID" --format '{{.State.Running}}')" != "true" ]]; then
  echo "CANDIDATE_PROCESS=EXITED"
  sudo -n docker inspect "$CID" --format 'EXIT_CODE={{.State.ExitCode}}
OOM_KILLED={{.State.OOMKilled}}
STATE_ERROR_PRESENT={{if .State.Error}}true{{else}}false{{end}}'
  echo "===== REDACTED STARTUP ERRORS (MAX 20 LINES) ====="
  sudo -n docker logs --tail 50 "$CID" 2>&1 | python3 -c '
import re, sys
rows = sys.stdin.read().splitlines()
for line in rows[-20:]:
    line = re.sub(r"(?i)(github_pat_|gh[pousr]_)[A-Za-z0-9_]+", "[REDACTED_TOKEN]", line)
    line = re.sub(r"(?i)(bearer|authorization|token|api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", line)
    line = re.sub(r"https?://[^\s]+", "[URL_REDACTED]", line)
    print(line[:240])
'
  echo "LOCAL_API_INFO=BLOCKED_PROCESS_EXITED"
  exit 1
fi

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

echo "===== LOCAL LOOPBACK API CHECK (HOST TOOL IN CANDIDATE NETWORK NS) ====="
# Image 2.2.5 has no python3 executable. Host-side curl + Python are used,
# entering ONLY the verified disposable candidate's network namespace.
# A network=none container remains offline; curl accesses 127.0.0.1 only.
# Do not print the API body, run a model, or contact external services.
PID="$(sudo -n docker inspect "$CID" --format '{{.State.Pid}}')"
[[ "$PID" =~ ^[0-9]+$ ]] && (( PID > 1 ))
test "$(sudo -n docker inspect "$CID" --format '{{.HostConfig.NetworkMode}}')" = "none"
if sudo -n nsenter --target "$PID" --net -- true; then
  echo "NET_NAMESPACE_ENTRY=PASS"
else
  echo "NET_NAMESPACE_ENTRY=BLOCKED"
  exit 1
fi
LOCAL_API_OK=0
for attempt in {1..15}; do
  if sudo -n nsenter --target "$PID" --net -- \
       curl --silent --fail --max-time 2 --noproxy '*' \
       'http://127.0.0.1:4096/api/info' | \
       python3 -c 'import json,sys; d=json.load(sys.stdin); assert isinstance(d,dict) and d.get("version")=="2.2.5"'; then
    LOCAL_API_OK=1
    break
  fi
  sleep 1
done
if (( LOCAL_API_OK )); then
  echo "LOCAL_API_INFO=PASS"
  echo "EXPECTED_VERSION=2.2.5"
else
  echo "LOCAL_API_INFO=FAIL"
  exit 1
fi

echo "NO_MODEL_CALL=YES"
echo "NO_GITHUB_CREDENTIAL=YES"
echo "GATE_10C17_RUNTIME=PASS"
