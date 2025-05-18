# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import getdate, today, add_days

@unittest.skip_test_for_test_record_creation
class TestVolunteerAggregatedAssignments(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_data()
        
    def tearDown(self):
        # Clean up test data
        try:
            frappe.delete_doc("Team", self.test_team.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Chapter", self.test_chapter.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Volunteer Activity", self.test_activity.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Volunteer", self.test_volunteer.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Member", self.test_member.name)
        except Exception:
            pass
    
    def create_test_data(self):
        """Create test data for aggregated assignments testing"""
        # 1. Create a member
        if frappe.db.exists("Member", {"email": "agg_test@example.com"}):
            frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": "agg_test@example.com"}, "name"))
        
        self.test_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Aggregated",
            "last_name": "Test",
            "email": "agg_test@example.com"
        })
        self.test_member.insert(ignore_permissions=True)
        
        # 2. Create a volunteer
        self.test_volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": "Aggregated Test Volunteer",
            "email": "agg.test@example.org",
            "member": self.test_member.name,
            "status": "Active",
            "start_date": today()
        })
        self.test_volunteer.insert(ignore_permissions=True)
        
        # 3. Create a chapter
        self.test_chapter = frappe.get_doc({
            "doctype": "Chapter",
            "chapter_head": self.test_member.name,
            "region": "Test Region",
            "introduction": "Test chapter for aggregated assignments"
        })
        
        # Add board membership
        self.test_chapter.append("board_members", {
            "member": self.test_member.name,
            "member_name": self.test_member.full_name,
            "email": self.test_member.email,
            "chapter_role": "Secretary",
            "from_date": today(),
            "is_active": 1
        })
        
        self.test_chapter.insert(ignore_permissions=True)
        
        # 4. Create a team
        self.test_team = frappe.get_doc({
            "doctype": "Team",
            "team_name": "Aggregated Test Team",
            "description": "Test team for aggregated assignments",
            "team_type": "Working Group",
            "start_date": today(),
            "status": "Active"
        })
        
        # Add team membership
        self.test_team.append("team_members", {
            "member": self.test_member.name,
            "member_name": self.test_member.full_name,
            "volunteer": self.test_volunteer.name,
            "volunteer_name": self.test_volunteer.volunteer_name,
            "role_type": "Team Member",
            "role": "Working Group Member",
            "from_date": today(),
            "is_active": 1,
            "status": "Active"
        })
        
        self.test_team.insert(ignore_permissions=True)
        
        # 5. Create a volunteer activity
        self.test_activity = frappe.get_doc({
            "doctype": "Volunteer Activity",
            "volunteer": self.test_volunteer.name,
            "activity_type": "Project",
            "role": "Project Contributor",
            "description": "Test volunteer activity for aggregated assignments",
            "status": "Active",
            "start_date": today()
        })
        self.test_activity.insert(ignore_permissions=True)
    
    def test_aggregated_assignments(self):
        """Test the aggregated assignments feature"""
        # Give some time for any background processes to complete
        import time
        time.sleep(1)
        
        # Reload volunteer to ensure we have latest data
        self.test_volunteer.reload()
        
        # Get aggregated assignments
        assignments = self.test_volunteer.get_aggregated_assignments()
        
        # We should have at least 3 assignments (board, team, activity)
        self.assertGreaterEqual(len(assignments), 3, "Should have at least 3 assignments")
        
        # Check for board assignment
        has_board_assignment = False
        for assignment in assignments:
            if (assignment["source_type"] == "Board Position" and 
                assignment["source_doctype"] == "Chapter" and
                assignment["source_name"] == self.test_chapter.name):
                has_board_assignment = True
                self.assertEqual(assignment["role"], "Secretary", "Board role should be Secretary")
                break
                
        self.assertTrue(has_board_assignment, "Should have board position assignment")
        
        # Check for team assignment
        has_team_assignment = False
        for assignment in assignments:
            if (assignment["source_type"] == "Team" and 
                assignment["source_doctype"] == "Team" and
                assignment["source_name"] == self.test_team.name):
                has_team_assignment = True
                self.assertEqual(assignment["role"], "Working Group Member", "Team role should be Working Group Member")
                break
                
        self.assertTrue(has_team_assignment, "Should have team assignment")
        
        # Check for activity assignment
        has_activity_assignment = False
        for assignment in assignments:
            if (assignment["source_type"] == "Activity" and 
                assignment["source_doctype"] == "Volunteer Activity" and
                assignment["source_name"] == self.test_activity.name):
                has_activity_assignment = True
                self.assertEqual(assignment["role"], "Project Contributor", "Activity role should be Project Contributor")
                break
                
        self.assertTrue(has_activity_assignment, "Should have activity assignment")
    
    def test_assignment_completion(self):
        """Test completing assignments and seeing them in assignment history"""
        # 1. End the activity
        self.test_activity.status = "Completed"
        self.test_activity.end_date = today()
        self.test_activity.save()
        
        # 2. End team membership
        for member in self.test_team.team_members:
            if member.volunteer == self.test_volunteer.name:
                member.status = "Completed"
                member.is_active = 0
                member.to_date = today()
                break
                
        self.test_team.save()
        
        # 3. End board membership
        for member in self.test_chapter.board_members:
            if member.member == self.test_member.name:
                member.is_active = 0
                member.to_date = today()
                break
                
        self.test_chapter.save()
        
        # Allow some time for processing
        import time
        time.sleep(1)
        
        # Reload volunteer
        self.test_volunteer.reload()
        
        # Check assignment history
        self.assertGreaterEqual(len(self.test_volunteer.assignment_history), 1, 
                               "Should have entries in assignment history")
        
        # Get aggregated assignments (should have none active)
        assignments = self.test_volunteer.get_aggregated_assignments()
        self.assertEqual(len(assignments), 0, "Should have no active assignments")
    
    def test_volunteer_history(self):
        """Test volunteer history timeline"""
        # Get volunteer history
        history = self.test_volunteer.get_volunteer_history()
        
        # We should have at least 3 history entries
        self.assertGreaterEqual(len(history), 3, "Should have at least 3 history entries")
        
        # Check for board entry
        has_board_entry = False
        for entry in history:
            if (entry["assignment_type"] == "Board Position" and 
                entry["reference"] == self.test_chapter.name):
                has_board_entry = True
                break
                
        self.assertTrue(has_board_entry, "Should have board position in history")
        
        # Check for team entry
        has_team_entry = False
        for entry in history:
            if (entry["assignment_type"] == "Team" and 
                entry["reference"] == self.test_team.name):
                has_team_entry = True
                break
                
        self.assertTrue(has_team_entry, "Should have team entry in history")
