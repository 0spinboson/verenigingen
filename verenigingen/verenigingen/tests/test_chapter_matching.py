# verenigingen/verenigingen/tests/test_chapter_matching.py
import frappe
import unittest
import random
import string
from frappe.utils import today
from verenigingen.verenigingen.tests.test_base import VereningingenTestCase

class TestChapterMatching(VereningingenTestCase):
    def setUp(self):
        # Create test chapters with different postal code patterns
        self.create_test_chapters()
        
        # Create a test member
        self.test_member = self.create_test_member()
        
        # Create test address
        self.test_address = self.create_test_address()
        
    def tearDown(self):
        # Clean up test data
        for chapter in self.test_chapters:
            try:
                frappe.delete_doc("Chapter", chapter)
            except Exception:
                pass
                
        try:
            frappe.delete_doc("Member", self.test_member.name)
        except Exception:
            pass
            
        try:
            frappe.delete_doc("Address", self.test_address.name)
        except Exception:
            pass
    
    def create_test_chapters(self):
        """Create test chapters with different postal code patterns"""
        self.test_chapters = []
        
        # Amsterdam chapter (1000-1099)
        amsterdam = self.create_test_chapter("Test Amsterdam", "Noord-Holland", "1000-1099")
        self.test_chapters.append(amsterdam.name)
        
        # Rotterdam chapter (3000-3099)
        rotterdam = self.create_test_chapter("Test Rotterdam", "Zuid-Holland", "3000-3099")
        self.test_chapters.append(rotterdam.name)
        
        # Utrecht chapter (specific postal code)
        utrecht = self.create_test_chapter("Test Utrecht", "Utrecht", "3500")
        self.test_chapters.append(utrecht.name)
        
        # Eindhoven chapter (wildcard pattern)
        eindhoven = self.create_test_chapter("Test Eindhoven", "Noord-Brabant", "56*")
        self.test_chapters.append(eindhoven.name)
    
    def create_test_chapter(self, name, region, postal_codes=None):
        """Create a test chapter"""
        chapter_data = {
            "doctype": "Chapter",
            "name": name,
            "region": region,
            "introduction": f"Test chapter for {name}",
            "published": 1
        }
        
        if postal_codes:
            chapter_data["postal_codes"] = postal_codes
            
        if frappe.db.exists("Chapter", name):
            return frappe.get_doc("Chapter", name)
            
        chapter = frappe.get_doc(chapter_data)
        chapter.insert(ignore_permissions=True)
        return chapter
    
    def create_test_address(self):
        """Create a test address"""
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": f"Test Address for {self.test_member.name}",
            "address_type": "Personal",
            "address_line1": "Test Street 123",
            "city": "Amsterdam",
            "state": "Noord-Holland",
            "country": "Netherlands",
            "pincode": "1001",  # Should match Amsterdam chapter
            "links": [{
                "link_doctype": "Member",
                "link_name": self.test_member.name
            }]
        })
        address.insert(ignore_permissions=True)
        return address
    
def test_postal_code_matching(self):
        """Test matching chapters based on postal code"""
        # Test matching by postal code range
        amsterdam_chapter = frappe.get_doc("Chapter", "Test Amsterdam")
        
        # Should match Amsterdam chapter
        self.assertTrue(amsterdam_chapter.matches_postal_code("1001"))
        self.assertTrue(amsterdam_chapter.matches_postal_code("1099"))
        self.assertFalse(amsterdam_chapter.matches_postal_code("1100"))
        
        # Test matching by exact postal code
        utrecht_chapter = frappe.get_doc("Chapter", "Test Utrecht")
        self.assertTrue(utrecht_chapter.matches_postal_code("3500"))
        self.assertFalse(utrecht_chapter.matches_postal_code("3501"))
        
        # Test matching by wildcard pattern
        eindhoven_chapter = frappe.get_doc("Chapter", "Test Eindhoven")
        self.assertTrue(eindhoven_chapter.matches_postal_code("5600"))
        self.assertTrue(eindhoven_chapter.matches_postal_code("5699"))
        self.assertFalse(eindhoven_chapter.matches_postal_code("4600"))

    def test_suggest_chapter_for_member(self):
        """Test suggesting chapters based on member address"""
        # Link the test address to the member
        self.test_member.primary_address = self.test_address.name
        self.test_member.save()
        
        # Call the suggestion function
        result = frappe.call("verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member", 
                             member_name=self.test_member.name, 
                             postal_code=self.test_address.pincode,
                             state=self.test_address.state,
                             city=self.test_address.city)
        
        # Should have matched Amsterdam chapter by postal code
        self.assertTrue(result["matches_by_postal"])
        self.assertEqual(result["matches_by_postal"][0].name, "Test Amsterdam")
        
        # Test with different postal code
        result = frappe.call("verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member",
                             member_name=self.test_member.name,
                             postal_code="3500",  # Utrecht
                             state=self.test_address.state,
                             city=self.test_address.city)
        
        # Should have matched Utrecht chapter by postal code
        self.assertTrue(result["matches_by_postal"])
        self.assertEqual(result["matches_by_postal"][0].name, "Test Utrecht")
        
        # Test matching by region only
        result = frappe.call("verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member",
                             member_name=self.test_member.name,
                             postal_code="9999",  # No match
                             state="Noord-Holland",  # Amsterdam
                             city="Unknown")
        
        # Should have matched Amsterdam chapter by region
        self.assertFalse(result["matches_by_postal"])
        self.assertTrue(result["matches_by_region"])
        self.assertEqual(result["matches_by_region"][0].name, "Test Amsterdam")
        
        # Test matching by city only
        result = frappe.call("verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member",
                             member_name=self.test_member.name,
                             postal_code=None,
                             state=None,
                             city="Amsterdam")
        
        # Should have matched Amsterdam chapter by city
        self.assertFalse(result["matches_by_postal"])
        self.assertFalse(result["matches_by_region"])
        self.assertTrue(result["matches_by_city"])
        self.assertEqual(result["matches_by_city"][0].name, "Test Amsterdam")

if __name__ == '__main__':
    unittest.main()
