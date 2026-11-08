#!/usr/bin/env bash
# Gate 10C.18p — explicitly approved, disposable NETWORK-ONLY test.
# Zero PAT/provider tokens, no model, no Docker image build/pull, no host port,
# no production mounts or global firewall edits. On errors, fail closed + teardown.
set -euo pipefail
umask 077

test "$#" -eq 3 || { echo "USAGE: bash runner proxy.py client.py test_proxy.py"; exit 2; }
PROXY_SOURCE="$1"
CLIENT_SOURCE="$2"
UNIT_SOURCE="$3"

PROXY_BLOB="c3b39f011c758ca778fa12dc6bb30b221dfffad3"
CLIENT_BLOB="753133db6164e97925c325175225a701eaaba6ba"
UNIT_BLOB="370cd93af87bd6d5fdcc9b42e62bcfcc924065a3"
IMAGE="local/tsinjoops-opencode:2.2.5-10c18-python-20261107"
IMAGE_ID="sha256:1285aa62ba2108f922682fbe66f4d99428583beb087dccff61be13afe15ae36b"

NET_IN="tsinjoops-10c18p-in-$$"
NET_OUT="tsinjoops-10c18p-out-$$"
PROXY_NAME="tsinjoops-10c18p-proxy-$$"
CLIENT_NAME="tsinjoops-10c18p-client-$$"
CREATED_IN=0
CREATED_OUT=0
CREATED_PROXY=0
CLIENT_STARTED=0
STAGE=""
PROD_ID=""
OVERLAY_ID=""

cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [[ "$CREATED_PROXY" = 1 ]]; then
    sudo -n docker rm -f "$PROXY_NAME" >/dev/null 2>&1 || rc=1
  fi
  if [[ "$CREATED_IN" = 1 ]]; then
    sudo -n docker network rm "$NET_IN" >/dev/null 2>&1 || rc=1
  fi
  if [[ "$CREATED_OUT" = 1 ]]; then
    sudo -n docker network rm "$NET_OUT" >/dev/null 2>&1 || rc=1
  fi
  # Never remove an unrelated pre-existing container after a name collision.
  if [[ "$CLIENT_STARTED" = 1 ]] && sudo -n docker container inspect "$CLIENT_NAME" >/dev/null 2>&1; then
    sudo -n docker rm -f "$CLIENT_NAME" >/dev/null 2>&1 || rc=1
  fi
  if [[ -n "$STAGE" ]]; then rm -rf -- "$STAGE"; fi

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
  echo "GATE_10C18P_EXIT_CODE=$rc"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for command in docker git python3 timeout sudo; do
  command -v "$command" >/dev/null || { echo "MISSING_COMMAND=$command"; exit 2; }
done
for file in "$PROXY_SOURCE" "$CLIENT_SOURCE" "$UNIT_SOURCE"; do test -f "$file"; done
test "$(git hash-object "$PROXY_SOURCE")" = "$PROXY_BLOB"
test "$(git hash-object "$CLIENT_SOURCE")" = "$CLIENT_BLOB"
test "$(git hash-object "$UNIT_SOURCE")" = "$UNIT_BLOB"
python3 - "$PROXY_SOURCE" "$CLIENT_SOURCE" "$UNIT_SOURCE" <<'PY'
import ast, sys
for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as f:
        ast.parse(f.read(), filename=path)
PY
STAGE="$(mktemp -d)"
install -m 0444 "$PROXY_SOURCE" "$STAGE/gate10c18p_connect_proxy.py"
install -m 0444 "$CLIENT_SOURCE" "$STAGE/client.py"
install -m 0444 "$UNIT_SOURCE" "$STAGE/test_gate10c18p_proxy.py"
echo "PINNED_SOURCES_AND_AST=PASS"

PYTHONPATH="$STAGE" PYTHONDONTWRITEBYTECODE=1 \
  python3 -B -m unittest -q test_gate10c18p_proxy
echo "OFFLINE_PROXY_PARSER_TESTS=PASS"

