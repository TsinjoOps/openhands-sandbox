"""Deterministic test for the controlled Issue #19 defect."""

import unittest

from poc_opencode_github_first.arithmetic import add


class AdditionTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)


if __name__ == "__main__":
    unittest.main()
