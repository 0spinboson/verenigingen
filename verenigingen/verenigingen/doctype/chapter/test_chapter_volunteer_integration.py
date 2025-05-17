# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import today, add_days
from verenigingen.verenigingen.doctype.volunteer.volunteer import sync_chapter_board_members

class TestChapterVolunteerIntegration(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_chapter()
        self.create_test_members()
        
    def tearDown(self):
        # Clean up test data
        try:
            frappe.delete_doc("Chapter", self.test_chapter.name)
        except Exception:
            pass
            
        for member in self.test_members:
            try:
                frappe.delete_doc("Member", member.name)
            except Exception:
                pass
                
        for volunteer in self.test_volunteers:
            try:
                frappe.delete_doc("Volunteer", volunteer)
            except Exception:
                pass
    
    def create_test_chapter(self):
        """Create a test chapter"""
        # First create a member for chapter head
        if frappe.db.exists("Member", {"email": "chapter_head@example.com"}):
            frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": "chapter_head@example.com"}, "name"))
        
        head_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Chapter",
            "last_name": "Head",
            "email": "chapter_head@example.com"
        })
        head_member.insert()
        
        # Create a chapter
        self.test_chapter = frappe.get_doc({
            "doctype": "Chapter",
            "chapter_head": head_member.name,
            "region": "Test Region",
            "introduction": "Test chapter for integration tests"
        })
        self.test_chapter.insert()
        
        return self.test_chapter
    
    def create_test_members(self):
        """Create test members for board positions"""
        self.test_members = []
        self.test_volunteers = []
        
        # Create a few test members
        for i in range(3):
            email = f"board_member_{i}@example.com"
            
            if frappe.db.exists("Member", {"email": email}):
                frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": email}, "name"))
            
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"Board",
                "last_name": f"Member {i}",
                "email": email
            })
            member.insert()
            self.test_members.append(member)
            
        # Create a volunteer for one member
        if self.test_members:
            volunteer = frappe.get_doc({
                "doctype": "Volunteer",
                "volunteer_name": self.test_members[0].full_name,
                "email": f"{self.test_members[0].full_name.lower().replace(' ', '.')}@example.org",
                "member": self.test_members[0].name,
                "status": "Active",
                "start_date": today()
            })
            volunteer.insert()
            self.test_volunteers.append(volunteer.name)
            
    def add_board_members_to_chapter(self):
        """Add test members as board members to test chapter"""
        # Define some board roles
        roles = ["Chair", "Secretary", "Treasurer"]
        
        # Add each member with a role
        for i, member in enumerate(self.test_members):
            role = roles[i % len(roles)]
            
            self.test_chapter.append("board_members", {
                "member": member.name,
                "member_name": member.full_name,
                "email": member.email,
                "chapter_role": role,
                "from_date": today(),
                "is_active": 1
            })
            
        self.test_chapter.save()
    
    def test_create_volunteer_from_board_member(self):
        """Test creating a volunteer record from a board member"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Use the sync function to create volunteers for board members
        result = sync_chapter_board_members()
        
        # Verify volunteers were created
        for member in self.test_members:
            # Skip the first member who already has a volunteer record
            if member.name == self.test_members[0].name:
                continue
                
            volunteer_exists = frappe.db.exists("Volunteer", {"member": member.name})
            self.assertTrue(volunteer_exists, f"Volunteer should be created for member {member.name}")
            
            if volunteer_exists:
                self.test_volunteers.append(volunteer_exists)
    
    def test_board_assignments_sync(self):
        """Test syncing board positions to volunteer assignments"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Run the sync function
        result = sync_chapter_board_members()
        
        # Check assignments for the pre-existing volunteer
        volunteer = frappe.get_doc("Volunteer", self.test_volunteers[0])
        
        # Should have a board position assignment
        has_board_assignment = False
        for assignment in volunteer.active_assignments:
            if (assignment.assignment_type == "Board Position" and 
                assignment.reference_doctype == "Chapter" and
                assignment.reference_name == self.test_chapter.name):
                has_board_assignment = True
                break
                
        self.assertTrue(has_board_assignment, "Volunteer should have a board position assignment")
    
    def test_board_role_change(self):
        """Test role changes for board members sync to volunteer assignments"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Run initial sync
        sync_chapter_board_members()
        
        # Change a board member's role
        for board_member in self.test_chapter.board_members:
            if board_member.member == self.test_members[0].name:
                board_member.chapter_role = "New Role"
                break
                
        self.test_chapter.save()
        
        # Run sync again
        sync_chapter_board_members()
        
        # Check if volunteer assignment was updated
        volunteer = frappe.get_doc("Volunteer", self.test_volunteers[0])
        
        has_new_role = False
        for assignment in volunteer.active_assignments:
            if (assignment.assignment_type == "Board Position" and 
                assignment.reference_name == self.test_chapter.name and
                assignment.role == "New Role"):
                has_new_role = True
                break
                
        self.assertTrue(has_new_role, "Volunteer assignment should be updated with new role")
