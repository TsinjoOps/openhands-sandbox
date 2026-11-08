#!/usr/bin/env bash
# Gate 10C.18r: approved single synthetic-invalid-token GitHub MCP tool call.
# No real GitHub/provider credential, LLM, write permission or production change.
set -euo pipefail
umask 077

test "$#" -eq 5 || {
  echo "USAGE: bash runner proxy.py client.py parser-test.py guard.py adapter.py"
  exit 2
}
PROXY_SOURCE="$1"
CLIENT_SOURCE="$2"
UNIT_SOURCE="$3"
GUARD_SOURCE="$4"
ADAPTER_SOURCE="$5"

PROXY_BLOB="0000000000000000000000000000000000000000"
CLIENT_BLOB="c0301dc9ef7f7c4d858f955aa174576602b2befe"
UNIT_BLOB="0000000000000000000000000000000000000000"
GUARD_BLOB="b6b635b0046a87bb70d320c6860275a103344ca2"
ADAPTER_BLOB="51946294f731e0f5decbeadd4b36dcc2c2ab96f9"
IMAGE="local/tsinjoops-opencode:2.2.5-10c18-python-20261107"
IMAGE_ID="sha256:1285aa62ba2108f922682fbe66f4d99428583beb087dccff61be13afe15ae36b"
MCP_SHA="cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
BINARY_URL="https://github.com/github/github-mcp-server/releases/download/v2.1.0/github-mcp-server_Linux_x86_64.tar.gz"

NET_IN="tsinjoops-10c18r-in-$$"
NET_OUT="tsinjoops-10c18r-out-$$"
PROXY_NAME="tsinjoops-10c18r-proxy-$$"
CLIENT_NAME="tsinjoops-10c18r-client-$$"
NET_IN_ID=""
NET_OUT_ID=""
PROXY_ID=""
CLIENT_STARTED=0
STAGE=""
PROD_ID=""
OVERLAY_ID=""

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  # Only delete resources created by this specific invocation.
  if [[ "$CLIENT_STARTED" = 1 ]] &&
     sudo -n docker container inspect "$CLIENT_NAME" >/dev/null 2>&1; then
    sudo -n docker rm -f "$CLIENT_NAME" >/dev/null 2>&1 || rc=1
  fi

  # Read *only* fixed diagnostic markers, never raw requests/headers.
  if [[ -n "$PROXY_ID" ]] &&
     [[ "$(sudo -n docker container inspect "$PROXY_NAME" --format '{{.Id}}' 2>/dev/null || true)" == "$PROXY_ID" ]]; then
    local count
    count="$(sudo -n docker logs "$PROXY_NAME" 2>/dev/null |
      grep -Fxc 'GATE10C18R_PROXY_CONNECT_ADMITTED=1' || true)"
    if [[ "$count" == 1 ]]; then
      echo "PROXY_SINGLE_CONNECT_OBSERVED=PASS"
    else
      echo "PROXY_SINGLE_CONNECT_OBSERVED=NV_OR_FAIL"
      rc=1
    fi
    sudo -n docker rm -f "$PROXY_NAME" >/dev/null 2>&1 || rc=1
  fi
  if [[ -n "$NET_IN_ID" ]]; then
    sudo -n docker network rm "$NET_IN_ID" >/dev/null 2>&1 || rc=1
  fi
  if [[ -n "$NET_OUT_ID" ]]; then
    sudo -n docker network rm "$NET_OUT_ID" >/dev/null 2>&1 || rc=1
  fi
  if [[ -n "$STAGE" ]]; then
    rm -rf -- "$STAGE"
  fi

  if ! sudo -n docker container inspect "$PROXY_NAME" >/dev/null 2>&1 &&
     ! sudo -n docker container inspect "$CLIENT_NAME" >/dev/null 2>&1 &&
     ! sudo -n docker network inspect "$NET_IN" >/dev/null 2>&1 &&
     ! sudo -n docker network inspect "$NET_OUT" >/dev/null 2>&1; then
    echo "DISPOSABLE_RESOURCES_REMOVED=PASS"
  else
    echo "DISPOSABLE_RESOURCES_REMOVED=FAIL"
    rc=1
  fi

  if [[ -n "$PROD_ID" && -n "$OVERLAY_ID" ]] &&
     [[ "$(sudo -n docker inspect opencode-lab --format '{{.Id}}' 2>/dev/null || true)" == "$PROD_ID" ]] &&
     [[ "$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}' 2>/dev/null || true)" == "$OVERLAY_ID" ]] &&
     [[ "$(sudo -n docker inspect opencode-lab --format '{{.State.Status}}' 2>/dev/null || true)" == running ]] &&
     [[ "$(sudo -n docker inspect opencode-sw-overlay --format '{{.State.Status}}' 2>/dev/null || true)" == running ]]; then
    echo "PRODUCTION_CONTAINER_IDS=UNCHANGED"
  else
    echo "PRODUCTION_CONTAINER_IDS=NV_OR_CHANGED"
    rc=1
  fi
  echo "GATE_10C18R_EXIT_CODE=$rc"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for cmd in git python3 bash tar awk curl sha256sum sudo timeout docker; do
  command -v "$cmd" >/dev/null || { echo "MISSING_COMMAND=$cmd"; exit 2; }
