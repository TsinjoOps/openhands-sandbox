#!/usr/bin/env python3
"""Gate 10C.18 — strict, one-call GitHub MCP stdio relay (candidate, not deployed)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading

BINARY_SHA256 = "cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
EXPECTED = {
    "owner": "TsinjoOps",
    "repo": "openhands-sandbox",
    "path": "README.md",
    "sha": "32ede1461b5120beabb318167c8cc914d1145f2a",
}
CONTROL = {"initialize", "notifications/initialized", "tools/list", "ping"}
LIMIT = 131072


def decide(msg, calls):
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return "BLOCK_PROTOCOL"
    method = msg.get("method")
    if method in CONTROL:
        return "ALLOW_CONTROL"
    if method != "tools/call":
        return "BLOCK_METHOD"
    if type(msg.get("id")) not in (str, int):
        return "BLOCK_ID"
    params = msg.get("params")
    if not isinstance(params, dict) or set(params) != {"name", "arguments"}:
        return "BLOCK_PARAMS"
    if params["name"] != "get_file_contents":
        return "BLOCK_NAME"
    if not isinstance(params["arguments"], dict) or params["arguments"] != EXPECTED:
        return "BLOCK_SCOPE"
    if calls:
        return "BLOCK_CALL_LIMIT"
    return "ALLOW_TOOL"


def tests():
    base = {"jsonrpc": "2.0", "method": "tools/call", "id": 1,
            "params": {"name": "get_file_contents", "arguments": EXPECTED}}
    items = [
        (base, 0, "ALLOW_TOOL"),
        (base, 1, "BLOCK_CALL_LIMIT"),
        ({**base, "params": {"name": "issue_read", "arguments": EXPECTED}}, 0, "BLOCK_NAME"),
        ({**base, "params": {"name": "get_file_contents", "arguments": {**EXPECTED, "repo": "other"}}}, 0, "BLOCK_SCOPE"),
        ({**base, "params": {"name": "get_file_contents", "arguments": {**EXPECTED, "owner": "air-madagascar"}}}, 0, "BLOCK_SCOPE"),
        ({**base, "params": {"name": "get_file_contents", "arguments": {**EXPECTED, "path": ".github/workflows/test.yml"}}}, 0, "BLOCK_SCOPE"),
        ({**base, "params": {"name": "get_file_contents", "arguments": {**EXPECTED, "sha": "0" * 40}}}, 0, "BLOCK_SCOPE"),
        ({**base, "params": {"name": "get_file_contents", "arguments": {**EXPECTED, "ref": "main"}}}, 0, "BLOCK_SCOPE"),
        ({**base, "method": "resources/read"}, 0, "BLOCK_METHOD"),
        ({**base, "params": {**base["params"], "_meta": {}}}, 0, "BLOCK_PARAMS"),
        ({**base, "id": None}, 0, "BLOCK_ID"),
        ({"jsonrpc": "2.0", "method": "tools/list", "id": 3}, 0, "ALLOW_CONTROL"),
        ({"jsonrpc": "2.0", "method": "initialize", "id": 4, "params": {}}, 0, "ALLOW_CONTROL"),
        ({"jsonrpc": "2.0", "method": "notifications/initialized"}, 0, "ALLOW_CONTROL"),
        ({"jsonrpc": "1.0", "method": "tools/list", "id": 4}, 0, "BLOCK_PROTOCOL"),
        ([], 0, "BLOCK_PROTOCOL"),
    ]
    for i, (msg, count, wanted) in enumerate(items, 1):
        if decide(msg, count) != wanted:
            raise AssertionError("CASE_" + str(i))
    print("MCP_SCOPE_TEST=PASS")
    print("MCP_SCOPE_CASES=" + str(len(items)))
    print("NO_NETWORK_OR_CREDENTIALS=YES")


def token_from_private_file(name):
    path = Path(name)
    if not path.is_absolute():
        raise ValueError("TOKEN_PATH")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o077 or s.st_nlink != 1 or s.st_size > 512:
            raise ValueError("TOKEN_PERMISSIONS")
        with os.fdopen(os.dup(fd), "rb") as f:
            key = f.read(513).strip()
        if not 16 <= len(key) <= 512 or any(c <= 32 or c >= 127 for c in key):
            raise ValueError("TOKEN_CONTENT")
        return key.decode("ascii")
    finally:
        os.close(fd)


def binary_valid(name):
    p = Path(name)
    if not p.is_absolute() or p.is_symlink() or not p.is_file() or not os.access(p, os.X_OK):
        return False
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest() == BINARY_SHA256


def reject(msg):
    mid = msg.get("id") if isinstance(msg, dict) else None
    if mid is None:
        return
    response = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "MCP gate denied request"}}
    sys.stdout.buffer.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
    sys.stdout.buffer.flush()


def run(binary, token_file):
    if not binary_valid(binary):
        raise ValueError("UNVERIFIED_BINARY")
    token = token_from_private_file(token_file)
    # Do not inherit production credentials, proxy settings or arbitrary environment.
    env = {"PATH": "/usr/bin:/bin", "HOME": "/home/opencode", "GITHUB_PERSONAL_ACCESS_TOKEN": token}
    # This candidate deliberately has no egress proxy: live activation is BLOCKED.
    child = subprocess.Popen(
        [binary, "stdio", "--read-only", "--tools=get_file_contents"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=env, close_fds=True, bufsize=0,
    )
    state = {"forwarded": 0, "denied": 0, "success": 0}
    ids = set()
    lock = threading.Lock()

    def relay():
        try:
            while True:
                line = child.stdout.readline(LIMIT + 1)
                if not line:
                    break
                if len(line) > LIMIT:
                    print("MCP_UPSTREAM_LINE_LIMIT=BLOCKED", file=sys.stderr, flush=True)
                    child.kill()
                    break
                try:
                    data = json.loads(line)
                except ValueError:
                    print("MCP_UPSTREAM_JSON=BLOCKED", file=sys.stderr, flush=True)
                    child.kill()
                    break
                if isinstance(data, dict):
                    with lock:
                        mid = data.get("id")
                        if mid in ids:
                            ids.discard(mid)
                            result = data.get("result")
                            if isinstance(result, dict) and result.get("isError") is False and result.get("content"):
                                state["success"] += 1
                                print("MCP_DOWNSTREAM_RESULT=PASS", file=sys.stderr, flush=True)
                            else:
                                print("MCP_DOWNSTREAM_RESULT=FAIL", file=sys.stderr, flush=True)
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
        except (BrokenPipeError, OSError):
            pass

    thread = threading.Thread(target=relay, daemon=True)
    thread.start()
    print("MCP_RELAY_READY=YES", file=sys.stderr, flush=True)
    try:
        for n in range(33):
            line = sys.stdin.buffer.readline(LIMIT + 1)
            if not line:
                break
            if len(line) > LIMIT or n >= 32:
                print("MCP_INPUT_LIMIT=BLOCKED", file=sys.stderr, flush=True)
                break
            try:
                msg = json.loads(line)
            except ValueError:
                print("MCP_INPUT_JSON=BLOCKED", file=sys.stderr, flush=True)
                break
            with lock:
                status = decide(msg, state["forwarded"])
                if status == "ALLOW_TOOL":
                    state["forwarded"] += 1
                    ids.add(msg["id"])
                    print("MCP_CALL_FORWARDED=" + str(state["forwarded"]), file=sys.stderr, flush=True)
                elif status != "ALLOW_CONTROL":
                    state["denied"] += 1
                    print("MCP_CALL_DENIED=" + status, file=sys.stderr, flush=True)
            if status not in ("ALLOW_TOOL", "ALLOW_CONTROL"):
                reject(msg)
                continue
            child.stdin.write(line)
            child.stdin.flush()
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=2)
        thread.join(timeout=2)
        print("MCP_FINAL_FORWARDED=" + str(state["forwarded"]), file=sys.stderr, flush=True)
        print("MCP_FINAL_DENIED=" + str(state["denied"]), file=sys.stderr, flush=True)
        print("MCP_FINAL_SUCCESS=" + str(state["success"]), file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    opts = ap.add_mutually_exclusive_group(required=True)
    opts.add_argument("--self-test", action="store_true")
    opts.add_argument("--server-binary")
    ap.add_argument("--token-file")
    args = ap.parse_args()
    if args.self_test:
        tests()
    elif not args.token_file:
        ap.error("--token-file is required")
    else:
        try:
            sys.exit(run(args.server_binary, args.token_file))
        except (OSError, ValueError, subprocess.SubprocessError) as err:
            print("MCP_RELAY_RUNTIME=BLOCKED_" + type(err).__name__, file=sys.stderr)
            sys.exit(2)
