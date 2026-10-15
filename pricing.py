"""Pricing calculations."""


def calculate_total(unit_price, quantity, discount_percent=0):
    """Calculate a quantity total after applying a percentage discount."""
    if unit_price < 0:
        raise ValueError("unit_price cannot be negative")
    if quantity < 0:
        raise ValueError("quantity cannot be negative")

    subtotal = unit_price * quantity
    return subtotal * (100 - discount_percent) / 100
