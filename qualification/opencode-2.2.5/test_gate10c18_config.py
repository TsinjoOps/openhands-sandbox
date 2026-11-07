"""Offline shape/least-privilege checks. Not a native OpenCode runtime test."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GLOBAL_DENY = [{"action": "*", "resource": "*", "effect": "deny"}]
AGENT_RULES = lambda effect: [
    {"action": "execute", "resource": "*", "effect": "allow"},
    {"action": "github_probe_get_file_contents", "resource": "*", "effect": effect},
]


def load(case):
    return json.loads((ROOT / f"config-gate10c18-{case}.json").read_text())


def evaluate(action, rules):
    """Only exact-action and '*' cases used in these fixtures; last match wins."""
    matched = [rule["effect"] for rule in rules if rule["action"] in ("*", action)]
    return matched[-1] if matched else "ask"


class Gate10C18ConfigTests(unittest.TestCase):
    def test_positive_and_negative_contract(self):
        for case, expected in (("positive", "allow"), ("negative", "deny")):
            with self.subTest(case=case):
                config = load(case)
                self.assertEqual(set(config), {"permissions", "agents"})
                self.assertEqual(config["permissions"], GLOBAL_DENY)
                self.assertEqual(set(config["agents"]), {"gate-producer"})
                agent = config["agents"]["gate-producer"]
                self.assertEqual(set(agent), {"mode", "steps", "permissions"})
                self.assertEqual(agent["mode"], "primary")
                self.assertEqual(agent["steps"], 2)
                self.assertEqual(agent["permissions"], AGENT_RULES(expected))
                rules = GLOBAL_DENY + agent["permissions"]
                self.assertEqual(evaluate("execute", rules), "allow")
                self.assertEqual(evaluate("github_probe_get_file_contents", rules), expected)
                for denied in ("shell", "bash", "webfetch", "edit", "read", "write", "task", "subagent", "git", "another_mcp_get_file_contents"):
                    with self.subTest(case=case, denied=denied):
                        self.assertEqual(evaluate(denied, rules), "deny")
                # No model keys, provider URLs, GitHub tokens, MCP commands, or egress policy belong in this fixture.
                for forbidden in ("providers", "mcp", "plugins", "model", "token", "api_key", "secret"):
                    self.assertNotIn(forbidden, config)


if __name__ == "__main__":
    unittest.main()
