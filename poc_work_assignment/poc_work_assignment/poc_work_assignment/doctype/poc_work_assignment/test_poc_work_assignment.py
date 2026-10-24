from uuid import uuid4
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase


class TestPOCWorkAssignment(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.employee_ref = f"SYNTH-{uuid4().hex}"

    def make_assignment(self, **overrides):
        values = {
            "doctype": "POC Work Assignment",
            "employee_ref": self.employee_ref,
            "assignment_date": "2026-10-21",
            "assignment_type": "Office",
        }
        values.update(overrides)
        return frappe.get_doc(values)

    def test_optional_fields_can_be_empty(self):
        doc = self.make_assignment().insert()
        doc.reload()
        self.assertEqual(doc.employee_ref, self.employee_ref)
        self.assertFalse(doc.location)
        self.assertFalse(doc.notes)

    def test_exact_duplicate_is_rejected(self):
        self.make_assignment().insert()
        with self.assertRaises(frappe.ValidationError):
            self.make_assignment().insert()

    def test_different_types_on_same_date(self):
        for assignment_type in ("Office", "Sales", "Training"):
            self.make_assignment(assignment_type=assignment_type).insert()
        self.assertEqual(frappe.db.count("POC Work Assignment", {
            "employee_ref": self.employee_ref,
        }), 3)

    def test_different_date_or_employee(self):
        self.make_assignment().insert()
        self.make_assignment(assignment_date="2026-10-22").insert()
        self.make_assignment(employee_ref=f"SYNTH-{uuid4().hex}").insert()

    def test_missing_required_fields(self):
        for field in ("employee_ref", "assignment_date", "assignment_type"):
            with self.subTest(field=field), self.assertRaises(frappe.ValidationError):
                # Frappe replaces None with Select defaults during insert; "" stays empty.
                self.make_assignment(**{field: ""}).insert()

    def test_none_type_uses_select_default(self):
        doc = self.make_assignment(assignment_type=None)
        self.assertIsNone(doc.assignment_type)
        doc.insert()
        doc.reload()
        self.assertEqual(doc.assignment_type, "Office")

    def test_invalid_type(self):
        with self.assertRaises(frappe.ValidationError):
            self.make_assignment(assignment_type="Remote").insert()

    def test_edit_keeps_own_key(self):
        doc = self.make_assignment().insert()
        doc.notes = "Synthetic test note"
        doc.save()
        doc.reload()
        self.assertEqual(doc.notes, "Synthetic test note")

    def test_edit_cannot_collide(self):
        self.make_assignment().insert()
        doc = self.make_assignment(assignment_type="Sales").insert()
        doc.assignment_type = "Office"
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_database_rejects_duplicate_without_precheck(self):
        self.make_assignment().insert()
        controller = type(self.make_assignment())
        frappe.db.savepoint("duplicate_constraint")
        try:
            with patch.object(controller, "validate_duplicate"), self.assertRaises(
                frappe.UniqueValidationError
            ):
                self.make_assignment().insert()
        finally:
            frappe.db.rollback(save_point="duplicate_constraint")
