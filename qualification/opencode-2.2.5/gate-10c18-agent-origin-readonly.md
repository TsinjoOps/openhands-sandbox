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

**Positive (new disposable session):** Producer receives a bounded prompt asking it to read only `TsinjoOps/openhands-sandbox/README.md` at the pinned commit `32ede1461b5120beabb318167c8cc914d1145f2a` (file Git blob `e1927d6f996fbe86c85defcbe3833ba296ea883c`) through the discovered GitHub MCP tool and summarize a recognizable public fact; the answer must not be supplied in the prompt. Validate the MCP input schema and pass the immutable commit via its supported SHA/ref argument. PASS only if: one native agent-origin `tool_use` is correlated with an inner successful `get_file_contents` (direct or Code Mode), downstream bridge receives **exactly one** matched `tools/call`, GitHub MCP returns success/nonempty content, the model response uses it, and *no other tool/network fallback* occurred. A model claim alone is **NV**, not PASS.

**Negative (fresh session, same sandbox/identity):** deny the exact MCP read action and explicitly retain `webfetch`/shell denies. Use an agent prompt requiring the same read. PASS for enforcement only if the native trace records a denied attempted MCP call, the downstream bridge receives **zero** calls, there is no direct HTTP/shell/other-tool fallback, and no file content is obtained. If the model simply never attempts a call, mark the permission-enforcement result **NV**, not PASS.

If the bridge does not expose a verified per-request counter/receipt, the gate is **BLOCKED**; do not infer downstream invocation from agent JSON. If either case times out, retries, makes extra calls or leaks a denied path, mark **FAIL/BLOCKED** with no automated rerun.

## Completion and rollback

- Preserve sanitized: OpenCode and MCP exact IDs, model/provider and approved limits, accepted rules, effective network-denial probes, native outer/inner event identities, bridge counters and result, runtime/expense summary, start/end state and exact exit status.
- Stop/delete **only** the owned disposable test project and relay; verify no residue, token-file cleanup, and unchanged `opencode-lab` and `opencode-sw-overlay` IDs. Do not silently rotate or revoke the historical PAT. An authorized test identity must have an explicit revocation owner/plan.
- A read-only PASS would **not** approve private repo access, Web/Desktop, code writes, Draft PR issuance, auth/backup/restore, migration or release. All remain separate gates.
- Existing sandbox PAT is documented as expiring **2026-11-13**; its current scope/validity, suitability and any change require inspection and GO.

**Gate decision:** 10C.18 source/test-contract **PASS (documentary)**; actual model-origin MCP test **BLOCKED / NV**; OpenCode 2.2.5 production migration **NO-GO**.


## Static preflight and permission fixtures (2026-11-07)

- `preflight-gate-10c18-readonly.sh`, Git blob `4b130b404a22dfc4edff0585ca0424125584c112`, inspects **only** host command availability, exact candidate image ID, production container IDs/states, and public resource counters. No network, container creation, secrets, model invocation or production mutation. Source hash/syntax **PASS**; operator VPS execution **PASS (host inventory only)** on 2026-11-07.
- `config-gate10c18-positive.json`, blob `36f8f6ae099505765f859e8aabdb667bdaa51a2f`, defines a default-deny test agent with `execute` and one exact MCP read permission ALLOW.
- `config-gate10c18-negative.json`, blob `161f61208f21c3d0537bfd1eed55c3f95f5d07ea`, retains Code Mode `execute` but explicitly DENIES the exact MCP read permission.
- `test_gate10c18_config.py`, blob `91855cd5327ad263ccae450041aff91217a6b82f`: Python stdlib structural/order checks PASS locally (1 test with positive/negative and alternative-tool subcases). The Python evaluator deliberately checks only exact action names and `*`, not the full OpenCode wildcard implementation. **This is not native policy enforcement evidence.**

