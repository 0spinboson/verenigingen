import frappe
import unittest
from frappe.utils import today, add_days, add_months
from verenigingen.verenigingen.doctype.sepa_mandate.sepa_mandate import SEPAMandate

class TestSEPAMandate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up any common test data
        pass
        
    def setUp(self):
        # Create a test member for use in tests
        self.test_member = create_test_member()
        # Create a clean mandate for each test
        self.mandate = frappe.get_doc({
            "doctype": "SEPA Mandate",
            "mandate_id": f"TEST-MANDATE-{frappe.utils.random_string(8)}",
            "member": self.test_member.name,
            "account_holder_name": self.test_member.full_name,
            "iban": "NL91ABNA0417164300",  # Test IBAN
            "sign_date": today(),
            "status": "Draft",
            "mandate_type": "RCUR",
            "scheme": "SEPA",
            "is_active": 1,
            "used_for_memberships": 1
        })
    
    def tearDown(self):
        # Clean up test data
        try:
            if frappe.db.exists("SEPA Mandate", self.mandate.name):
                frappe.delete_doc("SEPA Mandate", self.mandate.name)
            if self.test_member and frappe.db.exists("Member", self.test_member.name):
                frappe.delete_doc("Member", self.test_member.name)
        except:
            frappe.db.rollback()
    
    def test_validate_dates_future_sign_date(self):
        """Test that validation fails when sign date is in the future"""
        self.mandate.sign_date = add_days(today(), 5)  # 5 days in the future
        
        with self.assertRaises(frappe.exceptions.ValidationError):
            self.mandate.insert()
    
    def test_validate_dates_expiry_before_sign(self):
        """Test that validation fails when expiry date is before sign date"""
        self.mandate.sign_date = today()
        self.mandate.expiry_date = add_days(today(), -10)  # 10 days in the past
        
        with self.assertRaises(frappe.exceptions.ValidationError):
            self.mandate.insert()
    
    def test_validate_iban_format(self):
        """Test IBAN validation"""
        # Test invalid IBAN (too short)
        self.mandate.iban = "NL1234"
        
        with self.assertRaises(frappe.exceptions.ValidationError):
            self.mandate.insert()
        
        # Test valid IBAN
        self.mandate.iban = "NL91ABNA0417164300"
        self.mandate.insert()
        self.assertEqual(self.mandate.iban, "NL91ABNA0417164300")
    
    def test_set_status_active(self):
        """Test status is set to Active with valid configuration"""
        self.mandate.is_active = 1
        self.mandate.insert()
        self.assertEqual(self.mandate.status, "Active")
    
    def test_set_status_suspended(self):
        """Test status is set to Suspended when is_active=0"""
        self.mandate.is_active = 0
        self.mandate.insert()
        self.assertEqual(self.mandate.status, "Suspended")
    
    def test_set_status_expired(self):
        """Test status is set to Expired when expiry date is in the past"""
        self.mandate.expiry_date = add_days(today(), -1)  # Yesterday
        self.mandate.insert()
        self.assertEqual(self.mandate.status, "Expired")
    
    def test_on_update_member_relationship(self):
        """Test relationship with Member is properly set up on update"""
        # Insert mandate first
        self.mandate.insert()
        
        # Get the member and check if mandate was added
        member = frappe.get_doc("Member", self.test_member.name)
        
        # Find if our mandate is in the member's mandates
        mandate_found = False
        for member_mandate in member.sepa_mandates:
            if member_mandate.sepa_mandate == self.mandate.name:
                mandate_found = True
                self.assertTrue(member_mandate.is_current, "Mandate should be set as current")
                break
        
        self.assertTrue(mandate_found, "Mandate should be added to Member's mandate list")
    
    def test_multiple_mandates_current_handling(self):
        """Test how multiple mandates are handled for a Member"""
        # Create first mandate
        first_mandate = self.mandate
        first_mandate.insert()
        
        # Create second mandate
        second_mandate = frappe.get_doc({
            "doctype": "SEPA Mandate",
            "mandate_id": f"TEST-MANDATE-2-{frappe.utils.random_string(8)}",
            "member": self.test_member.name,
            "account_holder_name": self.test_member.full_name,
            "iban": "NL91ABNA0417164300",  # Test IBAN
            "sign_date": today(),
            "status": "Draft",
            "mandate_type": "RCUR",
            "scheme": "SEPA",
            "is_active": 1,
            "used_for_memberships": 1
        })
        second_mandate.insert()
        
        try:
            # Get the member and check mandate status
            member = frappe.get_doc("Member", self.test_member.name)
            
            # Verify that only one mandate is current
            current_mandates = [m for m in member.sepa_mandates if m.is_current]
            self.assertEqual(len(current_mandates), 1, "There should be only one current mandate")
            
            # Verify that the first mandate is no longer current (second one should be current)
            first_is_current = False
            for mandate in member.sepa_mandates:
                if mandate.sepa_mandate == first_mandate.name and mandate.is_current:
                    first_is_current = True
                    break
            
            self.assertFalse(first_is_current, "First mandate should no longer be current")
            
            # Clean up second mandate
            frappe.delete_doc("SEPA Mandate", second_mandate.name)
        except Exception as e:
            # Clean up second mandate in case of error
            if frappe.db.exists("SEPA Mandate", second_mandate.name):
                frappe.delete_doc("SEPA Mandate", second_mandate.name)
            raise e

def create_test_member():
    """Helper function to create a test member"""
    member_email = f"test_sepa_{frappe.utils.random_string(8)}@example.com"
    
    member = frappe.get_doc({
        "doctype": "Member",
        "first_name": "Test",
        "last_name": "SEPA",
        "email": member_email,
        "iban": "NL91ABNA0417164300"  # Test IBAN
    })
    member.insert(ignore_permissions=True)
    
    return member
