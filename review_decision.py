"""Fail-closed decision logic for independent OpenCodeReview evidence.

This module intentionally uses only the Python standard library.  It converts
raw OCR evidence plus the current GitHub PR head into one of four states:

PASS    - complete, current, publishable review with no material findings.
FAIL    - complete/current review with at least one medium/high/critical finding.
BLOCKED - review evidence is incomplete, truncated, unavailable, or unverifiable.
STALE   - the PR head changed after the reviewed SHA was captured.

The evaluator is deliberately independent from the implementation producer and
does not grant merge/deploy authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


MATERIAL_SEVERITIES = {"critical", "high", "medium"}
DEFAULT_POLICY_VERSION = "v1"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _valid_sha(value: str) -> bool:
    return bool(_SHA_RE.fullmatch(value))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _item_ids(items: Any) -> set[str]:
    result: set[str] = set()
    for item in _as_list(items):
        if isinstance(item, dict):
            item_id = item.get("item_id")
            if isinstance(item_id, str) and item_id:
                result.add(item_id)
    return result


def _coverage_ids(
    coverage: dict[str, Any], field: str, schema_errors: list[str]
) -> set[str]:
    raw = coverage.get(field)
    if not isinstance(raw, list):
        schema_errors.append(f"coverage.{field} is missing or is not a list")
        return set()

    ids = _item_ids(raw)
    if len(ids) != len(raw):
        schema_errors.append(
            f"coverage.{field} contains malformed or duplicate item_id values"
        )
    return ids


def evaluate_review(
    payload: dict[str, Any] | None,
    *,
    expected_head: str,
    current_head: str,
    ocr_outcome: str,
    comments_failed: int = 0,
    checkpoint_after: str = "",
    require_checkpoint: bool = True,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> dict[str, Any]:
    """Evaluate OCR evidence without inferring success from a green workflow."""

    expected_head = (expected_head or "").strip()
    current_head = (current_head or "").strip()
    ocr_outcome = (ocr_outcome or "").strip().lower()

    result: dict[str, Any] = {
        "state": "BLOCKED",
        "policy_version": policy_version,
        "reviewed_sha": "",
        "expected_sha": expected_head,
        "current_sha": current_head,
        "exact_range": "",
        "terminal_state": "",
        "budget_exceeded": False,
        "tokens": 0,
        "findings_total": 0,
        "material_findings": 0,
        "low_findings": 0,
        "unknown_findings": 0,
        "coverage": {
            "selected": 0,
            "completed": 0,
            "reused": 0,
            "failed": 0,
            "waived": 0,
        },
        "comments_failed": int(comments_failed or 0),
        "checkpoint_after": checkpoint_after or "",
        "reasons": [],
    }

    if not _valid_sha(expected_head):
        result["reasons"].append("expected reviewed SHA is missing or malformed")
        return result
    if not _valid_sha(current_head):
        result["reasons"].append("current PR head could not be verified as a full Git SHA")
        return result

    # A producer push after invocation makes the decision stale regardless of
    # what the old OCR run eventually reports.
    if expected_head != current_head:
        result["state"] = "STALE"
        result["reasons"].append(
            f"current PR head {current_head} differs from reviewed target {expected_head}"
        )
        return result
    if ocr_outcome != "success":
        result["reasons"].append(f"OCR step outcome is {ocr_outcome or 'unknown'}")
        return result
    if not isinstance(payload, dict):
        result["reasons"].append("OCR result JSON is missing or invalid")
        return result

    schema_errors: list[str] = []

    manifest_raw = payload.get("manifest")
    if not isinstance(manifest_raw, dict):
        schema_errors.append("manifest is missing or is not an object")
    manifest = manifest_raw if isinstance(manifest_raw, dict) else {}

    input_raw = manifest.get("input")
    if not isinstance(input_raw, dict):
        schema_errors.append("manifest.input is missing or is not an object")
    input_info = input_raw if isinstance(input_raw, dict) else {}

    summary_raw = payload.get("summary")
    if not isinstance(summary_raw, dict):
        schema_errors.append("summary is missing or is not an object")
    summary = summary_raw if isinstance(summary_raw, dict) else {}

    coverage_raw = manifest.get("coverage")
    if not isinstance(coverage_raw, dict):
        schema_errors.append("manifest.coverage is missing or is not an object")
    coverage = coverage_raw if isinstance(coverage_raw, dict) else {}

    reviewed_sha = input_info.get("resolved_head")
    reviewed_sha = reviewed_sha if isinstance(reviewed_sha, str) else ""
    result["reviewed_sha"] = reviewed_sha
    exact_range = input_info.get("exact_range")
    result["exact_range"] = exact_range if isinstance(exact_range, str) else ""

    terminal_state = manifest.get("terminal_state")
    terminal_state = terminal_state if isinstance(terminal_state, str) else ""
    result["terminal_state"] = terminal_state
    schema_version = manifest.get("schema_version")
    result["schema_version"] = schema_version if isinstance(schema_version, str) else ""

    total_tokens = summary.get("total_tokens")
    if not isinstance(total_tokens, int) or isinstance(total_tokens, bool) or total_tokens < 0:
        schema_errors.append("summary.total_tokens is missing or is not a non-negative integer")
        total_tokens = 0
    result["tokens"] = total_tokens

    budget_exceeded = summary.get("budget_exceeded") is True
    warnings = _as_list(payload.get("warnings"))
    if any(
        isinstance(w, dict) and w.get("type") == "token_budget_reached"
        for w in warnings
    ):
        budget_exceeded = True
    result["budget_exceeded"] = budget_exceeded

    selected = _coverage_ids(coverage, "selected", schema_errors)
    completed = _coverage_ids(coverage, "completed", schema_errors)
    reused = _coverage_ids(coverage, "reused", schema_errors)
    failed = _coverage_ids(coverage, "failed", schema_errors)
    waived = _coverage_ids(coverage, "waived", schema_errors)
    result["coverage"] = {
        "selected": len(selected),
        "completed": len(completed),
        "reused": len(reused),
        "failed": len(failed),
        "waived": len(waived),
    }

    comments_raw = payload.get("comments")
    if not isinstance(comments_raw, list):
        schema_errors.append("comments is missing or is not a list")
        comments_raw = []
    if any(not isinstance(comment, dict) for comment in comments_raw):
        schema_errors.append("comments contains a non-object finding")
    comments = [c for c in comments_raw if isinstance(c, dict)]
    material = [
        c
        for c in comments
        if str(c.get("severity", "")).strip().lower() in MATERIAL_SEVERITIES
    ]
    low = [
        c
        for c in comments
        if str(c.get("severity", "")).strip().lower() == "low"
    ]
    unknown = [
        c
        for c in comments
        if str(c.get("severity", "")).strip().lower()
        not in MATERIAL_SEVERITIES | {"low"}
    ]
    result["findings_total"] = len(comments)
    result["material_findings"] = len(material)
    result["low_findings"] = len(low)
    result["unknown_findings"] = len(unknown)

    blocking_reasons: list[str] = list(schema_errors)
    if payload.get("status") != "complete":
        blocking_reasons.append(
            f"OCR status is {payload.get('status', 'missing')!r}, not 'complete'"
        )
    if result["schema_version"] != "ocr.run-manifest/v1":
        blocking_reasons.append(
            f"unsupported or missing OCR manifest schema {result['schema_version'] or 'unknown'}"
        )
    if terminal_state != "complete":
        blocking_reasons.append(
            f"manifest terminal_state is {terminal_state or 'missing'}, not 'complete'"
        )
    if reviewed_sha != expected_head:
        blocking_reasons.append(
            f"resolved reviewed SHA {reviewed_sha or 'missing'} does not match target {expected_head}"
        )
    if budget_exceeded:
        blocking_reasons.append("OCR token budget was exceeded or truncated")
    summary_comments = summary.get("comments")
    if (
        not isinstance(summary_comments, int)
        or isinstance(summary_comments, bool)
        or summary_comments < 0
    ):
        blocking_reasons.append(
            "summary.comments is missing or is not a non-negative integer"
        )
    elif summary_comments != len(comments):
        blocking_reasons.append(
            f"summary reports {summary_comments} finding(s) but result contains {len(comments)}"
        )
    if unknown:
        blocking_reasons.append(
            f"{len(unknown)} finding(s) have missing or unsupported severity"
        )
    if failed:
        blocking_reasons.append(f"{len(failed)} selected coverage item(s) failed")
    if waived:
        blocking_reasons.append(f"{len(waived)} selected coverage item(s) were waived")

    classifications = {
        "completed": completed,
        "reused": reused,
        "failed": failed,
        "waived": waived,
    }
    classified = set().union(*classifications.values())
    extra = classified - selected
    if extra:
        blocking_reasons.append(
            f"{len(extra)} classified coverage item(s) are not in selected"
        )

    names = list(classifications)
    overlaps: set[str] = set()
    for index, left_name in enumerate(names):
        for right_name in names[index + 1 :]:
            overlaps |= classifications[left_name] & classifications[right_name]
    if overlaps:
        blocking_reasons.append(
            f"{len(overlaps)} selected coverage item(s) have multiple classifications"
        )

    covered = completed | reused
    missing = selected - covered
    if missing:
        blocking_reasons.append(
            f"{len(missing)} selected coverage item(s) are neither completed nor reused"
        )

    if result["comments_failed"] < 0:
        blocking_reasons.append("review publication count output is missing or invalid")
    elif result["comments_failed"] > 0:
        blocking_reasons.append(
            f"{result['comments_failed']} review comment(s) failed to publish"
        )

    if require_checkpoint:
        if not checkpoint_after:
            blocking_reasons.append("qualifying checkpoint was not advanced")
        elif checkpoint_after != expected_head:
            blocking_reasons.append(
                f"checkpoint {checkpoint_after} does not match reviewed target {expected_head}"
            )

    if blocking_reasons:
        result["reasons"].extend(blocking_reasons)
        result["state"] = "BLOCKED"
        return result

    if material:
        result["state"] = "FAIL"
        result["reasons"].append(
            f"{len(material)} material finding(s) at medium/high/critical severity"
        )
        return result

    result["state"] = "PASS"
    if low:
        result["reasons"].append(
            f"{len(low)} low-severity finding(s) remain non-blocking"
        )
    else:
        result["reasons"].append("complete current review with no material findings")
    return result


def render_markdown(decision: dict[str, Any]) -> str:
    state = str(decision.get("state", "BLOCKED"))
    icon = {
        "PASS": "✅",
        "FAIL": "❌",
        "BLOCKED": "⛔",
        "STALE": "⚪",
    }.get(state, "⛔")

    coverage = decision.get("coverage") or {}
    reasons = decision.get("reasons") or []
    reason_lines = "\n".join(f"- {reason}" for reason in reasons) or "- none"
    reviewed_marker = decision.get("reviewed_sha") or decision.get("expected_sha") or ""
    current_marker = decision.get("current_sha") or ""

    return f"""<!-- ocr-decision-status -->