All four files are uncredentialed and contain **no provider, MCP command, egress or deployment configuration**. The exact server/tool naming must be confirmed from the live MCP catalogue. OpenCode V2 source at `packages/core/src/permission.ts` (blob `f3cd4a65e058b99c1561b404da148305c41c5d5f`) uses **last matching rule wins**; the config agent loader at `packages/core/src/config/plugin/agent.ts` (blob `e78ad1243bac5a67d926c4fb23bbe73d6b57588b`) appends global and agent-specific ordered rules. Runtime inherited rules, session permissions, plugins and identity remain to be inspected; a static JSON assertion cannot establish the deployed effective policy.

**Next required observation:** qualify provider cost limit (2 USD maximum proposed for this trial), dedicated GitHub read-only scope, network egress boundary, bridge receipts and runtime configuration before any actual model call. No identity, cost or network trial has been activated by these repository edits. Positive/negative model trial still **NV**.


## Gate 10C.18a — VPS operator host baseline PASS (2026-11-07)

Operator executed the exact `preflight-gate-10c18-readonly.sh` from sandbox commit `a78a4c799661bf3d9c20a398c64db96fbf3bd465`; the separately pinned SHA-256 `1cb1ba9bb65d0a43e8cc782d21c05be2ef420ea0f17dddcb89b3d94df5ac2691` matched and `bash -n` passed. The script completed `PREFLIGHT_HOST_BASELINE=PASS` with exit 0. Observed host commands `docker`, `python3`, `curl`, `openssl`, `sha256sum`, `nsenter`, `socat`, `timeout` present, daemon and Compose queried, candidate image exact ID PASS. Container `opencode-lab` ID `254b9a2114a909531ed96b65f2a6387c6f3ad27c1ebc31cbf583749d101756ca` RUNNING; `opencode-sw-overlay` ID `2480f17d226b890c66f0b934f0c92878871719a48c2ed9983c5adbdc17d6d2b8` RUNNING. These are a **pre-execution baseline**, not a post-test unchanged-ID comparison.

Resource sample: MemTotal 11,956,728 kB; MemAvailable 5,427,672 kB (~5.18 GiB), SwapTotal 4,194,300 kB, SwapFree 313,780 kB (~3.70 GiB used, 92.5% occupied), `/tmp` available 36,558,508 kB, `/run` 1,188,584 kB. Swap occupancy alone does **not** prove active swap pressure; no PSI, swap-in/out or concurrent model workload sampled in this step. Do not infer sustained headroom.

**PASS** = host tools, candidate image, and live baseline containers inspected as planned. **NV** = GitHub PAT scope/expiry at runtime, provider key/model and billing ceiling, actual MCP binary availability, egress allowlist, bridge receipts and agent invocation. No secrets were read, no container was created and no outbound request was made by the script. **Gate 10C.18 model-origin invocation remains BLOCKED/NV**, production 2.2.5 migration NO-GO.

### Pre-execution identity and budget gate (OPEN — not activated)

