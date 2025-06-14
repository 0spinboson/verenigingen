import frappe
import unittest
from frappe.utils import today
from frappe.tests.utils import FrappeTestCase


class TestVolunteerPortalSimple(FrappeTestCase):
    """Simple test to verify basic portal functionality"""
    
    def setUp(self):
        """Set up for each test"""
        frappe.set_user("Administrator")
    
    def test_portal_imports(self):
        """Test that portal modules can be imported"""
        try:
            from verenigingen.templates.pages.volunteer.dashboard import get_context as dashboard_context
            from verenigingen.templates.pages.volunteer.expenses import get_context as expenses_context
            from verenigingen.templates.pages.volunteer.expenses import submit_expense
            from verenigingen.templates.pages.volunteer.expenses import get_organization_options
            
            self.assertTrue(callable(dashboard_context))
            self.assertTrue(callable(expenses_context))
            self.assertTrue(callable(submit_expense))
            self.assertTrue(callable(get_organization_options))
            
        except ImportError as e:
            self.fail(f"Failed to import portal modules: {e}")
    
    def test_approval_threshold_functions(self):
        """Test approval threshold functions"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_approval_thresholds
            
            thresholds = get_approval_thresholds()
            
            self.assertIsInstance(thresholds, dict)
            self.assertIn("basic_limit", thresholds)
            self.assertIn("financial_limit", thresholds) 
            self.assertIn("admin_limit", thresholds)
            self.assertEqual(thresholds["basic_limit"], 100.0)
            self.assertEqual(thresholds["financial_limit"], 500.0)
            
        except Exception as e:
            self.fail(f"Approval threshold function failed: {e}")
    
    def test_guest_access_denied(self):
        """Test that guest users are denied access"""
        frappe.set_user("Guest")
        
        try:
            from verenigingen.templates.pages.volunteer.dashboard import get_context
            
            with self.assertRaises(frappe.PermissionError):
                context = {}
                get_context(context)
                
        except ImportError:
            self.skipTest("Portal module not available")
        finally:
            frappe.set_user("Administrator")
    
    def test_expense_categories_function(self):
        """Test expense categories retrieval"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_expense_categories
            
            categories = get_expense_categories()
            
            self.assertIsInstance(categories, list)
            # Should return empty list if no categories exist
            
        except Exception as e:
            self.fail(f"Expense categories function failed: {e}")
    
    def test_portal_helper_functions(self):
        """Test various portal helper functions"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import (
                get_user_volunteer_record, get_status_class
            )
            
            # Test with no volunteer record (should return None)
            volunteer = get_user_volunteer_record()
            self.assertIsNone(volunteer)  # No volunteer for Administrator
            
            # Test status class function
            status_class = get_status_class("Approved")
            self.assertEqual(status_class, "badge-success")
            
            status_class = get_status_class("Submitted")
            self.assertEqual(status_class, "badge-warning")
            
        except Exception as e:
            self.fail(f"Helper functions failed: {e}")


if __name__ == "__main__":
    unittest.main()