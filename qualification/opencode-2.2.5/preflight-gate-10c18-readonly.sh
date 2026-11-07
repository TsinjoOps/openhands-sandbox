#!/usr/bin/env bash
# Gate 10C.18 - VPS prerequisite inventory. READ-ONLY. No GitHub/model credentials.
# Run as a child Bash process on the TsinjoOps VPS, never with 'source'.
set -euo pipefail
umask 077

EXPECTED_IMAGE='sha256:4accab77deb837737d073b6499147ff61ac6aae2161ebb3c1a0bc0a7b8e8c268'

fail() {
  printf 'PREFLIGHT_STATUS=BLOCKED\nREASON=%s\n' "$1"
  exit 1
}

echo '===== GATE 10C.18 | HOST READ-ONLY PREFLIGHT ====='
echo 'TARGET_OPENCODE=2.2.5_ISOLATED_CANDIDATE'
echo 'PRODUCTION_OPENCODE=2.2.0_UNCHANGED'

for tool in docker python3 curl openssl sha256sum nsenter socat timeout; do
  command -v "$tool" >/dev/null 2>&1 || fail "MISSING_COMMAND:$tool"
  printf 'COMMAND_%s=PRESENT\n' "$tool"
done
command -v sudo >/dev/null 2>&1 || fail 'MISSING_COMMAND:sudo'

# Read-only Docker inventory. Never inspect Env, mounts' sources, configs, logs, or exec into containers.
sudo -n docker info --format '{{.ServerVersion}}' >/dev/null 2>&1 || fail 'DOCKER_READ_ACCESS'
sudo -n docker compose version --short >/dev/null 2>&1 || fail 'DOCKER_COMPOSE_UNAVAILABLE'
for name in opencode-lab opencode-sw-overlay; do
  id="$(sudo -n docker inspect "$name" --format '{{.Id}}' 2>/dev/null)" || fail "CONTAINER_INSPECT:$name"
  status="$(sudo -n docker inspect "$name" --format '{{.State.Status}}' 2>/dev/null)" || fail "CONTAINER_STATUS:$name"
  [[ "$id" =~ ^[0-9a-f]{64}$ ]] || fail "INVALID_CONTAINER_ID:$name"
  printf 'CONTAINER_%s_ID=%s\n' "$name" "$id"
  printf 'CONTAINER_%s_STATUS=%s\n' "$name" "$status"
  [[ "$status" == 'running' ]] || fail "PRODUCTION_NOT_RUNNING:$name"
done

image_id="$(sudo -n docker image inspect local/tsinjoops-opencode:2.2.5-candidate --format '{{.Id}}' 2>/dev/null)" || fail 'PINNED_IMAGE_MISSING'
[[ "$image_id" == "$EXPECTED_IMAGE" ]] || fail 'IMAGE_ID_MISMATCH'
echo 'EXACT_CANDIDATE_IMAGE=PASS'

# Public host resource counters only. These are a point-in-time sample, not a capacity guarantee.
awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ {print "HOST_" $1 "=" $2 "_kB"}' /proc/meminfo
for mount in /tmp /run; do
  [[ -d "$mount" ]] || fail "MISSING_MOUNT:$mount"
  printf 'FREE_KB_%s=%s\n' "${mount#/}" "$(df -Pk "$mount" | awk 'NR==2 {print $4}')"
done

# Explicit non-claims: requires a separate security/pre-execution review.
echo 'MODEL_PROVIDER_KEY=NOT_INSPECTED'
echo 'GITHUB_TOKEN_SCOPE=NOT_INSPECTED'
echo 'MCP_BINARY_PATH=NOT_INSPECTED'
echo 'MODEL_COST_CAP=NOT_VERIFIED'
echo 'EGRESS_ALLOWLIST=NOT_VERIFIED'
echo 'NO_SECRET_CONTENT_READ=YES'
echo 'NO_DOCKER_MUTATION=YES'
echo 'NO_NETWORK_REQUEST=YES'
echo 'PREFLIGHT_HOST_BASELINE=PASS'
echo 'GATE_10C18_AGENT_EXECUTION=BLOCKED_UNTIL_SEPARATE_PRE_EXEC_CHECKS'
