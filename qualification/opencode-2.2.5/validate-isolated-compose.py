#!/usr/bin/env python3
"""Gate 10C.16: read-only validator for a rendered Compose service contract.

Input is JSON from: docker compose -f <manifest> config --format json
No Docker startup, network call, shell execution, secrets or file mutation.
"""
import json
import sys

EXPECTED_IMAGE = "local/tsinjoops-opencode:2.2.5-candidate"
EXPECTED_TARGETS = {
    "/tmp", "/workspace",
    "/home/opencode/.local/share/opencode",
    "/home/opencode/.local/state/opencode",
    "/home/opencode/.config/opencode",
    "/home/opencode/.config/gh",
    "/home/opencode/.config/git",
}


def fail(message):
    print("COMPOSE_STATIC_GATE=FAIL", message)
    raise SystemExit(1)


def require(value, message):
    if not value:
        fail(message)


def main():
    obj = json.load(sys.stdin)
    services = obj.get("services", {})
    require(list(services) == ["opencode-review"], "unexpected services")
    s = services["opencode-review"]
    require(s.get("image") == EXPECTED_IMAGE, "image tag mismatch")
    require(s.get("network_mode") == "none", "network must be none")
    require(not s.get("networks"), "networks attached")
    require(not s.get("ports"), "published ports")
    require(not s.get("expose"), "exposed ports")
    require(not s.get("volumes"), "any bind or volume mount")
    require(not s.get("secrets"), "secret injection")
    require(not s.get("configs"), "external config injection")
    require(s.get("read_only") is True, "rootfs not read-only")
    require(s.get("privileged") is False, "privileged container")
    require(s.get("user") == "10001:10001", "unexpected UID/GID")
    require("ALL" in s.get("cap_drop", []), "capabilities not dropped")
    require("no-new-privileges:true" in s.get("security_opt", []), "no-new-privileges absent")
    require(s.get("pids_limit", 0) > 0, "PID limit missing")
    require(s.get("restart") in ["no", "none", None], "unexpected restart policy")
    require("manual-qualification-only" in s.get("profiles", []), "manual profile absent")
    require(s.get("working_dir") == "/workspace", "working directory")
    require(s.get("command") == ["serve", "--hostname", "127.0.0.1", "--port", "4096"], "unexpected command")
    require(not s.get("entrypoint"), "entrypoint override")
    require(s.get("mem_limit"), "memory limit absent")
    require(s.get("cpus"), "CPU limit absent")
    env = s.get("environment", {})
    require(set(env) == {
        "HOME", "XDG_CONFIG_HOME", "OPENCODE_DISABLE_AUTOUPDATE",
        "OPENCODE_DISABLE_MODELS_FETCH", "OPENCODE_DISABLE_PROJECT_CONFIG", "DO_NOT_TRACK",
    }, "environment variable names unexpected")
    require(env["HOME"] == "/home/opencode", "home changed")
    mounts = s.get("tmpfs") or []
    require(isinstance(mounts, list), "tmpfs shape")
    targets = set()
    for mount in mounts:
        if isinstance(mount, str):
            target, sep, options = mount.partition(":")
            require(bool(sep), "tmpfs options absent")
            if target != "/tmp":
                require("uid=10001" in options and "gid=10001" in options, "tmpfs nonroot ownership missing")
        elif isinstance(mount, dict):
            target = mount.get("target")
        else:
            fail("unsupported tmpfs shape")
        require(target not in targets, "duplicate tmpfs target")
        targets.add(target)
    require(targets == EXPECTED_TARGETS, "tmpfs destinations mismatch")
    print("COMPOSE_STATIC_GATE=PASS")
    print("SCOPE=one credential-free offline non-root disposable runtime")
    print("BIND_MOUNTS=0")
    print("PUBLISHED_PORTS=0")
    print("NETWORK=none")
    print("NO_RUNTIME_EXECUTION=YES")
    print("IMAGE_ID_AND_USABILITY=NV")


if __name__ == "__main__":
    main()
