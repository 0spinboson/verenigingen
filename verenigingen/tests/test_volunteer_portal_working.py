import frappe
import unittest
from frappe.utils import today, add_days, flt
from frappe.tests.utils import FrappeTestCase


class TestVolunteerPortalWorking(FrappeTestCase):
    """Working tests for volunteer portal - uses existing data where possible"""
    
    def setUp(self):
        """Set up for each test"""
        frappe.set_user("Administrator")
    
    def test_portal_module_imports(self):
        """Test that all portal modules can be imported successfully"""
        try:
            from verenigingen.templates.pages.volunteer.dashboard import get_context as dashboard_context
            from verenigingen.templates.pages.volunteer.expenses import (
                get_context as expenses_context,
                submit_expense,
                get_organization_options,
                get_user_volunteer_record,
                get_volunteer_organizations,
                get_expense_categories,
                get_approval_thresholds,
                get_status_class
            )
            
            # Test all functions are callable
            self.assertTrue(callable(dashboard_context))
            self.assertTrue(callable(expenses_context))
            self.assertTrue(callable(submit_expense))
            self.assertTrue(callable(get_organization_options))
            self.assertTrue(callable(get_user_volunteer_record))
            self.assertTrue(callable(get_volunteer_organizations))
            self.assertTrue(callable(get_expense_categories))
            self.assertTrue(callable(get_approval_thresholds))
            self.assertTrue(callable(get_status_class))
            
        except ImportError as e:
            self.fail(f"Failed to import portal modules: {e}")
        except Exception as e:
            self.fail(f"Unexpected error importing portal modules: {e}")
    
    def test_approval_thresholds(self):
        """Test approval threshold configuration"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_approval_thresholds
            
            thresholds = get_approval_thresholds()
            
            # Verify structure
            self.assertIsInstance(thresholds, dict)
            required_keys = ["basic_limit", "financial_limit", "admin_limit"]
            
            for key in required_keys:
                self.assertIn(key, thresholds)
                self.assertIsInstance(thresholds[key], (int, float))
            
            # Verify logical progression
            self.assertEqual(thresholds["basic_limit"], 100.0)
            self.assertEqual(thresholds["financial_limit"], 500.0)
            self.assertGreater(thresholds["financial_limit"], thresholds["basic_limit"])
            
        except Exception as e:
            self.fail(f"Approval thresholds test failed: {e}")
    
    def test_status_class_mapping(self):
        """Test status class mapping function"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_status_class
            
            # Test known status mappings
            test_cases = [
                ("Draft", "badge-secondary"),
                ("Submitted", "badge-warning"),
                ("Approved", "badge-success"),
                ("Rejected", "badge-danger"),
                ("Reimbursed", "badge-primary"),
                ("Unknown Status", "badge-secondary")  # Default case
            ]
            
            for status, expected_class in test_cases:
                actual_class = get_status_class(status)
                self.assertEqual(actual_class, expected_class, 
                               f"Status '{status}' should map to '{expected_class}', got '{actual_class}'")
        
        except Exception as e:
            self.fail(f"Status class mapping test failed: {e}")
    
    def test_guest_access_denial(self):
        """Test that guest users cannot access portal pages"""
        frappe.set_user("Guest")
        
        try:
            # Test dashboard access
            from verenigingen.templates.pages.volunteer.dashboard import get_context as dashboard_context
            
            with self.assertRaises(frappe.PermissionError):
                context = {}
                dashboard_context(context)
            
            # Test expenses portal access
            from verenigingen.templates.pages.volunteer.expenses import get_context as expenses_context
            
            with self.assertRaises(frappe.PermissionError):
                context = {}
                expenses_context(context)
                
        except ImportError:
            self.skipTest("Portal modules not available")
        finally:
            frappe.set_user("Administrator")
    
    def test_user_volunteer_record_lookup(self):
        """Test volunteer record lookup for current user"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_user_volunteer_record
            
            # Test with Administrator (should return None)
            volunteer = get_user_volunteer_record()
            self.assertIsNone(volunteer, "Administrator should not have volunteer record")
            
            # Function should not crash and should return None or valid dict
            if volunteer is not None:
                self.assertIsInstance(volunteer, dict)
                self.assertIn("name", volunteer)
                self.assertIn("volunteer_name", volunteer)
        
        except Exception as e:
            self.fail(f"User volunteer record lookup failed: {e}")
    
    def test_expense_categories_retrieval(self):
        """Test expense categories retrieval"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_expense_categories
            
            categories = get_expense_categories()
            
            # Should return list (empty is fine)
            self.assertIsInstance(categories, list)
            
            # If categories exist, verify structure
            for category in categories:
                self.assertIsInstance(category, dict)
                self.assertIn("name", category)
                self.assertIn("category_name", category)
                # description is optional
        
        except Exception as e:
            self.fail(f"Expense categories retrieval failed: {e}")
    
    def test_organization_options_empty_volunteer(self):
        """Test organization options with non-existent volunteer"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_organization_options
            
            # Test with non-existent volunteer
            chapter_options = get_organization_options("Chapter", "NON-EXISTENT-VOLUNTEER")
            team_options = get_organization_options("Team", "NON-EXISTENT-VOLUNTEER")
            
            # Should return empty lists without crashing
            self.assertIsInstance(chapter_options, list)
            self.assertIsInstance(team_options, list)
            self.assertEqual(len(chapter_options), 0)
            self.assertEqual(len(team_options), 0)
            
            # Test with invalid organization type
            invalid_options = get_organization_options("InvalidType", "NON-EXISTENT-VOLUNTEER")
            self.assertEqual(invalid_options, [])
        
        except Exception as e:
            self.fail(f"Organization options test failed: {e}")
    
    def test_volunteer_organizations_empty(self):
        """Test volunteer organizations with non-existent volunteer"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_volunteer_organizations
            
            organizations = get_volunteer_organizations("NON-EXISTENT-VOLUNTEER")
            
            # Should return proper structure
            self.assertIsInstance(organizations, dict)
            self.assertIn("chapters", organizations)
            self.assertIn("teams", organizations)
            self.assertIsInstance(organizations["chapters"], list)
            self.assertIsInstance(organizations["teams"], list)
            
            # Should be empty for non-existent volunteer
            self.assertEqual(len(organizations["chapters"]), 0)
            self.assertEqual(len(organizations["teams"]), 0)
        
        except Exception as e:
            self.fail(f"Volunteer organizations test failed: {e}")
    
    def test_submit_expense_validation(self):
        """Test expense submission validation without creating data"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import submit_expense
            
            # Test with missing required fields
            invalid_data = {}
            
            result = submit_expense(invalid_data)
            
            # Should return error result
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertFalse(result["success"])
            self.assertIn("message", result)
        
        except Exception as e:
            self.fail(f"Submit expense validation test failed: {e}")
    
    def test_expense_statistics_empty(self):
        """Test expense statistics with non-existent volunteer"""
        try:
            from verenigingen.templates.pages.volunteer.expenses import get_expense_statistics
            
            stats = get_expense_statistics("NON-EXISTENT-VOLUNTEER")
            
            # Should return proper structure with zero values
            self.assertIsInstance(stats, dict)
            expected_keys = ["total_submitted", "total_approved", "pending_count", 
                           "approved_count", "total_count"]
            
            for key in expected_keys:
                self.assertIn(key, stats)
                self.assertEqual(stats[key], 0)
        
        except Exception as e:
            self.fail(f"Expense statistics test failed: {e}")
    
    def test_expense_permissions_module_import(self):
        """Test that expense permissions module can be imported"""
        try:
            from verenigingen.utils.expense_permissions import ExpensePermissionManager
            
            # Should be able to create instance
            manager = ExpensePermissionManager()
            self.assertIsNotNone(manager)
            
            # Test basic methods exist
            self.assertTrue(hasattr(manager, 'get_required_permission_level'))
            self.assertTrue(hasattr(manager, 'can_approve_expense'))
            
            # Test permission level calculation
            test_amounts = [50.0, 150.0, 750.0]
            expected_levels = ["basic", "financial", "admin"]
            
            for amount, expected in zip(test_amounts, expected_levels):
                level = manager.get_required_permission_level(amount)
                self.assertEqual(level, expected)
        
        except ImportError:
            self.skipTest("Expense permissions module not available")
        except Exception as e:
            self.fail(f"Expense permissions test failed: {e}")
    
    def test_notification_module_import(self):
        """Test that notification module can be imported"""
        try:
            from verenigingen.utils.expense_notifications import ExpenseNotificationManager
            
            # Should be able to create instance
            manager = ExpenseNotificationManager()
            self.assertIsNotNone(manager)
            
            # Test basic methods exist
            expected_methods = [
                'send_approval_request_notification',
                'send_approval_confirmation',
                'send_rejection_notification',
                'send_escalation_notification'
            ]
            
            for method_name in expected_methods:
                self.assertTrue(hasattr(manager, method_name))
                self.assertTrue(callable(getattr(manager, method_name)))
        
        except ImportError:
            self.skipTest("Expense notifications module not available")
        except Exception as e:
            self.fail(f"Expense notifications test failed: {e}")


if __name__ == "__main__":
    unittest.main()