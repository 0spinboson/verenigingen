# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import today, add_days
from verenigingen.verenigingen.doctype.volunteer.volunteer import sync_chapter_board_members

class TestChapterVolunteerIntegration(unittest.TestCase):
    def setUp(self):
        # Create a timestamp suffix to ensure unique test data names
        self.test_timestamp = frappe.utils.now().replace(":", "").replace("-", "").replace(" ", "")
        
        # Create test data in the right order
        self.test_members = []
        self.test_volunteers = []
        self.create_test_chapter_roles()
        self.create_test_chapter()
        self.create_test_members()
        
    def tearDown(self):
        # Clean up test data in reverse order to avoid link errors
        # First delete the board members (we don't need to delete them separately, just clear the relationship)
        if hasattr(self, 'test_chapter') and self.test_chapter:
            try:
                # Get the doc again to ensure we have the latest version
                self.test_chapter = frappe.get_doc("Chapter", self.test_chapter.name)
                # Clear board members
                self.test_chapter.board_members = []
                self.test_chapter.save(ignore_permissions=True)
            except Exception as e:
                print(f"Error clearing board members: {e}")
        
        # Delete the volunteer assignments and volunteer records
        for volunteer_name in self.test_volunteers:
            try:
                volunteer = frappe.get_doc("Volunteer", volunteer_name)
                # Clear assignments to break links
                if hasattr(volunteer, 'assignments'):
                    volunteer.assignments = []
                    volunteer.save(ignore_permissions=True)
                # Now delete the volunteer
                frappe.delete_doc("Volunteer", volunteer_name, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting volunteer {volunteer_name}: {e}")
        
        # Delete member records
        for member in self.test_members:
            try:
                frappe.delete_doc("Member", member.name, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting member {member.name}: {e}")
        
        # Delete the chapter
        if hasattr(self, 'test_chapter') and self.test_chapter:
            try:
                frappe.delete_doc("Chapter", self.test_chapter.name, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting chapter {self.test_chapter.name}: {e}")
        
        # Delete chapter head
        if hasattr(self, 'chapter_head_member') and self.chapter_head_member:
            try:
                frappe.delete_doc("Member", self.chapter_head_member.name, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting chapter head {self.chapter_head_member.name}: {e}")
            
        # Clean up chapter roles
        for role in ["Chair", "Secretary", "Treasurer", "New Role"]:
            try:
                if frappe.db.exists("Chapter Role", role):
                    frappe.delete_doc("Chapter Role", role, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting role {role}: {e}")
    
    def create_test_chapter(self):
        """Create a test chapter with unique name"""
        # Create a member for chapter head with unique email
        head_email = f"chapter_head_{self.test_timestamp}@example.com"
        
        # Check if a member with this email already exists
        existing_head = frappe.db.get_value("Member", {"email": head_email}, "name")
        if existing_head:
            self.chapter_head_member = frappe.get_doc("Member", existing_head)
        else:
            # Create new chapter head
            self.chapter_head_member = frappe.get_doc({
                "doctype": "Member",
                "first_name": "Chapter",
                "last_name": f"Head {self.test_timestamp}",
                "email": head_email
            })
            self.chapter_head_member.insert(ignore_permissions=True)
        
        # Generate a unique name for the test chapter
        test_chapter_name = f"Test Chapter {self.test_timestamp}"
        
        # Create a chapter
        self.test_chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": test_chapter_name,
            "chapter_head": self.chapter_head_member.name,
            "region": "Test Region",
            "introduction": "Test chapter for integration tests"
        })
        self.test_chapter.insert(ignore_permissions=True)
        
        return self.test_chapter
    
    def create_test_members(self):
        """Create test members for board positions with unique emails"""
        self.test_members = []
        
        # Create a few test members
        for i in range(3):
            email = f"board_member_{i}_{self.test_timestamp}@example.com"
            
            # Create the member with unique email
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"Board",
                "last_name": f"Member {i} {self.test_timestamp}",
                "email": email
            })
            member.insert(ignore_permissions=True)
            self.test_members.append(member)
            
        # Create a volunteer for one member
        if self.test_members:
            volunteer = frappe.get_doc({
                "doctype": "Volunteer",
                "volunteer_name": self.test_members[0].full_name,
                "email": f"{self.test_members[0].full_name.lower().replace(' ', '.')}@example.org",
                "member": self.test_members[0].name,
                "status": "Active",
                "start_date": frappe.utils.today()
            })
            volunteer.insert(ignore_permissions=True)
            self.test_volunteers.append(volunteer.name)
            
    def add_board_members_to_chapter(self):
        """Add test members as board members to test chapter"""
        # Define board roles - these should already be created in setUp
        roles = ["Chair", "Secretary", "Treasurer"]
        
        # Add each member with a role
        for i, member in enumerate(self.test_members):
            role = roles[i % len(roles)]
            
            # Verify the role exists before trying to use it
            if not frappe.db.exists("Chapter Role", role):
                frappe.throw(f"Test chapter role {role} does not exist. Please ensure create_test_chapter_roles was called.")
            
            self.test_chapter.append("board_members", {
                "member": member.name,
                "member_name": member.full_name,
                "email": member.email,
                "chapter_role": role,
                "from_date": frappe.utils.today(),
                "is_active": 1
            })
            
        self.test_chapter.save(ignore_permissions=True)
    
    def test_create_volunteer_from_board_member(self):
        """Test creating a volunteer record from a board member"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Use the sync function to create volunteers for board members - skip the first one
        # because it already has a volunteer (created in setup)
        member_to_check = self.test_members[1].name
        
        result = frappe.call("verenigingen.verenigingen.doctype.volunteer.volunteer.sync_chapter_board_members")
        
        # Verify volunteers were created
        volunteer_exists = frappe.db.exists("Volunteer", {"member": member_to_check})
        self.assertTrue(volunteer_exists, f"Volunteer should be created for member {member_to_check}")
        
        if volunteer_exists:
            self.test_volunteers.append(volunteer_exists)
    
    def test_board_assignments_sync(self):
        """Test syncing board positions to volunteer assignments"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Run the sync function
        result = frappe.call("verenigingen.verenigingen.doctype.volunteer.volunteer.sync_chapter_board_members")
        
        # Check assignments for the pre-existing volunteer
        volunteer = frappe.get_doc("Volunteer", self.test_volunteers[0])
        
        # Should have a board position assignment
        has_board_assignment = False
        
        # Check what fields exist on the volunteer document
        if hasattr(volunteer, 'assignments'):
            assignments_field = 'assignments'
        elif hasattr(volunteer, 'volunteer_assignments'):
            assignments_field = 'volunteer_assignments'
        else:
            frappe.msgprint(f"Available fields on volunteer: {dir(volunteer)}")
            assignments_field = None
        
        if assignments_field:
            for assignment in getattr(volunteer, assignments_field):
                if (assignment.get('assignment_type') == "Board Position" and 
                    assignment.get('reference_doctype') == "Chapter" and
                    assignment.get('reference_name') == self.test_chapter.name):
                    has_board_assignment = True
                    break
        
        # If no assignments field found, try to call a method that might access assignments
        if not has_board_assignment and hasattr(volunteer, 'get_active_assignments'):
            active_assignments = volunteer.get_active_assignments()
            for assignment in active_assignments:
                if (assignment.get('assignment_type') == "Board Position" and 
                    assignment.get('reference_doctype') == "Chapter" and
                    assignment.get('reference_name') == self.test_chapter.name):
                    has_board_assignment = True
                    break
                    
        self.assertTrue(has_board_assignment, "Volunteer should have a board position assignment")
    
    def test_board_role_change(self):
        """Test role changes for board members sync to volunteer assignments"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Run initial sync
        frappe.call("verenigingen.verenigingen.doctype.volunteer.volunteer.sync_chapter_board_members")
        
        # Change a board member's role
        for board_member in self.test_chapter.board_members:
            if board_member.member == self.test_members[0].name:
                board_member.chapter_role = "New Role"
                break
                
        self.test_chapter.save(ignore_permissions=True)
        
        # Run sync again
        frappe.call("verenigingen.verenigingen.doctype.volunteer.volunteer.sync_chapter_board_members")
        
        # Check if volunteer assignment was updated
        volunteer = frappe.get_doc("Volunteer", self.test_volunteers[0])
        
        # Should have a board position assignment with the new role
        has_new_role = False
        
        # Check what fields exist on the volunteer document
        if hasattr(volunteer, 'assignments'):
            assignments_field = 'assignments'
        elif hasattr(volunteer, 'volunteer_assignments'):
            assignments_field = 'volunteer_assignments'
        else:
            frappe.msgprint(f"Available fields on volunteer: {dir(volunteer)}")
            assignments_field = None
        
        if assignments_field:
            for assignment in getattr(volunteer, assignments_field):
                if (assignment.get('assignment_type') == "Board Position" and 
                    assignment.get('reference_name') == self.test_chapter.name and
                    assignment.get('role') == "New Role"):
                    has_new_role = True
                    break
        
        # If no assignments field found, try to call a method that might access assignments
        if not has_new_role and hasattr(volunteer, 'get_active_assignments'):
            active_assignments = volunteer.get_active_assignments()
            for assignment in active_assignments:
                if (assignment.get('assignment_type') == "Board Position" and 
                    assignment.get('reference_name') == self.test_chapter.name and
                    assignment.get('role') == "New Role"):
                    has_new_role = True
                    break
                    
        self.assertTrue(has_new_role, "Volunteer assignment should be updated with new role")
