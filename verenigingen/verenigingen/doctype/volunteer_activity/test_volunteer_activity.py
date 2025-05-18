# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import getdate, today, add_days
from frappe.tests.utils import FrappeTestCase

from frappe.test_runner import make_test_records, skip_test_for_test_record_creation

@unittest.skip_test_for_test_record_creation  # Skip automatic test record creation
class TestVolunteerActivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up test company and accounts if they don't exist
        if not frappe.db.exists("Company", "_Test Company"):
            from erpnext.setup.doctype.company.test_company import create_test_company
            create_test_company("_Test Company")
            
        # Create the USD account that's missing
        if not frappe.db.exists("Account", "_Test Payable USD - _TC"):
            # Create a USD currency if it doesn't exist
            if not frappe.db.exists("Currency", "USD"):
                frappe.get_doc({
                    "doctype": "Currency",
                    "currency_name": "USD",
                    "enabled": 1
                }).insert(ignore_permissions=True)
                
            # Get parent account
            parent_account = frappe.db.get_value("Account", 
                {"account_type": "Payable", "company": "_Test Company", "is_group": 1}, "name")
                
            if parent_account:
                # Create the USD payable account with correct name including company suffix
                usd_account = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": "_Test Payable USD",
                    "account_type": "Payable",
                    "parent_account": parent_account,
                    "company": "_Test Company",
                    "account_currency": "USD",
                    "is_group": 0
                })
                usd_account.insert(ignore_permissions=True)
                frappe.db.commit()
        
    def setUp(self):
        # Create test data for volunteer
        self.create_test_volunteer()
        
    def tearDown(self):
        # Clean up test data
        try:
            frappe.delete_doc("Volunteer Activity", self.test_activity.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Volunteer", self.test_volunteer.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Member", self.test_member.name)
        except Exception:
            pass
    
    def create_test_volunteer(self):
        """Create a test volunteer record"""
        # Create a test member first
        if frappe.db.exists("Member", {"email": "activity_test@example.com"}):
            frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": "activity_test@example.com"}, "name"))
        
        self.test_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Activity",
            "last_name": "Test",
            "email": "activity_test@example.com"
        })
        self.test_member.insert(ignore_permissions=True)
        
        # Create volunteer record
        self.test_volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": "Activity Test Volunteer",
            "email": "activity.test@example.org",
            "member": self.test_member.name,
            "status": "Active",
            "start_date": today()
        })
        self.test_volunteer.insert(ignore_permissions=True)
        
        return self.test_volunteer
    
    def create_test_activity(self):
        """Create a test volunteer activity"""
        self.test_activity = frappe.get_doc({
            "doctype": "Volunteer Activity",
            "volunteer": self.test_volunteer.name,
            "activity_type": "Project",
            "role": "Project Coordinator",
            "description": "Test volunteer activity",
            "status": "Active",
            "start_date": today()
        })
        self.test_activity.insert(ignore_permissions=True)
        
        return self.test_activity
    
    def test_activity_creation(self):
        """Test creating a volunteer activity"""
        activity = self.create_test_activity()
        
        # Verify activity was created correctly
        self.assertEqual(activity.volunteer, self.test_volunteer.name)
        self.assertEqual(activity.activity_type, "Project")
        self.assertEqual(activity.role, "Project Coordinator")
        self.assertEqual(activity.status, "Active")
    
    def test_activity_completion(self):
        """Test completing a volunteer activity"""
        activity = self.create_test_activity()
        
        # Set activity to completed
        activity.status = "Completed"
        activity.end_date = today()
        activity.actual_hours = 10
        activity.save()
        
        # Reload activity to get fresh data
        activity.reload()
        
        # Verify activity updated correctly
        self.assertEqual(activity.status, "Completed")
        self.assertEqual(activity.end_date, today())
        self.assertEqual(activity.actual_hours, 10)
        
        # Reload volunteer to check if activity was added to history
        self.test_volunteer.reload()
        
        # Check assignment history for this activity
        has_history_entry = False
        for entry in self.test_volunteer.assignment_history:
            if (entry.reference_doctype == "Volunteer Activity" and 
                entry.reference_name == activity.name and
                entry.status == "Completed"):
                has_history_entry = True
                break
                
        self.assertTrue(has_history_entry, "Activity should be recorded in volunteer's assignment history")
    
    def test_date_validation(self):
        """Test date validation in volunteer activity"""
        activity = self.create_test_activity()
        
        # Try to set end date before start date (should raise exception)
        with self.assertRaises(Exception):
            activity.end_date = add_days(today(), -10)  # 10 days before start date
            activity.save()
    
    def test_activity_deletion(self):
        """Test deletion of activity and its effect on volunteer record"""
        activity = self.create_test_activity()
        
        # First complete the activity to add it to history
        activity.status = "Completed"
        activity.end_date = today()
        activity.save()
        
        # Reload volunteer to check history
        self.test_volunteer.reload()
        
        # Verify activity is in history
        history_before_count = len(self.test_volunteer.assignment_history)
        
        # Now delete the activity
        activity.delete()
        
        # Reload volunteer again
        self.test_volunteer.reload()
        
        # History should now have one less entry
        history_after_count = len(self.test_volunteer.assignment_history)
        
        # This test might fail if on_trash isn't working correctly
        # In a real implementation, the history entry should be removed when the activity is deleted
        self.assertEqual(history_before_count - 1, history_after_count, 
                         "Activity entry should be removed from volunteer history when deleted")
