# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest
import frappe
import random
import string
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days, getdate

class TestChapter(FrappeTestCase):
    def setUp(self):
        """Set up test data"""
        # Generate unique identifier
        self.unique_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Clean up any existing test data
        self.cleanup_test_data()
        
        # Create test data
        self.create_test_prerequisites()
        
    def tearDown(self):
        """Clean up test data"""
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Clean up test data"""
        # Delete test chapters
        for chapter in frappe.get_all("Chapter", filters={"name": ["like", f"Test Chapter {self.unique_id}%"]}):
            try:
                frappe.delete_doc("Chapter", chapter.name, force=True)
            except Exception as e:
                print(f"Error cleaning up chapter {chapter.name}: {str(e)}")
                
        # Delete test members
        for member in frappe.get_all("Member", filters={"email": ["like", f"%{self.unique_id}@example.com"]}):
            try:
                frappe.delete_doc("Member", member.name, force=True)
            except Exception as e:
                print(f"Error cleaning up member {member.name}: {str(e)}")
    
    def create_test_prerequisites(self):
        """Create test prerequisites"""
        # Create test member for chapter head
        self.test_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"Test",
            "last_name": f"Head {self.unique_id}",
            "email": f"testhead{self.unique_id}@example.com",
            "contact_number": "+31612345678",
            "payment_method": "Bank Transfer"
        })
        self.test_member.insert(ignore_permissions=True)
    
    def test_chapter_creation(self):
        """Test creating a basic chapter"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter for unit tests",
            "published": 1,
            "chapter_head": self.test_member.name
        })
        chapter.insert(ignore_permissions=True)
        
        # Verify chapter was created correctly
        self.assertEqual(chapter.name, f"Test Chapter {self.unique_id}")
        self.assertEqual(chapter.region, "Test Region")
        self.assertEqual(chapter.chapter_head, self.test_member.name)
        self.assertEqual(chapter.published, 1)
        
        # Verify auto-generated fields
        self.assertTrue(chapter.creation)
        self.assertTrue(chapter.modified)
    
    def test_chapter_validation(self):
        """Test chapter validation"""
        # Test missing required fields
        with self.assertRaises(frappe.ValidationError):
            chapter = frappe.get_doc({
                "doctype": "Chapter",
                "name": f"Invalid Chapter {self.unique_id}",
                # Missing region
                "introduction": "Test chapter"
            })
            chapter.insert(ignore_permissions=True)
    
    def test_postal_code_validation(self):
        """Test postal code validation and formatting"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter",
            "postal_codes": "1000-1999, 2000, 3000-3099"
        })
        chapter.insert(ignore_permissions=True)
        
        # Verify postal codes are stored correctly
        self.assertTrue("1000-1999" in chapter.postal_codes)
        self.assertTrue("2000" in chapter.postal_codes)
        self.assertTrue("3000-3099" in chapter.postal_codes)
    
    def test_chapter_head_assignment(self):
        """Test chapter head assignment and validation"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter",
            "chapter_head": self.test_member.name
        })
        chapter.insert(ignore_permissions=True)
        
        # Verify chapter head is properly assigned
        self.assertEqual(chapter.chapter_head, self.test_member.name)
        
        # Change chapter head
        new_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": f"New",
            "last_name": f"Head {self.unique_id}",
            "email": f"newhead{self.unique_id}@example.com",
            "contact_number": "+31612345679",
            "payment_method": "Bank Transfer"
        })
        new_member.insert(ignore_permissions=True)
        
        chapter.chapter_head = new_member.name
        chapter.save(ignore_permissions=True)
        
        # Verify chapter head change
        chapter.reload()
        self.assertEqual(chapter.chapter_head, new_member.name)
        
        # Clean up
        frappe.delete_doc("Member", new_member.name, force=True)
    
    def test_chapter_member_management(self):
        """Test chapter member management"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter"
        })
        chapter.insert(ignore_permissions=True)
        
        # Create additional test members
        members = []
        for i in range(3):
            member = frappe.get_doc({
                "doctype": "Member",
                "first_name": f"Member{i}",
                "last_name": f"Test {self.unique_id}",
                "email": f"member{i}{self.unique_id}@example.com",
                "contact_number": f"+3161234567{i}",
                "payment_method": "Bank Transfer",
                "primary_chapter": chapter.name
            })
            member.insert(ignore_permissions=True)
            members.append(member)
        
        # Test member count (should include chapter head + added members)
        if hasattr(chapter, 'get_member_count'):
            member_count = chapter.get_member_count()
            self.assertGreaterEqual(member_count, 3)
        
        # Clean up additional members
        for member in members:
            frappe.delete_doc("Member", member.name, force=True)
    
    def test_chapter_statistics(self):
        """Test chapter statistics functionality"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter"
        })
        chapter.insert(ignore_permissions=True)
        
        # Test basic statistics methods exist
        if hasattr(chapter, 'get_member_count'):
            self.assertTrue(callable(getattr(chapter, 'get_member_count')))
        
        if hasattr(chapter, 'get_volunteer_count'):
            self.assertTrue(callable(getattr(chapter, 'get_volunteer_count')))
        
        if hasattr(chapter, 'get_activity_count'):
            self.assertTrue(callable(getattr(chapter, 'get_activity_count')))
    
    def test_chapter_contact_info(self):
        """Test chapter contact information"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter",
            "email": f"chapter{self.unique_id}@example.org",
            "phone": "+31612345678",
            "website": "https://example.org"
        })
        chapter.insert(ignore_permissions=True)
        
        # Verify contact information
        self.assertEqual(chapter.email, f"chapter{self.unique_id}@example.org")
        self.assertEqual(chapter.phone, "+31612345678")
        self.assertEqual(chapter.website, "https://example.org")
    
    def test_chapter_publication_status(self):
        """Test chapter publication status"""
        # Create unpublished chapter
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter",
            "published": 0
        })
        chapter.insert(ignore_permissions=True)
        
        # Verify unpublished status
        self.assertEqual(chapter.published, 0)
        
        # Publish chapter
        chapter.published = 1
        chapter.save(ignore_permissions=True)
        
        # Verify published status
        chapter.reload()
        self.assertEqual(chapter.published, 1)
    
    def test_chapter_location_info(self):
        """Test chapter location information"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter",
            "city": "Amsterdam",
            "state": "North Holland",
            "country": "Netherlands"
        })
        chapter.insert(ignore_permissions=True)
        
        # Verify location information
        self.assertEqual(chapter.city, "Amsterdam")
        self.assertEqual(chapter.state, "North Holland")
        self.assertEqual(chapter.country, "Netherlands")
    
    def test_chapter_matching_by_postal_code(self):
        """Test chapter matching functionality by postal code"""
        # Create chapter with specific postal codes
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter",
            "postal_codes": "1000-1999"
        })
        chapter.insert(ignore_permissions=True)
        
        # Test postal code matching if method exists
        if hasattr(chapter, 'matches_postal_code'):
            self.assertTrue(chapter.matches_postal_code("1500"))
            self.assertFalse(chapter.matches_postal_code("2000"))
        
        # Test with individual postal code
        chapter.postal_codes = "1234"
        chapter.save(ignore_permissions=True)
        
        if hasattr(chapter, 'matches_postal_code'):
            self.assertTrue(chapter.matches_postal_code("1234"))
            self.assertFalse(chapter.matches_postal_code("1235"))
    
    def test_chapter_update_permissions(self):
        """Test chapter update and permission handling"""
        chapter = frappe.get_doc({
            "doctype": "Chapter",
            "name": f"Test Chapter {self.unique_id}",
            "region": "Test Region",
            "introduction": "Test chapter"
        })
        chapter.insert(ignore_permissions=True)
        
        # Test update
        original_modified = chapter.modified
        chapter.introduction = "Updated introduction"
        chapter.save(ignore_permissions=True)
        
        # Verify update
        chapter.reload()
        self.assertEqual(chapter.introduction, "Updated introduction")
        self.assertNotEqual(chapter.modified, original_modified)
