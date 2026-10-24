# OCR integration plan — Issue #8

Status: **DESIGN / NOT QUALIFIED**. This file is a proposal, not proof of OCR availability.

## Current state

- `openhands-sandbox` has no independent OCR workflow on its default branch.
- `agent-workflow-lab` contains the qualified `independent-code-review.yml`, `review_decision.py` and repository-specific `.opencodereview/rule.json`.
- PR #7 is held at `b65b73fc549c06cf51b6c567241c313647d59a63`; CI and human UAT are PASS. **Do not push to PR #7** to introduce OCR.
- The active `Protect main from agents` ruleset requires an approving review, including last-push approval; OCR does not replace a human approver.

## Preferred design

1. **Shared reviewer policy:** extract the qualified OCR workflow/evaluator into a version-pinned reusable workflow or action owned by `agent-workflow-lab`. This requires a separate reviewed change there. The calling repository must not checkout/execute PR-controlled scripts with `OPENROUTER_API_KEY`.
2. **Local trigger:** minimal `issue_comment` workflow on `openhands-sandbox/main`, accepting only exact `/open-code-review` from authorized collaborators on same-repository PRs; delegate to the trusted, pinned reviewer. Verify that reusable-workflow event context, PR number, head SHA, and permission model remain correct before implementation.
3. **Local review rules:** scoped `.opencodereview/rule.json` covering Frappe DocType schema/validation, composite uniqueness and race handling, migrations, tests, packaging, privilege boundaries and evidence claims. Do not copy the lab's unrelated path rules.
4. **Secret:** verify `OPENROUTER_API_KEY` is configured for the calling workflow without printing it. GitHub repository secrets are not automatically shared across repositories. If absent, stop before invoking OCR.
5. **Cost:** one explicitly triggered review, no LLM on pushes, a bounded per-run budget appropriate to this small diff, with incomplete/budget-exceeded reviews classified BLOCKED rather than PASS.
6. **Fail-closed:** independently validate structured evidence, exact reviewed/current SHA, complete coverage, no material findings, successful GitHub publication, and STALE on a new push. Preserve PASS/FAIL/BLOCKED/STALE semantics.
7. **Human boundary:** OCR publishes a COMMENT-style review/decision only; a separate authorized human must APPROVE before merging.

## Implementation gates

- [ ] Verify reusable-workflow feasibility and event/secret semantics with a non-LLM test.
- [ ] Qualify shared component in `agent-workflow-lab` without regressing its existing workflow.
- [ ] Add minimal pinned caller and scoped rules to this branch; validate YAML and permissions.
- [ ] Test no-secret, invalid-command, unauthorized-actor, stale-SHA and incomplete-evidence paths without an LLM call.
- [ ] Verify secret availability privately, then explicitly authorize one paid OCR run.
- [ ] Confirm OCR decision on the exact head SHA of PR #7; keep the original UAT SHA intact.
- [ ] Obtain independent human approval under the active ruleset.

## Rejected shortcut

Do **not** copy the 25 KB workflow into this repository without its evaluator and tests, weaken the `main` ruleset, or treat a green CI check as an OCR PASS.

Reference: https://github.com/TsinjoOps/openhands-sandbox/issues/8