test "$(sudo -n docker image inspect "$IMAGE" --format '{{.Id}}')" = "$IMAGE_ID"
PROD_ID="$(sudo -n docker inspect opencode-lab --format '{{.Id}}')"
OVERLAY_ID="$(sudo -n docker inspect opencode-sw-overlay --format '{{.Id}}')"
test -n "$PROD_ID" && test -n "$OVERLAY_ID"
test "$(sudo -n docker inspect opencode-lab --format '{{.State.Status}}')" = running
test "$(sudo -n docker inspect opencode-sw-overlay --format '{{.State.Status}}')" = running
echo "PINNED_IMAGE_AND_PROD_BASELINE=PASS"

# Refuse to touch any existing name; no override or 'prune'.
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

# Docker's own temporary network management; no manual iptables/nft/ufw changes.
sudo -n docker network create --driver bridge --internal --ipv6=false \
  --label tsinjoops.gate=10c18p "$NET_IN" >/dev/null
CREATED_IN=1
sudo -n docker network create --driver bridge --ipv6=false \
  --label tsinjoops.gate=10c18p "$NET_OUT" >/dev/null
CREATED_OUT=1
test "$(sudo -n docker network inspect "$NET_IN" --format '{{.Internal}}')" = true
test "$(sudo -n docker network inspect "$NET_IN" --format '{{.EnableIPv6}}')" = false
test "$(sudo -n docker network inspect "$NET_OUT" --format '{{.Internal}}')" = false
test "$(sudo -n docker network inspect "$NET_OUT" --format '{{.EnableIPv6}}')" = false
echo "TEMP_NETWORK_TOPOLOGY=PASS"

# Proxy starts on an otherwise empty, disposable egress bridge.
CREATED_PROXY=1
sudo -n docker run --detach --rm --pull never \
  --name "$PROXY_NAME" --network "$NET_OUT" \
  --label tsinjoops.gate=10c18p \
  --user 10001:10001 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 48 \
  --memory 160m --cpus 0.5 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
  --env GITHUB_PERSONAL_ACCESS_TOKEN= --env GITHUB_TOKEN= \
  --env GH_TOKEN= --env OPENROUTER_API_KEY= \
  --env OPENAI_API_KEY= --env ANTHROPIC_API_KEY= \
  --mount "type=bind,src=$STAGE/gate10c18p_connect_proxy.py,dst=/opt/gate10c18p_connect_proxy.py,readonly" \
  --entrypoint /usr/bin/python3 "$IMAGE" \
  -B /opt/gate10c18p_connect_proxy.py >/dev/null
sudo -n docker network connect --alias tsinjoops-github-egress \
  "$NET_IN" "$PROXY_NAME"

test "$(sudo -n docker inspect "$PROXY_NAME" --format '{{len .NetworkSettings.Networks}}')" = 2
test "$(sudo -n docker inspect "$PROXY_NAME" --format '{{.State.Running}}')" = true
echo "PROXY_DUAL_NETWORKS=PASS"

# Client has ONLY the Docker internal bridge. No published ports/mounts from prod.
CLIENT_STARTED=1
sudo -n timeout --signal TERM --kill-after 5s 85s docker run \
  --rm --pull never --name "$CLIENT_NAME" --network "$NET_IN" \
  --label tsinjoops.gate=10c18p \
  --user 10001:10001 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 48 \
  --memory 192m --cpus 0.5 \
  --tmpfs /tmp:rw,nosuid,nodev,size=16m,mode=1777 \
  --env GITHUB_PERSONAL_ACCESS_TOKEN= --env GITHUB_TOKEN= \
  --env GH_TOKEN= --env OPENROUTER_API_KEY= \
  --env OPENAI_API_KEY= --env ANTHROPIC_API_KEY= \
  --mount "type=bind,src=$STAGE/client.py,dst=/opt/gate10c18p_client.py,readonly" \
  --entrypoint /usr/bin/python3 "$IMAGE" \
  -B /opt/gate10c18p_client.py

echo "NO_PAT_OR_PROVIDER_CALL=YES"
echo "NO_DOCKER_IMAGE_PULL_OR_BUILD=YES"
echo "NO_PUBLISHED_PORTS_OR_PRODUCTION_MOUNTS=YES"
echo "GATE_10C18P=PASS"
