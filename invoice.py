def calculate_invoice_total(subtotal, discount_percent=0, tax_percent=0):
    """Calculate the total by applying the discount before tax."""
    discounted_subtotal = subtotal * (1 - discount_percent / 100)
    return discounted_subtotal * (1 + tax_percent / 100)
