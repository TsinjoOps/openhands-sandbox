"""Business rules that do not require a Frappe site."""

ASSIGNMENT_TYPES = ("Office", "Sales", "Training")
REQUIRED_FIELDS = ("employee_ref", "assignment_date", "assignment_type")


def validate_assignment(employee_ref, assignment_date, assignment_type):
    values = (employee_ref, assignment_date, assignment_type)
    for fieldname, value in zip(REQUIRED_FIELDS, values):
        if not value or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"{fieldname} is required.")
    if assignment_type not in ASSIGNMENT_TYPES:
        raise ValueError("assignment_type must be Office, Sales or Training.")
