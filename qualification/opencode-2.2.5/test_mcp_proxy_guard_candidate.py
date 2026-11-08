#!/usr/bin/env python3
"""Gate 10C.18q — synthetic-only, offline subprocess spawn-contract tests.

Never start GitHub MCP, Docker, network or a provider. Patch Popen to abort
before the child is created. Check qualified guard invariants are retained.
"""
import inspect
import os
import unittest
from unittest.mock import patch

import mcp_proxy_guard_candidate as candidate
import mcp_read_scope_guard_reference as baseline
import mcp_egress_policy_candidate as policy

TOKEN = "github_pat_synthetic_invalid_offline_10c18q"


class StopBeforeSpawn(Exception):
    pass


class CandidateGuardTests(unittest.TestCase):
    def test_baseline_gate_and_read_scope_identical(self):
        self.assertEqual(candidate.EXPECTED, baseline.EXPECTED)
        self.assertEqual(candidate.CONTROL, baseline.CONTROL)
        self.assertEqual(candidate.BINARY_SHA256, baseline.BINARY_SHA256)
        self.assertEqual(candidate.LIMIT, baseline.LIMIT)
        for name in ("decide", "token_from_private_file", "binary_valid",
                     "reject", "tests"):
            self.assertEqual(inspect.getsource(getattr(candidate, name)),
                             inspect.getsource(getattr(baseline, name)))
        baseline.tests()
        candidate.tests()

    def test_subprocess_child_env_exact_and_no_inheritance(self):
        inherited = {
            "HTTP_PROXY": "http://attacker.invalid:80",
            "HTTPS_PROXY": "http://attacker.invalid:443",
            "ALL_PROXY": "socks5://attacker.invalid:1080",
            "NO_PROXY": "*",
            "LD_PRELOAD": "/tmp/evil.so",
            "OPENROUTER_API_KEY": "synthetic-do-not-inherit",
            "GITHUB_TOKEN": "synthetic-do-not-inherit",
        }
        with patch.dict(os.environ, inherited):
            with patch.object(candidate, "binary_valid", return_value=True):
                with patch.object(candidate, "token_from_private_file",
                                  return_value=TOKEN):
                    with patch.object(candidate.subprocess, "Popen",
                                      side_effect=StopBeforeSpawn) as spawn:
                        with self.assertRaises(StopBeforeSpawn):
                            candidate.run("/tmp/synthetic-binary", "/tmp/synthetic-token")
        spawn.assert_called_once()
        args, kwargs = spawn.call_args
        self.assertEqual(args[0], [
            "/tmp/synthetic-binary", "stdio", "--read-only",
            "--tools=get_file_contents",
        ])
        self.assertEqual(kwargs["env"], policy.github_mcp_child_env(
            TOKEN, policy.PINNED_PROXY,
        ))
        self.assertEqual(kwargs["env"]["HTTPS_PROXY"], policy.PINNED_PROXY)
        self.assertEqual(set(kwargs["env"]), {
            "PATH", "HOME", "HTTPS_PROXY", "NO_PROXY",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
        })
        self.assertEqual(kwargs["env"]["NO_PROXY"], "")
        self.assertEqual(kwargs["stderr"], candidate.subprocess.DEVNULL)
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["bufsize"], 0)
        for key in inherited:
            if key not in {"HTTPS_PROXY", "NO_PROXY"}:
                self.assertNotIn(key, kwargs["env"])

    def test_binary_validation_fails_before_token_and_spawn(self):
        with patch.object(candidate, "binary_valid", return_value=False):
            with patch.object(candidate, "token_from_private_file") as token:
                with patch.object(candidate.subprocess, "Popen") as spawn:
                    with self.assertRaisesRegex(ValueError, "UNVERIFIED_BINARY"):
                        candidate.run("/tmp/invalid", "/tmp/token")
        token.assert_not_called()
        spawn.assert_not_called()

    def test_invalid_proxy_fails_closed_before_spawn(self):
        with patch.object(candidate, "PINNED_PROXY", "http://evil.invalid:80"):
            with patch.object(candidate, "binary_valid", return_value=True):
                with patch.object(candidate, "token_from_private_file",
                                  return_value=TOKEN):
                    with patch.object(candidate.subprocess, "Popen") as spawn:
                        with self.assertRaisesRegex(policy.EgressContractError,
                                                    "^PROXY_NOT_PINNED$"):
                            candidate.run("/tmp/synthetic-binary", "/tmp/token")
        spawn.assert_not_called()

    def test_invalid_token_shape_fails_before_spawn(self):
        with patch.object(candidate, "binary_valid", return_value=True):
            with patch.object(candidate, "token_from_private_file",
                              return_value="bad"):
                with patch.object(candidate.subprocess, "Popen") as spawn:
                    with self.assertRaisesRegex(policy.EgressContractError,
                                                "^TOKEN_SHAPE$"):
                        candidate.run("/tmp/synthetic-binary", "/tmp/token")
        spawn.assert_not_called()

    def test_actual_token_permission_rule_preserved(self):
        self.assertEqual(
            inspect.getsource(candidate.token_from_private_file),
            inspect.getsource(baseline.token_from_private_file),
        )

if __name__ == "__main__":
    unittest.main(verbosity=1)
