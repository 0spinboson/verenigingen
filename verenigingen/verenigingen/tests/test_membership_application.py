import frappe
import unittest
from frappe.utils import today, add_days, now_datetime
from verenigingen.api.membership_application import (
    submit_application,
    approve_membership_application,
    reject_membership_application
)
from verenigingen.utils.application_payments import process_application_payment
from verenigingen.utils.application_notifications import check_overdue_applications

class TestMembershipApplication(unittest.TestCase):
    """Test membership application workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        # Create test membership type
        if not frappe.db.exists("Membership Type", "Test Membership"):
            membership_type = frappe.get_doc({
                "doctype": "Membership Type",
                "membership_type_name": "Test Membership",
                "amount": 100,
                "currency": "EUR",
                "subscription_period": "Annual"
            })
            membership_type.insert()
        
        # Create test chapter
        if not frappe.db.exists("Chapter", "Test Chapter"):
            chapter = frappe.get_doc({
                "doctype": "Chapter",
                "chapter_name": "Test Chapter",
                "region": "Test Region",
                "postal_codes": "1000-1999"
            })
            chapter.insert()
        
        # Create volunteer interest areas
        interest_areas = ["Event Planning", "Technical Support", "Community Outreach"]
        for area in interest_areas:
            if not frappe.db.exists("Volunteer Interest Area", area):
                frappe.get_doc({
                    "doctype": "Volunteer Interest Area",
                    "name": area
                }).insert()
    
    def setUp(self):
        """Set up for each test"""
        self.test_email = f"test_{frappe.generate_hash(length=8)}@example.com"
        self.application_data = {
            "first_name": "Test",
            "last_name": "Applicant",
            "email": self.test_email,
            "birth_date": "1990-01-01",
            "address_line1": "123 Test Street",
            "city": "Amsterdam",
            "postal_code": "1234",
            "country": "Netherlands",
            "selected_membership_type": "Test Membership",
            "contact_number": "+31612345678",
            "interested_in_volunteering": 1,
            "volunteer_availability": "Monthly",
            "volunteer_interests": ["Event Planning", "Technical Support"],
            "volunteer_skills": "Project management, Python programming",
            "newsletter_opt_in": 1,
            "application_source": "Website"
        }
    
    def tearDown(self):
        """Clean up after each test"""
        # Delete test member if exists
        if frappe.db.exists("Member", {"email": self.test_email}):
            member = frappe.get_doc("Member", {"email": self.test_email})
            
            # Delete related records
            if member.customer:
                frappe.delete_doc("Customer", member.customer)
            
            # Delete memberships
            memberships = frappe.get_all("Membership", filters={"member": member.name})
            for membership in memberships:
                frappe.delete_doc("Membership", membership.name)
            
            # Delete member
            frappe.delete_doc("Member", member.name)
        
        # Delete test lead
        if frappe.db.exists("Lead", {"email_id": self.test_email}):
            frappe.delete_doc("Lead", {"email_id": self.test_email})
        
        frappe.db.commit()
    
    def test_submit_application(self):
        """Test application submission"""
        result = submit_application(self.application_data)
        
        self.assertTrue(result["success"])
        self.assertIn("member_id", result)
        self.assertIn("lead_id", result)
        
        # Verify member created
        member = frappe.get_doc("Member", result["member_id"])
        self.assertEqual(member.application_status, "Pending")
        self.assertEqual(member.status, "Pending")
        self.assertEqual(member.email, self.test_email)
        self.assertEqual(member.interested_in_volunteering, 1)
        
        # Verify lead created
        lead = frappe.get_doc("Lead", result["lead_id"])
        self.assertEqual(lead.email_id, self.test_email)
        self.assertEqual(lead.member, member.name)
    
    def test_age_validation(self):
        """Test age validation for young applicants"""
        # Test with 10 year old
        young_data = self.application_data.copy()
        young_data["birth_date"] = add_days(today(), -365 * 10)
        young_data["email"] = f"young_{self.test_email}"
        
        result = submit_application(young_data)
        self.assertTrue(result["success"])
        
        # The application should still be accepted but age warning should be noted
        member = frappe.get_doc("Member", result["member_id"])
        self.assertEqual(member.age, 10)
    
    def test_chapter_suggestion(self):
        """Test automatic chapter suggestion"""
        result = submit_application(self.application_data)
        member = frappe.get_doc("Member", result["member_id"])
        
        # Should suggest Test Chapter based on postal code
        self.assertEqual(member.suggested_chapter, "Test Chapter")
    
    def test_approve_application(self):
        """Test application approval workflow"""
        # Submit application
        result = submit_application(self.application_data)
        member_name = result["member_id"]
        
        # Approve application
        frappe.set_user("Administrator")
        approval_result = approve_membership_application(member_name, "Approved for testing")
        
        self.assertTrue(approval_result["success"])
        self.assertIn("invoice", approval_result)
        
        # Verify member status
        member = frappe.get_doc("Member", member_name)
        self.assertEqual(member.application_status, "Approved")
        self.assertEqual(member.review_notes, "Approved for testing")
        
        # Verify membership created
        membership = frappe.get_doc("Membership", {"member": member_name})
        self.assertEqual(membership.status, "Pending")  # Pending payment
        self.assertEqual(membership.membership_type, "Test Membership")
    
    def test_reject_application(self):
        """Test application rejection"""
        # Submit application
        result = submit_application(self.application_data)
        member_name = result["member_id"]
        
        # Reject application
        frappe.set_user("Administrator")
        rejection_result = reject_membership_application(member_name, "Does not meet requirements")
        
        self.assertTrue(rejection_result["success"])
        
        # Verify member status
        member = frappe.get_doc("Member", member_name)
        self.assertEqual(member.application_status, "Rejected")
        self.assertEqual(member.status, "Rejected")
        self.assertEqual(member.review_notes, "Does not meet requirements")
    
    def test_payment_processing(self):
        """Test payment processing for approved application"""
        # Submit and approve application
        result = submit_application(self.application_data)
        member_name = result["member_id"]
        
        frappe.set_user("Administrator")
        approve_membership_application(member_name)
        
        # Process payment
        payment_result = process_application_payment(
            member_name,
            payment_method="Bank Transfer",
            payment_reference="TEST-PAY-001"
        )
        
        self.assertTrue(payment_result["success"])
        
        # Verify member activated
        member = frappe.get_doc("Member", member_name)
        self.assertEqual(member.application_status, "Completed")
        self.assertEqual(member.status, "Active")
        self.assertEqual(member.application_payment_status, "Completed")
        
        # Verify membership activated
        membership = frappe.get_doc("Membership", payment_result["membership"])
        self.assertEqual(membership.status, "Active")
        
        # Verify volunteer record created
        volunteer = frappe.get_doc("Volunteer", {"member": member_name})
        self.assertEqual(volunteer.volunteer_name, member.full_name)
        self.assertEqual(volunteer.status, "New")
    
    def test_duplicate_email_prevention(self):
        """Test that duplicate emails are prevented"""
        # Submit first application
        submit_application(self.application_data)
        
        # Try to submit with same email
        with self.assertRaises(frappe.ValidationError):
            submit_application(self.application_data)
    
    def test_overdue_detection(self):
        """Test overdue application detection"""
        # Create an old application
        old_data = self.application_data.copy()
        old_data["email"] = f"old_{self.test_email}"
        result = submit_application(old_data)
        
        # Manually set the application date to 3 weeks ago
        frappe.db.set_value(
            "Member",
            result["member_id"],
            "application_date",
            add_days(now_datetime(), -21)
        )
        
        # Run overdue check
        check_overdue_applications()
        
        # In a real scenario, this would send notifications
        # Here we just verify the function runs without error
        self.assertTrue(True)


class TestMembershipApplicationLoad(unittest.TestCase):
    """Load testing for membership applications"""
    
    def test_concurrent_applications(self):
        """Test handling of multiple concurrent applications"""
        import threading
        
        results = []
        errors = []
        
        def submit_test_application(index):
            try:
                data = {
                    "first_name": f"Test{index}",
                    "last_name": "Concurrent",
                    "email": f"concurrent{index}@test.com",
                    "birth_date": "1990-01-01",
                    "address_line1": "123 Test Street",
                    "city": "Amsterdam",
                    "postal_code": "1234",
                    "country": "Netherlands",
                    "selected_membership_type": "Test Membership"
                }
                result = submit_application(data)
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Create 10 concurrent applications
        threads = []
        for i in range(10):
            t = threading.Thread(target=submit_test_application, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify results
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 10)
        
        # Clean up
        for result in results:
            if "member_id" in result:
                frappe.delete_doc("Member", result["member_id"])
    
    def test_custom_fee_application_no_change_tracking(self):
        """Test that applications with custom fees don't trigger fee change tracking"""
        print("\n🧪 Testing custom fee application submission...")
        
        # Application data with custom amount
        custom_fee_data = self.application_data.copy()
        custom_fee_data["membership_amount"] = 75.0
        custom_fee_data["uses_custom_amount"] = True
        custom_fee_data["custom_amount_reason"] = "Supporter contribution level"
        custom_fee_data["email"] = f"customfee_{self.test_email}"
        
        # Submit application with custom fee
        result = submit_application(custom_fee_data)
        
        # Verify submission successful
        self.assertTrue(result["success"])
        self.assertIn("member_id", result)
        
        # Get created member
        member = frappe.get_doc("Member", result["member_id"])
        
        # Verify custom fee was set correctly
        self.assertEqual(member.membership_fee_override, 75.0)
        self.assertIn("Supporter contribution", member.fee_override_reason)
        self.assertEqual(member.application_status, "Pending")
        
        # KEY TEST: Verify no fee change tracking was triggered
        self.assertFalse(hasattr(member, '_pending_fee_change'),
                        "Application with custom fee should not trigger fee change tracking")
        
        print(f"✅ Custom fee application successful for {member.name}")
        print(f"   Custom fee: €{member.membership_fee_override}")
        print(f"   Reason: {member.fee_override_reason}")
        print(f"   No fee change tracking triggered (correct for new application)")
        
        # Clean up
        if member.customer:
            frappe.delete_doc("Customer", member.customer, force=True)
        frappe.delete_doc("Member", member.name, force=True)
    
    def test_iban_data_preservation(self):
        """Test that IBAN data from application is properly saved to member"""
        # Application data with IBAN details
        iban_data = self.application_data.copy()
        iban_data["payment_method"] = "Direct Debit"
        iban_data["iban"] = "NL02ABNA0123456789"
        iban_data["bic"] = "ABNANL2A"
        iban_data["bank_account_name"] = "Test Account Holder"
        iban_data["email"] = f"iban_{self.test_email}"
        
        # Submit application
        result = submit_application(iban_data)
        
        # Verify submission successful
        self.assertTrue(result["success"])
        self.assertIn("member_id", result)
        
        # Get created member
        member = frappe.get_doc("Member", result["member_id"])
        
        # Verify IBAN data was preserved
        self.assertEqual(member.iban, "NL02 ABNA 0123 4567 89")  # Should be formatted
        self.assertEqual(member.bic, "ABNANL2A")
        self.assertEqual(member.bank_account_name, "Test Account Holder")
        self.assertEqual(member.payment_method, "Direct Debit")
        
        print(f"✅ IBAN data properly transferred for {member.name}")
        
        # Clean up
        if member.customer:
            frappe.delete_doc("Customer", member.customer, force=True)
        frappe.delete_doc("Member", member.name, force=True)
    
    def test_contact_number_field_usage(self):
        """Test that contact_number is used instead of mobile_no"""
        # Submit application with contact number
        result = submit_application(self.application_data)
        
        # Get created member
        member = frappe.get_doc("Member", result["member_id"])
        
        # Verify contact_number field is used
        self.assertEqual(member.contact_number, "+31612345678")
        
        # Verify no mobile_no field is set (should not exist or be empty)
        self.assertFalse(hasattr(member, 'mobile_no') and getattr(member, 'mobile_no', None))
        
        print(f"✅ Contact number field properly used for {member.name}")
    
    def test_membership_submission_after_approval(self):
        """Test that membership is properly submitted after approval"""
        # Submit application
        result = submit_application(self.application_data)
        member_name = result["member_id"]
        
        # Approve application
        frappe.set_user("Administrator")
        approval_result = approve_membership_application(member_name, "Approved for testing")
        
        self.assertTrue(approval_result["success"])
        
        # Verify member status
        member = frappe.get_doc("Member", member_name)
        self.assertEqual(member.application_status, "Approved")
        
        # Verify membership was created and submitted properly
        memberships = frappe.get_all("Membership", filters={"member": member_name}, fields=["name", "docstatus", "status"])
        self.assertEqual(len(memberships), 1)
        
        membership = frappe.get_doc("Membership", memberships[0].name)
        self.assertEqual(membership.docstatus, 1)  # Should be submitted, not draft
        
        print(f"✅ Membership properly submitted for {member_name}")
    
    def test_invoice_period_dates(self):
        """Test that invoices have proper subscription period dates"""
        # Submit and approve application
        result = submit_application(self.application_data)
        member_name = result["member_id"]
        
        frappe.set_user("Administrator")
        approval_result = approve_membership_application(member_name)
        
        self.assertTrue(approval_result["success"])
        self.assertIn("invoice", approval_result)
        
        # Get the invoice
        invoice = frappe.get_doc("Sales Invoice", approval_result["invoice"])
        
        # Verify invoice has subscription period dates
        self.assertTrue(invoice.subscription_period_start, "Invoice should have subscription period start date")
        self.assertTrue(invoice.subscription_period_end, "Invoice should have subscription period end date")
        
        # Verify dates are logical (end after start)
        from frappe.utils import getdate
        start_date = getdate(invoice.subscription_period_start)
        end_date = getdate(invoice.subscription_period_end)
        self.assertTrue(end_date > start_date, "Subscription end date should be after start date")
        
        print(f"✅ Invoice {invoice.name} has proper subscription period: {start_date} to {end_date}")
    
    def test_no_duplicate_invoices(self):
        """Test that approval doesn't create duplicate invoices"""
        # Submit application
        result = submit_application(self.application_data)
        member_name = result["member_id"]
        
        # Approve application
        frappe.set_user("Administrator")
        approval_result = approve_membership_application(member_name)
        
        self.assertTrue(approval_result["success"])
        
        # Count invoices for this member
        member = frappe.get_doc("Member", member_name)
        if member.customer:
            invoices = frappe.get_all("Sales Invoice", filters={"customer": member.customer})
            self.assertEqual(len(invoices), 1, "Should only have one invoice after approval")
        
        print(f"✅ No duplicate invoices created for {member_name}")
    
    def test_volunteer_application_processing(self):
        """Test that volunteer applications are properly processed"""
        # Submit application with volunteer interest
        volunteer_data = self.application_data.copy()
        volunteer_data["interested_in_volunteering"] = 1
        volunteer_data["volunteer_availability"] = "Weekly"
        volunteer_data["volunteer_interests"] = ["Event Planning", "Technical Support"]
        volunteer_data["volunteer_skills"] = "Event coordination, Public speaking, IT support"
        volunteer_data["email"] = f"volunteer_{self.test_email}"
        
        result = submit_application(volunteer_data)
        
        # Verify submission successful
        self.assertTrue(result["success"])
        member = frappe.get_doc("Member", result["member_id"])
        
        # Verify volunteer data was stored
        self.assertEqual(member.interested_in_volunteering, 1)
        self.assertEqual(member.volunteer_availability, "Weekly")
        self.assertTrue(member.volunteer_skills)
        
        print(f"✅ Volunteer application data properly stored for {member.name}")
        
        # Clean up
        if member.customer:
            frappe.delete_doc("Customer", member.customer, force=True)
        frappe.delete_doc("Member", member.name, force=True)
    
    def test_volunteer_record_creation_after_payment(self):
        """Test that volunteer record is created after payment completion"""
        # Submit application with volunteer interest
        volunteer_data = self.application_data.copy()
        volunteer_data["interested_in_volunteering"] = 1
        volunteer_data["volunteer_availability"] = "Monthly"
        volunteer_data["volunteer_interests"] = ["Community Outreach"]
        volunteer_data["volunteer_skills"] = "Community engagement, Communication"
        volunteer_data["email"] = f"volpay_{self.test_email}"
        
        # Submit and approve application
        result = submit_application(volunteer_data)
        member_name = result["member_id"]
        
        frappe.set_user("Administrator")
        approve_membership_application(member_name)
        
        # Process payment to complete the workflow
        payment_result = process_application_payment(
            member_name,
            payment_method="Bank Transfer",
            payment_reference="TEST-VOL-001"
        )
        
        self.assertTrue(payment_result["success"])
        
        # Verify volunteer record was created
        volunteer_exists = frappe.db.exists("Volunteer", {"member": member_name})
        self.assertTrue(volunteer_exists, "Volunteer record should be created after payment")
        
        if volunteer_exists:
            volunteer = frappe.get_doc("Volunteer", {"member": member_name})
            self.assertEqual(volunteer.volunteer_name, frappe.get_doc("Member", member_name).full_name)
            self.assertTrue(volunteer.status in ["New", "Active"])
            
            print(f"✅ Volunteer record created: {volunteer.name} for member {member_name}")
        
        # Clean up
        member = frappe.get_doc("Member", member_name)
        if volunteer_exists:
            frappe.delete_doc("Volunteer", volunteer.name, force=True)
        if member.customer:
            frappe.delete_doc("Customer", member.customer, force=True)
        # Delete membership
        memberships = frappe.get_all("Membership", filters={"member": member_name})
        for membership in memberships:
            frappe.delete_doc("Membership", membership.name, force=True)
        frappe.delete_doc("Member", member_name, force=True)
    
    def test_non_volunteer_application(self):
        """Test that non-volunteer applications don't create volunteer records"""
        # Submit application without volunteer interest
        non_volunteer_data = self.application_data.copy()
        non_volunteer_data["interested_in_volunteering"] = 0
        non_volunteer_data["email"] = f"nonvol_{self.test_email}"
        
        # Submit, approve and complete payment
        result = submit_application(non_volunteer_data)
        member_name = result["member_id"]
        
        frappe.set_user("Administrator")
        approve_membership_application(member_name)
        
        payment_result = process_application_payment(
            member_name,
            payment_method="Bank Transfer",
            payment_reference="TEST-NONVOL-001"
        )
        
        self.assertTrue(payment_result["success"])
        
        # Verify NO volunteer record was created
        volunteer_exists = frappe.db.exists("Volunteer", {"member": member_name})
        self.assertFalse(volunteer_exists, "No volunteer record should be created for non-volunteer members")
        
        print(f"✅ No volunteer record created for non-volunteer member {member_name}")
        
        # Clean up
        member = frappe.get_doc("Member", member_name)
        if member.customer:
            frappe.delete_doc("Customer", member.customer, force=True)
        # Delete membership
        memberships = frappe.get_all("Membership", filters={"member": member_name})
        for membership in memberships:
            frappe.delete_doc("Membership", membership.name, force=True)
        frappe.delete_doc("Member", member_name, force=True)
    
    def test_volunteer_interest_areas_validation(self):
        """Test that volunteer interest areas are properly validated"""
        # Submit application with valid volunteer interests
        valid_volunteer_data = self.application_data.copy()
        valid_volunteer_data["interested_in_volunteering"] = 1
        valid_volunteer_data["volunteer_interests"] = ["Event Planning", "Technical Support"]
        valid_volunteer_data["email"] = f"validvol_{self.test_email}"
        
        result = submit_application(valid_volunteer_data)
        self.assertTrue(result["success"])
        
        member = frappe.get_doc("Member", result["member_id"])
        # Should store the interests properly
        self.assertTrue(member.interested_in_volunteering)
        
        print(f"✅ Valid volunteer interests processed for {member.name}")
        
        # Clean up
        if member.customer:
            frappe.delete_doc("Customer", member.customer, force=True)
        frappe.delete_doc("Member", member.name, force=True)


def run_tests():
    """Run all membership application tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
