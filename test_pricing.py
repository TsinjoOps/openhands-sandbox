import unittest

from pricing import calculate_total


class CalculateTotalTests(unittest.TestCase):
    def test_applies_percentage_discount(self):
        self.assertEqual(calculate_total(100, 2, 10), 180)

    def test_uses_zero_discount_by_default(self):
        self.assertEqual(calculate_total(25, 3), 75)

    def test_rejects_negative_unit_price(self):
        with self.assertRaises(ValueError):
            calculate_total(-1, 2)

    def test_rejects_negative_quantity(self):
        with self.assertRaises(ValueError):
            calculate_total(10, -1)


if __name__ == "__main__":
    unittest.main()
