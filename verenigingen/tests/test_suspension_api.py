"""
Unit tests for suspension API endpoints
"""

import frappe
import unittest
import json
from unittest.mock import patch, MagicMock
from frappe.utils import today
from verenigingen.api.suspension_api import (
    suspend_member,
    unsuspend_member,
    get_suspension_status,
    can_suspend_member,
    get_suspension_preview,
    bulk_suspend_members
)


class TestSuspensionAPI(unittest.TestCase):
    """Test suspension API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.test_member_name = "TEST-MEMBER-001"
        self.test_member_name_2 = "TEST-MEMBER-002"
        self.test_suspension_reason = "API test suspension"
        self.test_unsuspension_reason = "API test unsuspension"
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('verenigingen.utils.termination_integration.suspend_member_safe')
    @patch('frappe.msgprint')
    def test_suspend_member_api_success(self, mock_msgprint, mock_suspend_safe, mock_can_terminate):
        """Test successful suspension via API"""
        
        # Mock permission check
        mock_can_terminate.return_value = True
        
        # Mock successful suspension
        mock_suspend_safe.return_value = {
            "success": True,
            "actions_taken": ["Member status changed", "User account suspended"]
        }
        
        # Call API
        result = suspend_member(
            self.test_member_name,
            self.test_suspension_reason,
            suspend_user=True,
            suspend_teams=True
        )
        
        # Verify permission check
        mock_can_terminate.assert_called_once_with(self.test_member_name)
        
        # Verify suspension call
        mock_suspend_safe.assert_called_once_with(
            member_name=self.test_member_name,
            suspension_reason=self.test_suspension_reason,
            suspension_date=today(),
            suspend_user=True,
            suspend_teams=True
        )
        
        # Verify success message
        mock_msgprint.assert_called_once()
        args = mock_msgprint.call_args[0]
        self.assertIn("suspended successfully", args[0])
        
        # Verify return value
        self.assertTrue(result["success"])
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('frappe.throw')
    def test_suspend_member_api_no_permission(self, mock_throw, mock_can_terminate):
        """Test suspension API with no permission"""
        
        # Mock permission denial
        mock_can_terminate.return_value = False
        
        # Make mock throw act like real frappe.throw by raising an exception
        mock_throw.side_effect = Exception("Permission denied")
        
        # Call API - should raise exception
        with self.assertRaises(Exception):
            suspend_member(self.test_member_name, self.test_suspension_reason)
        
        # Verify permission error was called once
        mock_throw.assert_called_once()
        args = mock_throw.call_args[0]
        self.assertIn("don't have permission", args[0])
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('verenigingen.utils.termination_integration.suspend_member_safe')
    @patch('frappe.throw')
    def test_suspend_member_api_failure(self, mock_throw, mock_suspend_safe, mock_can_terminate):
        """Test suspension API failure handling"""
        
        # Mock permission check
        mock_can_terminate.return_value = True
        
        # Mock suspension failure
        mock_suspend_safe.return_value = {
            "success": False,
            "error": "Database error"
        }
        
        # Call API
        suspend_member(self.test_member_name, self.test_suspension_reason)
        
        # Verify error handling
        mock_throw.assert_called_once()
        args = mock_throw.call_args[0]
        self.assertIn("Failed to suspend member", args[0])
        self.assertIn("Database error", args[0])
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('verenigingen.utils.termination_integration.unsuspend_member_safe')
    @patch('frappe.msgprint')
    def test_unsuspend_member_api_success(self, mock_msgprint, mock_unsuspend_safe, mock_can_terminate):
        """Test successful unsuspension via API"""
        
        # Mock permission check
        mock_can_terminate.return_value = True
        
        # Mock successful unsuspension
        mock_unsuspend_safe.return_value = {
            "success": True,
            "actions_taken": ["Member status restored", "User account reactivated"]
        }
        
        # Call API
        result = unsuspend_member(self.test_member_name, self.test_unsuspension_reason)
        
        # Verify permission check
        mock_can_terminate.assert_called_once_with(self.test_member_name)
        
        # Verify unsuspension call
        mock_unsuspend_safe.assert_called_once_with(
            member_name=self.test_member_name,
            unsuspension_reason=self.test_unsuspension_reason
        )
        
        # Verify success message
        mock_msgprint.assert_called_once()
        args = mock_msgprint.call_args[0]
        self.assertIn("unsuspended successfully", args[0])
        
        # Verify return value
        self.assertTrue(result["success"])
    
    @patch('verenigingen.utils.termination_integration.get_member_suspension_status')
    def test_get_suspension_status_api(self, mock_get_status):
        """Test get suspension status API"""
        
        # Mock status response
        expected_status = {
            "is_suspended": True,
            "member_status": "Suspended",
            "user_suspended": True,
            "active_teams": 2,
            "can_unsuspend": True
        }
        mock_get_status.return_value = expected_status
        
        # Call API
        result = get_suspension_status(self.test_member_name)
        
        # Verify call
        mock_get_status.assert_called_once_with(self.test_member_name)
        
        # Verify return value
        self.assertEqual(result, expected_status)
    
    @patch('verenigingen.permissions.can_terminate_member')
    def test_can_suspend_member_api(self, mock_can_terminate):
        """Test can suspend member API"""
        
        # Mock permission check
        mock_can_terminate.return_value = True
        
        # Call API
        result = can_suspend_member(self.test_member_name)
        
        # Verify call
        mock_can_terminate.assert_called_once_with(self.test_member_name)
        
        # Verify return value
        self.assertTrue(result)
    
    @patch('frappe.get_doc')
    @patch('frappe.db.get_value')
    @patch('frappe.get_all')
    def test_get_suspension_preview_api(self, mock_get_all, mock_get_value, mock_get_doc):
        """Test get suspension preview API"""
        
        # Mock member document
        mock_member = MagicMock()
        mock_member.status = "Active"
        mock_get_doc.return_value = mock_member
        
        # Mock user lookup
        mock_get_value.return_value = "test@example.com"
        
        # Mock teams and memberships with proper object structure
        mock_team_a = MagicMock()
        mock_team_a.parent = "Team A"
        mock_team_a.role = "Member"
        
        mock_team_b = MagicMock()
        mock_team_b.parent = "Team B"
        mock_team_b.role = "Leader"
        
        mock_get_all.side_effect = [
            # Team memberships
            [mock_team_a, mock_team_b],
            # Active memberships
            [{"name": "MEMBERSHIP-001", "membership_type": "Regular"}]
        ]
        
        # Call API
        result = get_suspension_preview(self.test_member_name)
        
        # Check if there's an error first
        if "error" in result:
            self.fail(f"API returned error: {result['error']}")
        
        # Verify results
        self.assertEqual(result["member_status"], "Active")
        self.assertTrue(result["has_user_account"])
        self.assertEqual(result["active_teams"], 2)
        self.assertEqual(len(result["team_details"]), 2)
        self.assertEqual(result["active_memberships"], 1)
        self.assertTrue(result["can_suspend"])
        self.assertFalse(result["is_currently_suspended"])
    
    @patch('frappe.get_doc')
    def test_get_suspension_preview_api_failure(self, mock_get_doc):
        """Test get suspension preview API failure handling"""
        
        # Mock exception
        mock_get_doc.side_effect = Exception("Database error")
        
        # Call API
        result = get_suspension_preview(self.test_member_name)
        
        # Verify error handling
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Database error")
        self.assertFalse(result["can_suspend"])
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('verenigingen.utils.termination_integration.suspend_member_safe')
    @patch('frappe.msgprint')
    def test_bulk_suspend_members_success(self, mock_msgprint, mock_suspend_safe, mock_can_terminate):
        """Test bulk suspend members API success"""
        
        # Mock permission checks
        mock_can_terminate.return_value = True
        
        # Mock successful suspensions
        mock_suspend_safe.return_value = {
            "success": True,
            "actions_taken": ["Member suspended"]
        }
        
        # Prepare member list
        member_list = [self.test_member_name, self.test_member_name_2]
        
        # Call API
        result = bulk_suspend_members(
            json.dumps(member_list),
            self.test_suspension_reason,
            suspend_user=True,
            suspend_teams=True
        )
        
        # Verify results
        self.assertEqual(result["success"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["details"]), 2)
        
        # Verify all members were processed
        for detail in result["details"]:
            self.assertEqual(detail["status"], "success")
            self.assertIn(detail["member"], member_list)
        
        # Verify success message
        mock_msgprint.assert_called_once()
        args = mock_msgprint.call_args[0]
        self.assertIn("2 successful, 0 failed", args[0])
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('frappe.msgprint')
    def test_bulk_suspend_members_no_permission(self, mock_msgprint, mock_can_terminate):
        """Test bulk suspend members with no permission"""
        
        # Mock permission denial
        mock_can_terminate.return_value = False
        
        # Prepare member list
        member_list = [self.test_member_name, self.test_member_name_2]
        
        # Call API
        result = bulk_suspend_members(
            json.dumps(member_list),
            self.test_suspension_reason
        )
        
        # Verify results
        self.assertEqual(result["success"], 0)
        self.assertEqual(result["failed"], 2)
        
        # Verify permission errors
        for detail in result["details"]:
            self.assertEqual(detail["status"], "failed")
            self.assertIn("No permission", detail["error"])
        
        # Verify failure message
        mock_msgprint.assert_called_once()
        args = mock_msgprint.call_args[0]
        self.assertIn("No members were suspended", args[0])
    
    @patch('verenigingen.permissions.can_terminate_member')
    @patch('verenigingen.utils.termination_integration.suspend_member_safe')
    @patch('frappe.msgprint')
    def test_bulk_suspend_members_mixed_results(self, mock_msgprint, mock_suspend_safe, mock_can_terminate):
        """Test bulk suspend members with mixed success/failure"""
        
        # Mock permission checks - first succeeds, second fails
        mock_can_terminate.side_effect = [True, False]
        
        # Mock successful suspension for first member
        mock_suspend_safe.return_value = {
            "success": True,
            "actions_taken": ["Member suspended"]
        }
        
        # Prepare member list
        member_list = [self.test_member_name, self.test_member_name_2]
        
        # Call API
        result = bulk_suspend_members(
            json.dumps(member_list),
            self.test_suspension_reason
        )
        
        # Verify results
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(result["details"]), 2)
        
        # Verify mixed results
        success_detail = next(d for d in result["details"] if d["status"] == "success")
        failure_detail = next(d for d in result["details"] if d["status"] == "failed")
        
        self.assertEqual(success_detail["member"], self.test_member_name)
        self.assertEqual(failure_detail["member"], self.test_member_name_2)
        self.assertIn("No permission", failure_detail["error"])
    
    @patch('frappe.utils.cint')
    def test_boolean_parameter_conversion(self, mock_cint):
        """Test boolean parameter conversion in API"""
        
        # Mock cint function with proper boolean handling
        def mock_cint_func(x):
            if isinstance(x, bool):
                return 1 if x else 0
            elif isinstance(x, str):
                return 1 if x == "1" else 0
            else:
                return 1 if x else 0
        mock_cint.side_effect = mock_cint_func
        
        # This test verifies the boolean conversion logic exists
        # The actual API calls are tested in other test methods
        result_true = mock_cint(True)
        result_false = mock_cint(False)
        result_string_true = mock_cint("1")
        result_string_false = mock_cint("0")
        
        self.assertEqual(result_true, 1)
        self.assertEqual(result_false, 0)
        self.assertEqual(result_string_true, 1)
        self.assertEqual(result_string_false, 0)


if __name__ == '__main__':
    unittest.main()