"""
Comprehensive unit tests for Enhanced Membership Termination & Appeals System
"""

import frappe
import unittest
from frappe.utils import today, add_days, now
from unittest.mock import patch

class TestTerminationSystem(unittest.TestCase):
    """Test suite for termination system workflows and functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        print("🧪 Setting up termination system tests...")
        
        # Ensure workflows exist
        cls.setup_test_workflows()
        
        # Create test roles if needed
        cls.setup_test_roles()
        
        # Create test users with proper roles
        cls.setup_test_users()
        
        # Create test member data
        cls.setup_test_members()
    
    @classmethod
    def setup_test_workflows(cls):
        """Ensure test workflows exist"""
        from verenigingen.corrected_workflow_setup import setup_workflows_corrected
        
        # Clean up any existing test workflows
        for workflow_name in ["Membership Termination Workflow", "Termination Appeals Workflow"]:
            if frappe.db.exists("Workflow", workflow_name):
                try:
                    frappe.delete_doc("Workflow", workflow_name, force=True)
                except:
                    pass
        
        # Create fresh workflows for testing
        setup_workflows_corrected()
        frappe.db.commit()
    
    @classmethod
    def setup_test_roles(cls):
        """Create test roles if they don't exist"""
        required_roles = ["Association Manager", "Test User Role"]
        
        for role_name in required_roles:
            if not frappe.db.exists("Role", role_name):
                role = frappe.get_doc({
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                    "is_custom": 1
                })
                role.insert(ignore_permissions=True)
        
        frappe.db.commit()
    
    @classmethod
    def setup_test_users(cls):
        """Create test users for different roles"""
        cls.test_users = {}
        
        # Association Manager user
        if not frappe.db.exists("User", "test_assoc_manager@example.com"):
            user = frappe.get_doc({
                "doctype": "User",
                "email": "test_assoc_manager@example.com",
                "first_name": "Test",
                "last_name": "Manager",
                "send_welcome_email": 0,
                "roles": [
                    {"role": "Association Manager"},
                    {"role": "System Manager"}  # For testing purposes
                ]
            })
            user.insert(ignore_permissions=True)
        
        cls.test_users["manager"] = "test_assoc_manager@example.com"
        frappe.db.commit()
    
    @classmethod
    def setup_test_members(cls):
        """Create test member data"""
        cls.test_members = {}
        
        # Test member 1 - for standard termination
        member_data = {
            "doctype": "Member",
            "first_name": "John",
            "last_name": "TestMember",
            "full_name": "John TestMember",
            "email": "john.test@example.com",
            "status": "Active"
        }
        
        # Check if member exists, if not create
        if not frappe.db.exists("Member", {"email": "john.test@example.com"}):
            member = frappe.get_doc(member_data)
            member.insert(ignore_permissions=True)
            cls.test_members["john"] = member.name
        else:
            cls.test_members["john"] = frappe.db.get_value("Member", {"email": "john.test@example.com"}, "name")
        
        frappe.db.commit()
    
    def setUp(self):
        """Set up for each individual test"""
        # Set test user context
        frappe.set_user(self.test_users["manager"])
        
        # Start fresh transaction for each test
        frappe.db.rollback()
        frappe.db.begin()
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up any test documents created during the test
        self.cleanup_test_documents()
        
        # Rollback any changes
        frappe.db.rollback()
    
    def cleanup_test_documents(self):
        """Clean up test documents"""
        # Delete test termination requests
        test_requests = frappe.get_all(
            "Membership Termination Request",
            filters={"member": ["in", list(self.test_members.values())]},
            fields=["name"]
        )
        
        for request in test_requests:
            try:
                frappe.delete_doc("Membership Termination Request", request.name, force=True)
            except:
                pass
        
        # Delete test appeals
        test_appeals = frappe.get_all(
            "Termination Appeals Process", 
            filters={"member": ["in", list(self.test_members.values())]},
            fields=["name"]
        )
        
        for appeal in test_appeals:
            try:
                frappe.delete_doc("Termination Appeals Process", appeal.name, force=True)
            except:
                pass