done

for arg in "$PROXY_SOURCE" "$CLIENT_SOURCE" "$UNIT_SOURCE" "$GUARD_SOURCE" "$ADAPTER_SOURCE"; do
  test -f "$arg"
done
test "$(git hash-object "$PROXY_SOURCE")" = "$PROXY_BLOB"
test "$(git hash-object "$CLIENT_SOURCE")" = "$CLIENT_BLOB"
test "$(git hash-object "$UNIT_SOURCE")" = "$UNIT_BLOB"
test "$(git hash-object "$GUARD_SOURCE")" = "$GUARD_BLOB"
test "$(git hash-object "$ADAPTER_SOURCE")" = "$ADAPTER_BLOB"

python3 - "$PROXY_SOURCE" "$CLIENT_SOURCE" "$UNIT_SOURCE" "$GUARD_SOURCE" "$ADAPTER_SOURCE" <<'PY'
import ast, sys
for name in sys.argv[1:]:
    with open(name, encoding="utf-8") as f:
        ast.parse(f.read(), filename=name)
PY

STAGE="$(mktemp -d)"
install -m 0444 "$PROXY_SOURCE" "$STAGE/gate10c18r_connect_proxy.py"
install -m 0444 "$CLIENT_SOURCE" "$STAGE/gate10c18r_mcp_client.py"
install -m 0444 "$UNIT_SOURCE" "$STAGE/test_gate10c18r_proxy.py"
install -m 0444 "$GUARD_SOURCE" "$STAGE/mcp_proxy_guard_candidate.py"
install -m 0444 "$ADAPTER_SOURCE" "$STAGE/mcp_egress_policy_candidate.py"
echo "SOURCE_BLOBS_AND_SYNTAX=PASS"

PYTHONPATH="$STAGE" PYTHONDONTWRITEBYTECODE=1 \
  python3 -B -m unittest -q test_gate10c18r_proxy
echo "OFFLINE_PROXY_PARSER_TESTS=PASS"

test "$(sudo -n docker image inspect "$IMAGE" --format '{{.Id}}')" = "$IMAGE_ID"
PROD_ID="$(sudo -n docker inspect opencode-lab --format '{{.Id}}')"
OVERLAY_ID="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}')"
test -n "$PROD_ID" && test -n "$OVERLAY_ID"
test "$(sudo -n docker inspect opencode-lab --format '{{.State.Status}}')" = running
test "$(sudo -n docker inspect opencode-sw-overlay --format '{{.State.Status}}')" = running
echo "IMAGE_AND_PRODUCTION_BASELINE=PASS"

# No host PAT is read. The *public release* is fetched only to stage the exact
# SHA-pinned GitHub MCP binary; this is not a model/REST API invocation.
curl -q -fLsS --retry 0 --connect-timeout 10 --max-time 80 \
  --max-filesize 31457280 "$BINARY_URL" -o "$STAGE/github-mcp-server.tar.gz"
ENTRY="$(tar -tzf "$STAGE/github-mcp-server.tar.gz" |
  awk '$0=="github-mcp-server" || $0=="./github-mcp-server" {print}')"
test "$ENTRY" = github-mcp-server || test "$ENTRY" = ./github-mcp-server
tar -xOzf "$STAGE/github-mcp-server.tar.gz" "$ENTRY" >"$STAGE/github-mcp-server"
printf '%s  %s\n' "$MCP_SHA" "$STAGE/github-mcp-server" | sha256sum -c - >/dev/null
chmod 0555 "$STAGE/github-mcp-server"
echo "OFFICIAL_MCP_BINARY_HASH=PASS"

for name in "$NET_IN" "$NET_OUT"; do
  if sudo -n docker network inspect "$name" >/dev/null 2>&1; then
    echo "NETWORK_NAME_COLLISION=BLOCKED"; exit 2
  fi
