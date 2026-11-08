#!/usr/bin/env python3
"""Gate 10C.18l: OpenCode native MCP explicit-config attachment, synthetic identity.

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
        # Exact upstream server-process.ts wires this variable to config.file.
        # Explicit file admission removes global-discovery ambiguity.
        env["OPENCODE_CONFIG"] = str(config)
        demand(config.is_file() and config.stat().st_mode & 0o777 == 0o600,
               "SYNTHETIC_CONFIG_NOT_PRIVATE")
        print("SYNTHETIC_MCP_CONFIG=PASS", flush=True)

        # Compare the two exact 2.2.5 config channels using *synthetic* data.
        # First inspect the explicit-file channel without assuming that a
        # matching Document entry exists; that was the prior false-positive.
        effective = cli(["debug", "config", "--standalone"], env, 20)
        demand(effective.returncode == 0, "OPENCODE_DEBUG_CONFIG_NONZERO")
        try:
            decoded = json.loads(effective.stdout)
        except (ValueError, TypeError):
            raise RuntimeError("OPENCODE_DEBUG_CONFIG_NOT_JSON")

        def entries_from(decoded):
            if isinstance(decoded, list):
                return decoded
            if isinstance(decoded, dict) and isinstance(decoded.get("data"), list):
                return decoded["data"]
            raise RuntimeError("OPENCODE_DEBUG_CONFIG_SHAPE")

        def has_server(entry):
            if not isinstance(entry, dict) or entry.get("type") != "document":
                return False
            info = entry.get("info")
            mcp = info.get("mcp") if isinstance(info, dict) else None
            servers = mcp.get("servers") if isinstance(mcp, dict) else None
            return isinstance(servers, dict) and "github-readonly-probe" in servers

        entries = entries_from(decoded)
        print("OPENCODE_DEBUG_CONFIG_ENTRIES=PASS", flush=True)
        exact_file = [
            entry for entry in entries
            if isinstance(entry, dict) and entry.get("type") == "document"
            and entry.get("path") == str(config)
        ]
        file_present = len(exact_file) == 1 and has_server(exact_file[0])
        print("OPENCODE_EXPLICIT_FILE_MCP=" +
              ("PRESENT" if file_present else "NOT_CONFIRMED"),
              flush=True)

        if file_present:
            # Prefer the file mode if the exact file source is observed.
            print("OPENCODE_CONFIG_ROUTE=EXPLICIT_FILE", flush=True)
        else:
            # Explicit config-content is supported by the same exact upstream
            # server-process.ts and Config.load() code. Its Document has no
            # source path, by design. Only synthetic config (no secret) is passed.
            env.pop("OPENCODE_CONFIG", None)
            env["OPENCODE_CONFIG_CONTENT"] = config.read_text(encoding="utf-8")
            content_probe = cli(["debug", "config", "--standalone"], env, 20)
            demand(content_probe.returncode == 0,
                   "OPENCODE_CONTENT_CONFIG_NONZERO")
            try:
                content_entries = entries_from(json.loads(content_probe.stdout))
            except (ValueError, TypeError):
                raise RuntimeError("OPENCODE_CONTENT_CONFIG_NOT_JSON")
            virtual = [
                entry for entry in content_entries
                if isinstance(entry, dict) and entry.get("type") == "document"
                and entry.get("path") is None and has_server(entry)
            ]
            print("OPENCODE_CONTENT_DOCUMENT=" +
                  ("PRESENT" if len(virtual) == 1 else "ABSENT_OR_AMBIGUOUS"),
                  flush=True)
            demand(len(virtual) == 1, "OPENCODE_CONTENT_CONFIG_NOT_LOADED")
            print("OPENCODE_CONFIG_ROUTE=CONTENT", flush=True)

        print("OPENCODE_EFFECTIVE_MCP_CONFIG=SERVER_PRESENT", flush=True)

        cmd = cli(["mcp", "list", "--standalone"], env, 45)
        output = cmd.stdout.strip()
        # Never echo raw CLI output: it can contain unrelated messages.
        lines = output.splitlines()
        connected = any(re.search(
            r"\bgithub-readonly-probe\s+connected\s*$", line
        ) for line in lines)
        bad = any("failed" in line.lower() or "needs authentication" in line.lower()
                  for line in lines if "github-readonly-probe" in line)
        if cmd.returncode == 0 and (not connected or bad):
            # Summarize only fixed, non-secret categories. Do not emit raw
            # CLI output, stderr, config JSON, or process environment.
            status = (
                "NO_SERVERS" if "No MCP servers configured" in output
                else "FAILED" if "failed" in output.lower()
                else "NEEDS_AUTH" if "needs authentication" in output.lower()
                else "PENDING" if "pending" in output.lower()
                else "DISABLED" if "disabled" in output.lower()
                else "CONNECTED_UNPARSED" if "connected" in output.lower()
                else "UNRECOGNIZED"
            )
            print("OPENCODE_MCP_LIST_CLASS=" + status, flush=True)
            source = (cmd.stdout + "\n" + cmd.stderr).lower()
            reason = (
                "ENOENT" if "no such file" in source or "enoent" in source
                else "EACCES" if "permission denied" in source or "eacces" in source
                else "EXEC" if "exec format" in source or "spawn" in source
                else "TIMEOUT" if "timed out" in source or "timeout" in source
                else "CONNECTION" if "connection closed" in source
                else "CONFIG" if "invalid config" in source or "configuration" in source
                else "UNCLASSIFIED"
            )
            print("OPENCODE_MCP_FAILURE_CATEGORY=" + reason, flush=True)

            debug = cli(["debug", "config", "--standalone"], env, 20)
            config_class = "COMMAND_FAILED" if debug.returncode else "UNPARSEABLE"
            if debug.returncode == 0:
                try:
                    parsed = json.loads(debug.stdout)
                    items = (parsed if isinstance(parsed, list)
                             else parsed.get("data") if isinstance(parsed, dict)
                             else None)
                    config_class = "MCP_ABSENT"
                    if isinstance(items, list):
                        for entry in items:
                            if not isinstance(entry, dict):
                                continue
                            info = entry.get("info")
                            mcp = info.get("mcp") if isinstance(info, dict) else None
                            servers = mcp.get("servers") if isinstance(mcp, dict) else None
                            if isinstance(servers, dict) and "github-readonly-probe" in servers:
                                config_class = "SERVER_PRESENT"
                                break
                except (ValueError, TypeError):
                    pass
            print("OPENCODE_EFFECTIVE_MCP_CONFIG=" + config_class, flush=True)

            paths = cli(["debug", "paths"], env, 15)
            config_path = (
                "MATCH" if paths.returncode == 0
                and str(CFG_DIR) in paths.stdout
                else "MISMATCH_OR_UNAVAILABLE"
            )
            print("OPENCODE_CONFIG_DIRECTORY=" + config_path, flush=True)
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