- **Model provider choice:** OpenRouter is a candidate for a separate, disposable test-only key. Its official [limits documentation](https://openrouter.ai/docs/api-reference/limits) describes per-key credit caps and `GET /api/v1/key` returning `limit` / `limit_remaining`; [API key creation](https://openrouter.ai/docs/api/api-reference/api-keys/create-keys) accepts `limit` USD and optional `limit_reset`, with no reset when null. Propose a **non-resetting 2 USD total key cap**, short key expiry, sequential positive then negative run, and no provider-owned retry/fallback until verified. Provider enforcement and key identity **NV**; a proposed cap is not an enforced cap. **No key or management credential is stored in GitHub.**
- **GitHub:** operator must verify on the GitHub fine-grained token settings that the account/repository selection is *only* `TsinjoOps/openhands-sandbox`, `Contents: read` (and automatically required metadata), expiration on/after the test, no write/admin rights; never paste its plaintext value or reuse `gh` admin login. Previous successful read of a public file does **not** prove token repository scope. Scope validation via actual inaccessible private repo is a separate gate requiring separate authority, not implied here.
- **Runtime:** before network activation, independently review the exact provider and GitHub egress endpoints, isolation from production identities, effective permissions including `webfetch` denial, bridge-level receipts and provider budget evidence. If any remain NV, **BLOCKED** and do not run model inference. No permanent infrastructure, external access or credentials introduced by this documentation.

## Gate 10C.18b — Fine-grained PAT settings screenshot (2026-11-07)

**PASS (visible UI configuration, not persisted token proof):** screenshot of the GitHub fine-grained PAT named `tsinjoops-opencode-mcp-poc-read`, issued for the `TsinjoOps` organization, shows `Only select repositories` with exactly one repository selected: `TsinjoOps/openhands-sandbox`. The four displayed repository permissions are `Contents: Read-only`, `Issues: Read-only`, `Metadata: Read-only (Required)`, and `Pull requests: Read-only`; no write permission is visible. Expiration is Friday **2026-11-13**. An `Update`/`Cancel` editing interface is visible, so saved/effective settings and token acceptance are **NV**.

**Least privilege adjustment proposed, not performed:** Gate 10C.18 only requires `get_file_contents`, hence Contents read + required Metadata read. Issues/Pull requests read should be removed for this gate unless a separately approved extended test requires them. Do not silently modify the token or its expiration.

**GitHub UI caveat:** the repository-selection control explicitly states public repositories remain readable (read-only), even when `Only select repositories` is chosen. Accordingly **this PAT does not enforce a universal one-repository boundary for public read requests**. The agent must also be constrained by MCP tool selection, effective deny rules, allowed outbound network destinations and auditable single-tool receipts. No secret value, access token plaintext, or repo outside TsinjoOps was inspected.

**Gate verdict:** UI configuration **PASS with qualification**; save/effective permissions, actual key usability, model provider key, spending cap, egress and agent invocation remain **NV/BLOCKED**. Do not infer a runtime GitHub access test from this screenshot.

## Gate 10C.18b-bis — Minimal PAT configuration reported saved (2026-11-07)

The operator reports **Updated** after reducing the GitHub fine-grained PAT `tsinjoops-opencode-mcp-poc-read` to **two repository permissions**. Screenshot of the configuration displays `Only select repositories` with exactly `TsinjoOps/openhands-sandbox`, `Contents: Read-only`, and `Metadata: Read-only (Required)`. `Issues` and `Pull requests` are no longer present. The prior screenshot recorded expiration **2026-11-13**; this new cropped screenshot does not independently re-show the expiration.

**PASS — minimal intended permission configuration and operator-reported save.** **NV — independently re-fetched post-save settings, actual credential scope/effectiveness and revocation.** The screenshot still contains `Update`/`Cancel` controls in the editing interface; do not misrepresent it as runtime token proof. The GitHub UI explicitly states that a fine-grained PAT can still read other public repositories; public-repository isolation must therefore be provided by the scoped MCP request boundary, not the token's repo picker alone.

**Next gate:** provider identity with a separately verifiable non-resetting **2 USD** cap and short expiration, then immutable network/security admission and live agent-origin invocation. No token or provider secret copied into documentation; no production changes.


## Gate 10C.18c — OpenRouter test-key admission checker (2026-11-07)

**Source:** `verify-openrouter-key-cap.py`, sandbox commit `fa918ee2518598bde934001ce836e8976dc6ad30`, Git blob `75598e244ffb242828efbeefcdf1d186d86652d5`, SHA-256 `2a31ed1e27d80bbe814e51145a8b6bd3f63781b97201e677b98245eb6b041951`. An identical local source reproduced the Git blob and SHA-256. Python compile and `--self-test` **PASS**, including 12 scenarios (valid 2026-11-14 16:38 UTC expiry, invalid exhausted/extended/renewing keys). Actual authenticated provider call **NV**.

**Version-aligned contract:** official [GET /api/v1/key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key) includes `limit`, `limit_remaining`, `limit_reset`, `is_management_key`, `is_provisioning_key`, `expires_at`. Admission requires 2 USD, 0..2 USD remaining, no reset, not management/provisioning, expiry after current UTC but by 2026-11-15 00:00 UTC. One direct TLS GET, no retries or redirects and only categorical output; the provider key itself must be held in a private same-owner non-symlink file.

**Operator screenshot checkpoint 10C.18d (2026-11-07):** OpenRouter workspace `Personal / TsinjoOps` displays enabled key `tsinjoops-gate10c18`, `Credit limit: $2`, `Reset limit: N/A`, expiration **2026-11-14 19:38 GMT+3**, spending **$0.00**, `Last used: Never`. This is **PASS UI configuration**, not proof that the provider authenticated the key or enforced billing. The previously proposed Nov 13 expiry is superseded by the short-lived actual date; it is still a limited-duration trial.

**Access rule:** no OpenRouter plaintext key in GitHub, chats, logs or shell arguments. Check key metadata first on a trusted operator computer, not in `opencode-lab` and not by mounting the key into a VPS container. Do not incur model spend until network and identity containment is reviewed. **Provider authenticated admission NV; model-origin GitHub MCP invocation BLOCKED.**

## Gate 10C.18e — Authenticated OpenRouter admission PASS (operator VPS, 2026-11-07)

**Observed command output:** the operator ran `verify-openrouter-key-cap.py` from immutable GitHub commit `fa918ee2518598bde934001ce836e8976dc6ad30` on `ubuntu@vps-deabe3bd`. `sha256sum -c` reported `check.py: OK`; the offline self-test reported `OPENROUTER_KEY_POLICY_SELF_TEST=PASS`, `OFFLINE_TEST_CASES=12`, `NETWORK_REQUEST=NO`. Then a masked interactive key input was written under a private `/dev/shm/tsinjoops-10c18.*` temporary directory and passed to the verifier, which reported `OPENROUTER_KEY_ADMISSION=PASS`, `INFERENCE_CALLS=0`, and shell returned to prompt. By the pinned checker source, this entails an authenticated **metadata-only GET** to `https://openrouter.ai/api/v1/key` whose returned data met the configured cap/expiry/non-management criteria. The script has no inference endpoint.

**Evidence boundary:** provider admission **PASS** (operator evidence, under pinned verifier); **not** proof of cost enforcement under concurrent use or OpenCode-internal credential delivery. The script was intended for the **operator local Ubuntu desktop**, but was actually run on the **VPS**. Its `trap` should delete the temporary directory on normal exit, and output confirms exit to the prompt; independent absence of residual temporary files, process-memory exposure, host backups/monitoring exposure and any possible credential capture are **NV**. An authenticated metadata GET did send the secret to OpenRouter over TLS and an authorized use of the same key within the VPS is now a new custody condition. Do not log, reuse in production `opencode-lab`, or claim the key is compromised without evidence. If VPS trust cannot be established, revoke/replace this **dedicated** key via the account owner before the live agent gate; do not silently rotate it.

**Next qualification:** design and verify a disposable network trust boundary for `api.github.com:443` plus the **minimum necessary** OpenRouter provider endpoint, and an MCP `get_file_contents` call receipt proving an exact `owner=TsinjoOps, repo=openhands-sandbox, path=README.md, sha=32ede1461b5120beabb318167c8cc914d1145f2a` request. A general HTTPS allowlist for `api.github.com` is **insufficient** to restrict repository arguments; add pre-forward MCP argument validation and response audit, or mark repo-boundary control NV. Test negative tool permission and denied direct HTTP/shell fallbacks. Avoid re-running 10C.17 bootstrap or repeating the completed provider key GET absent a new reason.

**Decision:** 10C.18e provider identity/limit/expiry verification **PASS (scoped)**; model selected MCP call **NV/BLOCKED**, egress proof **NV**, strict repo boundary **NV**, production migration **NO-GO**.
