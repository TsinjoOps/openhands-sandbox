#!/usr/bin/env bash
# TsinjoOps 10C.11: inspect the existing OpenCode 2.2.0 boundary.
# READ ONLY. Does not authenticate, print credentials or enumerate sessions.
# Run on the VPS as a CHILD process, e.g. bash preflight_web_identity_readonly.sh
set -uo pipefail
umask 077

CONTAINER="opencode-lab"
HOST="opencode.dgid.pro"

echo "===== GATE 10C.11 / READ-ONLY WEB IDENTITY PREFLIGHT ====="
echo "TARGET_DEPLOYED_BASELINE=2.2.0"
echo "TARGET_CANDIDATE=2.2.5_NOT_DEPLOYED"
echo "CONTAINER=$CONTAINER"
echo "WEB_HOST=$HOST"

echo "===== DOCKER CONTAINER METADATA (NO ENV VALUES) ====="
if ! command -v docker >/dev/null 2>&1; then
  echo "DOCKER_CLI=BLOCKED"
elif ! sudo -n docker inspect "$CONTAINER" --format 'CONTAINER_ID={{.Id}}
IMAGE={{.Config.Image}}
STATUS={{.State.Status}}
NETWORK_MODE={{.HostConfig.NetworkMode}}
READONLY_ROOTFS={{.HostConfig.ReadonlyRootfs}}
USER={{.Config.User}}' 2>/dev/null; then
  echo "DOCKER_INSPECT=BLOCKED (sudo -n or container access)"
else
  echo "DOCKER_INSPECT=PASS"
fi

echo "===== CONTAINER MOUNTS / DESTINATIONS ONLY ====="
if command -v docker >/dev/null 2>&1; then
  sudo -n docker inspect "$CONTAINER" --format '{{range .Mounts}}{{println .Destination}}{{end}}' 2>/dev/null |
    while IFS= read -r dest; do
      if [[ -n "$dest" ]]; then printf 'MOUNT_DESTINATION=%s\n' "$dest"; fi
    done || true
fi

echo "===== ANONYMOUS HTTPS CHALLENGE / NO COOKIE OR REDIRECT FOLLOW ====="
if ! command -v curl >/dev/null 2>&1; then
  echo "CURL=BLOCKED"
else
  # Only status, final URL scheme, remote host, and redirect count are printed.
  # No headers, Set-Cookie, tokens, response bodies or private session data.
  for path in / /session /api/session; do
    code="$(curl --silent --show-error --max-time 12 --connect-timeout 4 \
      --output /dev/null --max-redirs 0 \
      --write-out '%{http_code}' "https://$HOST$path" 2>/dev/null)"
    rc=$?
    printf 'ANONYMOUS_PATH=%s HTTP_CODE=%s CURL_EXIT=%s\n' "$path" "${code:-unknown}" "$rc"
  done
fi

echo "===== INVENTORY LIMITS ====="
echo "NO_COOKIES_OR_TOKENS=YES"
echo "NO_SESSION_CONTENT=YES"
echo "NO_CONFIGURATION_VALUES=YES"
echo "NO_RUNTIME_MUTATION=YES"
echo "NO_2_2_5_IDENTITY_PROOF=YES"
echo "NO_MULTIUSER_ISOLATION_PROOF=YES"
echo "PREFLIGHT_COMPLETE=YES"