done
for name in "$PROXY_NAME" "$CLIENT_NAME"; do
  if sudo -n docker container inspect "$name" >/dev/null 2>&1; then
    echo "CONTAINER_NAME_COLLISION=BLOCKED"; exit 2
  fi
done

# Docker-owned temporary bridge rules only. No host firewall modifications.
NET_IN_ID="$(sudo -n docker network create --driver bridge --internal --ipv6=false \
  --label tsinjoops.gate=10c18r "$NET_IN")"
NET_OUT_ID="$(sudo -n docker network create --driver bridge --ipv6=false \
  --label tsinjoops.gate=10c18r "$NET_OUT")"
test "$(sudo -n docker network inspect "$NET_IN_ID" --format '{{.Internal}}')" = true
test "$(sudo -n docker network inspect "$NET_IN_ID" --format '{{.EnableIPv6}}')" = false
test "$(sudo -n docker network inspect "$NET_OUT_ID" --format '{{.Internal}}')" = false
test "$(sudo -n docker network inspect "$NET_OUT_ID" --format '{{.EnableIPv6}}')" = false
echo "DISPOSABLE_BRIDGES=PASS"

# One proxy on two disposable bridges. No published host port, no token.
PROXY_ID="$(sudo -n docker run -d --pull never \
  --name "$PROXY_NAME" --network "$NET_OUT" \
  --label tsinjoops.gate=10c18r \
  --user 10001:10001 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 48 \
  --memory 160m --cpus 0.5 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
  --env GITHUB_PERSONAL_ACCESS_TOKEN= --env GITHUB_TOKEN= \
  --env GH_TOKEN= --env OPENROUTER_API_KEY= \
  --env OPENAI_API_KEY= --env ANTHROPIC_API_KEY= \
  --mount "type=bind,src=$STAGE/gate10c18r_connect_proxy.py,dst=/opt/gate10c18r_connect_proxy.py,readonly" \
  --entrypoint /usr/bin/python3 "$IMAGE" \
  -B /opt/gate10c18r_connect_proxy.py)"
sudo -n docker network connect --alias tsinjoops-github-egress \
  "$NET_IN" "$PROXY_ID"
test "$(sudo -n docker inspect "$PROXY_ID" --format '{{len .NetworkSettings.Networks}}')" = 2
test "$(sudo -n docker inspect "$PROXY_ID" --format '{{.State.Running}}')" = true
echo "PROXY_DUAL_NETWORKS=PASS"

# Client uses ONLY the --internal bridge. Token is generated inside /tmp tmpfs
# under UID10001, never supplied to Docker inspect, host files or env.
CLIENT_STARTED=1
sudo -n timeout --signal TERM --kill-after 5s 70s docker run \
  --rm --pull never --name "$CLIENT_NAME" --network "$NET_IN" \
  --label tsinjoops.gate=10c18r \
  --user 10001:10001 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 64 \
  --memory 320m --cpus 1.0 \
  --tmpfs /tmp:rw,nosuid,nodev,size=32m,mode=1777,uid=10001,gid=10001 \
  --env GITHUB_PERSONAL_ACCESS_TOKEN= --env GITHUB_TOKEN= \
  --env GH_TOKEN= --env OPENROUTER_API_KEY= \
  --env OPENAI_API_KEY= --env ANTHROPIC_API_KEY= \
  --mount "type=bind,src=$STAGE/github-mcp-server,dst=/usr/local/bin/github-mcp-server,readonly" \
  --mount "type=bind,src=$STAGE/gate10c18r_mcp_client.py,dst=/opt/gate10c18r_mcp_client.py,readonly" \
  --mount "type=bind,src=$STAGE/mcp_proxy_guard_candidate.py,dst=/usr/local/libexec/tsinjoops/mcp_proxy_guard_candidate.py,readonly" \
  --mount "type=bind,src=$STAGE/mcp_egress_policy_candidate.py,dst=/usr/local/libexec/tsinjoops/mcp_egress_policy_candidate.py,readonly" \
  --entrypoint /usr/bin/python3 "$IMAGE" \
  -B /opt/gate10c18r_mcp_client.py

echo "ONE_ALLOWED_MCP_CALL_WITH_SYNTHETIC_INVALID_TOKEN=YES"
echo "NO_REAL_GITHUB_OR_PROVIDER_CREDENTIAL=YES"
echo "NO_LLM_OR_BILLABLE_PROVIDER_CALL=YES"
echo "NO_PUBLISHED_PORTS_OR_PRODUCTION_MOUNTS=YES"
echo "GATE_10C18R_CLIENT=PASS"
