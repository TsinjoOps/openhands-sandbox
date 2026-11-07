#!/usr/bin/env python3
"""Gate 10C.18l: OpenCode native local MCP connection using synthetic identity.

Run only in disposable, no-network, non-root image with pinned GitHub MCP binary
mounted read-only. Never inject real GitHub/OpenRouter tokens into this test.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

IMAGE_VERSION = "opencode v2.2.5"
MCP_SHA = "cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324"
MCP_BIN = Path("/usr/local/bin/github-mcp-server")
GUARD = Path("/usr/local/libexec/tsinjoops/mcp-read-scope-guard.py")
OPENCODE = Path("/usr/local/bin/opencode")
CFG_DIR = Path("/home/opencode/.config/opencode")


def demand(value, code):
    if not value:
        raise RuntimeError(code)


def cli(args, env, timeout):
    try:
        return subprocess.run(
            [str(OPENCODE), *args],
            env=env, cwd="/workspace",
            capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("OPENCODE_CLI_TIMEOUT")


def main():
    demand(os.geteuid() == 10001, "NONROOT_UID_REQUIRED")
    demand(not any(os.getenv(k) for k in [
        "GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
        "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    ]), "HOST_SECRET_ENV_PRESENT")
    demand(MCP_BIN.is_file() and MCP_BIN.stat().st_size > 0, "MCP_BINARY_MISSING")
    demand(GUARD.is_file() and OPENCODE.is_file(), "IMAGE_COMPONENT_MISSING")
    with MCP_BIN.open("rb") as fp:
        digest = hashlib.file_digest(fp, "sha256").hexdigest()
    demand(digest == MCP_SHA, "MCP_BINARY_SHA256")
    print("MCP_BINARY_SHA256=PASS", flush=True)

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
        "DO_NOT_TRACK": "1",
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
    }

    v = cli(["--version"], env, 15)
    demand(v.returncode == 0 and v.stdout.strip() == IMAGE_VERSION, "OPENCODE_VERSION")
    print("OPENCODE_VERSION=PASS", flush=True)

    with tempfile.TemporaryDirectory(prefix="gate10c18l-", dir="/tmp") as root:
        token = Path(root) / "synthetic-github-key"
        token.write_text("github_pat_synthetic_invalid_offline_10c18l", encoding="ascii")
        token.chmod(0o600)
        CFG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        config = CFG_DIR / "opencode.json"
        demand(not config.exists(), "CONFIG_PATH_NOT_EMPTY")
        config.write_text(json.dumps({
            "mcp": {
                "servers": {
                    "github-readonly-probe": {
                        "type": "local",
                        "command": [
                            "/usr/bin/python3", "-B",
                            str(GUARD),
                            "--server-binary", str(MCP_BIN),
                            "--token-file", str(token),
                        ],
                        "disabled": False,
                        "codemode": True,
                        "timeout": {"startup": 10000, "catalog": 10000}
                    }
                }
            }
        }, separators=(",", ":")), encoding="utf-8")
        config.chmod(0o600)
        print("SYNTHETIC_MCP_CONFIG=PASS", flush=True)
        cmd = cli(["mcp", "list", "--standalone"], env, 45)
        output = cmd.stdout.strip()
        # Never echo raw CLI output: it can contain unrelated messages.
        lines = output.splitlines()
        connected = any(re.search(
            r"\bgithub-readonly-probe\s+connected\s*$", line
        ) for line in lines)
        bad = any("failed" in line.lower() or "needs authentication" in line.lower()
                  for line in lines if "github-readonly-probe" in line)
        demand(cmd.returncode == 0, "OPENCODE_MCP_LIST_NONZERO")
        demand(connected and not bad, "OPENCODE_MCP_NOT_CONNECTED")
        print("OPENCODE_NATIVE_MCP_CONNECTED=PASS", flush=True)
        print("OPENCODE_MCP_LIST_EXIT_CODE=0", flush=True)
    print("NO_REAL_KEYS_OR_MODEL=YES")
    print("NO_GITHUB_API_NETWORK=CONTAINER_NETWORK_NONE")
    print("GATE_10C18L_NATIVE_ATTACH=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("GATE_10C18L_NATIVE_ATTACH=BLOCKED")
        print("FAILURE_CLASS=" + type(error).__name__)
        if isinstance(error, RuntimeError):
            print("FAILURE_CODE=" + str(error))
        sys.exit(2)
