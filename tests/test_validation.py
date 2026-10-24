import unittest

from poc_work_assignment.validation import validate_assignment


class TestAssignmentValidation(unittest.TestCase):
    def test_each_allowed_type(self):
        for assignment_type in ("Office", "Sales", "Training"):
            with self.subTest(assignment_type=assignment_type):
                validate_assignment("SYNTH-001", "2026-10-21", assignment_type)

    def test_missing_required_values(self):
        for position in range(3):
            for empty in (None, "", "   "):
                values = ["SYNTH-001", "2026-10-21", "Office"]
                values[position] = empty
                with self.subTest(position=position, empty=empty):
                    with self.assertRaisesRegex(ValueError, "is required"):
                        validate_assignment(*values)

    def test_unknown_or_non_exact_type(self):
        for value in ("Remote", "office", "Office ", "Sales\n", 123):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "must be"):
                    validate_assignment("SYNTH-001", "2026-10-21", value)


if __name__ == "__main__":
    unittest.main()
