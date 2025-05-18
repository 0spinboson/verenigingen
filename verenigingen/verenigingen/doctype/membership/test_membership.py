import frappe
import unittest
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today, add_days, add_months, nowdate, flt
from verenigingen.verenigingen.doctype.membership.membership import Membership
from verenigingen.verenigingen.doctype.membership.enhanced_subscription import sync_membership_with_subscription

class TestMembership(FrappeTestCase):
    def setUp(self):
        # Create test data
        self.setup_test_data()
    
    def tearDown(self):
        # Clean up test data
        self.cleanup_test_data()
    
    def setup_test_data(self):
        # Create "Membership" item group if it doesn't exist
        if not frappe.db.exists("Item Group", "Membership"):
            item_group = frappe.new_doc("Item Group")
            item_group.item_group_name = "Membership"
            item_group.parent_item_group = "All Item Groups"
            item_group.insert(ignore_permissions=True)
            
        # Create test member
        self.member_data = {
            "first_name": "Test",
            "last_name": "Member",
            "email": "test.membership@example.com",
            "mobile_no": "+31612345678",
            "payment_method": "Bank Transfer"
        }
        
        # Delete existing test members
        for m in frappe.get_all("Member", filters={"email": self.member_data["email"]}):
            frappe.delete_doc("Member", m.name, force=True)
            
        # Create a test member
        self.member = frappe.new_doc("Member")
        self.member.update(self.member_data)
        self.member.insert()
        
        # Create customer for member
        self.member.create_customer()
        self.member.reload()
        
        # Create a test membership type
        self.membership_type_name = "Test Membership Type"
        if frappe.db.exists("Membership Type", self.membership_type_name):
            frappe.delete_doc("Membership Type", self.membership_type_name, force=True)
            
        self.membership_type = frappe.new_doc("Membership Type")
        self.membership_type.membership_type_name = self.membership_type_name
        self.membership_type.subscription_period = "Annual"
        self.membership_type.amount = 120
        self.membership_type.currency = "EUR"
        self.membership_type.is_active = 1
        self.membership_type.allow_auto_renewal = 1
        self.membership_type.insert()
        
        # Create subscription plan without creating an item
        # We'll use a more test-friendly approach
        self.create_test_subscription_plan()
    
    def create_test_subscription_plan(self):
        """Create a subscription plan for testing without the item dependency"""
        plan_name = f"Test Plan - {self.membership_type_name}"
        
        # Delete existing plan if it exists
        if frappe.db.exists("Subscription Plan", plan_name):
            frappe.delete_doc("Subscription Plan", plan_name)
            
        # Create a test item for the plan if it doesn't exist
        item_code = f"TEST-MEMBERSHIP-ITEM"
        if not frappe.db.exists("Item", item_code):
            item = frappe.new_doc("Item")
            item.item_code = item_code
            item.item_name = "Test Membership Item"
            item.item_group = "Membership"
            item.is_stock_item = 0
            item.include_item_in_manufacturing = 0
            item.is_service_item = 1
            item.is_subscription_item = 1
            
            # Default warehouse
            item.append("item_defaults", {
                "company": frappe.defaults.get_global_default('company') or '_Test Company'
            })
            
            item.insert(ignore_permissions=True)
        
        # Create subscription plan
        plan = frappe.new_doc("Subscription Plan")
        plan.plan_name = plan_name
        plan.item = item_code
        plan.price_determination = "Fixed Rate"
        plan.cost = self.membership_type.amount
        plan.billing_interval = "Year"
        plan.billing_interval_count = 1
        plan.insert(ignore_permissions=True)
        
        # Link plan to membership type
        self.membership_type.subscription_plan = plan.name
        self.membership_type.save()
    
    def cleanup_test_data(self):
        # Clean up memberships
        for m in frappe.get_all("Membership", filters={"member": self.member.name}):
            try:
                membership = frappe.get_doc("Membership", m.name)
                if membership.docstatus == 1:
                    membership.cancel()
                frappe.delete_doc("Membership", m.name, force=True)
            except Exception as e:
                # Ignore errors during cleanup
                print(f"Error during cleanup: {str(e)}")
        
        # Clean up member
        if frappe.db.exists("Member", self.member.name):
            frappe.delete_doc("Member", self.member.name, force=True)
        
        # Clean up membership type
        if frappe.db.exists("Membership Type", self.membership_type_name):
            frappe.delete_doc("Membership Type", self.membership_type_name, force=True)
        
        # Clean up subscription plan
        plan_name = f"Test Plan - {self.membership_type_name}"
        if frappe.db.exists("Subscription Plan", plan_name):
            frappe.delete_doc("Subscription Plan", plan_name, force=True)
        
        # Clean up test item
        item_code = "TEST-MEMBERSHIP-ITEM"
        if frappe.db.exists("Item", item_code):
            frappe.delete_doc("Item", item_code, force=True)
        
        # We don't delete the Item Group as it might be used by other tests
    
    def test_create_membership(self):
        """Test creating a new membership"""
        # Create membership for the member
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = today()
        membership.insert()
        
        # Check initial values
        self.assertEqual(membership.member, self.member.name)
        self.assertEqual(membership.membership_type, self.membership_type_name)
        self.assertEqual(membership.status, "Draft")
        
        # Check renewal date calculation
        expected_renewal_date = add_months(getdate(membership.start_date), 12)
        self.assertEqual(getdate(membership.renewal_date), getdate(expected_renewal_date))
        
        # Check member name and email have been fetched
        self.assertEqual(membership.member_name, self.member.full_name)
        self.assertEqual(membership.email, self.member.email)
    
    def test_submit_membership(self):
        """Test submitting a membership"""
        # Create membership for the member
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = today()
        membership.insert()
        
        # Submit the membership
        membership.submit()
        
        # Reload the document
        membership.reload()
        
        # Check status after submission
        self.assertEqual(membership.status, "Active")
        self.assertEqual(membership.docstatus, 1)
        
        # Check if subscription was created
        self.assertTrue(membership.subscription, "Subscription should be created")
        
        # Verify subscription exists
        subscription = frappe.get_doc("Subscription", membership.subscription)
        self.assertEqual(subscription.party, self.member.customer)
        self.assertEqual(getdate(subscription.start_date), getdate(membership.start_date))
    
    def test_renew_membership(self):
        """Test membership renewal"""
        # Create and submit membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = add_months(today(), -12)  # Last year
        membership.insert()
        membership.submit()
        
        # Renew the membership
        new_membership_name = membership.renew_membership()
        
        # Check new membership
        new_membership = frappe.get_doc("Membership", new_membership_name)
        self.assertEqual(new_membership.member, membership.member)
        self.assertEqual(new_membership.membership_type, membership.membership_type)
        self.assertEqual(getdate(new_membership.start_date), getdate(membership.renewal_date))
    
    def test_cancel_membership(self):
        """Test cancelling a membership"""
        # Create and submit membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = add_months(today(), -13)  # More than 1 year ago (to allow cancellation)
        membership.insert()
        membership.submit()
        
        # Cancel the membership with reason
        from verenigingen.verenigingen.doctype.membership.membership import cancel_membership
        cancel_membership(
            membership_name=membership.name,
            cancellation_date=today(),
            cancellation_reason="Test cancellation",
            cancellation_type="Immediate"
        )
        
        # Reload the document
        membership.reload()
        
        # Check status after cancellation
        self.assertEqual(membership.status, "Cancelled")
        self.assertEqual(membership.cancellation_date, today())
        self.assertEqual(membership.cancellation_reason, "Test cancellation")
        self.assertEqual(membership.cancellation_type, "Immediate")
    
    def test_validate_dates(self):
        """Test validation of membership dates"""
        # Create membership with future start date
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = add_days(today(), 30)  # 30 days in future
        membership.insert()
        membership.submit()
        
        # Future cancellation date should be allowed
        from verenigingen.verenigingen.doctype.membership.membership import cancel_membership
        cancel_membership(
            membership_name=membership.name,
            cancellation_date=add_months(membership.start_date, 13),  # After 1 year minimum
            cancellation_reason="Future cancellation",
            cancellation_type="End of Period"
        )
        
        # Reload the document
        membership.reload()
        
        # Status should still be Active since cancellation is in future with End of Period
        self.assertEqual(membership.status, "Active")
        self.assertEqual(membership.cancellation_type, "End of Period")
    
    def test_early_cancellation_validation(self):
        """Test validation preventing early cancellation"""
        # Create and submit membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = add_months(today(), -6)  # 6 months ago (less than 1 year)
        membership.insert()
        membership.submit()
        
        # Try to cancel before 1 year - should raise an error
        from verenigingen.verenigingen.doctype.membership.membership import cancel_membership
        with self.assertRaises(frappe.exceptions.ValidationError):
            cancel_membership(
                membership_name=membership.name,
                cancellation_date=today(),
                cancellation_reason="Early cancellation",
                cancellation_type="Immediate"
            )
    
    def test_payment_sync(self):
        """Test payment synchronization from subscription"""
        # Create and submit membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = today()
        membership.insert()
        membership.submit()
        
        # Create a dummy invoice and payment
        # Mock a subscription update - normally this would be called by system events
        subscription = frappe.get_doc("Subscription", membership.subscription)
        
        # Manually set next billing date
        membership.next_billing_date = add_months(today(), 1)
        membership.save()
        
        # Call sync method directly to test
        membership.sync_payment_details_from_subscription()
        
        # Verify next_billing_date is preserved after sync
        self.assertEqual(getdate(membership.next_billing_date), getdate(add_months(today(), 1)))
    
    def test_end_of_period_cancellation(self):
        """Test end-of-period cancellation behavior"""
        # Create and submit membership
        membership = frappe.new_doc("Membership")
        membership.member = self.member.name
        membership.membership_type = self.membership_type_name
        membership.start_date = add_months(today(), -13)  # More than 1 year ago
        membership.insert()
        membership.submit()
        
        # Cancel with End of Period
        from verenigingen.verenigingen.doctype.membership.membership import cancel_membership
        cancel_membership(
            membership_name=membership.name,
            cancellation_date=today(),
            cancellation_reason="End of period test",
            cancellation_type="End of Period"
        )
        
        # Reload the document
        membership.reload()
        
        # Status should NOT be Cancelled because End of Period means active until renewal date
        # Assuming renewal date is in the future here
        if getdate(membership.renewal_date) > getdate(today()):
            self.assertNotEqual(membership.status, "Cancelled")
            self.assertEqual(membership.cancellation_type, "End of Period")

    def test_multiple_membership_validation(self):
        """Test validation preventing multiple active memberships"""
        # Create and submit first membership
        membership1 = frappe.new_doc("Membership")
        membership1.member = self.member.name
        membership1.membership_type = self.membership_type_name
        membership1.start_date = today()
        membership1.insert()
        membership1.submit()
        
        # Try to create a second membership - should validate and prevent
        membership2 = frappe.new_doc("Membership")
        membership2.member = self.member.name
        membership2.membership_type = self.membership_type_name
        membership2.start_date = add_days(today(), 1)
        
        # Should raise validation error unless allow_multiple_memberships is checked
        with self.assertRaises(frappe.exceptions.ValidationError):
            membership2.insert()
        
        # Now enable multiple memberships and try again
        membership2.allow_multiple_memberships = 1
        membership2.insert()
        
        # Should be allowed now
        self.assertTrue(membership2.name)

if __name__ == '__main__':
    unittest.main()
