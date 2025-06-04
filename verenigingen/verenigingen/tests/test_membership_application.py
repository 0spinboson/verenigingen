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
            "mobile_no": "+31612345678",
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


def run_tests():
    """Run all membership application tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
