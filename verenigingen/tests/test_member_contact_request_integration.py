"""
Comprehensive integration tests for Member Contact Request workflow
Tests the complete flow from portal submission to CRM integration
"""

import unittest
import frappe
from frappe.utils import today, add_days
from unittest.mock import patch, MagicMock


class TestMemberContactRequestIntegration(unittest.TestCase):
    """Test Member Contact Request integration end-to-end"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        frappe.set_user("Administrator")
    
    def setUp(self):
        """Set up test data for each test"""
        # Create test member
        self.test_member = frappe.get_doc({
            "doctype": "Member",
            "member_name": "John Doe Test",
            "first_name": "John",
            "last_name": "Doe",
            "email_address": "john.doe.test@example.com",
            "phone_number": "+31612345678",
            "membership_status": "Active",
            "status": "Active"
        })
        self.test_member.insert(ignore_permissions=True)
        
        # Clean up any existing contact requests for this member
        frappe.db.delete("Member Contact Request", {"member": self.test_member.name})
        frappe.db.commit()
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up contact requests
        frappe.db.delete("Member Contact Request", {"member": self.test_member.name})
        
        # Clean up CRM leads (if any were created)
        try:
            leads = frappe.get_all("Lead", 
                filters={"custom_member_id": self.test_member.name},
                fields=["name"]
            )
            for lead in leads:
                frappe.delete_doc("Lead", lead.name, force=True, ignore_permissions=True)
        except:
            pass  # CRM module might not be available
        
        # Clean up member
        frappe.delete_doc("Member", self.test_member.name, force=True, ignore_permissions=True)
        frappe.db.commit()
    
    def test_contact_request_creation_basic(self):
        """Test basic contact request creation"""
        from verenigingen.verenigingen.doctype.member_contact_request.member_contact_request import create_contact_request
        
        # Create contact request
        result = create_contact_request(
            member=self.test_member.name,
            subject="Test Integration Request",
            message="This is a test message for integration testing",
            request_type="General Inquiry",
            preferred_contact_method="Email",
            urgency="Normal"
        )
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertIn("contact_request", result)
        
        # Verify contact request was created
        contact_request = frappe.get_doc("Member Contact Request", result["contact_request"])
        self.assertEqual(contact_request.member, self.test_member.name)
        self.assertEqual(contact_request.subject, "Test Integration Request")
        self.assertEqual(contact_request.status, "Open")
        self.assertEqual(contact_request.member_name, self.test_member.member_name)
        self.assertEqual(contact_request.email, self.test_member.email_address)
        self.assertTrue(contact_request.created_by_portal)
    
    @patch('frappe.get_doc')
    def test_crm_lead_creation(self, mock_get_doc):
        """Test CRM Lead creation from contact request"""
        # Mock the Lead doctype to simulate CRM module availability
        mock_lead = MagicMock()
        mock_lead.name = "LEAD-001"
        mock_lead.insert.return_value = None
        
        # Mock frappe.get_doc to return our mock lead when creating Lead
        def mock_get_doc_side_effect(data_or_doctype, name=None):
            if isinstance(data_or_doctype, dict) and data_or_doctype.get("doctype") == "Lead":
                return mock_lead
            elif data_or_doctype == "Member":
                return self.test_member
            else:
                # For other doctypes, call the real function
                return frappe.get_doc.__wrapped__(data_or_doctype, name)
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Mock DocType existence check
        with patch('frappe.db.exists') as mock_exists:
            mock_exists.return_value = True
            
            # Create contact request
            contact_request = frappe.get_doc({
                "doctype": "Member Contact Request",
                "member": self.test_member.name,
                "subject": "CRM Integration Test",
                "message": "Testing CRM lead creation",
                "request_type": "Volunteer Opportunity",
                "preferred_contact_method": "Email",
                "urgency": "High",
                "created_by_portal": 1
            })
            contact_request.insert(ignore_permissions=True)
            
            # Verify CRM lead reference was set
            self.assertEqual(contact_request.crm_lead, "LEAD-001")
    
    def test_contact_request_status_transitions(self):
        """Test contact request status transitions and automation"""
        # Create contact request
        contact_request = frappe.get_doc({
            "doctype": "Member Contact Request",
            "member": self.test_member.name,
            "subject": "Status Transition Test",
            "message": "Testing status transitions",
            "request_type": "Technical Support",
            "status": "Open"
        })
        contact_request.insert(ignore_permissions=True)
        
        # Test status change to In Progress
        contact_request.status = "In Progress"
        contact_request.save(ignore_permissions=True)
        
        # Verify response date was set
        self.assertIsNotNone(contact_request.response_date)
        
        # Test status change to Resolved
        contact_request.status = "Resolved"
        contact_request.save(ignore_permissions=True)
        
        # Verify closed date was set
        self.assertIsNotNone(contact_request.closed_date)
    
    def test_assignment_workflow(self):
        """Test assignment workflow and notifications"""
        # Create a test user for assignment
        test_user_email = "test.user@example.com"
        
        # Create contact request
        contact_request = frappe.get_doc({
            "doctype": "Member Contact Request",
            "member": self.test_member.name,
            "subject": "Assignment Test",
            "message": "Testing assignment workflow",
            "request_type": "Complaint",
            "urgency": "High"
        })
        contact_request.insert(ignore_permissions=True)
        
        # Mock sendmail to prevent actual email sending during tests
        with patch('frappe.sendmail') as mock_sendmail:
            # Assign to user
            contact_request.assigned_to = "Administrator"
            contact_request.save(ignore_permissions=True)
            
            # Verify follow-up date was set
            self.assertIsNotNone(contact_request.follow_up_date)
    
    def test_get_member_contact_requests_api(self):
        """Test API for retrieving member contact requests"""
        from verenigingen.verenigingen.doctype.member_contact_request.member_contact_request import get_member_contact_requests
        
        # Create multiple contact requests
        for i in range(3):
            contact_request = frappe.get_doc({
                "doctype": "Member Contact Request",
                "member": self.test_member.name,
                "subject": f"Test Request {i+1}",
                "message": f"Test message {i+1}",
                "request_type": "General Inquiry",
                "status": "Open" if i % 2 == 0 else "Resolved"
            })
            contact_request.insert(ignore_permissions=True)
        
        # Test API call
        requests = get_member_contact_requests(self.test_member.name, limit=5)
        
        # Verify results
        self.assertEqual(len(requests), 3)
        self.assertTrue(all(req["member"] == self.test_member.name for req in requests))
    
    def test_portal_form_submission(self):
        """Test contact request submission through portal form"""
        # Simulate portal form submission
        form_data = {
            "subject": "Portal Form Test",
            "message": "Testing portal form submission",
            "request_type": "Event Information",
            "preferred_contact_method": "Phone",
            "urgency": "Normal",
            "preferred_time": "Weekdays 9-17"
        }
        
        # Mock session user as the test member
        with patch('frappe.session.user', self.test_member.email_address):
            # Mock member lookup to return our test member
            with patch('frappe.db.get_value') as mock_get_value:
                mock_get_value.return_value = self.test_member.name
                
                # Mock member permission check
                with patch.object(self.test_member, 'has_permission', return_value=True):
                    from verenigingen.verenigingen.doctype.member_contact_request.member_contact_request import create_contact_request
                    
                    result = create_contact_request(
                        member=self.test_member.name,
                        subject=form_data["subject"],
                        message=form_data["message"],
                        request_type=form_data["request_type"],
                        preferred_contact_method=form_data["preferred_contact_method"],
                        urgency=form_data["urgency"],
                        preferred_time=form_data["preferred_time"]
                    )
                    
                    # Verify submission success
                    self.assertTrue(result["success"])
                    
                    # Verify contact request was created with portal flag
                    contact_request = frappe.get_doc("Member Contact Request", result["contact_request"])
                    self.assertTrue(contact_request.created_by_portal)
                    self.assertEqual(contact_request.preferred_time, form_data["preferred_time"])
    
    @patch('frappe.sendmail')
    def test_automation_workflows(self, mock_sendmail):
        """Test automated workflows like follow-ups and escalations"""
        from verenigingen.verenigingen.doctype.member_contact_request.contact_request_automation import (
            send_follow_up_reminders,
            escalate_overdue_requests,
            auto_close_resolved_requests
        )
        
        # Create overdue contact request
        overdue_request = frappe.get_doc({
            "doctype": "Member Contact Request",
            "member": self.test_member.name,
            "subject": "Overdue Test Request",
            "message": "Testing overdue automation",
            "request_type": "Urgent",
            "urgency": "Urgent",
            "status": "Open",
            "request_date": add_days(today(), -2),  # 2 days ago
            "follow_up_date": today(),  # Due today
            "assigned_to": "Administrator"
        })
        overdue_request.insert(ignore_permissions=True)
        
        # Test follow-up reminders
        send_follow_up_reminders()
        
        # Verify follow-up date was updated
        overdue_request.reload()
        self.assertNotEqual(overdue_request.follow_up_date, today())
        
        # Test auto-close for resolved requests
        resolved_request = frappe.get_doc({
            "doctype": "Member Contact Request",
            "member": self.test_member.name,
            "subject": "Auto-close Test",
            "message": "Testing auto-close",
            "status": "Resolved",
            "response_date": add_days(today(), -8)  # 8 days ago
        })
        resolved_request.insert(ignore_permissions=True)
        
        auto_close_resolved_requests()
        
        # Verify request was auto-closed
        resolved_request.reload()
        self.assertEqual(resolved_request.status, "Closed")
        self.assertIsNotNone(resolved_request.closed_date)
    
    def test_permission_validation(self):
        """Test permission validation for contact requests"""
        from verenigingen.verenigingen.doctype.member_contact_request.member_contact_request import create_contact_request
        
        # Test guest user access (should fail)
        with patch('frappe.session.user', 'Guest'):
            with self.assertRaises(frappe.exceptions.PermissionError):
                create_contact_request(
                    member=self.test_member.name,
                    subject="Unauthorized Test",
                    message="This should fail"
                )
        
        # Test user without member record (should fail)
        with patch('frappe.session.user', 'no.member@example.com'):
            with patch('frappe.db.get_value', return_value=None):
                with self.assertRaises(frappe.exceptions.DoesNotExistError):
                    create_contact_request(
                        member=self.test_member.name,
                        subject="No Member Test",
                        message="This should fail"
                    )
    
    def test_analytics_and_reporting(self):
        """Test analytics and reporting functionality"""
        from verenigingen.verenigingen.doctype.member_contact_request.contact_request_automation import get_contact_request_analytics
        
        # Create test contact requests with different statuses and types
        test_requests = [
            {"status": "Open", "request_type": "General Inquiry"},
            {"status": "In Progress", "request_type": "Technical Support"},
            {"status": "Resolved", "request_type": "General Inquiry"},
            {"status": "Closed", "request_type": "Complaint"}
        ]
        
        for req_data in test_requests:
            contact_request = frappe.get_doc({
                "doctype": "Member Contact Request",
                "member": self.test_member.name,
                "subject": f"Analytics Test - {req_data['request_type']}",
                "message": "Test for analytics",
                "request_type": req_data["request_type"],
                "status": req_data["status"],
                "response_date": today() if req_data["status"] != "Open" else None
            })
            contact_request.insert(ignore_permissions=True)
        
        # Test analytics
        analytics = get_contact_request_analytics()
        
        # Verify analytics structure
        self.assertIn("status_distribution", analytics)
        self.assertIn("request_types", analytics)
        self.assertIn("avg_response_time_days", analytics)
        self.assertIn("monthly_volume", analytics)


def run_integration_tests():
    """Run all integration tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMemberContactRequestIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    # Set up Frappe environment
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    
    try:
        success = run_integration_tests()
        print(f"\nIntegration tests {'PASSED' if success else 'FAILED'}")
    except Exception as e:
        print(f"Error running integration tests: {str(e)}")
        frappe.log_error(f"Integration test error: {str(e)}", "Test Error")
    finally:
        frappe.destroy()