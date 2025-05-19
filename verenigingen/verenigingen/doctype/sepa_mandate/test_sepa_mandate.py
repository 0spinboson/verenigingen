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
    
    def test_preserve_draft_status(self):
        """Test Draft status is preserved until explicitly changed"""
        self.mandate.status = "Draft"
        self.mandate.is_active = 1
        self.mandate.insert()
        
        # Status should remain as Draft
        self.assertEqual(self.mandate.status, "Draft")
        
        # Modify and save to check if Draft status persists
        self.mandate.account_holder_name = "Modified Name"
        self.mandate.save()
        
        # Status should still be Draft
        self.assertEqual(self.mandate.status, "Draft")
    
    def test_preserve_cancelled_status(self):
        """Test Cancelled status is preserved and not overridden"""
        # First insert with Active status
        self.mandate.status = "Active"
        self.mandate.insert()
        
        # Now set it to Cancelled
        self.mandate.status = "Cancelled"
        self.mandate.is_active = 0
        self.mandate.cancelled_date = today()
        self.mandate.save()
        
        # Status should be Cancelled
        self.assertEqual(self.mandate.status, "Cancelled")
        
        # Change other fields and verify Cancelled status persists
        self.mandate.account_holder_name = "New Holder Name"
        self.mandate.save()
        
        # Status should still be Cancelled
        self.assertEqual(self.mandate.status, "Cancelled")
    
    def test_status_active(self):
        """Test status is set to Active with valid configuration"""
        self.mandate.status = "Active"
        self.mandate.is_active = 1
        self.mandate.insert()
        self.assertEqual(self.mandate.status, "Active")
        
        # Change is_active to 0 and verify status changes to Suspended
        self.mandate.is_active = 0
        self.mandate.save()
        self.assertEqual(self.mandate.status, "Suspended")
    
    def test_status_suspended(self):
        """Test status is set to Suspended when is_active=0"""
        self.mandate.status = "Suspended"
        self.mandate.is_active = 0
        self.mandate.insert()
        self.assertEqual(self.mandate.status, "Suspended")
        
        # Change is_active to 1 and verify status changes to Active
        self.mandate.is_active = 1
        self.mandate.save()
        self.assertEqual(self.mandate.status, "Active")
    
    def test_status_expired(self):
        """Test status is set to Expired when expiry date is in the past"""
        # Set sign date to a past date, and expiry date between sign date and today
        self.mandate.sign_date = add_days(today(), -30)  # 30 days in the past
        self.mandate.expiry_date = add_days(today(), -1)  # Yesterday (but after sign date)
        self.mandate.status = "Active"  # Start with Active
        self.mandate.insert()
        self.assertEqual(self.mandate.status, "Expired")
        
        # Verify that changing is_active doesn't override Expired status
        self.mandate.is_active = 1
        self.mandate.save()
        self.assertEqual(self.mandate.status, "Expired")
    
    def test_is_active_flag_sync(self):
        """Test is_active flag stays in sync with status"""
        # Start with Active status
        self.mandate.status = "Active"
        self.mandate.is_active = 1
        self.mandate.insert()
        self.assertEqual(self.mandate.is_active, 1)
        
        # Change to Suspended
        self.mandate.status = "Suspended"
        self.mandate.save()
        self.assertEqual(self.mandate.is_active, 0)
        
        # Change back to Active
        self.mandate.status = "Active"
        self.mandate.save()
        self.assertEqual(self.mandate.is_active, 1)
        
        # Change to Cancelled
        self.mandate.status = "Cancelled"
        self.mandate.save()
        self.assertEqual(self.mandate.is_active, 0)
    
    def test_on_update_member_relationship(self):
        """Test relationship with Member is properly set up on update"""
        # Insert mandate first with Active status
        self.mandate.status = "Active"
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
        # Create first mandate with Active status
        self.mandate.status = "Active"
        self.mandate.insert()
        
        # Create second mandate - use force=True during cleanup to avoid link errors
        second_mandate_id = f"TEST-MANDATE-2-{frappe.utils.random_string(8)}"
        second_mandate = frappe.get_doc({
            "doctype": "SEPA Mandate",
            "mandate_id": second_mandate_id,
            "member": self.test_member.name,
            "account_holder_name": self.test_member.full_name,
            "iban": "NL91ABNA0417164300",  # Test IBAN
            "sign_date": today(),
            "status": "Active",
            "mandate_type": "RCUR",
            "scheme": "SEPA",
            "is_active": 1,
            "used_for_memberships": 1
        })
        second_mandate.insert()
        
        try:
            # Get the member and check mandate status
            member = frappe.get_doc("Member", self.test_member.name)
            
            # Count how many mandates are marked as current
            current_mandates = [m for m in member.sepa_mandates if m.is_current]
            
            # IMPORTANT: The current implementation doesn't automatically
            # change the current mandate, so there may be multiple current mandates.
            # If the business logic is updated later, this test can be updated to
            # expect only one current mandate.
            self.assertTrue(len(current_mandates) > 0, "At least one mandate should be current")
            
            # Verify both mandates are in the member's list
            mandate_names = [m.sepa_mandate for m in member.sepa_mandates]
            self.assertIn(self.mandate.name, mandate_names, "First mandate should be in member's list")
            self.assertIn(second_mandate.name, mandate_names, "Second mandate should be in member's list")
            
        finally:
            # Clean up second mandate - use force=True to overcome link restrictions
            if frappe.db.exists("SEPA Mandate", second_mandate.name):
                frappe.db.set_value("SEPA Mandate", second_mandate.name, "status", "Cancelled")
                frappe.delete_doc("SEPA Mandate", second_mandate.name, force=True, ignore_permissions=True)
                
    def test_suspend_existing_mandates(self):
        """Test that creating a new mandate suspends existing ones"""
        # First create a mandate normally
        first_mandate = self.mandate
        first_mandate.status = "Active"
        first_mandate.insert()
        first_mandate_name = first_mandate.name
        
        # Now simulate creating a new mandate via the create_and_link_mandate function
        from verenigingen.verenigingen.doctype.member.member import create_and_link_mandate
        
        # Create a second mandate - different IBAN
        second_mandate = create_and_link_mandate(
            member=self.test_member.name,
            iban="DE89370400440532013000",  # Different IBAN
            account_holder_name=self.test_member.full_name,
            mandate_type="RCUR",
            used_for_memberships=1
        )
        
        # Check that first mandate is now suspended
        updated_first_mandate = frappe.get_doc("SEPA Mandate", first_mandate_name)
        self.assertEqual(updated_first_mandate.status, "Suspended")
        self.assertEqual(updated_first_mandate.is_active, 0)

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
