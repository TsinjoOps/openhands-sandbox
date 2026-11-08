#!/usr/bin/env python3
"""Gate 10C.18m — one long-lived OpenCode 2.2.5 server, native MCP registry.

Offline, non-root, no model or genuine token. Docker --network none is mandatory.
Verify configured source AND eventual MCP status on the SAME server process.
"""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

OPENCODE = Path("/usr/local/bin/opencode")
BINARY = Path("/usr/local/bin/github-mcp-server")
GUARD = Path("/usr/local/libexec/tsinjoops/mcp-read-scope-guard.py")
PIN = "cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
SERVER = "github-readonly-probe"
ROOT = Path("/workspace")


def check(ok, code):
    if not ok:
        raise RuntimeError(code)


def http_get(port, password, route):
    # Raw http.client neither follows redirects nor uses proxy settings.
    auth = base64.b64encode(("opencode:" + password).encode()).decode("ascii")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        conn.request("GET", route, headers={
            "Authorization": "Basic " + auth,
            "Accept": "application/json",
            "X-OpenCode-Directory": str(ROOT),
        })
        result = conn.getresponse()
        payload = result.read(262145)
        check(len(payload) <= 262144, "HTTP_RESPONSE_TOO_LARGE")
        check(result.status == 200, "HTTP_STATUS_" + str(result.status))
        return json.loads(payload)
    finally:
        conn.close()


def read_server_address(proc):
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        deadline = time.monotonic() + 30
        pending = bytearray()
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("SERVER_EXITED_EARLY")
            events = selector.select(0.4)
            if not events:
                continue
            for _, _ in events:
                chunk = os.read(proc.stdout.fileno(), 4096)
                check(bool(chunk), "SERVER_STDOUT_CLOSED")
                pending.extend(chunk)
                check(len(pending) < 16384, "SERVER_READY_OUTPUT_LIMIT")
                while b"\n" in pending:
                    line, _, rest = pending.partition(b"\n")
                    pending = bytearray(rest)
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(obj, dict) and isinstance(obj.get("url"), str):
                        url = urlsplit(obj["url"])
                        check(url.scheme == "http" and url.hostname == "127.0.0.1",
                              "SERVER_BIND_NOT_LOOPBACK")
                        check(isinstance(url.port, int) and 0 < url.port < 65536,
                              "SERVER_PORT_INVALID")
                        return url.port
        raise RuntimeError("SERVER_READY_TIMEOUT")
    finally:
        selector.close()


