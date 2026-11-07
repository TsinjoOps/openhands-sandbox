#!/usr/bin/env bash
# Execute the synthetic OpenCode 2.2.5 MCP deny/allow test on a local
# Ubuntu Docker host. No GitHub token, LLM, production container or VPS.
# Run as a standalone child process: bash run-local-isolated.sh
set -Eeuo pipefail
umask 077

UPSTREAM_SHA="9bbb8ce18c80f099e0e448775f59d965ead40a21"
FIXTURE_SHA="7f6e5c34439322a9fc2ab193e6b8d951ec3e7815"
BUN_IMAGE="oven/bun:1.4.4"
ROOT=""
CONTAINER=""
LOG="$(mktemp "${HOME}/opencode-mcp-225-XXXXXX.log")"

cleanup() {
  if [[ -n "$CONTAINER" ]]; then
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
  if [[ -n "$ROOT" && -d "$ROOT" ]]; then
    rm -rf -- "$ROOT"
  fi
}
trap cleanup EXIT

{
  echo "===== LOCAL MCP TEST PRECHECK ====="
  command -v git >/dev/null
  command -v docker >/dev/null
  command -v timeout >/dev/null
  command -v python3 >/dev/null
  command -v sha256sum >/dev/null
  docker info >/dev/null
  echo "DOCKER=AVAILABLE"
  echo "UPSTREAM_SHA=$UPSTREAM_SHA"
  echo "FIXTURE_BLOB_SHA=$FIXTURE_SHA"
  echo "BUN_TAG=$BUN_IMAGE"

  ROOT="$(mktemp -d "${TMPDIR:-/tmp}/oc225-mcp-XXXXXX")"
  # Do not reuse a host Git credential helper or user gitconfig.
  mkdir -m 700 "$ROOT/git-home"
  export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
  export GIT_TERMINAL_PROMPT=0
  export HOME_GIT="$ROOT/git-home"

  free_kib="$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')"
  if (( free_kib < 8 * 1024 * 1024 )); then
    echo "DISK_AVAILABLE=INSUFFICIENT (<8 GiB)"
    exit 2
  fi
  echo "DISK_AVAILABLE=PASS"

  echo "===== PINNED SOURCE FETCH ====="
  git -c credential.helper= -c core.askPass=/bin/false init -q "$ROOT/upstream"
  timeout 240s env HOME="$HOME_GIT" git -C "$ROOT/upstream" \
    -c credential.helper= -c core.askPass=/bin/false \
    fetch --depth=1 https://github.com/anomalyco/opencode.git "$UPSTREAM_SHA"
  git -C "$ROOT/upstream" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$ROOT/upstream" rev-parse HEAD)" = "$UPSTREAM_SHA"
  echo "SOURCE_SHA=PASS"

  echo "===== TEST FIXTURE FETCH ====="
  # GitHub raw is a public read. The Git blob SHA is independently verified.
  python3 - "$ROOT" "$FIXTURE_SHA" <<'PY'
import hashlib, pathlib, sys, urllib.request
root = pathlib.Path(sys.argv[1])
expected = sys.argv[2]
url = (
    "https://raw.githubusercontent.com/TsinjoOps/openhands-sandbox/"
    "d34a3ecc4b6e71b54a52199c13a02580180c4e12/"
    "qualification/opencode-2.2.5/mcp-permission-gate.test.ts"
)
request = urllib.request.Request(url, headers={"User-Agent": "TsinjoOps-OC225-local-test"})
with urllib.request.urlopen(request, timeout=30) as response:
    body = response.read(1000000)
digest = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
if digest != expected:
    raise SystemExit("FIXTURE_SHA=FAIL")
target = root / "upstream/packages/core/test/mcp-permission-gate.test.ts"
target.write_bytes(body)
print("FIXTURE_SHA=PASS")
PY

  echo "===== BUN IMAGE PULL ====="
  timeout 300s docker pull "$BUN_IMAGE" >/dev/null
  IMAGE_ID="$(docker image inspect -f '{{.Id}}' "$BUN_IMAGE")"
  echo "BUN_IMAGE_ID=$IMAGE_ID"

  mkdir -p "$ROOT/.home" "$ROOT/.bun-cache" "$ROOT/.cache" "$ROOT/tmp"
  CONTAINER="oc225-mcp-$(basename "$ROOT" | tr '[:upper:]' '[:lower:]')"

  common=(
    --rm --name "$CONTAINER"
    --user "$(id -u):$(id -g)"
    --cap-drop ALL --security-opt no-new-privileges
    --pids-limit 256 --memory 5g --cpus 2
    --read-only
    --tmpfs /tmp:rw,nosuid,nodev,size=256m,mode=1777
    --volume "$ROOT:/work:rw"
    --workdir /work/upstream
    --env HOME=/work/.home
    --env XDG_CACHE_HOME=/work/.cache
    --env BUN_INSTALL_CACHE_DIR=/work/.bun-cache
    --env CI=true
    --env OPENCODE_DISABLE_AUTOUPDATE=1
    --env OPENCODE_DISABLE_MODELS_FETCH=1
    --env OPENCODE_DISABLE_PROJECT_CONFIG=1
    --entrypoint /bin/sh
  )
  echo "===== DEPENDENCY INSTALL (NETWORK ENABLED, SCRIPTS DISABLED) ====="
  timeout 600s docker run "${common[@]}" --network bridge "$IMAGE_ID" -c \
    'test "$(bun --version)" = "1.4.4" && bun install --frozen-lockfile --ignore-scripts'
  CONTAINER=""

  echo "===== FOCUSED TEST (NO NETWORK) ====="
  CONTAINER="oc225-mcp-$(basename "$ROOT" | tr '[:upper:]' '[:lower:]')"
  timeout 180s docker run "${common[@]}" --network none "$IMAGE_ID" -c \
    'bun run --cwd packages/core script/test.ts mcp-permission-gate.test.ts'
  CONTAINER=""
  echo "NATIVE_MCP_TEST=PASS"
} >"$LOG" 2>&1
result=$?
echo "LOG=$LOG"
echo "EXIT_CODE=$result"
tail -n 90 "$LOG"
