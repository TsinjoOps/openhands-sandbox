#!/usr/bin/env python3
"""Gate 10C.18k: one real GitHub MCP stdio handshake through scoped guard, OFFLINE.

No API keys or outbound network. Host must enforce Docker --network none,
non-root, and exact pinned mount/source hashes before invoking this test.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time

BINARY = Path("/usr/local/bin/github-mcp-server")
GUARD = Path("/usr/local/libexec/tsinjoops/mcp-read-scope-guard.py")
EXPECTED_BINARY_SHA256 = "cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
EXPECTED_ARGS = {
    "owner": "TsinjoOps",
    "repo": "openhands-sandbox",
    "path": "README.md",
    "sha": "32ede1461b5120beabb318167c8cc914d1145f2a",
}
SYNTHETIC_TOKEN = "github_pat_synthetic_invalid_offline_10c18k"
MAX_WIRE = 262144


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class Client:
    def __init__(self, token_path):
        self.proc = subprocess.Popen(
            [
                sys.executable, "-B", str(GUARD),
                "--server-binary", str(BINARY),
                "--token-file", str(token_path),
            ],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, close_fds=True,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": "/home/opencode",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ, "stdout")
        self.selector.register(self.proc.stderr, selectors.EVENT_READ, "stderr")
        self.buffers = {"stdout": bytearray(), "stderr": bytearray()}
        self.responses = {}
        self.wire_bytes = 0

    def send(self, method, mid=None, params=None):
        data = {"jsonrpc": "2.0", "method": method}
        if mid is not None:
            data["id"] = mid
        if params is not None:
            data["params"] = params
        self.proc.stdin.write((json.dumps(data, separators=(",", ":")) + "\n").encode())
        self.proc.stdin.flush()

    def read(self, target, max_seconds=10):
        end = time.monotonic() + max_seconds
        while target not in self.responses:
            remaining = end - time.monotonic()
            require(remaining > 0, "MCP_REPLY_TIMEOUT")
            events = self.selector.select(min(remaining, 0.5))
            if not events:
                require(self.proc.poll() is None, "MCP_PROCESS_EXITED")
                continue
            for key, _ in events:
                stream = key.data
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    self.selector.unregister(key.fileobj)
                    continue
                self.wire_bytes += len(chunk)
                require(self.wire_bytes <= MAX_WIRE, "MCP_WIRE_LIMIT")
                self.buffers[stream].extend(chunk)
                if stream == "stdout":
                    while b"\n" in self.buffers["stdout"]:
                        line, _, tail = self.buffers["stdout"].partition(b"\n")
                        self.buffers["stdout"] = bytearray(tail)
                        data = json.loads(line)
                        require(isinstance(data, dict), "MCP_REPLY_SHAPE")
                        if "id" in data:
                            self.responses[data["id"]] = data
        return self.responses.pop(target)

    def finish(self):
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
            self.proc.stdin = None
        out, err = self.proc.communicate(timeout=10)
        require(self.proc.returncode == 0, "MCP_RELAY_EXIT_NONZERO")
        require(not out.strip(), "MCP_UNEXPECTED_TRAILING_STDOUT")
        return (bytes(self.buffers["stderr"]) + err).decode("utf-8", "replace")

    def stop(self):
        if self.proc.poll() is None:
            self.proc.kill()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        self.selector.close()


def main():
    require(os.geteuid() == 10001, "BAD_UID")
    for name in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN",
                 "GH_TOKEN", "OPENROUTER_API_KEY"):
        require(not os.environ.get(name), "UNEXPECTED_REAL_CREDENTIAL_ENV")
    require(BINARY.is_file() and os.access(BINARY, os.X_OK), "MCP_BINARY_MISSING")
    require(sha256(BINARY) == EXPECTED_BINARY_SHA256, "MCP_BINARY_CHECKSUM")
    require(GUARD.is_file(), "GUARD_MISSING")
    print("MCP_BINARY_SHA256=PASS", flush=True)
    with tempfile.TemporaryDirectory(prefix="gate10c18k-", dir="/tmp") as td:
        token = Path(td) / "synthetic"
        fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(SYNTHETIC_TOKEN)
        client = Client(token)
        try:
            client.send("initialize", 1, {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "gate10c18k", "version": "1"},
            })
            init = client.read(1)
            require(isinstance(init.get("result"), dict), "MCP_INITIALIZE")
            require(bool(init["result"].get("serverInfo")), "MCP_SERVER_INFO")
            print("MCP_REAL_INITIALIZE=PASS", flush=True)

            client.send("notifications/initialized")
            client.send("tools/list", 2, {})
            listing = client.read(2)
            catalog = listing.get("result")
            require(isinstance(catalog, dict), "MCP_CATALOG_SHAPE")
            tools = catalog.get("tools")
            require(isinstance(tools, list), "MCP_CATALOG_TOOLS")
            names = [entry.get("name") for entry in tools if isinstance(entry, dict)]
            require(names == ["get_file_contents"], "MCP_CATALOG_NOT_EXACT")
            print("MCP_REAL_TOOL_CATALOG=PASS", flush=True)

            invalid = [
                ("wrong-repo", "get_file_contents", {**EXPECTED_ARGS, "repo": "not-allowed"}),
                ("wrong-tool", "issue_read", dict(EXPECTED_ARGS)),
                ("ref-override", "get_file_contents", {**EXPECTED_ARGS, "ref": "main"}),
            ]
            for i, (name, tool, arguments) in enumerate(invalid, 3):
                client.send("tools/call", i, {"name": tool, "arguments": arguments})
                response = client.read(i)
                require(
                    isinstance(response.get("error"), dict)
                    and response["error"].get("code") == -32602,
                    "MCP_DENIAL_" + name,
                )
            print("MCP_REAL_NEGATIVE_DENIALS=PASS", flush=True)
            logs = client.finish()
            require("MCP_FINAL_FORWARDED=0" in logs, "MCP_FORWARDED_UNEXPECTED")
            require("MCP_FINAL_DENIED=3" in logs, "MCP_DENIED_COUNT")
            require("MCP_FINAL_SUCCESS=0" in logs, "MCP_SUCCESS_UNEXPECTED")
            print("MCP_REAL_FORWARDED=0")
            print("MCP_REAL_DENIED=3")
            print("MCP_NO_REAL_API_REQUEST=CONTAINER_NETWORK_NONE")
            print("MCP_REAL_STDIO_OFFLINE=PASS")
        finally:
            client.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not expose raw messages, token files, subprocess environment or output.
        print("MCP_REAL_STDIO_OFFLINE=BLOCKED")
        print("MCP_FAILURE_CLASS=" + type(exc).__name__)
        if isinstance(exc, RuntimeError) and str(exc).startswith("MCP_"):
            print("MCP_FAILURE_CODE=" + str(exc))
        sys.exit(2)
