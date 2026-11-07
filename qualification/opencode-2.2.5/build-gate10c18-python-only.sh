#!/usr/bin/env bash
# Gate 10C.18i - bounded, disposable Python-bridge image build; NO CREDENTIALS.
# Run as a CHILD bash process with two exact Git-blob-verified files.
# This builds ONE extra local image. It does NOT connect MCP or a model.
set -euo pipefail
umask 077

test "$#" -eq 2 || { echo "USAGE: bash runner Dockerfile guard.py"; exit 2; }
DOCKERFILE="$1"
GUARD="$2"
BASE="local/tsinjoops-opencode:2.2.5-candidate"
BASE_ID="sha256:4accab77deb837737d073b6499147ff61ac6aae2161ebb3c1a0bc0a7b8e8c268"
TAG="local/tsinjoops-opencode:2.2.5-10c18-python-20261107"
DOCKERFILE_BLOB="6eda73737494db55f8c81d636e4b9b9b940e785b"
GUARD_BLOB="c3c6fe2c853ef2ce0b9bbb5e9d3caa8f72e245c2"
NAME="tsinjoops-10c18-python-probe-$$"
BUILD_ATTEMPTED=0
KEEP_IMAGE=0
BASE_PROD=""
BASE_OVERLAY=""
STAGE=""

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [[ -n "$STAGE" ]]; then rm -rf -- "$STAGE"; fi
  sudo -n docker rm -f "$NAME" >/dev/null 2>&1 || true
  if (( BUILD_ATTEMPTED && ! KEEP_IMAGE )); then
    sudo -n docker image rm "$TAG" >/dev/null 2>&1 || true
    if sudo -n docker image inspect "$TAG" >/dev/null 2>&1; then
      echo "DERIVED_TAG_CLEANUP=FAIL"
      rc=1
    else
      echo "DERIVED_TAG_CLEANUP=PASS"
    fi
  fi
  local prod overlay
  prod="$(sudo -n docker inspect opencode-lab --format '{{.Id}}' 2>/dev/null || true)"
  overlay="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}' 2>/dev/null || true)"
  if [[ -n "$BASE_PROD" && "$BASE_PROD" == "$prod" &&
        -n "$BASE_OVERLAY" && "$BASE_OVERLAY" == "$overlay" ]]; then
    echo "PRODUCTION_CONTAINER_IDS=UNCHANGED"
  else
    echo "PRODUCTION_CONTAINER_IDS=NV_OR_CHANGED"
    rc=1
  fi
  echo "GATE_10C18I_EXIT_CODE=$rc"
  exit "$rc"
}
trap cleanup EXIT

command -v git >/dev/null
command -v timeout >/dev/null
command -v sudo >/dev/null
test -f "$DOCKERFILE" && test -f "$GUARD"
test "$(git hash-object "$DOCKERFILE")" = "$DOCKERFILE_BLOB"
test "$(git hash-object "$GUARD")" = "$GUARD_BLOB"
echo "SOURCE_GIT_BLOBS=PASS"

sudo -n docker info --format '{{.ServerVersion}}' >/dev/null
test "$(sudo -n docker image inspect "$BASE" --format '{{.Id}}')" = "$BASE_ID"
if sudo -n docker image inspect "$TAG" >/dev/null 2>&1; then
  echo "DERIVED_TAG_ALREADY_EXISTS=BLOCKED"
  exit 1
fi
BASE_PROD="$(sudo -n docker inspect opencode-lab --format '{{.Id}}')"
BASE_OVERLAY="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}')"
test -n "$BASE_PROD" && test -n "$BASE_OVERLAY"
echo "BASE_IMAGE_AND_PROD_BASELINE=PASS"

STAGE="$(mktemp -d)"
install -m 0444 "$DOCKERFILE" "$STAGE/Dockerfile"
install -m 0444 "$GUARD" "$STAGE/mcp-read-scope-guard.py"
test "$(find "$STAGE" -maxdepth 1 -type f | wc -l)" -eq 2

