#!/usr/bin/env python3
"""Offline MCP stdio transport regression for Gate 10C.18. No live credentials."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent
GUARD_PATH = ROOT / "mcp-read-scope-guard.py"
spec = importlib.util.spec_from_file_location("mcp_scope_guard", GUARD_PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

FAKE_SERVER = r'''
import json
import sys
for raw in sys.stdin.buffer:
    msg = json.loads(raw)
    method = msg.get("method")
    if "id" not in msg:
        continue
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "synthetic-mcp", "version": "0"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "get_file_contents", "description": "Synthetic read", "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        # A success is allowed to omit isError entirely.
        result = {"content": [{"type": "text", "text": "synthetic public sandbox"}]}
    else:
        result = {}
    response = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
    sys.stdout.buffer.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
    sys.stdout.buffer.flush()
'''

REAL_POPEN = subprocess.Popen


def call(mid, arguments, name="get_file_contents"):
    return {"jsonrpc": "2.0", "method": "tools/call", "id": mid, "params": {
        "name": name,
        "arguments": arguments,
    }}


def trial(messages, expected):
    wire = b"".join((json.dumps(m, separators=(",", ":")) + "\n").encode() for m in messages)
    fake_in = SimpleNamespace(buffer=io.BytesIO(wire))
    fake_out = SimpleNamespace(buffer=io.BytesIO())
    fake_err = io.StringIO()
    actual = (sys.stdin, sys.stdout, sys.stderr)

    def fake_popen(argv, **kwargs):
        assert argv[1:] == ["stdio", "--read-only", "--tools=get_file_contents"]
        assert kwargs.get("close_fds") is True
        assert kwargs.get("env", {}).get("GITHUB_PERSONAL_ACCESS_TOKEN") == "synthetic-dummy-token"
        assert set(kwargs["env"]) == {"PATH", "HOME", "GITHUB_PERSONAL_ACCESS_TOKEN"}
        return REAL_POPEN(
            [sys.executable, "-u", "-c", FAKE_SERVER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, close_fds=True, bufsize=0,
            env={"PYTHONUNBUFFERED": "1"},
        )

    try:
        sys.stdin, sys.stdout, sys.stderr = fake_in, fake_out, fake_err
        with mock.patch.object(guard, "binary_valid", return_value=True), \
             mock.patch.object(guard, "token_from_private_file", return_value="synthetic-dummy-token"), \
             mock.patch.object(guard.subprocess, "Popen", side_effect=fake_popen):
            rc = guard.run("/synthetic/binary", "/synthetic/token-file")
    finally:
        sys.stdin, sys.stdout, sys.stderr = actual

    results = [json.loads(line) for line in fake_out.buffer.getvalue().splitlines()]
    evidence = fake_err.getvalue()
    assert rc == 0, "relay returned a nonzero status"
    assert f'MCP_FINAL_FORWARDED={expected["forwarded"]}' in evidence
    assert f'MCP_FINAL_DENIED={expected["denied"]}' in evidence
    assert f'MCP_FINAL_SUCCESS={expected["success"]}' in evidence
    assert len(results) == len([m for m in messages if "id" in m])
    for item in results:
        if item["id"] in expected["denied_ids"]:
            assert item.get("error", {}).get("message") == "MCP gate denied request"
        else:
            assert "result" in item and "error" not in item
    if expected["success"]:
        assert "MCP_DOWNSTREAM_RESULT=PASS" in evidence
    assert "synthetic-dummy-token" not in evidence
    return results


def main():
    base = dict(guard.EXPECTED)
    controls = [
        {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": "catalog", "method": "tools/list"},
    ]
    good = controls + [
        call("allowed", base),
        call("wrong-repo", {**base, "repo": "anything-else"}),
        call("second-call", base),
    ]
    trial(good, {"forwarded": 1, "denied": 2, "success": 1,
                 "denied_ids": {"wrong-repo", "second-call"}})

    denied = controls + [
        call("wrong-owner", {**base, "owner": "air-madagascar"}),
        call("wrong-sha", {**base, "sha": "0" * 40}),
        call("wrong-tool", base, name="issue_read"),
    ]
    trial(denied, {"forwarded": 0, "denied": 3, "success": 0,
                   "denied_ids": {"wrong-owner", "wrong-sha", "wrong-tool"}})
    print("MCP_TRANSPORT_SIMULATION=PASS")
    print("MCP_TRANSPORT_CASES=2")
    print("MCP_TRANSPORT_FORWARDED_POSITIVE=1")
    print("MCP_TRANSPORT_FORWARDED_NEGATIVE=0")
    print("NO_REAL_BINARY_OR_CREDENTIALS=YES")


if __name__ == "__main__":
    main()
