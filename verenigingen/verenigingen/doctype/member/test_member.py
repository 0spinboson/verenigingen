# vereinigingen/vereinigingen/doctype/member/test_member.py

from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.utils import add_days, today

class TestMemberFields(FrappeTestCase):
    def test_field_existence(self):
        """Test that fields referenced in code actually exist in the DocType"""
        # Get DocType metadata
        member_meta = frappe.get_meta("Member")
        
        # List of fields referenced in Member methods
        critical_fields = [
            "first_name", "middle_name", "last_name", "full_name", 
            "email", "mobile_no", "customer", "user", "payment_method",
            "iban", "bank_account_name", "primary_chapter"
        ]
        
        # Check each field exists
        missing_fields = []
        for field in critical_fields:
            if not member_meta.has_field(field):
                missing_fields.append(field)
        
        self.assertEqual(
            len(missing_fields), 0, 
            f"The following fields are referenced in code but don't exist in Member DocType: {', '.join(missing_fields)}"
        )