echo "===== BUILD DISPOSABLE IMAGE (Alpine v3.24/main only, no credentials) ====="
BUILD_ATTEMPTED=1
# The build accesses Alpine's public CDN. This is NOT an egress-isolated runtime.
# Do not place API keys, GitHub credentials, or private code in the build context.
sudo -n timeout 240 docker build \
  --pull=false --no-cache --network default \
  --file "$STAGE/Dockerfile" \
  --tag "$TAG" \
  "$STAGE"

test "$(sudo -n docker image inspect "$TAG" --format '{{index .Config.Labels "org.tsinjoops.scope"}}')" = "disposable-gate10c18-python-only"
test "$(sudo -n docker image inspect "$TAG" --format '{{.Config.User}}')" = "10001:10001"
echo "DERIVED_IMAGE_ID=$(sudo -n docker image inspect "$TAG" --format '{{.Id}}')"

echo "===== CREDENTIAL-FREE, OFFLINE RUNTIME ====="
sudo -n timeout 40 docker run --rm --name "$NAME" \
  --pull never --network none --read-only \
  --user 10001:10001 \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 32 --memory 256m --cpus 0.5 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint /usr/bin/python3 "$TAG" \
  -B /usr/local/libexec/tsinjoops/mcp-read-scope-guard.py --self-test

echo "===== OPENCODE VERSION (OFFLINE; QUALIFIED TMPFS RUNTIME PATHS) ====="
# OpenCode initializes its log/data directories even for --version.
# Reuse the eight already qualified temporary paths from Gate 10C.17.
# Preserve the read-only rootfs and network:none; no host binds or secrets.
OPENCODE_VERSION_OUTPUT="$(sudo -n timeout 40 docker run --rm --name "$NAME" \
  --pull never --network none --read-only \
  --user 10001:10001 --workdir /workspace \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 32 --memory 256m --cpus 0.5 \
  --env HOME=/home/opencode \
  --env XDG_CONFIG_HOME=/home/opencode/.config \
  --env OPENCODE_DISABLE_AUTOUPDATE=1 \
  --env OPENCODE_DISABLE_MODELS_FETCH=1 \
  --env OPENCODE_DISABLE_PROJECT_CONFIG=1 \
  --env DO_NOT_TRACK=1 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
  --tmpfs /workspace:rw,nosuid,nodev,size=32m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.cache/opencode:rw,nosuid,nodev,size=64m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.local/share/opencode:rw,nosuid,nodev,size=64m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.local/state/opencode:rw,nosuid,nodev,size=16m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.config/opencode:rw,nosuid,nodev,size=16m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.config/gh:rw,nosuid,nodev,size=4m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.config/git:rw,nosuid,nodev,size=4m,mode=0700,uid=10001,gid=10001 \
  --entrypoint /usr/local/bin/opencode "$TAG" --version)"
# The exact pinned CLI prints "opencode v2.2.5" (not a bare version token).
# Validate the complete output; do not accept 2.2.50 or unrelated text.
[[ "$OPENCODE_VERSION_OUTPUT" == "opencode v2.2.5" ]] || {
  echo "OPENCODE_VERSION_CHECK=FAIL"
  exit 1
}
echo "OPENCODE_VERSION_CHECK=PASS"

echo "NO_PROVIDER_OR_GITHUB_TOKEN=YES"
echo "NO_MODEL_OR_GITHUB_MCP_CALL=YES"
echo "NO_NETWORK_AT_RUNTIME=YES"
echo "BUILD_EGRESS_NOT_STRICTLY_ISOLATED=YES"
echo "PYTHON_IMAGE_OFFLINE_RUNTIME=PASS"
echo "DERIVED_IMAGE_TAG=$TAG"
echo "ROLLBACK=sudo docker image rm $TAG"
KEEP_IMAGE=1
