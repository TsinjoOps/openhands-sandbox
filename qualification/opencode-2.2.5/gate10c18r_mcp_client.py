#!/usr/bin/env python3
"""Gate 10C.18r: single real GitHub MCP call, INVALID SYNTHETIC token only.

Executes inside a UID10001 container with only an internal Docker bridge.
Never log the token, MCP raw tool result, HTTP headers, or response body.
The only authorized tool call is the exact public sandbox README at pinned SHA.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import socket
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, "/usr/local/libexec/tsinjoops")
from mcp_proxy_guard_candidate import EXPECTED

GH_SERVER = Path("/usr/local/bin/github-mcp-server")
GUARD = Path("/usr/local/libexec/tsinjoops/mcp_proxy_guard_candidate.py")
ADAPTER = Path("/usr/local/libexec/tsinjoops/mcp_egress_policy_candidate.py")
PIN = "cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
SYNTHETIC = "github_pat_synthetic_invalid_gate10c18r"
MAX_MESSAGE = 131072


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


class Rpc:
    def __init__(self, proc):
        self.proc = proc
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(proc.stdout, selectors.EVENT_READ)
        self.count = 0

    def close(self):
        self.selector.close()

    def send(self, message):
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
        require(len(payload) < MAX_MESSAGE, "REQUEST_TOO_LARGE")
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()

    def call(self, method, params, mid, timeout=18):
        self.send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Drain a final already-buffered response even if the guard
            # has exited; a process can close after writing its last line.
            wait = min(0.6, deadline - time.monotonic())
            events = self.selector.select(max(0.01, wait))
            if not events and self.proc.poll() is not None:
                raise RuntimeError("GUARD_EXITED_EARLY")
            for _, _ in events:
                chunk = os.read(self.proc.stdout.fileno(), 4096)
                require(chunk, "RPC_STDOUT_CLOSED")
                self.buffer.extend(chunk)
                require(len(self.buffer) <= MAX_MESSAGE, "RPC_RESPONSE_TOO_LARGE")
                while b"\n" in self.buffer:
                    line, _, rest = self.buffer.partition(b"\n")
                    self.buffer = bytearray(rest)
                    try:
                        decoded = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        raise RuntimeError("RPC_INVALID_JSON")
                    require(isinstance(decoded, dict), "RPC_RESPONSE_SHAPE")
                    require(decoded.get("id") == mid, "RPC_UNEXPECTED_ID")
                    return decoded
        raise RuntimeError("RPC_CALL_TIMEOUT")


def main():
    require(os.geteuid() == 10001, "NONROOT_REQUIRED")
    require(not any(os.environ.get(k) for k in (
        "GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
        "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    )), "EXTERNAL_CREDENTIAL_PRESENT")
    require(GH_SERVER.is_file() and GUARD.is_file() and ADAPTER.is_file(),
            "PINNED_COMPONENT_MISSING")
    with GH_SERVER.open("rb") as binary:
        require(hashlib.file_digest(binary, "sha256").hexdigest() == PIN,
                "MCP_BINARY_SHA256")
    require(EXPECTED == {
        "owner": "TsinjoOps", "repo": "openhands-sandbox",
        "path": "README.md", "sha": "32ede1461b5120beabb318167c8cc914d1145f2a",
    }, "GITHUB_SCOPE_DRIFT")
    print("PINNED_GITHUB_MCP_AND_SCOPE=PASS", flush=True)

    # Independently verify the client cannot connect directly to the Internet
    # before starting any GitHub MCP subprocess. These are denial probes only.
    for ip, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        try:
            with socket.create_connection((ip, port), timeout=2):
                raise RuntimeError("DIRECT_IPV4_EGRESS_ALLOWED")
        except OSError:
            pass
    print("DIRECT_IPV4_DENIAL_SAMPLES=PASS", flush=True)

    # A TCP readiness check sends no CONNECT or HTTP request and consumes
    # none of the proxy's one-tunnel admission budget.
    ready_by = time.monotonic() + 12
    while True:
        try:
            with socket.create_connection(("tsinjoops-github-egress", 3128),
                                          timeout=2):
                break
        except OSError:
            require(time.monotonic() < ready_by, "PROXY_NOT_READY")
            time.sleep(0.3)
    print("GITHUB_PROXY_READY=PASS", flush=True)

    # The token is synthetic, stored exclusively in container tmpfs.
    with tempfile.TemporaryDirectory(prefix="gate10c18r-", dir="/tmp") as tmp:
        secret = Path(tmp) / "invalid-token"
        secret.write_text(SYNTHETIC, encoding="ascii")
        secret.chmod(0o600)
        require(secret.stat().st_uid == os.geteuid()
                and (secret.stat().st_mode & 0o777) == 0o600,
                "SYNTHETIC_TOKEN_PERMISSIONS")
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/opencode",
            "PYTHONDONTWRITEBYTECODE": "1",
            # No outer proxy settings or provider credentials.
        }
        process = subprocess.Popen(
            ["/usr/bin/python3", "-B", str(GUARD),
             "--server-binary", str(GH_SERVER),
             "--token-file", str(secret)],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
            close_fds=True, bufsize=0,
        )
        rpc = Rpc(process)
        try:
            init = rpc.call("initialize", {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "tsinjoops-10c18r", "version": "1"},
            }, mid=1, timeout=12)
            require(isinstance(init.get("result"), dict),
                    "MCP_INITIALIZE_NOT_OK")
            print("MCP_REAL_INITIALIZE=PASS", flush=True)
            rpc.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            catalogue = rpc.call("tools/list", {}, mid=2, timeout=12)
            tools = catalogue.get("result", {}).get("tools", [])
            require(isinstance(tools, list) and len(tools) == 1
                    and tools[0].get("name") == "get_file_contents",
                    "MCP_TOOL_CATALOG_DRIFT")
            print("MCP_SINGLE_TOOL_CATALOG=PASS", flush=True)

            # Two denials before the only permitted tool call.
            for mid, params in (
                (3, {"name": "get_file_contents",
                     "arguments": {**EXPECTED, "repo": "other"}}),
                (4, {"name": "issue_read", "arguments": EXPECTED}),
            ):
                answer = rpc.call("tools/call", params, mid=mid, timeout=5)
                require(isinstance(answer.get("error"), dict)
                        and answer["error"].get("code") == -32602,
                        "OFF_SCOPE_DENIAL_FAILED")
            print("MCP_GATE_DENIED_BEFORE_FORWARD=2", flush=True)

            # This is THE ONLY forwarded tools/call. The exact commit is public,
            # but authentication must fail with the deliberately invalid token.
            response = rpc.call("tools/call", {
                "name": "get_file_contents", "arguments": EXPECTED,
            }, mid=5, timeout=20)
            result = response.get("result")
            require(isinstance(result, dict) and result.get("isError") is True,
                    "EXPECTED_TOOL_AUTH_ERROR_NOT_OBSERVED")
            raw = json.dumps(result, separators=(",", ":")).lower()
            require(any(term in raw for term in ("401", "bad credentials",
                                                "unauthorized", "invalid token")),
                    "AUTH_ERROR_NOT_IDENTIFIED")
            print("GITHUB_SYNTHETIC_AUTH_REJECTED=PASS", flush=True)
        finally:
            rpc.close()
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait(timeout=3)
            if process.stderr:
                raw_stderr = process.stderr.read(8192).decode(errors="replace")
                process.stderr.close()
            else:
                raw_stderr = ""
            if process.stdout:
                process.stdout.close()
            # Guard exits 2 when the single downstream call returned isError.
            print("GUARD_EXIT_EXPECTED_AUTH_ERROR=" +
                  ("PASS" if code == 2 else "FAIL"), flush=True)
            for key, wanted in (
                ("MCP_FINAL_FORWARDED", "1"),
                ("MCP_FINAL_DENIED", "2"),
                ("MCP_FINAL_SUCCESS", "0"),
            ):
                observed = re.search(r"^" + re.escape(key) +
                                     r"=(\d+)$", raw_stderr, flags=re.M)
                print(key + "_EXPECTED=" +
                      ("PASS" if observed and observed.group(1) == wanted
                       else "FAIL"), flush=True)
            # Hard-fail on mismatch without emitting raw guard/server stderr.
            require(code == 2, "GUARD_EXIT_NOT_EXPECTED")
            for key, wanted in (
                ("MCP_FINAL_FORWARDED", "1"),
                ("MCP_FINAL_DENIED", "2"),
                ("MCP_FINAL_SUCCESS", "0"),
            ):
                require(bool(re.search(
                    r"^" + re.escape(key) + r"=" + wanted + r"$",
                    raw_stderr, flags=re.M,
                )), "GUARD_ACCOUNTING_" + key)
    print("GATE_10C18R_SYNTHETIC_MCP_CLIENT=PASS", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("GATE_10C18R_SYNTHETIC_MCP_CLIENT=BLOCKED", flush=True)
        print("FAILURE_CLASS=" + type(exc).__name__, flush=True)
        if isinstance(exc, RuntimeError):
            print("FAILURE_CODE=" + str(exc), flush=True)
        sys.exit(2)