<!-- ocr-decision-state:{state} -->
<!-- ocr-decision-policy:{decision.get('policy_version') or 'unknown'} -->
<!-- ocr-reviewed-sha:{reviewed_marker} -->
<!-- ocr-current-sha:{current_marker} -->
## {icon} Independent review decision — {state}

| Evidence | Value |
| --- | --- |
| Reviewed SHA | \`{decision.get('reviewed_sha') or decision.get('expected_sha') or 'unknown'}\` |
| Current PR head | \`{decision.get('current_sha') or 'unknown'}\` |
| Review range | \`{decision.get('exact_range') or 'not available'}\` |
| Terminal state | \`{decision.get('terminal_state') or 'unknown'}\` |
| Token budget exceeded | **{str(bool(decision.get('budget_exceeded'))).lower()}** |
| Tokens reported | {decision.get('tokens', 0)} |
| Findings | {decision.get('findings_total', 0)} total / {decision.get('material_findings', 0)} material / {decision.get('low_findings', 0)} low / {decision.get('unknown_findings', 0)} unknown |
| Coverage | {coverage.get('selected', 0)} selected = {coverage.get('completed', 0)} completed + {coverage.get('reused', 0)} reused + {coverage.get('failed', 0)} failed + {coverage.get('waived', 0)} waived |
| Publication failures | {decision.get('comments_failed', 0)} |
| Checkpoint after | \`{decision.get('checkpoint_after') or 'none'}\` |

### Decision basis
{reason_lines}

This is **review evidence**, not merge/deployment authority. Enforceable private-repository branch protection remains a separate control.
"""


def _load_payload(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_github_output(values: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="/tmp/ocr-result.json")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--current-head", required=True)
    parser.add_argument("--ocr-outcome", required=True)
    parser.add_argument("--comments-failed", type=int, default=0)
    parser.add_argument("--checkpoint-after", default="")
    parser.add_argument("--policy-version", default=DEFAULT_POLICY_VERSION)
    parser.add_argument("--output-json", default="/tmp/review-decision.json")
    parser.add_argument("--output-markdown", default="/tmp/review-decision.md")
    args = parser.parse_args()

    decision = evaluate_review(
        _load_payload(Path(args.result)),
        expected_head=args.expected_head,
        current_head=args.current_head,
        ocr_outcome=args.ocr_outcome,
        comments_failed=args.comments_failed,
        checkpoint_after=args.checkpoint_after,
        require_checkpoint=True,
        policy_version=args.policy_version,
    )

    Path(args.output_json).write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown = render_markdown(decision)
    Path(args.output_markdown).write_text(markdown, encoding="utf-8")

    _write_github_output(
        {
            "state": str(decision["state"]),
            "reviewed_sha": str(decision.get("reviewed_sha") or ""),
            "current_sha": str(decision.get("current_sha") or ""),
            "material_findings": str(decision.get("material_findings", 0)),
            "budget_exceeded": str(bool(decision.get("budget_exceeded"))).lower(),
        }
    )
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
