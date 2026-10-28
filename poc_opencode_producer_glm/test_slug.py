"""Unit tests for poc_opencode_producer_glm.slug (Issue #22 fixture)."""

import unittest

from poc_opencode_producer_glm.slug import normalize_slug


class TestNormalizeSlug(unittest.TestCase):
    def test_trim_whitespace_and_lowercase(self):
        self.assertEqual(normalize_slug("  Hello World  "), "hello-world")

    def test_runs_of_non_alnum_collapse_to_single_dash(self):
        self.assertEqual(normalize_slug("A__B---C"), "a-b-c")

    def test_mixed_text_and_digits(self):
        self.assertEqual(normalize_slug("  Flight 123 / IVTSS  "), "flight-123-ivtss")

    def test_no_alphanumeric_characters_returns_empty(self):
        self.assertEqual(normalize_slug("***"), "")

    def test_already_normalized_value_unchanged(self):
        self.assertEqual(normalize_slug("flight-123-ivtss"), "flight-123-ivtss")

    def test_leading_and_trailing_dashes_removed(self):
        self.assertEqual(normalize_slug("--Hello--World--"), "hello-world")

    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_slug(""), "")

    def test_whitespace_only_returns_empty(self):
        self.assertEqual(normalize_slug("   "), "")

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            normalize_slug(123)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
