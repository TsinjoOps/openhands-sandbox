#!/usr/bin/env bash
# Gate 10C.18l: no-credential native OpenCode->MCP attachment, offline.
# Requires previously qualified Python-enabled image. No Docker image changes.
set -euo pipefail
umask 077
test "$#" -eq 1 || { echo "USAGE: bash runner exact-test.py"; exit 2; }
TEST="$1"
TEST_BLOB="5dd1319d0e06a1fcc88e79008e05722a4eb912c7"
IMAGE="local/tsinjoops-opencode:2.2.5-10c18-python-20261107"
IMAGE_ID="sha256:1285aa62ba2108f922682fbe66f4d99428583beb087dccff61be13afe15ae36b"
MCP_SHA="cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
URL="https://github.com/github/github-mcp-server/releases/download/v2.1.0/github-mcp-server_Linux_x86_64.tar.gz"
STAGE=""
NAME="tsinjoops-10c18l-$$"
BEFORE_PROD=""
BEFORE_OVERLAY=""

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  sudo -n docker rm -f "$NAME" >/dev/null 2>&1 || true
  if [[ -n "$STAGE" ]]; then rm -rf -- "$STAGE"; fi
  if [[ -n "$BEFORE_PROD" && -n "$BEFORE_OVERLAY" &&
        "$(sudo -n docker inspect opencode-lab --format '{{.Id}}' 2>/dev/null || true)" == "$BEFORE_PROD" &&
        "$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}' 2>/dev/null || true)" == "$BEFORE_OVERLAY" ]]; then
    echo "PRODUCTION_CONTAINER_IDS=UNCHANGED"
  else
    echo "PRODUCTION_CONTAINER_IDS=NV_OR_CHANGED"
    rc=1
  fi
  echo "GATE_10C18L_EXIT_CODE=$rc"
  exit "$rc"
}
trap cleanup EXIT INT TERM

test -f "$TEST"
test "$(git hash-object "$TEST")" = "$TEST_BLOB"
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$TEST"
echo "NATIVE_TEST_SOURCE=PASS"

test "$(sudo -n docker image inspect "$IMAGE" --format '{{.Id}}')" = "$IMAGE_ID"
BEFORE_PROD="$(sudo -n docker inspect opencode-lab --format '{{.Id}}')"
BEFORE_OVERLAY="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}')"
test -n "$BEFORE_PROD" && test -n "$BEFORE_OVERLAY"
echo "EXACT_IMAGE_AND_PROD_BASELINE=PASS"

STAGE="$(mktemp -d)"
install -m 0444 "$TEST" "$STAGE/native-test.py"
curl -q --fail --location --silent --show-error \
  --retry 0 --connect-timeout 10 --max-time 90 --max-filesize 31457280 \
  "$URL" -o "$STAGE/release.tar.gz"
ENTRY="$(tar -tzf "$STAGE/release.tar.gz" |
  awk '$0=="github-mcp-server" || $0=="./github-mcp-server" {print}')"
if [[ "$ENTRY" != "github-mcp-server" && "$ENTRY" != "./github-mcp-server" ]]; then
  echo "ARCHIVE_LAYOUT=BLOCKED"
  exit 2
fi
tar -xOzf "$STAGE/release.tar.gz" "$ENTRY" > "$STAGE/github-mcp-server"
printf '%s  %s\n' "$MCP_SHA" "$STAGE/github-mcp-server" | sha256sum -c - >/dev/null
chmod 0555 "$STAGE/github-mcp-server"
echo "MCP_BINARY_HASH=PASS"

echo "===== OPEN CODE NATIVE MCP ATTACH (NO NETWORK, SYNTHETIC IDENTITY) ====="
sudo -n timeout 90 docker run --rm --name "$NAME" \
  --pull never --network none --read-only \
  --user 10001:10001 --workdir /workspace \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 64 --memory 512m --cpus 1.0 \
  --tmpfs /tmp:rw,nosuid,nodev,size=32m,mode=1777 \
  --tmpfs /workspace:rw,nosuid,nodev,size=64m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.cache/opencode:rw,nosuid,nodev,size=128m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.local/share/opencode:rw,nosuid,nodev,size=128m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.local/state/opencode:rw,nosuid,nodev,size=32m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.config/opencode:rw,nosuid,nodev,size=32m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.config/gh:rw,nosuid,nodev,size=8m,mode=0700,uid=10001,gid=10001 \
  --tmpfs /home/opencode/.config/git:rw,nosuid,nodev,size=8m,mode=0700,uid=10001,gid=10001 \
  --env HOME=/home/opencode \
  --env XDG_CONFIG_HOME=/home/opencode/.config \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env GITHUB_PERSONAL_ACCESS_TOKEN= \
  --env GITHUB_TOKEN= \
  --env GH_TOKEN= \
  --env OPENROUTER_API_KEY= \
  --mount "type=bind,src=$STAGE/github-mcp-server,dst=/usr/local/bin/github-mcp-server,readonly" \
  --mount "type=bind,src=$STAGE/native-test.py,dst=/usr/local/libexec/tsinjoops/native-test.py,readonly" \
  --entrypoint /usr/bin/python3 "$IMAGE" \
  -B /usr/local/libexec/tsinjoops/native-test.py
echo "NO_REAL_GITHUB_OR_PROVIDER_TOKEN=YES"
echo "NO_MODEL_INFERENCE=YES"
echo "NO_NETWORK_AT_RUNTIME=YES"
echo "NO_NEW_IMAGE_BUILD=YES"
echo "GATE_10C18L=PASS"
