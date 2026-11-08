#!/usr/bin/env python3
"""Gate 10C.18o: test only the pure candidate proxy environment policy.

No docker/network, GitHub MCP executable, PAT, provider model or production data.
"""
import os
import unittest
from unittest.mock import patch

import mcp_egress_policy_candidate as policy

FAKE_TOKEN = "github_pat_synthetic_offline_10c18o"


class ChildEgressPolicyTests(unittest.TestCase):
    def test_exact_child_environment(self):
        child = policy.github_mcp_child_env(FAKE_TOKEN, policy.PINNED_PROXY)
        self.assertEqual(set(child), {
            "PATH", "HOME", "HTTPS_PROXY", "NO_PROXY",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
        })
        self.assertEqual(child["PATH"], "/usr/bin:/bin")
        self.assertEqual(child["HOME"], "/home/opencode")
        self.assertEqual(child["HTTPS_PROXY"],
                         "http://tsinjoops-github-egress:3128")
        self.assertEqual(child["NO_PROXY"], "")
        self.assertEqual(child["GITHUB_PERSONAL_ACCESS_TOKEN"], FAKE_TOKEN)

    def test_no_inheritance_from_attacker_environment(self):
        attacker = {
            "HTTPS_PROXY": "http://malicious.example:9000",
            "https_proxy": "http://malicious.example:9001",
            "HTTP_PROXY": "http://malicious.example:9002",
            "ALL_PROXY": "socks5://malicious.example:1080",
            "NO_PROXY": "*",
            "AWS_SECRET_ACCESS_KEY": "synthetic-should-not-leak",
            "OPENROUTER_API_KEY": "synthetic-should-not-leak",
            "OPENAI_API_KEY": "synthetic-should-not-leak",
            "GITHUB_TOKEN": "synthetic-should-not-leak",
            "HOME": "/root",
            "PATH": "/tmp/attacker-bin",
            "LD_PRELOAD": "/tmp/attacker.so",
        }
        with patch.dict(os.environ, attacker):
            before = dict(os.environ)
            child = policy.github_mcp_child_env(FAKE_TOKEN,
                                                policy.PINNED_PROXY)
            self.assertEqual(dict(os.environ), before)
        self.assertTrue(set(child).isdisjoint(set(attacker) - {
            "HTTPS_PROXY", "HOME", "PATH", "NO_PROXY"
        }))
        self.assertEqual(child["HTTPS_PROXY"], policy.PINNED_PROXY)
        self.assertEqual(child["NO_PROXY"], "")

    def test_proxy_strictly_pinned(self):
        invalid = (
            "", "https://tsinjoops-github-egress:3128",
            "http://tsinjoops-github-egress:80",
            "http://127.0.0.1:3128",
            "http://tsinjoops-github-egress",
            "http://tsinjoops-github-egress:3128/",
            "http://user:pass@tsinjoops-github-egress:3128",
            "http://tsinjoops-github-egress:3128?x=1",
            "http://tsinjoops-github-egress:3128#frag",
            "HTTP://tsinjoops-github-egress:3128",
            "http://tsinjoops-github-egress:3128\n",
            "http://tsinjoops-github-egress:3128\r\nNO_PROXY=*",
            "http://malicious.example:3128",
        )
        for url in invalid:
            with self.subTest(proxy="invalid"):
                with self.assertRaisesRegex(policy.EgressContractError,
                                            "^PROXY_NOT_PINNED$"):
                    policy.github_mcp_child_env(FAKE_TOKEN, url)
        for url in (None, True, 3128):
            with self.assertRaises(policy.EgressContractError):
                policy.github_mcp_child_env(FAKE_TOKEN, url)

    def test_token_uses_strict_shape(self):
        invalid = (
            "", "short", "a" * 513,
            "a" * 16 + "\n",
            "a" * 16 + "\x00",
            "a" * 16 + "\t",
            "a" * 16 + "\u00e9",
            "a" * 16 + " ",
        )
        for token in invalid:
            with self.subTest(token="invalid"):
                with self.assertRaisesRegex(policy.EgressContractError,
                                            "^TOKEN_SHAPE$"):
                    policy.github_mcp_child_env(token, policy.PINNED_PROXY)
        for token in (None, True, b"a" * 24, ["abc"]):
            with self.assertRaises(policy.EgressContractError):
                policy.github_mcp_child_env(token, policy.PINNED_PROXY)

    def test_nonempty_synthetic_token_and_minimum_length(self):
        token = "a" * 16
        self.assertEqual(
            policy.github_mcp_child_env(token, policy.PINNED_PROXY)
            ["GITHUB_PERSONAL_ACCESS_TOKEN"],
            token,
        )

    def test_no_mutable_template_shared_between_sessions(self):
        first = policy.github_mcp_child_env(FAKE_TOKEN, policy.PINNED_PROXY)
        first["HTTPS_PROXY"] = "http://attacker"
        second = policy.github_mcp_child_env(FAKE_TOKEN, policy.PINNED_PROXY)
        self.assertEqual(second["HTTPS_PROXY"], policy.PINNED_PROXY)


if __name__ == "__main__":
    unittest.main(verbosity=0)
