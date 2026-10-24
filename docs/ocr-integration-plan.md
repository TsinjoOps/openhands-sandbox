# Local OCR integration — Issue #8

Status: **IMPLEMENTED ON PR #9; OFFLINE CI PASS; LIVE OCR NOT YET QUALIFIED** (2026-10-24).

## Decision and boundaries

- `TsinjoOps/agent-workflow-lab` is private and `TsinjoOps/openhands-sandbox` is public; a public workflow cannot directly call the private reusable workflow. **Use local OCR integration in the public sandbox**, approved by the project owner. Do not add a shared caller.
- The local `.github/workflows/independent-code-review.yml` and `review_decision.py` originate from the qualified lab mechanism. The review policy is adapted locally in `.opencodereview/rule.json` for Frappe v16.50.
- OCR is explicitly triggered by an authorized collaborator posting exactly `/open-code-review` on a same-repository PR. A producer push only invalidates a previous decision; it does not trigger a paid review.
- `OPENROUTER_API_KEY` is a repository Actions secret, configured by the owner (reported 2026-10-24). Its **runtime accessibility has not yet been verified**; never print or commit its value.
- The OCR action and evaluator are pinned; `OCR_NO_UPDATE=1`. The configured model is `qwen/qwen3.8-27b`; token budget is 200,000, and budget exhaustion/incomplete evidence must yield BLOCKED.
- OCR results are independent COMMENT-style review evidence, **not an approving human review**, merge authority, deployment authority or UAT.
- Trusted evaluator checkout uses the default-branch workflow SHA, not PR-controlled code. Fork PRs are rejected. A current-head mismatch yields STALE.

## Evidence and status

- PR #9: https://github.com/TsinjoOps/openhands-sandbox/pull/9 — draft pending human review and merge.
- Offline workflows `ocr-preflight` and `ocr-decision-tests`: PASS on `896a512620dea6311a7f05b7c3ea81c6e08444fd` (before this documentation change). They test negative metadata cases, evaluator failure behavior and static guard presence; **they do not demonstrate a real OCR run or live secret access**.
- PR #7: https://github.com/TsinjoOps/openhands-sandbox/pull/7 — candidate SHA `b65b73fc549c06cf51b6c567241c313647d59a63`, CI and human UAT PASS; OCR not yet executed. Do not push or merge it to bootstrap OCR.
- Private lab PR #127 proposed a reusable workflow but cannot be consumed by this public repository. Treat that proposal as superseded for this sandbox; do not merge it as a dependency.

## Release gates

- [x] Confirm public/private visibility and select local integration.
- [x] Add local review workflow, fail-closed evaluator and Frappe-specific rules.
- [x] Add offline tests; confirm two green checks on commit `896a5126`.
- [x] Owner reports GitHub Actions secret created; value never shared.
- [ ] Review final diff and latest CI; resolve any workflow or documentation inconsistencies.
- [ ] Mark PR #9 Ready for review, obtain independent human APPROVE, then merge under ruleset.
- [ ] Confirm installed default-branch workflow and secret availability in a controlled run; authorize the first paid OCR run explicitly.
- [ ] Run `/open-code-review` on PR #7 only after authorization, and validate exact SHA, complete coverage, publication and PASS/FAIL/BLOCKED/STALE.
- [ ] Keep human approval, UAT and merge as separate controls.

## Scope exclusions

No VPS work, no cross-repository secret sharing, no automatic paid review on push, no change to PR #7, and no claim that offline CI proves OCR PASS.
