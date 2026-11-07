# OpenCode 2.2.5 — Gate MCP permission deny/allow (proposal)

Status: **STAGED / NOT EXECUTED (NV)**. Synthetic test only; no deployment.

## Purpose

Qualify the real OpenCode MCP execution path without an LLM, a GitHub token or network access. Specifically: verify that a denied MCP tool is never invoked by the in-memory MCP server, while the same tool is invoked exactly once when permitted.

- Upstream source: `anomalyco/opencode`
- Pinned commit: `9bbb8ce18c80f099e0e448775f59d965ead40a21` (version 2.2.5)
- Bun: version `1.4.4` required by upstream `package.json`
- Relevant upstream reference tests: `packages/core/test/mcp-attach.test.ts`, `packages/core/test/permission.test.ts`, `packages/core/test/lib/tool.ts`
- Owner / architecture gate: [TsinjoOps/platform#100](https://github.com/TsinjoOps/platform/issues/100), [Draft PR #101](https://github.com/TsinjoOps/platform/pull/101).

## Fixture

`mcp-permission-gate.test.ts` is **an unexecuted candidate test source** intended to be copied into a separate upstream checkout at `packages/core/test/mcp-permission-gate.test.ts`. It uses the upstream native `Tool.Service`, `McpTool.Service`, live `Permission.Service`, an actual persisted in-test session, and an in-memory MCP server with an invocation counter. No mocked `Permission.assert`.

Expected verification:
1. MCP tool `probe_ping` registered before the test begins.
2. Explicit deny rule for `probe_ping` while Code Mode itself is enabled: `execute` returns an error and the MCP callback count remains **0**.
3. Change permission to allow: `execute` returns success and the MCP callback count becomes **1**.
4. The test does not use `OPENCODE_SIMULATE`, `OPENCODE_DRIVE`, LLM, GitHub token, or external Github MCP.

**Path qualification:** the fixture uses the upstream `executeTool` helper, which creates an unfiltered `Tool.snapshot()`; the MCP tool is therefore still presented to Code Mode. The explicit `probe_ping` denial must be checked by the **real** `Permission.assert()` in the MCP tool executor, rather than by a filtered catalog alone. The positive control also asserts the server's actual `pong` response, not just a completed status. A separate filtered-catalog test remains optional and must not be confused with effective runtime refusal.

**Potential failure boundary:** candidate has not been typechecked or run against actual upstream source at the commit. Real service dependency graph, counter semantics and Code Mode exposure may need adjustment. All expected behaviors remain **NV** until independently executed.

## Staged manual-only CI definition

A dormant workflow has been added **on the qualification branch only** at `.github/workflows/poc-opencode-mcp-permission-225.yml`, commit `c5ef88dd046b6b79ca045a5f12a2dee4eac622a1`. It uses `workflow_dispatch` exclusively (no `push`, `pull_request`, `schedule`, or `workflow_call`), `contents: read`, no explicit secrets, a 15-minute GitHub-hosted Ubuntu 24.04 job limit, SHA-pinned checkout and Bun setup actions, exact OpenCode SHA verification, Bun 1.4.4, and `bun install --frozen-lockfile --ignore-scripts`, then only the focused test. The dependency install still uses outbound network and runs on a third-party-hosted runner; it remains subject to provenance review and explicitly authorized CI resource use. The fixture is not sandboxed against arbitrary network calls, so it must be reviewed before enabling.

**Activation hardening (2026-11-07):** the workflow now checks out the sandbox fixture at the **exact reviewed commit** `dcc9f7c4235f015c1da4f78f2abd7994c14b3f4f`, and verifies that checkout SHA. It also requires `github.ref == 'refs/heads/main'` for its job. This prevents an eventual default-branch workflow from accidentally loading an unrelated/absent `main` fixture or running on a differently named ref. Source action SHAs for `actions/checkout` and `oven-sh/setup-bun` were confirmed readable from their upstream repositories at the exact refs. It still cannot execute until a reviewed default-branch workflow exists; this does **not** grant merge, enablement, or spending authority.

**Important operational limitation:** GitHub does not offer `workflow_dispatch` for a workflow existing only on a feature branch unless a version exists on the default branch. No default-branch change or dispatch has been made, no run occurred, and no Draft PR has been opened. Before activation: independently review the exact workflow diff, the existing workflow triggers and repository/org Actions policies, confirm billing/runner quota and branch protections, then request a discrete GO. Do not merge a dormant workflow into `main` simply to make it triggerable without that decision.

## Controlled execution proposal (not authorized or scheduled)

Use a separate disposable GitHub Actions runner / isolated test environment only after the operational owner authorizes any CI resource consumption:

1. Fetch upstream source with checkout pinned to the full SHA, check exact `git rev-parse HEAD`.
2. Install Bun 1.4.4, use upstream lockfile with a frozen dependency install, and avoid postinstall scripts unless individually reviewed. Do not pass any repository or organization secret.
3. Add this file into `packages/core/test/`; execute **only** this test via `bun test packages/core/test/mcp-permission-gate.test.ts` (or upstream's qualified focused test entrypoint).
4. Capture exact SHA, Bun version, exit code, assertions, tool call count, dependency source, runtime resource usage and CI job URL.
5. Remove all working files when the disposable job finishes. Keep results in the architecture Draft PR, not in production repositories.

Do not run this in the production VPS. No `pull_request`-triggered workflow has been added: opening a draft PR must not silently trigger a new resource-consuming workflow.

**GitHub workflow_dispatch caveat:** a newly defined workflow on a branch does not become manually dispatchable until it exists on the default branch; do not claim a Draft-only workflow can be executed with the Dispatch UI. A separately approved workflow strategy will be necessary before CI execution.

## Separate qualifications still NV

- Runtime denial from a model-driven user-facing Web/Desktop session.
- Credential isolation and denied access to unauthorized private repositories.
- Other network egress bypasses beyond the tests already reported.
- Authentik authorization, session/worktree isolation, revocation, and production rollback.

Do not merge, deploy, expose credentials or upgrade OpenCode as part of this fixture. Production migration **NO-GO**.