def entries_from(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    raise RuntimeError("CONFIG_RESPONSE_SHAPE")


def configured(entries):
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "document":
            continue
        info = entry.get("info")
        mcp = info.get("mcp") if isinstance(info, dict) else None
        servers = mcp.get("servers") if isinstance(mcp, dict) else None
        if isinstance(servers, dict) and SERVER in servers:
            return True
    return False


def server_states(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        items = payload["data"]
    elif isinstance(payload, list):
        items = payload
    else:
        raise RuntimeError("MCP_RESPONSE_SHAPE")
    found = [i for i in items if isinstance(i, dict) and i.get("name") == SERVER]
    check(len(found) <= 1, "MCP_DUPLICATE_SERVER")
    if not found:
        return "NO_SERVERS", "NONE"
    status = found[0].get("status")
    state = status.get("status") if isinstance(status, dict) else None
    check(state in ("connected", "pending", "failed", "needs_auth", "disabled"),
          "MCP_STATUS_SHAPE")
    detail = status.get("error", "") if isinstance(status, dict) else ""
    if state == "failed" and isinstance(detail, str):
        lower = detail.lower()
        category = (
            "NO_FILE" if "no such file" in lower or "enoent" in lower
            else "DENIED" if "permission denied" in lower or "eacces" in lower
            else "SPAWN" if "spawn" in lower or "exec format" in lower
            else "PROTOCOL" if "initialize" in lower or "protocol" in lower
            else "TIMEOUT" if "timeout" in lower or "timed out" in lower
            else "CONNECTION" if "connection" in lower
            else "UNCLASSIFIED"
        )
    else:
        category = "NONE"
    return state.upper(), category


def main():
    check(os.geteuid() == 10001, "NONROOT_REQUIRED")
    check(not any(os.environ.get(x) for x in (
        "GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN",
        "GH_TOKEN", "OPENROUTER_API_KEY", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "OPENCODE_PASSWORD",
    )), "REAL_CREDENTIAL_ENV_PRESENT")
    check(BINARY.is_file() and OPENCODE.is_file() and GUARD.is_file(),
          "RUNTIME_FILE_MISSING")
    with BINARY.open("rb") as fp:
        check(hashlib.file_digest(fp, "sha256").hexdigest() == PIN,
              "MCP_BINARY_CHECKSUM")
    print("MCP_BINARY_SHA256=PASS", flush=True)

    with tempfile.TemporaryDirectory(prefix="gate10c18m-", dir="/tmp") as tmp:
        password = "synthetic-private-server-10c18m"
        secret = Path(tmp) / "synthetic-github-token"
        secret.write_text("github_pat_synthetic_invalid_offline_10c18m", encoding="ascii")
        secret.chmod(0o600)
        cfg = {
            "mcp": {
                "servers": {
                    SERVER: {
                        "type": "local",
                        "command": ["/usr/bin/python3", "-B", str(GUARD),
                                    "--server-binary", str(BINARY),
                                    "--token-file", str(secret)],
                        "disabled": False,
                        "codemode": True,
                        "timeout": {"startup": 10000, "catalog": 10000},
                    }
                }
            }
        }
        # Only synthetic config data; no provider credential or other tools.
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/opencode",
            "XDG_CONFIG_HOME": "/home/opencode/.config",
            "XDG_DATA_HOME": "/home/opencode/.local/share",
            "XDG_STATE_HOME": "/home/opencode/.local/state",
            "XDG_CACHE_HOME": "/home/opencode/.cache",
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_DISABLE_MODELS_FETCH": "1",
            "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
            "OPENCODE_PASSWORD": password,
            "OPENCODE_CONFIG_CONTENT": json.dumps(cfg, separators=(",", ":")),
            "DO_NOT_TRACK": "1",
            "NO_PROXY": "127.0.0.1,localhost,::1",
        }
        child = subprocess.Popen(
            [str(OPENCODE), "serve", "--stdio", "--port", "0", "--hostname", "127.0.0.1"],
            cwd=str(ROOT), env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            bufsize=0,
        )
        try:
            port = read_server_address(child)
            print("OPENCODE_PRIVATE_SERVER=READY", flush=True)
            entries = entries_from(http_get(port, password, "/api/config"))
            check(configured(entries), "MCP_CONFIG_NOT_VISIBLE_SAME_SERVER")
            print("OPENCODE_SAME_SERVER_CONFIG=PASS", flush=True)
            seen = []
            deadline = time.monotonic() + 16
            last, category = "NO_SERVERS", "NONE"
            while time.monotonic() < deadline:
                check(child.poll() is None, "PRIVATE_SERVER_STOPPED")
                last, category = server_states(http_get(port, password, "/api/mcp"))
                if last not in seen:
                    seen.append(last)
                if last in ("CONNECTED", "FAILED", "NEEDS_AUTH", "DISABLED"):
                    break
                time.sleep(0.5)
            print("MCP_NATIVE_STATES=" + ",".join(seen), flush=True)
            print("MCP_NATIVE_LAST_STATUS=" + last, flush=True)
            print("MCP_NATIVE_FAILURE_CATEGORY=" + category, flush=True)
            check(last == "CONNECTED", "NATIVE_MCP_NOT_CONNECTED")
            print("GATE_10C18M_SAME_SERVER=PASS", flush=True)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.communicate(timeout=3)
            else:
                child.communicate(timeout=2)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("GATE_10C18M_SAME_SERVER=BLOCKED")
        print("FAILURE_CLASS=" + type(e).__name__)
        if isinstance(e, RuntimeError):
            print("FAILURE_CODE=" + str(e))
        sys.exit(2)