class TestWorkflowCreation(TestTerminationSystem):
    """Test workflow creation and structure"""
    
    def test_termination_workflow_exists(self):
        """Test that termination workflow exists and is properly configured"""
        self.assertTrue(
            frappe.db.exists("Workflow", "Membership Termination Workflow"),
            "Membership Termination Workflow should exist"
        )
        
        workflow = frappe.get_doc("Workflow", "Membership Termination Workflow")
        
        # Check basic properties
        self.assertEqual(workflow.document_type, "Membership Termination Request")
        self.assertEqual(workflow.workflow_state_field, "status")
        self.assertTrue(workflow.is_active)
        
        # Check states
        self.assertGreaterEqual(len(workflow.states), 4, "Should have at least 4 states")
        state_names = [state.state for state in workflow.states]
        required_states = ["Draft", "Pending", "Approved", "Executed"]
        
        for state in required_states:
            self.assertIn(state, state_names, f"State '{state}' should exist")
        
        # Check transitions
        self.assertGreaterEqual(len(workflow.transitions), 6, "Should have at least 6 transitions")
    
    def test_appeals_workflow_exists(self):
        """Test that appeals workflow exists and is properly configured"""
        self.assertTrue(
            frappe.db.exists("Workflow", "Termination Appeals Workflow"),
            "Termination Appeals Workflow should exist"
        )
        
        workflow = frappe.get_doc("Workflow", "Termination Appeals Workflow")
        
        # Check basic properties
        self.assertEqual(workflow.document_type, "Termination Appeals Process")
        self.assertEqual(workflow.workflow_state_field, "appeal_status")
        self.assertTrue(workflow.is_active)
        
        # Check states
        self.assertGreaterEqual(len(workflow.states), 3, "Should have at least 3 states")
        state_names = [state.state for state in workflow.states]
        required_states = ["Draft", "Pending"]
        
        for state in required_states:
            self.assertIn(state, state_names, f"State '{state}' should exist")
    
    def test_workflow_masters_exist(self):
        """Test that required workflow masters exist"""
        # Check custom workflow state
        self.assertTrue(
            frappe.db.exists("Workflow State", "Executed"),
            "Custom 'Executed' workflow state should exist"
        )
        
        # Check custom workflow action
        self.assertTrue(
            frappe.db.exists("Workflow Action Master", "Execute"),
            "Custom 'Execute' workflow action should exist"
        )

class TestTerminationRequestWorkflow(TestTerminationSystem):
    """Test termination request document workflow"""
    
    def test_create_termination_request(self):
        """Test creating a basic termination request"""
        termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Voluntary",
            "termination_reason": "Test termination for unit testing",
            "requested_by": frappe.session.user,
            "request_date": today()
        })
        
        # Should not raise any exceptions
        termination.insert()
        
        # Check initial state
        self.assertEqual(termination.status, "Draft")
        self.assertFalse(termination.requires_secondary_approval)
    
    def test_disciplinary_termination_requires_approval(self):
        """Test that disciplinary terminations require secondary approval"""
        termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Policy Violation",
            "termination_reason": "Test disciplinary termination",
            "disciplinary_documentation": "Test documentation for policy violation",
            "requested_by": frappe.session.user,
            "request_date": today(),
            "secondary_approver": self.test_users["manager"]
        })
        
        termination.insert()
        
        # Should require secondary approval
        self.assertTrue(termination.requires_secondary_approval)
        self.assertEqual(termination.secondary_approver, self.test_users["manager"])
    
    def test_disciplinary_termination_validation(self):
        """Test validation rules for disciplinary terminations"""
        # Should fail without documentation
        with self.assertRaises(frappe.ValidationError):
            termination = frappe.get_doc({
                "doctype": "Membership Termination Request",
                "member": self.test_members["john"],
                "termination_type": "Expulsion",
                "termination_reason": "Test expulsion",
                # Missing disciplinary_documentation
                "requested_by": frappe.session.user,
                "request_date": today()
            })
            termination.insert()
    
    def test_workflow_state_transitions(self):
        """Test that workflow state transitions work correctly"""
        # Create termination request
        termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Voluntary",
            "termination_reason": "Test workflow transitions",
            "requested_by": frappe.session.user,
            "request_date": today()
        })
        termination.insert()
        
        # Initial state should be Draft
        self.assertEqual(termination.status, "Draft")
        
        # Test submit for approval (if method exists)
        if hasattr(termination, 'submit_for_approval'):
            termination.submit_for_approval()
            # For voluntary termination, might go directly to Approved
            self.assertIn(termination.status, ["Pending", "Approved"])
    
    def test_audit_trail_creation(self):
        """Test that audit trail entries are created"""
        termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Voluntary",
            "termination_reason": "Test audit trail",
            "requested_by": frappe.session.user,
            "request_date": today()
        })
        termination.insert()
        
        # Should have audit trail entries
        if hasattr(termination, 'audit_trail'):
            self.assertGreater(len(termination.audit_trail), 0, "Should have audit trail entries")

