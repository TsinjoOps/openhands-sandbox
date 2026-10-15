import unittest

from invoice import calculate_invoice_total


class CalculateInvoiceTotalTests(unittest.TestCase):
    def test_discount_then_tax(self):
        self.assertEqual(calculate_invoice_total(100, 10, 20), 108.0)

    def test_default_discount_and_tax(self):
        self.assertEqual(calculate_invoice_total(100), 100.0)

    def test_subtotal_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_invoice_total(-1)

    def test_discount_percent_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_invoice_total(100, -1)

    def test_discount_percent_over_100_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_invoice_total(100, 101)

    def test_tax_percent_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_invoice_total(100, 0, -1)

    def test_tax_percent_boundary_and_rounding(self):
        self.assertEqual(calculate_invoice_total(100, 0, 2.675), 102.68)


if __name__ == "__main__":
    unittest.main()
