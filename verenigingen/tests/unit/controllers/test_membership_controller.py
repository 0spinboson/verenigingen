# -*- coding: utf-8 -*-
# Copyright (c) 2025, Your Organization and Contributors
# See license.txt

"""
Unit tests for Membership controller methods
Tests the Python controller methods including minimum period enforcement
"""

import unittest
import frappe
from frappe.utils import today, add_days, add_months, getdate
from verenigingen.verenigingen.tests.utils.base import VereningingenUnitTestCase
from verenigingen.verenigingen.tests.utils.factories import TestDataBuilder
from verenigingen.verenigingen.tests.utils.setup_helpers import TestEnvironmentSetup
from verenigingen.tests.test_membership_utilities import MembershipTestUtilities


class TestMembershipController(VereningingenUnitTestCase):
    """Test Membership controller methods"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        super().setUpClass()
        cls.test_env = TestEnvironmentSetup.create_standard_test_environment()
        
    def setUp(self):
        """Set up for each test"""
        super().setUp()
        self.builder = TestDataBuilder()
        
    def tearDown(self):
        """Clean up after each test"""
        self.builder.cleanup()
        super().tearDown()
        
    def test_validate_dates_method(self):
        """Test the validate_dates method"""
        # Create member and membership type
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        membership_type = self.test_env["membership_types"][0]  # Annual type
        
        # Test valid dates
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": membership_type.name,
            "start_date": today(),
            "end_date": add_days(today(), 365)
        })
        
        # Should not raise error
        membership.validate_dates()
        
        # Test end date before start date
        membership.end_date = add_days(today(), -1)
        with self.assert_validation_error("End date"):
            membership.validate_dates()
            
    def test_set_renewal_date_with_minimum_period_enabled(self):
        """Test renewal date calculation with minimum period enforced"""
        # Create membership type with minimum period enabled
        membership_type = frappe.get_doc({
            "doctype": "Membership Type",
            "membership_type_name": "Test Enforced Annual",
            "amount": 100,
            "currency": "EUR",
            "subscription_period": "Monthly",  # Monthly but enforced to 1 year
            "enforce_minimum_period": 1
        })
        membership_type.insert(ignore_permissions=True)
        self.track_doc("Membership Type", membership_type.name)
        
        # Create member and membership
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": membership_type.name,
            "start_date": today()
        })
        
        # Set renewal date should enforce minimum 1 year
        membership.set_renewal_date()
        
        expected_end_date = add_months(today(), 12)
        self.assertEqual(getdate(membership.end_date), getdate(expected_end_date))
        
    def test_set_renewal_date_with_minimum_period_disabled(self):
        """Test renewal date calculation with minimum period disabled"""
        # Create membership type with minimum period disabled
        membership_type = frappe.get_doc({
            "doctype": "Membership Type",
            "membership_type_name": "Test Monthly No Minimum",
            "amount": 10,
            "currency": "EUR",
            "subscription_period": "Monthly",
            "enforce_minimum_period": 0
        })
        membership_type.insert(ignore_permissions=True)
        self.track_doc("Membership Type", membership_type.name)
        
        # Create member and membership
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": membership_type.name,
            "start_date": today()
        })
        
        # Set renewal date should follow subscription period (1 month)
        membership.set_renewal_date()
        
        expected_end_date = add_months(today(), 1)
        self.assertEqual(getdate(membership.end_date), getdate(expected_end_date))
        
    def test_set_renewal_date_daily_period(self):
        """Test renewal date calculation for daily period"""
        # Use context manager to temporarily disable minimum period
        with MembershipTestUtilities.with_minimum_period_disabled(["Test Daily Membership"]):
            membership_type = self.test_env["membership_types"][3]  # Daily type
            
            test_data = self.builder.with_member().build()
            member = test_data["member"]
            
            membership = frappe.get_doc({
                "doctype": "Membership",
                "member": member.name,
                "membership_type": membership_type.name,
                "start_date": today()
            })
            
            # Set renewal date for daily period
            membership.set_renewal_date()
            
            expected_end_date = add_days(today(), 1)
            self.assertEqual(getdate(membership.end_date), getdate(expected_end_date))
            
    def test_create_subscription_method(self):
        """Test subscription creation from membership"""
        # Create member with membership
        test_data = (self.builder
            .with_member()
            .with_membership(membership_type=self.test_env["membership_types"][0].name)
            .build())
        
        member = test_data["member"]
        membership = test_data["membership"]
        
        # Test subscription creation
        # This would test the actual subscription creation logic
        # Implementation depends on ERPNext subscription setup
        
    def test_sync_payment_details_from_subscription(self):
        """Test payment details sync from subscription"""
        # Create member with membership and subscription
        test_data = (self.builder
            .with_member()
            .with_membership(membership_type=self.test_env["membership_types"][0].name)
            .build())
        
        membership = test_data["membership"]
        
        # Test payment sync
        # This would test syncing payment status from subscription
        
    def test_cancel_subscription_method(self):
        """Test subscription cancellation"""
        # Create member with active membership
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=self.test_env["membership_types"][0].name,
                status="Active"
            )
            .build())
        
        membership = test_data["membership"]
        
        # Test cancellation
        # This would test the subscription cancellation logic
        
    def test_on_cancel_with_minimum_period(self):
        """Test membership cancellation respects minimum period"""
        # Create membership with minimum period enforced
        membership_type = self.test_env["membership_types"][0]  # Annual with minimum
        
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=membership_type.name,
                start_date=add_days(today(), -30)  # Started 30 days ago
            )
            .build())
        
        membership = test_data["membership"]
        membership.submit()  # Submit to enable cancellation
        
        # Try to cancel before minimum period
        with self.assert_validation_error("minimum period"):
            membership.cancel()
            
    def test_membership_lifecycle_hooks(self):
        """Test membership lifecycle event hooks"""
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        membership_type = self.test_env["membership_types"][0]
        
        # Test before_insert
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": membership_type.name,
            "start_date": today()
        })
        
        # Insert should trigger hooks
        membership.insert()
        self.track_doc("Membership", membership.name)
        
        # Should have end date set
        self.assertIsNotNone(membership.end_date)
        
        # Test on_update
        membership.status = "Suspended"
        membership.save()
        
        # Member status should be updated
        member.reload()
        # Implementation depends on status sync logic
        
    def test_get_membership_details(self):
        """Test getting membership details for display"""
        test_data = (self.builder
            .with_member()
            .with_membership(membership_type=self.test_env["membership_types"][0].name)
            .build())
        
        membership = test_data["membership"]
        
        # Test getting formatted details
        details = membership.get_membership_details()
        
        self.assertIn("type", details)
        self.assertIn("status", details)
        self.assertIn("start_date", details)
        self.assertIn("end_date", details)
        
    def test_renewal_notification_scheduling(self):
        """Test scheduling of renewal notifications"""
        # Create membership near expiry
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=self.test_env["membership_types"][0].name,
                start_date=add_days(today(), -335),  # Expires in 30 days
                end_date=add_days(today(), 30)
            )
            .build())
        
        membership = test_data["membership"]
        
        # Test notification scheduling
        # This would test the notification scheduling logic
        
    def test_payment_status_sync(self):
        """Test payment status synchronization"""
        test_data = (self.builder
            .with_member()
            .with_membership(membership_type=self.test_env["membership_types"][0].name)
            .build())
        
        membership = test_data["membership"]
        
        # Test various payment status scenarios
        payment_statuses = ["Paid", "Overdue", "Failed", "Pending"]
        
        for status in payment_statuses:
            # This would test payment status sync logic
            pass
            
    def test_membership_type_change(self):
        """Test changing membership type"""
        test_data = (self.builder
            .with_member()
            .with_membership(membership_type=self.test_env["membership_types"][0].name)
            .build())
        
        membership = test_data["membership"]
        
        # Try to change to different type
        new_type = self.test_env["membership_types"][1]  # Student type
        membership.membership_type = new_type.name
        
        # This would test the membership type change logic
        # Including pro-rating, fee adjustments, etc.
        
    def test_concurrent_membership_validation(self):
        """Test validation of concurrent memberships"""
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        
        # Create first active membership
        membership1 = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": self.test_env["membership_types"][0].name,
            "start_date": today(),
            "end_date": add_days(today(), 365),
            "status": "Active"
        })
        membership1.insert()
        self.track_doc("Membership", membership1.name)
        
        # Try to create overlapping membership
        membership2 = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": self.test_env["membership_types"][1].name,
            "start_date": add_days(today(), 30),
            "status": "Active"
        })
        
        # Should raise validation error for overlap
        with self.assert_validation_error("overlapping"):
            membership2.insert()
            
    def test_renew_membership_method(self):
        """Test the renew_membership method"""
        # Create expired membership
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=self.test_env["membership_types"][0].name,
                start_date=add_days(today(), -400),
                end_date=add_days(today(), -35),
                status="Expired"
            )
            .build())
        
        membership = test_data["membership"]
        
        # Renew membership
        new_membership = membership.renew_membership()
        
        # Verify new membership created
        self.assertIsNotNone(new_membership)
        self.assertEqual(new_membership.member, membership.member)
        self.assertEqual(new_membership.membership_type, membership.membership_type)
        self.assertEqual(new_membership.status, "Active")
        self.assertEqual(getdate(new_membership.start_date), getdate(today()))
        
    def test_calculate_effective_amount(self):
        """Test membership fee calculation with discounts"""
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        membership_type = self.test_env["membership_types"][0]
        
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": membership_type.name,
            "start_date": today()
        })
        
        # Test normal amount
        amount = membership.calculate_effective_amount()
        self.assertEqual(amount, membership_type.amount)
        
        # Test with discount
        membership.discount_percentage = 25
        amount = membership.calculate_effective_amount()
        expected = membership_type.amount * 0.75
        self.assertEqual(amount, expected)
        
        # Test with fee override on member
        member.membership_fee_override = 50
        member.save(ignore_permissions=True)
        membership.reload()
        amount = membership.calculate_effective_amount()
        self.assertEqual(amount, 50)
        
    def test_update_member_status_method(self):
        """Test member status updates from membership changes"""
        test_data = (self.builder
            .with_member(status="Active")
            .with_membership(
                membership_type=self.test_env["membership_types"][0].name,
                status="Active"
            )
            .build())
        
        member = test_data["member"]
        membership = test_data["membership"]
        
        # Change membership to expired
        membership.status = "Expired"
        membership.update_member_status()
        
        # Member status should reflect membership
        member.reload()
        self.assertEqual(member.membership_status, "Expired")
        
    def test_get_billing_amount(self):
        """Test billing amount calculation"""
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=self.test_env["membership_types"][2].name  # Monthly
            )
            .build())
        
        membership = test_data["membership"]
        
        # Test billing amount
        billing_amount = membership.get_billing_amount()
        self.assertGreater(billing_amount, 0)
        
    def test_validate_membership_type(self):
        """Test membership type validation"""
        test_data = self.builder.with_member().build()
        member = test_data["member"]
        
        # Test with invalid membership type
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": "Invalid Type",
            "start_date": today()
        })
        
        with self.assert_validation_error("Membership Type"):
            membership.validate_membership_type()
            
    def test_on_submit_hooks(self):
        """Test on_submit lifecycle hooks"""
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=self.test_env["membership_types"][0].name
            )
            .build())
        
        membership = test_data["membership"]
        member = test_data["member"]
        
        # Submit membership
        membership.submit()
        
        # Check member fields updated
        member.reload()
        self.assertEqual(member.membership_status, "Active")
        self.assertIsNotNone(member.current_membership_type)
        
    def test_regenerate_pending_invoices(self):
        """Test regeneration of pending invoices"""
        test_data = (self.builder
            .with_member()
            .with_membership(
                membership_type=self.test_env["membership_types"][0].name
            )
            .build())
        
        membership = test_data["membership"]
        
        # This would test invoice regeneration logic
        # Implementation depends on ERPNext integration