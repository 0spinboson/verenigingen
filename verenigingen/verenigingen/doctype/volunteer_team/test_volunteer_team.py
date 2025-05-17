# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import today, add_days

class TestVolunteerTeam(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_volunteers()
        
    def tearDown(self):
        # Clean up test data
        try:
            frappe.delete_doc("Volunteer Team", self.test_team.name)
        except Exception:
            pass
            
        for volunteer in self.test_volunteers:
            try:
                frappe.delete_doc("Volunteer", volunteer.name)
            except Exception:
                pass
                
        for member in self.test_members:
            try:
                frappe.delete_doc("Member", member.name)
            except Exception:
                pass
    
    def create_test_volunteers(self):
        """Create test volunteers for team"""
        self.test_members = []
        self.test_volunteers = []
        
        # Create members first
        for i in range(3):
            email = f"team_member_{i}@example.com"
            
            if frappe.db.exists("Member", {"email": email}):
                frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": email}, "name"))
            
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"Team",
                "last_name": f"Member {i}",
                "email": email
            })
            member.insert()
            self.test_members.append(member)
            
            # Create volunteer for each member
            volunteer = frappe.get_doc({
                "doctype": "Volunteer",
                "volunteer_name": member.full_name,
                "email": f"{member.full_name.lower().replace(' ', '.')}@example.org",
                "member": member.name,
                "status": "Active",
                "start_date": today()
            })
            volunteer.insert()
            self.test_volunteers.append(volunteer)
    
    def create_test_team(self):
        """Create a test volunteer team"""
        self.test_team = frappe.get_doc({
            "doctype": "Volunteer Team",
            "team_name": "Test Team",
            "description": "Test team for unit tests",
            "team_type": "Committee",
            "start_date": today(),
            "status": "Active"
        })
        
        # Add team leader
        self.test_team.append("team_members", {
            "volunteer": self.test_volunteers[0].name,
            "volunteer_name": self.test_volunteers[0].volunteer_name,
            "role_type": "Team Leader",
            "role": "Committee Chair",
            "from_date": today(),
            "status": "Active"
        })
        
        # Add team members
        for i in range(1, len(self.test_volunteers)):
            self.test_team.append("team_members", {
                "volunteer": self.test_volunteers[i].name,
                "volunteer_name": self.test_volunteers[i].volunteer_name,
                "role_type": "Team Member",
                "role": "Committee Member",
                "from_date": today(),
                "status": "Active"
            })
            
        self.test_team.insert()
        return self.test_team
    
    def test_team_creation(self):
        """Test creating a volunteer team"""
        team = self.create_test_team()
        
        # Verify team was created
        self.assertEqual(team.team_name, "Test Team")
        self.assertEqual(team.team_type, "Committee")
        self.assertEqual(team.status, "Active")
        
        # Verify team members
        self.assertEqual(len(team.team_members), len(self.test_volunteers))
        
        # Check leader role
        leader = next((m for m in team.team_members if m.role_type == "Team Leader"), None)
        self.assertIsNotNone(leader, "Team should have a leader")
        self.assertEqual(leader.role, "Committee Chair")
        
        # Check member roles
        members = [m for m in team.team_members if m.role_type == "Team Member"]
        self.assertEqual(len(members), len(self.test_volunteers) - 1, "All non-leaders should be members")
    
    def test_volunteer_assignment_integration(self):
        """Test volunteer assignments get created for team members"""
        team = self.create_test_team()
        
        # Verify assignments were created for all team members
        for volunteer in self.test_volunteers:
            # Reload volunteer to get latest assignments
            volunteer.reload()
            
            # Check if there's a team assignment
            has_team_assignment = False
            for assignment in volunteer.active_assignments:
                if (assignment.assignment_type == "Team" and 
                    assignment.reference_doctype == "Volunteer Team" and
                    assignment.reference_name == team.name):
                    has_team_assignment = True
                    break
                    
            self.assertTrue(has_team_assignment, f"Volunteer {volunteer.name} should have team assignment")
    
    def test_team_member_status_change(self):
        """Test changing team member status updates volunteer assignment"""
        team = self.create_test_team()
        
        # Change status of one team member to inactive
        member_to_change = team.team_members[1]
        member_to_change.status = "Inactive"
        member_to_change.to_date = today()
        team.save()
        
        # Verify volunteer assignment was updated
        volunteer = frappe.get_doc("Volunteer", member_to_change.volunteer)
        
        # Check that team assignment is now in history
        has_active_assignment = False
        for assignment in volunteer.active_assignments:
            if (assignment.assignment_type == "Team" and 
                assignment.reference_name == team.name):
                has_active_assignment = True
                break
                
        # Should not have active assignment after status change
        self.assertFalse(has_active_assignment, "Team assignment should not be active")
    
    def test_team_responsibilities(self):
        """Test adding responsibilities to a team"""
        team = self.create_test_team()
        
        # Add some responsibilities
        team.append("key_responsibilities", {
            "responsibility": "Organize monthly meetings",
            "description": "Schedule and prepare agenda for monthly committee meetings",
            "status": "In Progress"
        })
        
        team.append("key_responsibilities", {
            "responsibility": "Annual report",
            "description": "Prepare annual report of committee activities",
            "status": "Pending"
        })
        
        team.save()
        
        # Verify responsibilities
        self.assertEqual(len(team.key_responsibilities), 2)
        
        # Verify responsibility details
        responsibilities = [r.responsibility for r in team.key_responsibilities]
        self.assertIn("Organize monthly meetings", responsibilities)
        self.assertIn("Annual report", responsibilities)
