import unittest
import frappe
from frappe.utils import today, add_days
import uuid
from verenigingen.verenigingen.doctype.volunteer.volunteer import sync_chapter_board_members

class TestChapterVolunteerIntegration(unittest.TestCase):
    def setUp(self):
        # Create a unique identifier for this test run
        self.test_id = str(uuid.uuid4()).replace('-', '')[:12]
        
        # Test data
        self.test_members = []
        self.test_volunteers = []
        
        # Create test data in the right order
        self.create_test_chapter_roles()
        self.create_test_chapter()
        self.create_test_members()
        
    def tearDown(self):
        # Clean up test data in reverse order to avoid link errors
        # First clear board members from chapter
        if hasattr(self, 'test_chapter') and self.test_chapter:
            try:
                self.test_chapter = frappe.get_doc("Chapter", self.test_chapter.name)
                self.test_chapter.board_members = []
                self.test_chapter.save(ignore_permissions=True)
            except Exception as e:
                print(f"Error clearing board members: {e}")
        
        # Delete test volunteers
        for volunteer in self.test_volunteers:
            try:
                frappe.delete_doc("Volunteer", volunteer, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting volunteer {volunteer}: {e}")
        
        # Delete test members
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
        
        # Delete the chapter head member
        if hasattr(self, 'chapter_head_member') and self.chapter_head_member:
            try:
                frappe.delete_doc("Member", self.chapter_head_member.name, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting chapter head {self.chapter_head_member.name}: {e}")
        
        # Delete chapter roles
        for role in ["Chair", "Secretary", "Treasurer", "New Role"]:
            try:
                if frappe.db.exists("Chapter Role", role):
                    frappe.delete_doc("Chapter Role", role, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"Error deleting role {role}: {e}")

    def create_test_chapter_roles(self):
        """Create test chapter roles for use in board memberships"""
        roles = ["Chair", "Secretary", "Treasurer", "New Role"]
        
        for role in roles:
            if not frappe.db.exists("Chapter Role", role):
                role_doc = frappe.get_doc({
                    "doctype": "Chapter Role",
                    "name": role,
                    "role_name": role,
                    "permissions_level": "Admin",
                    "is_active": 1
                })
                role_doc.insert(ignore_permissions=True)
                
    def create_test_chapter(self):
        """Create a test chapter with unique name using UUID"""
        # Create a member for chapter head with unique email
        head_email = f"chapterhead{self.test_id}@example.com"
        
        # Create a new chapter head
        self.chapter_head_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Chapter",
            "last_name": f"Head{self.test_id[:8]}", 
            "email": head_email
        })
        self.chapter_head_member.insert(ignore_permissions=True)
        
        # Generate a unique name for the test chapter
        test_chapter_name = f"TestChapter{self.test_id[:8]}"
        
        # Create the chapter
        self.test_chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": test_chapter_name,
            "chapter_head": self.chapter_head_member.name,
            "region": "TestRegion",
            "introduction": "Test chapter for integration tests"
        })
        self.test_chapter.insert(ignore_permissions=True)
        
        return self.test_chapter
        
    def create_test_members(self):
        """Create test members with unique names using UUID"""
        for i in range(3):
            # Unique email with UUID
            email = f"boardmember{i}{self.test_id}@example.com"
            
            # Create member with unique name
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"Board{i}",
                "last_name": f"Test{self.test_id[:6]}{i}", # Using UUID for uniqueness
                "email": email
            })
            member.insert(ignore_permissions=True)
            self.test_members.append(member)
        
        # Create a volunteer for first member
        if self.test_members:
            unique_name = f"TestVol{self.test_id[:8]}"
            volunteer = frappe.get_doc({
                "doctype": "Volunteer",
                "volunteer_name": unique_name,
                "email": f"{unique_name.lower()}@example.org",
                "member": self.test_members[0].name,
                "status": "Active",
                "start_date": today()
            })
            volunteer.insert(ignore_permissions=True)
            self.test_volunteers.append(volunteer.name)
    
    def add_board_members_to_chapter(self):
        """Add test members as board members to test chapter"""
        # Define board roles
        roles = ["Chair", "Secretary", "Treasurer"]
        
        # Add each member with a role
        for i, member in enumerate(self.test_members):
            role = roles[i % len(roles)]
            
            # Verify the role exists
            if not frappe.db.exists("Chapter Role", role):
                frappe.throw(f"Test chapter role {role} does not exist")
            
            self.test_chapter.append("board_members", {
                "member": member.name,
                "member_name": member.full_name,
                "email": member.email,
                "chapter_role": role,
                "from_date": today(),
                "is_active": 1
            })
        
        self.test_chapter.save(ignore_permissions=True)

    def test_board_assignments_sync(self):
        """Test syncing board positions to volunteer assignments"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Run the sync function
        sync_chapter_board_members()
        
        # Reload volunteer to get latest data
        volunteer = frappe.get_doc("Volunteer", self.test_volunteers[0])
        
        # Get aggregated assignments - the proper way to check assignments
        assignments = volunteer.get_aggregated_assignments()
        
        # Check if there's a board assignment for this chapter
        has_board_assignment = False
        for assignment in assignments:
            if (assignment.get('source_type') == "Board Position" and 
                assignment.get('source_doctype') == "Chapter" and
                assignment.get('source_name') == self.test_chapter.name):
                has_board_assignment = True
                break
        
        self.assertTrue(has_board_assignment, "Volunteer should have a board position assignment")

    def test_create_volunteer_from_board_member(self):
        """Test creating a volunteer record from a board member"""
        # Add board members to chapter
        self.add_board_members_to_chapter()
        
        # Select a member that doesn't have a volunteer yet
        member_to_check = self.test_members[1].name
        
        # First make sure this member doesn't already have a volunteer
        existing_volunteer = frappe.db.exists("Volunteer", {"member": member_to_check})
        if existing_volunteer:
            frappe.delete_doc("Volunteer", existing_volunteer, force=True, ignore_permissions=True)
        
        # Run the sync
        sync_chapter_board_members()
        
        # Check if a volunteer was created
        volunteer_exists = frappe.db.exists("Volunteer", {"member": member_to_check})
        
        # Add to test_volunteers if created
        if volunteer_exists:
            self.test_volunteers.append(volunteer_exists)
        
        self.assertTrue(volunteer_exists, f"Volunteer should be created for member {member_to_check}")

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
        
        self.test_chapter.save(ignore_permissions=True)
        
        # Run sync again
        sync_chapter_board_members()
        
        # Get volunteer and check for updated role
        volunteer = frappe.get_doc("Volunteer", self.test_volunteers[0])
        
        # Get aggregated assignments
        assignments = volunteer.get_aggregated_assignments()
        
        # Check if there's an assignment with the new role
        has_new_role = False
        for assignment in assignments:
            if (assignment.get('source_type') == "Board Position" and 
                assignment.get('source_doctype') == "Chapter" and
                assignment.get('source_name') == self.test_chapter.name and
                assignment.get('role') == "New Role"):
                has_new_role = True
                break
        
        self.assertTrue(has_new_role, "Volunteer assignment should be updated with new role")
