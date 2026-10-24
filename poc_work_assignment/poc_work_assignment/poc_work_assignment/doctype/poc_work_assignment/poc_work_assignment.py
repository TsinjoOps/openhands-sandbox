import frappe
from frappe import _
from frappe.model.document import Document

from poc_work_assignment.validation import REQUIRED_FIELDS, validate_assignment


class POCWorkAssignment(Document):
    def validate(self):
        try:
            validate_assignment(self.employee_ref, self.assignment_date, self.assignment_type)
        except ValueError as error:
            frappe.throw(str(error), frappe.ValidationError)
        self.validate_duplicate()

    def validate_duplicate(self):
        filters = {field: self.get(field) for field in REQUIRED_FIELDS}
        if self.name:
            filters["name"] = ["!=", self.name]
        if frappe.db.exists("POC Work Assignment", filters):
            frappe.throw(
                _("An assignment already exists for this employee, date and type."),
                frappe.ValidationError,
            )


def on_doctype_update():
    # The database constraint also prevents duplicates from concurrent writes.
    frappe.db.add_unique(
        "POC Work Assignment",
        list(REQUIRED_FIELDS),
        constraint_name="unique_poc_work_assignment",
    )
