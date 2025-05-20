import frappe
import unittest
import random
import string
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, add_days, today

class TestChapterHead(FrappeTestCase):
    def setUp(self):
        # Generate a unique identifier using only alphanumeric characters
        self.unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Clean up any existing test data
        self.cleanup_test_data()
        
        # Create test chair role
        self.chair_role = frappe.get_doc({
            "doctype": "Chapter Role",
            "role_name": f"Chair {self.unique_id}",
            "permissions_level": "Admin",
            "is_chair": 1,
            "is_active": 1
        })
        self.chair_role.insert(ignore_permissions=True)
        
        # Create test regular role
        self.regular_role = frappe.get_doc({
            "doctype": "Chapter Role",
            "role_name": f"Secretary {self.unique_id}",
            "permissions_level": "Basic",
            "is_chair": 0,
            "is_active": 1
        })
        self.regular_role.insert(ignore_permissions=True)
        
        # Create test members
        self.chair_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"Chair",
            "last_name": f"Member {self.unique_id}",
            "email": f"chair{self.unique_id}@example.com"
        })
        self.chair_member.insert(ignore_permissions=True)
        
        self.regular_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"Regular",
            "last_name": f"Member {self.unique_id}",
            "email": f"regular{self.unique_id}@example.com"
        })
        self.regular_member.insert(ignore_permissions=True)
        
        # Create test chapter
        self.chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test Chapter for Head Tests",
            "published": 1
        })
        self.chapter.insert(ignore_permissions=True)
        
    def tearDown(self):
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        # Delete any test roles
        for role in frappe.get_all("Chapter Role", filters={"role_name": ["like", f"%{self.unique_id}"]}):
            try:
                frappe.delete_doc("Chapter Role", role.name, force=True)
            except Exception as e:
                print(f"Error cleaning up role {role.name}: {str(e)}")
                
        # Delete any test chapters
        for chapter in frappe.get_all("Chapter", filters={"name": ["like", f"Test Chapter {self.unique_id}%"]}):
            try:
                frappe.delete_doc("Chapter", chapter.name, force=True)
            except Exception as e:
                print(f"Error cleaning up chapter {chapter.name}: {str(e)}")
                
        # Delete any test members
        for member in frappe.get_all("Member", filters={"email": ["like", f"%{self.unique_id}@example.com"]}):
            try:
                frappe.delete_doc("Member", member.name, force=True)
            except Exception as e:
                print(f"Error cleaning up member {member.name}: {str(e)}")
    
    def test_chapter_head_auto_update(self):
        """Test that chapter head is automatically updated based on chair role"""
        # Initially chapter should have no head
        self.assertFalse(self.chapter.chapter_head, "Chapter should not have a head initially")
        
        # Add regular member as board member with regular role
        self.chapter.append("board_members", {
            "member": self.regular_member.name,
            "member_name": self.regular_member.full_name,
            "email": self.regular_member.email,
            "chapter_role": self.regular_role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        self.chapter.save()
        self.chapter.reload()
        
        # Chapter head should still not be set
        self.assertFalse(self.chapter.chapter_head, 
                      "Chapter head should not be set for regular role")
        
        # Add chair member as board member with chair role
        self.chapter.append("board_members", {
            "member": self.chair_member.name,
            "member_name": self.chair_member.full_name,
            "email": self.chair_member.email,
            "chapter_role": self.chair_role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        self.chapter.save()
        self.chapter.reload()
        
        # Chapter head should now be set to chair member
        self.assertEqual(self.chapter.chapter_head, self.chair_member.name,
                      "Chapter head should be set to member with chair role")
    
    def test_chapter_head_role_change(self):
        """Test that chapter head is updated when a role is changed to chair"""
        # Add regular member as board member with regular role
        self.chapter.append("board_members", {
            "member": self.regular_member.name,
            "member_name": self.regular_member.full_name,
            "email": self.regular_member.email,
            "chapter_role": self.regular_role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        self.chapter.save()
        
        # Update regular role to be chair
        self.regular_role.is_chair = 1
        self.regular_role.save()
        
        # Reload chapter to see changes (should be updated by the role's after_save hook)
        self.chapter.reload()
        
        # Chapter head should now be set to the regular member
        self.assertEqual(self.chapter.chapter_head, self.regular_member.name,
                      "Chapter head should be updated when role is changed to chair")
    
    def test_chapter_head_member_change(self):
        """Test that chapter head is updated when board members change"""
        # Add chair member as board member with chair role
        self.chapter.append("board_members", {
            "member": self.chair_member.name,
            "member_name": self.chair_member.full_name,
            "email": self.chair_member.email,
            "chapter_role": self.chair_role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        self.chapter.save()
        self.chapter.reload()
        
        # Chapter head should be set to chair member
        self.assertEqual(self.chapter.chapter_head, self.chair_member.name,
                      "Chapter head should be set to member with chair role")
        
        # Deactivate the chair member
        for board_member in self.chapter.board_members:
            if board_member.member == self.chair_member.name:
                board_member.is_active = 0
                board_member.to_date = frappe.utils.today()
                break
                
        self.chapter.save()
        self.chapter.reload()
        
        # Chapter head should now be empty
        self.assertFalse(self.chapter.chapter_head, 
                      "Chapter head should be cleared when chair member is deactivated")
        
        # Add regular member as new chair
        self.chapter.append("board_members", {
            "member": self.regular_member.name,
            "member_name": self.regular_member.full_name,
            "email": self.regular_member.email,
            "chapter_role": self.chair_role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        self.chapter.save()
        self.chapter.reload()
        
        # Chapter head should now be set to regular member
        self.assertEqual(self.chapter.chapter_head, self.regular_member.name,
                      "Chapter head should be updated to new chair member")
    
    def test_chapter_head_multiple_chairs(self):
        """Test chapter head selection with multiple chair roles"""
        # Create another chair role
        chair_role2 = frappe.get_doc({
            "doctype": "Chapter Role",
            "role_name": f"President {self.unique_id}",
            "permissions_level": "Admin",
            "is_chair": 1,
            "is_active": 1
        })
        chair_role2.insert(ignore_permissions=True)
        
        # Create another member for the second chair role
        chair_member2 = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"President",
            "last_name": f"Member {self.unique_id}",
            "email": f"president{self.unique_id}@example.com"
        })
        chair_member2.insert(ignore_permissions=True)
        
        # Add first chair member
        self.chapter.append("board_members", {
            "member": self.chair_member.name,
            "member_name": self.chair_member.full_name,
            "email": self.chair_member.email,
            "chapter_role": self.chair_role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        
        # Add second chair member with later date
        tomorrow = frappe.utils.add_days(frappe.utils.today(), 1)
        self.chapter.append("board_members", {
            "member": chair_member2.name,
            "member_name": chair_member2.full_name,
            "email": chair_member2.email,
            "chapter_role": chair_role2.name,
            "from_date": tomorrow,
            "is_active": 1
        })
        
        self.chapter.save()
        self.chapter.reload()
        
        # One of the chair members should be set as chapter head
        # In case of multiple chairs, the implementation should be consistent
        # about which one it chooses (typically the first one found)
        self.assertTrue(
            self.chapter.chapter_head in [self.chair_member.name, chair_member2.name],
            "One of the chair members should be set as chapter head"
        )
