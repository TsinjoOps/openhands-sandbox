"""Offline fail-closed smoke tests for the local OCR evaluator.

No GitHub API calls, model requests or secrets are used.
"""
import unittest

from review_decision import evaluate_review, render_markdown

A = "a" * 40
B = "b" * 40


class ReviewDecisionSmokeTests(unittest.TestCase):
    def decision(self, payload=None, **overrides):
        options = dict(
            expected_head=A, current_head=A, ocr_outcome="success",
            comments_failed=0, checkpoint_after=A,
        )
        options.update(overrides)
        return evaluate_review(payload, **options)

    def test_stale_sha_overrides_missing_evidence(self):
        self.assertEqual(self.decision(current_head=B)["state"], "STALE")

    def test_missing_evidence_blocked(self):
        self.assertEqual(self.decision()["state"], "BLOCKED")

    def test_empty_evidence_blocked(self):
        self.assertEqual(self.decision({})["state"], "BLOCKED")

    def test_failed_ocr_blocked(self):
        self.assertEqual(self.decision(ocr_outcome="failure")["state"], "BLOCKED")

    def test_missing_checkpoint_blocked(self):
        self.assertEqual(self.decision({}, checkpoint_after="")["state"], "BLOCKED")

    def test_incomplete_manifest_blocked(self):
        self.assertEqual(self.decision({"status": "complete", "manifest": {}})["state"], "BLOCKED")

    def test_malformed_sha_blocked(self):
        self.assertEqual(self.decision(expected_head="bad")["state"], "BLOCKED")

    def test_markdown_never_grants_merge(self):
        markdown = render_markdown(self.decision({}))
        self.assertIn("BLOCKED", markdown)
        self.assertIn("not merge/deployment authority", markdown)


if __name__ == "__main__":
    unittest.main()
