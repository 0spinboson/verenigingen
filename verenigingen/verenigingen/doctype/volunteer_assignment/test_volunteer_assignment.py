# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import today, add_days

class TestVolunteerAssignment(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_volunteer()
        
    def tearDown(self):
        # Clean up test data
        try:
            frappe.delete_doc("Volunteer", self.test_volunteer.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Member", self.test_member.name)
        except Exception:
            pass
            
        if frappe.db.exists("Chapter", "Assignment Test Chapter"):
            frappe.delete_doc("Chapter", "Assignment Test Chapter")
    
    def create_test_volunteer(self):
        """Create a test volunteer record"""
        # Create a test member first
        if frappe.db.exists("Member", {"email": "assignment_test@example.com"}):
            frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": "assignment_test@example.com"}, "name"))
        
        self.test_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Assignment",
            "last_name": "Test",
            "email": "assignment_test@example.com"
        })
        self.test_member.insert()
        
        # Create volunteer record
        self.test_volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": "Assignment Test Volunteer",
            "email": "assignment.test@example.org",
            "member": self.test_member.name,
            "status": "Active",
            "start_date": today()
        })
        self.test_volunteer.insert()
        
        return self.test_volunteer
    
    def test_board_assignment(self):
        """Test creating a board position assignment"""
        # Create a test chapter
        if not frappe.db.exists("Chapter", "Assignment Test Chapter"):
            chapter = frappe.get_doc({
                "doctype": "Chapter",
                "chapter_head": self.test_member.name,
                "region": "Test Region",
                "introduction": "Test chapter for assignment tests"
            })
            chapter.insert()
        
        # Add a board assignment
        self.test_volunteer.add_board_assignment(
            chapter="Assignment Test Chapter",
            role="Test Board Role",
            start_date=today()
        )
        
        # Reload the volunteer
        self.test_volunteer.reload()
        
        # Verify assignment creation
        self.assertEqual(len(self.test_volunteer.active_assignments), 1)
        self.assertEqual(self.test_volunteer.active_assignments[0].assignment_type, "Board Position")
        self.assertEqual(self.test_volunteer.active_assignments[0].reference_doctype, "Chapter")
        self.assertEqual(self.test_volunteer.active_assignments[0].reference_name, "Assignment Test Chapter")
        self.assertEqual(self.test_volunteer.active_assignments[0].role, "Test Board Role")
        self.assertEqual(self.test_volunteer.active_assignments[0].status, "Active")
    
    def test_team_assignment(self):
        """Test creating a team assignment"""
        # Add a team assignment
        self.test_volunteer.append("active_assignments", {
            "assignment_type": "Team",
            "reference_doctype": "Volunteer Team",
            "reference_name": "Test Team",
            "role": "Team Member",
            "start_date": today(),
            "status": "Active"
        })
        self.test_volunteer.save()
        
        # Verify assignment creation
        self.assertEqual(len(self.test_volunteer.active_assignments), 1)
        self.assertEqual(self.test_volunteer.active_assignments[0].assignment_type, "Team")
        self.assertEqual(self.test_volunteer.active_assignments[0].reference_name, "Test Team")
        self.assertEqual(self.test_volunteer.active_assignments[0].role, "Team Member")
    
    def test_assignment_dates(self):
        """Test assignment date validations"""
        # Try to create assignment with end date before start date (should raise ValueError)
        with self.assertRaises(Exception):
            self.test_volunteer.append("active_assignments", {
                "assignment_type": "Project",
                "reference_doctype": "Project",
                "reference_name": "Test Project",
                "role": "Project Member",
                "start_date": today(),
                "end_date": add_days(today(), -10),  # End date before start date
                "status": "Active"
            })
            self.test_volunteer.save()
    
    def test_assignment_transition(self):
        """Test transitioning an assignment from active to completed"""
        # Create an active assignment
        self.test_volunteer.append("active_assignments", {
            "assignment_type": "Event",
            "reference_doctype": "Event",
            "reference_name": "Test Event",
            "role": "Event Coordinator",
            "start_date": add_days(today(), -30),
            "status": "Active"
        })
        self.test_volunteer.save()
        
        # End the assignment (should move to assignment_history)
        self.test_volunteer.end_assignment(
            assignment_idx=1,
            end_date=today(),
            notes="Assignment completed successfully"
        )
        
        # Verify active assignment was moved to history
        self.assertEqual(len(self.test_volunteer.active_assignments), 0)
        self.assertEqual(len(self.test_volunteer.assignment_history), 1)
        self.assertEqual(self.test_volunteer.assignment_history[0].status, "Completed")
        self.assertEqual(self.test_volunteer.assignment_history[0].role, "Event Coordinator")
        self.assertEqual(self.test_volunteer.assignment_history[0].end_date, today())
    
    def test_volunteer_history(self):
        """Test retrieving volunteer assignment history"""
        # Add one active and one completed assignment
        # Active assignment
        self.test_volunteer.append("active_assignments", {
            "assignment_type": "Board Position",
            "reference_doctype": "Chapter",
            "reference_name": "Current Chapter",
            "role": "Board Member",
            "start_date": today(),
            "status": "Active"
        })
        
        # Historical assignment
        self.test_volunteer.append("assignment_history", {
            "assignment_type": "Team",
            "reference_doctype": "Volunteer Team",
            "reference_name": "Past Team",
            "role": "Team Member",
            "start_date": add_days(today(), -100),
            "end_date": add_days(today(), -10),
            "status": "Completed"
        })
        
        self.test_volunteer.save()
        
        # Get volunteer history
        history = self.test_volunteer.get_volunteer_history()
        
        # Verify history content
        self.assertEqual(len(history), 2)
        
        # Check that active assignment is in history
        active_assignments = [h for h in history if h.get("is_active")]
        self.assertEqual(len(active_assignments), 1)
        self.assertEqual(active_assignments[0].get("assignment_type"), "Board Position")
        self.assertEqual(active_assignments[0].get("role"), "Board Member")
        
        # Check that completed assignment is in history
        completed_assignments = [h for h in history if not h.get("is_active")]
        self.assertEqual(len(completed_assignments), 1)
        self.assertEqual(completed_assignments[0].get("assignment_type"), "Team")
        self.assertEqual(completed_assignments[0].get("role"), "Team Member")
