#!/usr/bin/env python3
"""Offline fixed-term floor of OCR 1.13.0 estimate.go heuristic, NOT actual billing."""
import argparse
import json
from pathlib import Path

PROMPT_OVERHEAD = 2000
MAIN_ROUNDS = 7
OUTPUT_PER_ROUND = 700
PLAN_OUTPUT = 400
PER_FILE_FLOOR = PROMPT_OVERHEAD * (1 + MAIN_ROUNDS) + PLAN_OUTPUT + OUTPUT_PER_ROUND * MAIN_ROUNDS


def analyze(preview: dict, budget: int) -> dict:
    if not isinstance(preview, dict) or not isinstance(preview.get("files"), list):
        raise ValueError("Preview manifest missing files list")
    if not isinstance(budget, int) or budget <= 0:
        raise ValueError("Budget must be positive")
    entries = preview["files"]
    if not all(isinstance(e, dict) and isinstance(e.get("will_review"), bool)
               and isinstance(e.get("path"), str) for e in entries):
        raise ValueError("Invalid preview entry")
    if len(set(e["path"] for e in entries)) != len(entries):
        raise ValueError("Duplicate preview paths")
    selected = [e["path"] for e in entries if e["will_review"]]
    excluded = [{"path": e["path"], "reason": e.get("exclude_reason", "unspecified")}
                for e in entries if not e["will_review"]]
    if (preview.get("total_files") != len(entries)
            or preview.get("reviewable_count") != len(selected)
            or preview.get("excluded_count") != len(excluded)):
        raise ValueError("Preview counts do not reconcile")
    fixed_floor = PER_FILE_FLOOR * len(selected)
    return {
        "evidence_kind": "offline_structural_heuristic_floor_not_actual_tokens",
        "ocr_version": "1.13.0",
        "selected_count": len(selected), "excluded_count": len(excluded),
        "selected_paths": selected, "excluded_paths": excluded,
        "configured_token_budget": budget,
        "heuristic_fixed_floor_per_selected_file": PER_FILE_FLOOR,
        "heuristic_fixed_floor_total": fixed_floor,
        "budget_below_fixed_heuristic_floor": fixed_floor > budget,
        "decision": "PREVIEW_ONLY_NO_OCR_PASS",
        "limitations": "Actual requests, semantic grouping, tool rounds and provider billing NOT measured. "
                       "Upstream heuristic constants are NOT guaranteed minimum real consumption.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(json.loads(args.manifest.read_text(encoding="utf-8")), args.budget)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OCR 1.13.0 fixed-term heuristic: {result['selected_count']} files x {PER_FILE_FLOOR} = "
          f"{result['heuristic_fixed_floor_total']} tokens, budget={args.budget}, "
          f"above={result['budget_below_fixed_heuristic_floor']}")
    print("PREVIEW_ONLY: no LLM, no OCR PASS")


if __name__ == "__main__":
    main()
