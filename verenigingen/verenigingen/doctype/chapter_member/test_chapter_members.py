import frappe
import unittest
import random
import string
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, add_days, today

class TestChapterMemberIntegration(FrappeTestCase):
    def setUp(self):
        # Generate a unique identifier using only alphanumeric characters
        self.unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Clean up any existing test data
        self.cleanup_test_data()
        
        # Create test role
        self.role = frappe.get_doc({
            "doctype": "Chapter Role",
            "role_name": f"Board Role {self.unique_id}",
            "permissions_level": "Basic",
            "is_chair": 0,
            "is_active": 1
        })
        self.role.insert(ignore_permissions=True)
        
        # Create test members
        self.test_member1 = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"Test1",
            "last_name": f"Member {self.unique_id}",
            "email": f"test1{self.unique_id}@example.com"
        })
        self.test_member1.insert(ignore_permissions=True)
        
        self.test_member2 = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"Test2",
            "last_name": f"Member {self.unique_id}",
            "email": f"test2{self.unique_id}@example.com"
        })
        self.test_member2.insert(ignore_permissions=True)
        
        # Create test chapter
        self.chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test Chapter for Member Integration",
            "published": 1,
            "members": [] # Ensure this starts empty
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
    
    def test_add_member_method(self):
        """Test directly adding a member to a chapter"""
        # Initially chapter should have no members
        self.chapter.reload()
        self.assertEqual(len(self.chapter.members), 0, "Chapter should start with no members")
        
        # Add member using the add_member method
        result = self.chapter.add_member(
            self.test_member1.name,
            introduction="Test introduction",
            website_url="https://example.com"
        )
        
        # Reload chapter to see changes
        self.chapter.reload()
        
        # Verify member was added
        self.assertEqual(len(self.chapter.members), 1, "Chapter should now have 1 member")
        self.assertEqual(self.chapter.members[0].member, self.test_member1.name, 
                      "Member should be added to chapter")
        self.assertEqual(self.chapter.members[0].introduction, "Test introduction", 
                      "Member introduction should be set")
        self.assertEqual(self.chapter.members[0].website_url, "https://example.com", 
                      "Member website URL should be set")
        self.assertTrue(result, "add_member method should return True for success")
        
        # Try to add same member again - should not add duplicate
        result = self.chapter.add_member(self.test_member1.name)
        
        # Reload chapter
        self.chapter.reload()
        
        # Verify no duplicate was added
        self.assertEqual(len(self.chapter.members), 1, "Chapter should still have 1 member")
        self.assertFalse(result, "add_member method should return False for already a member")
    
    def test_board_member_auto_added_to_members(self):
        """Test that board members are automatically added to chapter members"""
        # Initially chapter should have no members
        self.assertEqual(len(self.chapter.members), 0, "Chapter should start with no members")
        
        # Add member as board member
        self.chapter.append("board_members", {
            "member": self.test_member1.name,
            "member_name": self.test_member1.full_name,
            "email": self.test_member1.email,
            "chapter_role": self.role.name,
            "from_date": frappe.utils.today(),
            "is_active": 1
        })
        self.chapter.save()
        
        # Reload chapter to see changes
        self.chapter.reload()
        
        # Verify member was automatically added to members
        self.assertTrue(
            any(m.member == self.test_member1.name for m in self.chapter.members),
            "Board member should be automatically added to chapter members"
        )
    
    def test_remove_member_method(self):
        """Test removing a member from a chapter"""
        # Add two members
        self.chapter.add_member(self.test_member1.name)
        self.chapter.add_member(self.test_member2.name)
        
        # Reload chapter
        self.chapter.reload()
        
        # Verify both members are in the chapter
        self.assertEqual(len(self.chapter.members), 2, "Chapter should have 2 members")
        
        # Remove first member
        result = self.chapter.remove_member(self.test_member1.name)
        
        # Reload chapter
        self.chapter.reload()
        
        # Verify first member is removed and second is still there
        self.assertEqual(len(self.chapter.members), 1, "Chapter should now have 1 member")
        self.assertEqual(self.chapter.members[0].member, self.test_member2.name, 
                      "Second member should still be in chapter")
        self.assertTrue(result, "remove_member method should return True for success")
        
        # Try to remove a member that's not in the chapter
        result = self.chapter.remove_member('NonExistentMember')
        
        # Verify return value
        self.assertFalse(result, "remove_member should return False for non-existent member")
    
    def test_assign_member_to_chapter(self):
        """Test assigning a member to a chapter sets primary_chapter and adds to members"""
        # Use the server method to assign member to chapter
        from verenigingen.verenigingen.doctype.chapter.chapter import assign_member_to_chapter
        
        # Initially member should not have a primary chapter
        self.assertFalse(self.test_member1.get("primary_chapter"), 
                      "Member should not have a primary chapter initially")
        
        # Assign member to chapter
        result = assign_member_to_chapter(self.test_member1.name, self.chapter.name, "Test note")
        
        # Reload member and chapter
        self.test_member1.reload()
        self.chapter.reload()
        
        # Verify member's primary chapter is set
        self.assertEqual(self.test_member1.primary_chapter, self.chapter.name, 
                      "Member's primary chapter should be set")
        
        # Verify member is added to chapter members
        self.assertTrue(
            any(m.member == self.test_member1.name for m in self.chapter.members),
            "Member should be added to chapter members"
        )
        
        # Verify result
        self.assertTrue(result.get("success"), "assign_member_to_chapter should return success")
        self.assertTrue(result.get("added_to_members"), 
                     "assign_member_to_chapter should indicate member was added")
    
    def test_join_and_leave_chapter(self):
        """Test joining and leaving a chapter"""
        from verenigingen.verenigingen.doctype.chapter.chapter import join_chapter, leave_chapter
        
        # Set up test session user (necessary to simulate permission checks)
        original_user = frappe.session.user
        try:
            # Set session user to member's email to pass permission check
            frappe.set_user(self.test_member1.email)
            
            # Join chapter
            result = join_chapter(
                self.test_member1.name, 
                self.chapter.name,
                "Test introduction",
                "https://example.com"
            )
            
            # Reload data
            self.test_member1.reload()
            self.chapter.reload()
            
            # Verify join success
            self.assertTrue(result.get("success"), "join_chapter should return success")
            self.assertTrue(result.get("added"), "join_chapter should indicate member was added")
            self.assertEqual(self.test_member1.primary_chapter, self.chapter.name, 
                          "Member's primary chapter should be set")
            self.assertTrue(
                any(m.member == self.test_member1.name for m in self.chapter.members),
                "Member should be added to chapter members"
            )
            
            # Leave chapter
            result = leave_chapter(
                self.test_member1.name,
                self.chapter.name,
                "Test leave reason"
            )
            
            # Reload data
            self.test_member1.reload()
            self.chapter.reload()
            
            # Verify leave success
            self.assertTrue(result.get("success"), "leave_chapter should return success")
            self.assertTrue(result.get("removed"), "leave_chapter should indicate member was removed")
            self.assertFalse(self.test_member1.primary_chapter, 
                          "Member's primary chapter should be cleared")
            self.assertFalse(
                any(m.member == self.test_member1.name and m.enabled == 1 for m in self.chapter.members),
                "Member should be removed from active chapter members"
            )
        finally:
            # Restore original user
            frappe.set_user(original_user)
    
    def test_get_members_method(self):
        """Test getting list of members from a chapter"""
        # Add two members with different properties
        self.chapter.add_member(
            self.test_member1.name,
            introduction="First member intro", 
            website_url="https://first.example.com"
        )
        self.chapter.add_member(
            self.test_member2.name,
            introduction="Second member intro", 
            website_url="https://second.example.com"
        )
        
        # Disable the second member
        for member in self.chapter.members:
            if member.member == self.test_member2.name:
                member.enabled = 0
                member.leave_reason = "Test leave reason"
                break
        self.chapter.save()
        
        # Get active members
        active_members = self.chapter.get_members(include_disabled=False)
        
        # Verify only active members are returned
        self.assertEqual(len(active_members), 1, "Should return only 1 active member")
        self.assertEqual(active_members[0]["id"], self.test_member1.name, 
                      "Active member should be the first member")
        
        # Get all members including disabled
        all_members = self.chapter.get_members(include_disabled=True)
        
        # Verify all members are returned
        self.assertEqual(len(all_members), 2, "Should return both members")
        
        # Verify member details are included
        member1 = next((m for m in all_members if m["id"] == self.test_member1.name), None)
        self.assertIsNotNone(member1, "First member should be in the result")
        self.assertEqual(member1["name"], self.test_member1.full_name, "Member name should match")
        self.assertEqual(member1["email"], self.test_member1.email, "Member email should match")
        self.assertEqual(member1["introduction"], "First member intro", "Member intro should match")
        self.assertEqual(member1["website_url"], "https://first.example.com", "Member URL should match")
        self.assertTrue(member1["enabled"], "First member should be enabled")
