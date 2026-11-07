#!/usr/bin/env bash
# Gate 10C.18k — real GitHub MCP protocol handshake through guard, offline.
# Requires pinned test harness as argument. Synthetic token is generated
# inside a network=none, non-root test container. No production image mutation.
set -euo pipefail
umask 077
test "$#" -eq 1 || { echo "USAGE: bash runner pinned-test.py"; exit 2; }
TEST_FILE="$1"
EXPECTED_TEST_BLOB="e4966332fb071a547535edeba17934d4a082a2b1"
BASE="local/tsinjoops-opencode:2.2.5-10c18-python-20261107"
BASE_ID="sha256:1285aa62ba2108f922682fbe66f4d99428583beb087dccff61be13afe15ae36b"
BINARY_SHA="cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
URL="https://github.com/github/github-mcp-server/releases/download/v2.1.0/github-mcp-server_Linux_x86_64.tar.gz"
NAME="tsinjoops-10c18k-$$"
STAGE=""
BEFORE_PROD=""
BEFORE_OVERLAY=""

cleanup() {
  rc=$?
  trap - EXIT
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
  echo "GATE_10C18K_EXIT_CODE=$rc"
  exit "$rc"
}
trap cleanup EXIT
command -v git >/dev/null
command -v curl >/dev/null
command -v sha256sum >/dev/null
command -v timeout >/dev/null
test -f "$TEST_FILE"
test "$(git hash-object "$TEST_FILE")" = "$EXPECTED_TEST_BLOB"
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1],encoding="utf-8").read())' "$TEST_FILE"
echo "TEST_SOURCE_AND_SYNTAX=PASS"

test "$(sudo -n docker image inspect "$BASE" --format '{{.Id}}')" = "$BASE_ID"
BEFORE_PROD="$(sudo -n docker inspect opencode-lab --format '{{.Id}}')"
BEFORE_OVERLAY="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}')"
test -n "$BEFORE_PROD" && test -n "$BEFORE_OVERLAY"
echo "DERIVED_IMAGE_AND_PROD_BASELINE=PASS"

STAGE="$(mktemp -d)"
install -m 0444 "$TEST_FILE" "$STAGE/test_mcp_real_stdio_offline.py"
echo "===== OFFICIAL PINNED MCP BINARY: HOST DOWNLOAD ====="
curl -q --fail --location --silent --show-error \
  --retry 0 --connect-timeout 10 --max-time 90 --max-filesize 31457280 \
  "$URL" -o "$STAGE/release.tar.gz"
ENTRY="$(tar -tzf "$STAGE/release.tar.gz" | awk '$0=="github-mcp-server" || $0=="./github-mcp-server" {print}')"
if [[ "$ENTRY" != "github-mcp-server" && "$ENTRY" != "./github-mcp-server" ]]; then
  echo "ARCHIVE_LAYOUT=BLOCKED"
  exit 2
fi
tar -xOzf "$STAGE/release.tar.gz" "$ENTRY" > "$STAGE/github-mcp-server"
printf '%s  %s\n' "$BINARY_SHA" "$STAGE/github-mcp-server" | sha256sum -c - >/dev/null
chmod 0555 "$STAGE/github-mcp-server"
echo "MCP_BINARY_SHA256_HOST=PASS"

echo "===== REAL MCP STDIO THROUGH PYTHON GUARD (OFFLINE) ====="
sudo -n timeout 75 docker run --rm --name "$NAME" \
  --pull never --network none --read-only \
  --user 10001:10001 \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 32 --memory 256m --cpus 0.5 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env GITHUB_PERSONAL_ACCESS_TOKEN= \
  --env GITHUB_TOKEN= \
  --env GH_TOKEN= \
  --env OPENROUTER_API_KEY= \
  --mount "type=bind,src=$STAGE/github-mcp-server,dst=/usr/local/bin/github-mcp-server,readonly" \
  --mount "type=bind,src=$STAGE/test_mcp_real_stdio_offline.py,dst=/usr/local/libexec/tsinjoops/test_mcp_real_stdio_offline.py,readonly" \
  --entrypoint /usr/bin/python3 \
  "$BASE" -B /usr/local/libexec/tsinjoops/test_mcp_real_stdio_offline.py

echo "NO_REAL_TOKEN_OR_MODEL=YES"
echo "NO_NETWORK_AT_RUNTIME=YES"
echo "NO_NEW_IMAGE_BUILD=YES"
echo "GATE_10C18K=PASS"
