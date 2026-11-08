#!/usr/bin/env python3
"""Gate 10C.18o — pure candidate for explicit GitHub MCP child egress environment.

NO runtime/network permission is granted by this module. It is deliberately NOT
wired into the previously qualified mcp-read-scope-guard.py. The Docker internal
bridge plus a separately audited CONNECT relay remain mandatory before any use.
"""
from __future__ import annotations

PINNED_PROXY = "http://tsinjoops-github-egress:3128"
PINNED_PATH = "/usr/bin:/bin"
PINNED_HOME = "/home/opencode"


class EgressContractError(ValueError):
    """Reject unreviewed proxy destinations or credential shapes."""


def github_mcp_child_env(token: str, proxy_url: str) -> dict[str, str]:
    """Build the *entire* child process env, never copy a parent environment.

    The proxy DNS name is an isolated Docker service alias, not a public URL.
    Docker's isolated bridge and a separately enforced CONNECT allowlist must
    block direct egress; this Python code alone cannot restrict network access.
    """
    if type(proxy_url) is not str or proxy_url != PINNED_PROXY:
        raise EgressContractError("PROXY_NOT_PINNED")
    if type(token) is not str or not 16 <= len(token) <= 512:
        raise EgressContractError("TOKEN_SHAPE")
    if not all(32 < ord(c) < 127 for c in token):
        raise EgressContractError("TOKEN_SHAPE")
    return {
        "PATH": PINNED_PATH,
        "HOME": PINNED_HOME,
        "HTTPS_PROXY": PINNED_PROXY,
        "NO_PROXY": "",
        "GITHUB_PERSONAL_ACCESS_TOKEN": token,
    }
