# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import today, add_days

@unittest.skip_test_for_test_record_creation
class TestTeam(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_volunteers()
        
    def tearDown(self):
        # Clean up test data
        try:
            frappe.delete_doc("Team", self.test_team.name)
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
        """Create test members and volunteers for team"""
        self.test_members = []
        self.test_volunteers = []
        
        # Create members first
        for i in range(3):
            email = f"team_test_{i}@example.com"
            
            if frappe.db.exists("Member", {"email": email}):
                frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": email}, "name"))
            
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"Team",
                "last_name": f"Test {i}",
                "email": email
            })
            member.insert(ignore_permissions=True)
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
            volunteer.insert(ignore_permissions=True)
            self.test_volunteers.append(volunteer)
    
    def create_test_team(self):
        """Create a test team"""
        self.test_team = frappe.get_doc({
            "doctype": "Team",
            "team_name": "Test Team",
            "description": "Test team for unit tests",
            "team_type": "Committee",
            "start_date": today(),
            "status": "Active"
        })
        
        # Add team leader
        self.test_team.append("team_members", {
            "member": self.test_members[0].name,
            "member_name": self.test_members[0].full_name,
            "volunteer": self.test_volunteers[0].name,
            "volunteer_name": self.test_volunteers[0].volunteer_name,
            "role_type": "Team Leader",
            "role": "Committee Chair",
            "from_date": today(),
            "is_active": 1,
            "status": "Active"
        })
        
        # Add team members
        for i in range(1, len(self.test_members)):
            self.test_team.append("team_members", {
                "member": self.test_members[i].name,
                "member_name": self.test_members[i].full_name,
                "volunteer": self.test_volunteers[i].name,
                "volunteer_name": self.test_volunteers[i].volunteer_name,
                "role_type": "Team Member",
                "role": "Committee Member",
                "from_date": today(),
                "is_active": 1,
                "status": "Active"
            })
            
        self.test_team.insert(ignore_permissions=True)
        return self.test_team
    
    def test_team_creation(self):
        """Test creating a team"""
        team = self.create_test_team()
        
        # Verify team was created
        self.assertEqual(team.team_name, "Test Team")
        self.assertEqual(team.team_type, "Committee")
        self.assertEqual(team.status, "Active")
        
        # Verify team members
        self.assertEqual(len(team.team_members), len(self.test_members))
        
        # Check leader role
        leader = next((m for m in team.team_members if m.role_type == "Team Leader"), None)
        self.assertIsNotNone(leader, "Team should have a leader")
        self.assertEqual(leader.role, "Committee Chair")
        
        # Check member roles
        members = [m for m in team.team_members if m.role_type == "Team Member"]
        self.assertEqual(len(members), len(self.test_members) - 1, "All non-leaders should be members")
    
    def test_volunteer_integration(self):
        """Test volunteer assignments get created for team members"""
        team = self.create_test_team()
        
        # Update team to trigger volunteer assignment processing
        team.description = "Updated description to trigger save"
        team.save()
        
        # Verify assignments were reflected in volunteer aggregated assignments
        for volunteer in self.test_volunteers:
            # Reload volunteer to get latest assignments
            volunteer.reload()
            
            # Get aggregated assignments
            assignments = volunteer.get_aggregated_assignments()
            
            # Check if there's a team assignment
            has_team_assignment = False
            for assignment in assignments:
                if (assignment["source_type"] == "Team" and 
                    assignment["source_doctype"] == "Team" and
                    assignment["source_name"] == team.name):
                    has_team_assignment = True
                    break
                    
            self.assertTrue(has_team_assignment, f"Volunteer {volunteer.volunteer_name} should have team assignment")
    
    def test_team_member_status_change(self):
        """Test changing team member status updates volunteer assignment"""
        team = self.create_test_team()
        
        # Change status of one team member to inactive
        for member in team.team_members:
            if member.role_type == "Team Member":
                member.status = "Inactive"
                member.is_active = 0
                member.to_date = today()
                break
                
        team.save()
        
        # Wait for a moment to allow async processes to complete if any
        import time
        time.sleep(1)
        
        # Reload team to get fresh data
        team.reload()
        
        # Find the volunteer corresponding to the deactivated member
        deactivated_volunteer = None
        for i, tm in enumerate(team.team_members):
            if tm.status == "Inactive":
                deactivated_volunteer = self.test_volunteers[i]
                break
        
        if deactivated_volunteer:
            # Reload volunteer to get latest assignments
            deactivated_volunteer.reload()
            
            # Get aggregated assignments
            assignments = deactivated_volunteer.get_aggregated_assignments()
            
            # There should be no active team assignment
            active_team_assignment = False
            for assignment in assignments:
                if (assignment["source_type"] == "Team" and 
                    assignment["source_doctype"] == "Team" and
                    assignment["source_name"] == team.name and
                    assignment["is_active"]):
                    active_team_assignment = True
                    break
                    
            self.assertFalse(active_team_assignment, 
                            f"Deactivated member should not have active team assignment")
            
            # Check volunteer's assignment history for completed team assignment
            has_history_entry = False
            for entry in deactivated_volunteer.assignment_history:
                if (entry.reference_doctype == "Team" and 
                    entry.reference_name == team.name):
                    has_history_entry = True
                    break
                    
            self.assertTrue(has_history_entry, 
                           "Deactivated team assignment should be in volunteer's assignment history")
    
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
        
    def test_member_volunteer_linkage(self):
        """Test that adding a member automatically links the volunteer"""
        team = frappe.get_doc({
            "doctype": "Team",
            "team_name": "Test Linkage Team",
            "description": "Test team for member-volunteer linkage",
            "team_type": "Working Group",
            "start_date": today(),
            "status": "Active"
        })
        
        # Add only member without volunteer
        team.append("team_members", {
            "member": self.test_members[0].name,
            "member_name": self.test_members[0].full_name,
            "role_type": "Team Leader",
            "role": "Working Group Lead",
            "from_date": today(),
            "is_active": 1,
            "status": "Active"
        })
        
        team.insert(ignore_permissions=True)
        
        # Reload to verify volunteer was automatically linked
        team.reload()
        
        # Check that volunteer is now linked
        self.assertEqual(team.team_members[0].volunteer, self.test_volunteers[0].name)
        self.assertEqual(team.team_members[0].volunteer_name, self.test_volunteers[0].volunteer_name)
        
        # Clean up
        frappe.delete_doc("Team", team.name)
