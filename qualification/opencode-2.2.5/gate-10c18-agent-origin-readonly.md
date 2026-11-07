# Gate 10C.18 — Minimal agent-origin GitHub MCP test contract

**Status (2026-11-07):** source contract reviewed; execution **BLOCKED / NV**. This is a disposable-test specification, **not** a runnable deployment, model authorization, credential grant or production change.

**Owner:** [TsinjoOps/platform#100](https://github.com/TsinjoOps/platform/issues/100). Architectural history and prior evidence remain in [Draft PR #101](https://github.com/TsinjoOps/platform/pull/101), `ops/opencode/README.md`. Do not copy the runbook chronology into this fixture.

## Existing qualified baseline; do not repeat

- OpenCode 2.2.5 pinned upstream SHA `9bbb8ce18c80f099e0e448775f59d965ead40a21`; candidate image ID `sha256:4accab77deb837737d073b6499147ff61ac6aae2161ebb3c1a0bc0a7b8e8c268`.
- GitHub MCP server v2.1.0 binary SHA256 `cdd2dfbf269ca249f7e31148e20d072a22e224dd7cab0d5a176d146900b85324`.
- 10C.9h-quater: a *direct MCP client* read public `TsinjoOps/openhands-sandbox/README.md` through an allowlisted CONNECT relay. This was **not** an OpenCode agent call.
- 10C.10n: synthetic in-memory MCP deny/allow counters qualified; not a model-selected call.
- 10C.17h: isolated candidate API, hardening and cleanup qualified; its `network_mode: none` and publicly known synthetic API password **must not** be carried over to a networked candidate.

## Version-pinned agent execution contract

Reviewed source from `anomalyco/opencode@9bbb8ce18c80f099e0e448775f59d965ead40a21`:

| Source path | Git blob | Relevant fact |
| --- | --- | --- |
| `packages/cli/src/commands/handlers/run.ts` | `535dc90944272f16814c38cbdfa7fecbab28f96b` | `run` selects agent/model; `--auto`, `--yolo`, and `--dangerously-skip-permissions` bypass manual-approval expectations |
| `packages/cli/src/run/noninteractive.ts` | `9062df1be6c76a4d9311997220e6f91f08e4aac4` | `--format json` emits `tool_use` records; noninteractive mode rejects permission requests unless `auto` is enabled |
| `packages/core/src/tool/mcp.ts` | `7fbce8a31daecd2f15dda1a792bf0647f97c26fa` | MCP tool permission asserted **before** `mcp.callTool`; registry name derives from server/tool name |
| `packages/core/src/codemode/tool.ts` | `1fd67439350af825a52394fa955f2e2d880d3abc` | An agent may use outer `execute` with nested MCP `toolCalls`; actual inner call rows are in Code Mode tool metadata |
| `packages/core/src/codemode/fetch.ts` | `06d163012f8e63b2f4e0e2f2debbdf4ee0d3f30d` | Code Mode has an HTTP `fetch` escape route guarded by the `webfetch` permission |
| `packages/schema/src/mcp.ts` | `2d782dd6a40aa3ddf58d060bc182c8fca60c3812` | MCP local server has command/environment fields and Code Mode exposure; do not use an unqualified legacy config schema |

For this fixture, a hypothetical server name `github_probe` avoids JavaScript identifier ambiguity. Confirm the **actual** discovered tool path rather than inventing it. In Code Mode a successful invocation may be recorded as outer `tool_use(part.tool=execute)` with inner `toolCalls` entry for `github_probe.get_file_contents`; looking only for an outer GitHub tool name would incorrectly report failure.

## Preconditions before a separately authorized live run

1. Explicit GO for **one disposable TsinjoOps-only** test environment, model/provider identity, a bounded inference budget (maximum two agent attempts: positive and negative), an expendable **single-repository, contents-read-only** GitHub identity, and network egress to precisely reviewed endpoints. No Air Madagascar data, credentials or repositories.
2. Re-qualify the networked candidate configuration: unique project/container, distinct UID/home/workspace/config, read-only rootfs where compatible, no production binds, no Docker socket, no host ports, no shared `gh` login and no production OpenCode credentials. The prior offline synthetic password is forbidden. The OpenCode server must remain reachable only inside the disposable trust boundary.
3. Use the previously demonstrated temporary egress relay pattern. Provider and GitHub destinations need an explicit review; fail closed and test both an unauthorized destination and an attempted direct bypass. **An HTTP proxy allowlist alone does not prove all egress is restricted.**
4. Expose **only** GitHub MCP `get_file_contents` in `--read-only` mode, verify exact MCP catalogue before model invocation. The PAT must itself have only the sandbox repository permission; MCP filtering is not sufficient.
5. Explicit OpenCode permissions: allow only the exact MCP read action for the positive case; deny `webfetch`, shell/process commands, edits/writes, arbitrary alternative tools and subagent delegation. Verify effective policy (not merely config text). All other tools must fail closed, including the nested Code Mode `fetch` route.
6. Require a real inference-provider cost ceiling, a hard runtime cap, a maximum tool-call budget and no automatic retry. Source-review any purported request/turn limits against this pinned version before calling them enforced.
7. Keep evidence in a private, access-restricted local location. Native `--format json` records can contain prompt, tool input and content; **never publish raw logs, token values, provider responses or authorization headers.** Record only sanitized event shape, call counts, hashes, model/version and exit codes.

## Two controlled agent observations

**Positive (new disposable session):** Producer receives a bounded prompt asking it to read only `TsinjoOps/openhands-sandbox/README.md` through the discovered GitHub MCP tool and summarize a recognizable public fact. PASS only if: one native agent-origin `tool_use` is correlated with an inner successful `get_file_contents` (direct or Code Mode), downstream bridge receives **exactly one** matched `tools/call`, GitHub MCP returns success/nonempty content, the model response uses it, and *no other tool/network fallback* occurred. A model claim alone is **NV**, not PASS.

**Negative (fresh session, same sandbox/identity):** deny the exact MCP read action and explicitly retain `webfetch`/shell denies. Use an agent prompt requiring the same read. PASS for enforcement only if the native trace records a denied attempted MCP call, the downstream bridge receives **zero** calls, there is no direct HTTP/shell/other-tool fallback, and no file content is obtained. If the model simply never attempts a call, mark the permission-enforcement result **NV**, not PASS.

If the bridge does not expose a verified per-request counter/receipt, the gate is **BLOCKED**; do not infer downstream invocation from agent JSON. If either case times out, retries, makes extra calls or leaks a denied path, mark **FAIL/BLOCKED** with no automated rerun.

## Completion and rollback

- Preserve sanitized: OpenCode and MCP exact IDs, model/provider and approved limits, accepted rules, effective network-denial probes, native outer/inner event identities, bridge counters and result, runtime/expense summary, start/end state and exact exit status.
- Stop/delete **only** the owned disposable test project and relay; verify no residue, token-file cleanup, and unchanged `opencode-lab` and `opencode-sw-overlay` IDs. Do not silently rotate or revoke the historical PAT. An authorized test identity must have an explicit revocation owner/plan.
- A read-only PASS would **not** approve private repo access, Web/Desktop, code writes, Draft PR issuance, auth/backup/restore, migration or release. All remain separate gates.
- Existing sandbox PAT is documented as expiring **2026-11-13**; its current scope/validity, suitability and any change require inspection and GO.

**Gate decision:** 10C.18 source/test-contract **PASS (documentary)**; actual model-origin MCP test **BLOCKED / NV**; OpenCode 2.2.5 production migration **NO-GO**.
