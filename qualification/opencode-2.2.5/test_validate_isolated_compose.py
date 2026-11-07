#!/usr/bin/env python3
"""Synthetic regression: Compose normalizes privileged:false to an omitted field."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate-isolated-compose.py")
TARGETS = [
    "/tmp",
    "/workspace",
    "/home/opencode/.cache/opencode",
    "/home/opencode/.local/share/opencode",
    "/home/opencode/.local/state/opencode",
    "/home/opencode/.config/opencode",
    "/home/opencode/.config/gh",
    "/home/opencode/.config/git",
]
ENV = {
    "HOME": "/home/opencode",
    "XDG_CONFIG_HOME": "/home/opencode/.config",
    "OPENCODE_DISABLE_AUTOUPDATE": "1",
    "OPENCODE_DISABLE_MODELS_FETCH": "1",
    "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
    "DO_NOT_TRACK": "1",
    "OPENCODE_PASSWORD": "synthetic-offline-gate-10c17-only",
}

def rendered():
    return {"services": {"opencode-review": {
        "image": "local/tsinjoops-opencode:2.2.5-candidate",
        "profiles": ["manual-qualification-only"],
        "command": ["serve", "--hostname", "127.0.0.1", "--port", "4096"],
        "user": "10001:10001", "working_dir": "/workspace",
        "network_mode": "none", "read_only": True,
        "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
        "pids_limit": 256, "mem_limit": "1073741824",
        "cpus": 1, "restart": "no", "environment": ENV,
        "tmpfs": [TARGETS[0] + ":rw,nosuid,nodev,size=64m,mode=1777"] +
                 [p + ":rw,nosuid,nodev,size=8m,mode=0700,uid=10001,gid=10001" for p in TARGETS[1:]],
    }}}

def verify(data):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(data), text=True, capture_output=True, check=False,
    )

class ComposeGateTests(unittest.TestCase):
    def test_omitted_privileged_is_safe_default(self):
        result = verify(rendered())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("COMPOSE_STATIC_GATE=PASS", result.stdout)

    def test_explicit_privileged_false(self):
        data = rendered()
        data["services"]["opencode-review"]["privileged"] = False
        self.assertEqual(verify(data).returncode, 0)

    def test_explicit_privileged_true_denied(self):
        data = rendered()
        data["services"]["opencode-review"]["privileged"] = True
        result = verify(data)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("privileged container", result.stdout)

    def test_wrong_synthetic_password_denied(self):
        data = rendered()
        data["services"]["opencode-review"]["environment"]["OPENCODE_PASSWORD"] = "unexpected"
        self.assertNotEqual(verify(data).returncode, 0)

    def test_cache_tmpfs_missing_denied(self):
        data = rendered()
        data["services"]["opencode-review"]["tmpfs"] = [m for m in data["services"]["opencode-review"]["tmpfs"] if not m.startswith("/home/opencode/.cache/opencode:")]
        self.assertNotEqual(verify(data).returncode, 0)

    def test_network_enabled_denied(self):
        data = rendered()
        data["services"]["opencode-review"]["network_mode"] = "bridge"
        self.assertNotEqual(verify(data).returncode, 0)

    def test_production_bind_denied(self):
        data = rendered()
        data["services"]["opencode-review"]["volumes"] = ["/opt/opencode-lab:/workspace"]
        self.assertNotEqual(verify(data).returncode, 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
