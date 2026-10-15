def calculate_invoice_total(subtotal, discount_percent=0, tax_percent=0):
    """Calculate the total by applying the discount before tax."""
    if subtotal < 0:
        raise ValueError("subtotal must be non-negative")
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("discount_percent must be between 0 and 100")
    if tax_percent < 0:
        raise ValueError("tax_percent must be non-negative")

    discounted_subtotal = subtotal * (1 - discount_percent / 100)
    total = discounted_subtotal * (1 + tax_percent / 100)
    return round(total, 2)
