import unittest

from invoice import calculate_invoice_total


class CalculateInvoiceTotalTests(unittest.TestCase):
    def test_discount_then_tax(self):
        self.assertEqual(calculate_invoice_total(100, 10, 20), 108.0)

    def test_default_discount_and_tax(self):
        self.assertEqual(calculate_invoice_total(100), 100.0)


if __name__ == "__main__":
    unittest.main()
