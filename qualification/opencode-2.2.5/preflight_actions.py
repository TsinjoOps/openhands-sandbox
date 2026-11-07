#!/usr/bin/env python3
"""Read-only inventory of Actions workflows on TsinjoOps/openhands-sandbox main.

Uses unauthenticated GitHub REST endpoints for this PUBLIC repository.
Does not modify repository, invoke GitHub Actions or read any local credentials.
Fail-closed if workflows or trigger lines cannot be inspected.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "TsinjoOps/openhands-sandbox"
BASE = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "TsinjoOps-OpenCode-MCP-ReadOnly-Preflight/1.0",
    "X-GitHub-Api-Version": "2022-11-28",
}
TIMEOUT = 12

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP_{r.status}")
        return r.read()

def main():
    workflows = []
    page = 1
    while True:
        url = f"{BASE}/repos/{REPO}/actions/workflows?per_page=100&page={page}"
        payload = json.loads(fetch(url))
        entries = payload.get("workflows")
        if not isinstance(entries, list):
            raise RuntimeError("workflow inventory response missing workflows")
        workflows.extend(entries)
        if len(entries) < 100:
            break
        page += 1
        if page > 10:
            raise RuntimeError("inventory pagination cap hit")

    print(f"REPOSITORY={REPO}")
    print(f"WORKFLOW_COUNT={len(workflows)}")
    print("MAIN_TRIGGER_INSPECTION=START")
    risk_count = 0
    for item in workflows:
        path = item.get("path", "")
        state = item.get("state", "unknown")
        name = item.get("name", "unknown")
        if not path.startswith(".github/workflows/") or any(x in path for x in ("..", "\\", "?")):
            raise RuntimeError("invalid workflow path")
        encoded = urllib.parse.quote(path, safe="/")
        file_url = f"https://raw.githubusercontent.com/{REPO}/main/{encoded}"
        body = fetch(file_url).decode("utf-8")
        # We intentionally avoid partial YAML parsers: report top-level
        # trigger sections verbatim, and mark syntax ambiguity for review.
        trigger_lines = [
            line.strip()
            for line in body.splitlines()
            if line.startswith("on:") or line.startswith("'on':") or line.startswith('"on":')
        ]
        suspicious = (
            "pull_request" in body or "push:" in body
            or "workflow_run" in body or "pull_request_target" in body
        )
        if suspicious and state == "active":
            risk_count += 1
        print(json.dumps({
            "path": path, "name": name, "state": state,
            "top_level_triggers": trigger_lines,
            "requires_review": suspicious or len(trigger_lines) != 1,
        }, ensure_ascii=False))
    print(f"ACTIVE_WORKFLOWS_POSSIBLY_TRIGGERED_BY_PR_OR_PUSH={risk_count}")
    print("ACTIONS_BILLING_AND_ORG_POLICY=NV")
    print("NO_ACTIONS_DISPATCHED=PASS")
    print("NO_GITHUB_CREDENTIAL_USED=PASS")
    print("READ_ONLY_PREFLIGHT=COMPLETE")

if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, ValueError, RuntimeError, UnicodeError) as exc:
        print("READ_ONLY_PREFLIGHT=BLOCKED")
        print(f"ERROR_TYPE={type(exc).__name__}")
        sys.exit(1)