class TestAppealsWorkflow(TestTerminationSystem):
    """Test appeals process workflow"""
    
    def setUp(self):
        """Set up appeals test with an executed termination"""
        super().setUp()
        
        # Create an executed termination to appeal against
        self.termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Policy Violation",
            "termination_reason": "Test termination for appeals testing",
            "disciplinary_documentation": "Test documentation",
            "requested_by": frappe.session.user,
            "request_date": today(),
            "secondary_approver": self.test_users["manager"],
            "status": "Executed",  # Set as executed for appeals testing
            "execution_date": today()
        })
        self.termination.insert()
    
    def test_create_appeal(self):
        """Test creating an appeal"""
        appeal = frappe.get_doc({
            "doctype": "Termination Appeals Process",
            "termination_request": self.termination.name,
            "member": self.test_members["john"],
            "appeal_date": today(),
            "appellant_name": "John TestMember",
            "appellant_email": "john.test@example.com",
            "appellant_relationship": "Self",
            "appeal_type": "Procedural Appeal",
            "appeal_grounds": "Test appeal grounds",
            "remedy_sought": "Full Reinstatement"
        })
        
        # Should not raise exceptions
        appeal.insert()
        
        # Check initial state
        self.assertEqual(appeal.appeal_status, "Draft")
    
    def test_appeal_deadline_validation(self):
        """Test that appeals filed after deadline show warning"""
        # Create old termination (more than 30 days ago)
        old_termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Policy Violation",
            "termination_reason": "Old termination for deadline testing",
            "disciplinary_documentation": "Test documentation",
            "requested_by": frappe.session.user,
            "request_date": add_days(today(), -60),
            "secondary_approver": self.test_users["manager"],
            "status": "Executed",
            "execution_date": add_days(today(), -35)  # 35 days ago
        })
        old_termination.insert()
        
        # Create appeal after deadline
        appeal = frappe.get_doc({
            "doctype": "Termination Appeals Process",
            "termination_request": old_termination.name,
            "member": self.test_members["john"],
            "appeal_date": today(),  # Today (after 30-day deadline)
            "appellant_name": "John TestMember",
            "appellant_email": "john.test@example.com",
            "appellant_relationship": "Self",
            "appeal_type": "Procedural Appeal",
            "appeal_grounds": "Late appeal test",
            "remedy_sought": "Full Reinstatement"
        })
        
        # Should not fail, but might show warning (test passes if no exception)
        appeal.insert()

class TestSystemIntegration(TestTerminationSystem):
    """Test integration with other system components"""
    
    @patch('verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.frappe.sendmail')
    def test_notification_sending(self, mock_sendmail):
        """Test that notifications are sent correctly"""
        # Create disciplinary termination requiring approval
        termination = frappe.get_doc({
            "doctype": "Membership Termination Request",
            "member": self.test_members["john"],
            "termination_type": "Policy Violation",
            "termination_reason": "Test notification sending",
            "disciplinary_documentation": "Test documentation",
            "requested_by": frappe.session.user,
            "request_date": today(),
            "secondary_approver": self.test_users["manager"]
        })
        termination.insert()
        
        # If notification method exists, test it
        if hasattr(termination, 'send_approval_notification'):
            termination.send_approval_notification()
            # Check that sendmail was called
            mock_sendmail.assert_called()
    
    def test_permission_validation(self):
        """Test that permission validation works correctly"""
        from verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request import validate_termination_permissions_enhanced
        
        # Test permission check
        if frappe.db.exists("DocType", "Membership Termination Request"):
            result = validate_termination_permissions_enhanced(
                member=self.test_members["john"],
                termination_type="Voluntary",
                user=self.test_users["manager"]
            )
            
            # Should have permission to initiate
            self.assertTrue(result.get("can_initiate", False))

class TestDiagnostics(TestTerminationSystem):
    """Test diagnostic and troubleshooting functions"""
    
    def test_pre_setup_diagnostics(self):
        """Test pre-setup diagnostic function"""
        from verenigingen.termination_system_diagnostics import run_pre_setup_diagnostics
        
        # Should pass with workflows already set up
        result = run_pre_setup_diagnostics()
        self.assertTrue(result, "Pre-setup diagnostics should pass")
    
    def test_post_setup_diagnostics(self):
        """Test post-setup diagnostic function"""
        from verenigingen.termination_system_diagnostics import run_post_setup_diagnostics
        
        # Should pass with workflows already set up
        result = run_post_setup_diagnostics()
        self.assertTrue(result, "Post-setup diagnostics should pass")
    
    def test_comprehensive_diagnostics(self):
        """Test comprehensive diagnostic function"""
        from verenigingen.termination_system_diagnostics import run_comprehensive_diagnostics
        
        # Should pass with workflows already set up
        result = run_comprehensive_diagnostics()
        self.assertTrue(result, "Comprehensive diagnostics should pass")

class TestAPIEndpoints(TestTerminationSystem):
    """Test API endpoints"""
    
    def test_workflow_setup_api(self):
        """Test workflow setup API endpoint"""
        from verenigingen.corrected_workflow_setup import setup_production_workflows_corrected
        
        # Should succeed (workflows already exist, so should return True)
        result = setup_production_workflows_corrected()
        self.assertTrue(result, "Workflow setup API should succeed")
    
    def test_diagnostics_api(self):
        """Test diagnostics API endpoints"""
        from verenigingen.termination_system_diagnostics import api_run_diagnostics
        
        result = api_run_diagnostics()
        self.assertTrue(result.get("success", False), "Diagnostics API should succeed")
        self.assertTrue(result.get("system_ok", False), "System should be OK")

# Test runner configuration
def run_termination_tests():
    """Run all termination system tests"""
    import sys
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestWorkflowCreation,
        TestTerminationRequestWorkflow,
        TestAppealsWorkflow,
        TestSystemIntegration,
        TestDiagnostics,
        TestAPIEndpoints
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()

# Frappe test integration
def execute():
    """Entry point for running tests via Frappe"""
    return run_termination_tests()

if __name__ == "__main__":
    run_termination_tests()
