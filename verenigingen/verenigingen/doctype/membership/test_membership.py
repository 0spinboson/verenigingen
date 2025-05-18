import frappe
import unittest
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today, add_days, add_months

class TestMembershipType(FrappeTestCase):
    def setUp(self):
        # Create test membership type data
        self.membership_type_data = {
            "membership_type_name": "Test Membership Type",
            "description": "Test Membership Type for Unit Tests",
            "subscription_period": "Annual",
            "amount": 120,
            "currency": "EUR",
            "is_active": 1,
            "allow_auto_renewal": 1
        }
        
        # Delete any existing test membership types
        if frappe.db.exists("Membership Type", self.membership_type_data["membership_type_name"]):
            frappe.delete_doc("Membership Type", self.membership_type_data["membership_type_name"], force=True)
            
        # Delete any test subscription plans
        for plan in frappe.get_all("Subscription Plan", filters={"plan_name": self.membership_type_data["membership_type_name"]}):
            frappe.delete_doc("Subscription Plan", plan.name, force=True)
            
        # Delete any test items
        item_code = f"MEM-{self.membership_type_data['membership_type_name']}".upper().replace(" ", "-")
        if frappe.db.exists("Item", item_code):
            frappe.delete_doc("Item", item_code, force=True)
    
    def tearDown(self):
        # Clean up test data
        if frappe.db.exists("Membership Type", self.membership_type_data["membership_type_name"]):
            frappe.delete_doc("Membership Type", self.membership_type_data["membership_type_name"], force=True)
            
        # Clean up any test subscription plans
        for plan in frappe.get_all("Subscription Plan", filters={"plan_name": self.membership_type_data["membership_type_name"]}):
            frappe.delete_doc("Subscription Plan", plan.name, force=True)
            
        # Clean up any test items
        item_code = f"MEM-{self.membership_type_data['membership_type_name']}".upper().replace(" ", "-")
        if frappe.db.exists("Item", item_code):
            frappe.delete_doc("Item", item_code, force=True)
    
    def test_create_membership_type(self):
        """Test creating a new membership type"""
        membership_type = frappe.new_doc("Membership Type")
        membership_type.update(self.membership_type_data)
        membership_type.insert()
        
        self.assertEqual(membership_type.membership_type_name, "Test Membership Type")
        self.assertEqual(membership_type.subscription_period, "Annual")
        self.assertEqual(membership_type.amount, 120)
    
    def test_custom_subscription_period(self):
        """Test validation for custom subscription period"""
        membership_type = frappe.new_doc("Membership Type")
        membership_type.update(self.membership_type_data)
        
        # Change to custom period without setting months
        membership_type.subscription_period = "Custom"
        
        # Should raise an error
        with self.assertRaises(frappe.exceptions.ValidationError):
            membership_type.insert()
            
        # Now set the months
        membership_type.subscription_period_in_months = 6
        membership_type.insert()
        
        # Should be valid now
        self.assertEqual(membership_type.subscription_period, "Custom")
        self.assertEqual(membership_type.subscription_period_in_months, 6)
    
    def test_negative_amount(self):
        """Test validation for negative amount"""
        membership_type = frappe.new_doc("Membership Type")
        membership_type.update(self.membership_type_data)
        
        # Set negative amount
        membership_type.amount = -100
        
        # Should raise an error
        with self.assertRaises(frappe.exceptions.ValidationError):
            membership_type.insert()
    
    def test_create_subscription_plan(self):
        """Test creating a subscription plan from membership type"""
        membership_type = frappe.new_doc("Membership Type")
        membership_type.update(self.membership_type_data)
        membership_type.insert()
        
        # Initially no subscription plan
        self.assertFalse(membership_type.subscription_plan)
        
        # Create subscription plan
        plan_name = membership_type.create_subscription_plan()
        
        # Reload membership type
        membership_type.reload()
        
        # Verify subscription plan is linked
        self.assertTrue(membership_type.subscription_plan)
        self.assertEqual(membership_type.subscription_plan, plan_name)
        
        # Verify subscription plan details
        plan = frappe.get_doc("Subscription Plan", plan_name)
        self.assertEqual(plan.plan_name, membership_type.membership_type_name)
        self.assertEqual(float(plan.cost), float(membership_type.amount))
        self.assertEqual(plan.billing_interval, "Year")  # Annual -> Year
    
    def test_default_membership_type(self):
        """Test setting a membership type as default"""
        # Create a first membership type
        first_type = frappe.new_doc("Membership Type")
        first_type.membership_type_name = "First Default Type"
        first_type.subscription_period = "Annual"
        first_type.amount = 100
        first_type.currency = "EUR"
        first_type.default_for_new_members = 1
        first_type.insert()
        
        # Create a second membership type
        second_type = frappe.new_doc("Membership Type")
        second_type.membership_type_name = "Second Default Type"
        second_type.subscription_period = "Annual"
        second_type.amount = 120
        second_type.currency = "EUR"
        second_type.default_for_new_members = 1
        second_type.insert()
        
        # Reload first type
        first_type.reload()
        
        # First type should no longer be default
        self.assertEqual(first_type.default_for_new_members, 0)
        
        # Only second type should be default
        self.assertEqual(second_type.default_for_new_members, 1)
        
        # Clean up
        first_type.delete()
        second_type.delete()
    
    def test_subscription_period_mapping(self):
        """Test mapping of subscription periods to intervals"""
        # Test cases for different subscription periods
        test_cases = [
            {"period": "Monthly", "expected_interval": "Month", "expected_count": 1},
            {"period": "Quarterly", "expected_interval": "Quarter", "expected_count": 1},
            {"period": "Biannual", "expected_interval": "Half-Year", "expected_count": 1},
            {"period": "Annual", "expected_interval": "Year", "expected_count": 1},
            {"period": "Lifetime", "expected_interval": "Year", "expected_count": 1},
        ]
        
        for test_case in test_cases:
            # Create membership type with this period
            membership_type = frappe.new_doc("Membership Type")
            membership_type.membership_type_name = f"Test {test_case['period']}"
            membership_type.subscription_period = test_case["period"]
            membership_type.amount = 100
            membership_type.currency = "EUR"
            membership_type.insert()
            
            # Create subscription plan
            plan_name = membership_type.create_subscription_plan()
            
            # Verify plan details
            plan = frappe.get_doc("Subscription Plan", plan_name)
            self.assertEqual(plan.billing_interval, test_case["expected_interval"])
            self.assertEqual(plan.billing_interval_count, test_case["expected_count"])
            
            # Clean up
            membership_type.delete()
            frappe.delete_doc("Subscription Plan", plan_name, force=True)
    
    def test_custom_period_mapping(self):
        """Test mapping of custom subscription periods"""
        # Test custom period with specific months
        membership_type = frappe.new_doc("Membership Type")
        membership_type.membership_type_name = "Test Custom Period"
        membership_type.subscription_period = "Custom"
        membership_type.subscription_period_in_months = 9
        membership_type.amount = 100
        membership_type.currency = "EUR"
        membership_type.insert()
        
        # Create subscription plan
        plan_name = membership_type.create_subscription_plan()
        
        # Verify plan details
        plan = frappe.get_doc("Subscription Plan", plan_name)
        self.assertEqual(plan.billing_interval, "Month")
        self.assertEqual(plan.billing_interval_count, 9)
        
        # Clean up
        membership_type.delete()
        frappe.delete_doc("Subscription Plan", plan_name, force=True)

if __name__ == '__main__':
    unittest.main()
