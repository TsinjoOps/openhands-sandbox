import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ocr_heuristic_floor import analyze, PER_FILE_FLOOR


def fixture(selected=13, excluded=5):
    items = [{"path": f"file{i}.py", "will_review": True} for i in range(selected)]
    items += [{"path": f"skip{i}.txt", "will_review": False,
               "exclude_reason": "unsupported_ext"} for i in range(excluded)]
    return {"files": items, "total_files": len(items),
            "reviewable_count": selected, "excluded_count": excluded}


class BudgetFloorTests(unittest.TestCase):
    def test_pr7_floor(self):
        result = analyze(fixture(), 50000)
        self.assertEqual(PER_FILE_FLOOR, 21300)
        self.assertEqual(result["heuristic_fixed_floor_total"], 276900)
        self.assertTrue(result["budget_below_fixed_heuristic_floor"])
        self.assertEqual(result["decision"], "PREVIEW_ONLY_NO_OCR_PASS")

    def test_smaller_scope(self):
        self.assertFalse(analyze(fixture(1, 0), 50000)["budget_below_fixed_heuristic_floor"])
        self.assertTrue(analyze(fixture(3, 0), 50000)["budget_below_fixed_heuristic_floor"])

    def test_mismatch_rejected(self):
        bad = fixture(2, 1)
        bad["reviewable_count"] = 1
        with self.assertRaises(ValueError):
            analyze(bad, 50000)

    def test_duplicate_rejected(self):
        bad = fixture(2, 0)
        bad["files"][1]["path"] = bad["files"][0]["path"]
        with self.assertRaises(ValueError):
            analyze(bad, 50000)

    def test_zero_budget_rejected(self):
        with self.assertRaises(ValueError):
            analyze(fixture(), 0)


if __name__ == "__main__":
    unittest.main()
