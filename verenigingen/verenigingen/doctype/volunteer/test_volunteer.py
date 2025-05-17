# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import getdate, add_days, today

class TestVolunteer(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.create_test_member()
        self.create_test_interest_categories()
        
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
            
        for category in ["Test Category 1", "Test Category 2"]:
            try:
                frappe.delete_doc("Volunteer Interest Category", category)
            except Exception:
                pass
    
    def create_test_member(self):
        """Create a test member record"""
        if frappe.db.exists("Member", {"email": "test_volunteer@example.com"}):
            frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": "test_volunteer@example.com"}, "name"))
        
        self.test_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Test",
            "last_name": "Volunteer",
            "email": "test_volunteer@example.com"
        })
        self.test_member.insert()
    
    def create_test_interest_categories(self):
        """Create test interest categories"""
        categories = ["Test Category 1", "Test Category 2"]
        for category in categories:
            if not frappe.db.exists("Volunteer Interest Category", category):
                frappe.get_doc({
                    "doctype": "Volunteer Interest Category",
                    "category_name": category,
                    "description": f"Test category {category}"
                }).insert()

    def create_test_volunteer(self):
        """Create a test volunteer record"""
        self.test_volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": "Test Volunteer",
            "email": "test.volunteer@example.org",
            "member": self.test_member.name,
            "status": "Active",
            "start_date": today()
        })
        
        # Add interests
        self.test_volunteer.append("interests", {
            "interest_area": "Test Category 1"
        })
        
        # Add skills
        self.test_volunteer.append("skills_and_qualifications", {
            "skill_category": "Technical",
            "volunteer_skill": "Python Programming",
            "proficiency_level": "4 - Advanced"
        })
        
        self.test_volunteer.insert()
        return self.test_volunteer
        
    def test_volunteer_creation(self):
        """Test creating a volunteer record"""
        volunteer = self.create_test_volunteer()
        
        # Verify record was created correctly
        self.assertEqual(volunteer.volunteer_name, "Test Volunteer")
        self.assertEqual(volunteer.member, self.test_member.name)
        self.assertEqual(volunteer.status, "Active")
        
        # Verify interests
        self.assertEqual(len(volunteer.interests), 1)
        self.assertEqual(volunteer.interests[0].interest_area, "Test Category 1")
        
        # Verify skills
        self.assertEqual(len(volunteer.skills_and_qualifications), 1)
        self.assertEqual(volunteer.skills_and_qualifications[0].volunteer_skill, "Python Programming")
        self.assertEqual(volunteer.skills_and_qualifications[0].proficiency_level, "4 - Advanced")
        
    def test_add_assignment(self):
        """Test adding an assignment to a volunteer"""
        volunteer = self.create_test_volunteer()
        
        # Create a test chapter for assignment
        if not frappe.db.exists("Chapter", "Test Chapter"):
            chapter = frappe.get_doc({
                "doctype": "Chapter",
                "chapter_head": self.test_member.name,
                "region": "Test Region",
                "introduction": "Test chapter for assignments"
            })
            chapter.insert()
            
        # Add a board assignment
        volunteer.add_board_assignment(
            chapter="Test Chapter",
            role="Test Role",
            start_date=today()
        )
        
        # Reload the volunteer to get updated data
        volunteer.reload()
        
        # Verify assignment was added
        self.assertEqual(len(volunteer.active_assignments), 1)
        self.assertEqual(volunteer.active_assignments[0].assignment_type, "Board Position")
        self.assertEqual(volunteer.active_assignments[0].reference_doctype, "Chapter")
        self.assertEqual(volunteer.active_assignments[0].reference_name, "Test Chapter")
        self.assertEqual(volunteer.active_assignments[0].role, "Test Role")
        
    def test_end_assignment(self):
        """Test ending an active assignment"""
        volunteer = self.create_test_volunteer()
        
        # Create a test assignment
        volunteer.append("active_assignments", {
            "assignment_type": "Team",
            "reference_doctype": "Volunteer Team",
            "reference_name": "Test Team",
            "role": "Team Member",
            "start_date": add_days(today(), -30),
            "status": "Active"
        })
        volunteer.save()
        
        # End the assignment
        volunteer.end_assignment(
            assignment_idx=1,
            end_date=today(),
            notes="Test completion"
        )
        
        # Reload volunteer
        volunteer.reload()
        
        # Verify active assignment was moved to history
        self.assertEqual(len(volunteer.active_assignments), 0)
        self.assertEqual(len(volunteer.assignment_history), 1)
        self.assertEqual(volunteer.assignment_history[0].status, "Completed")
        self.assertEqual(volunteer.assignment_history[0].role, "Team Member")
        
    def test_get_skills_by_category(self):
        """Test retrieving skills grouped by category"""
        volunteer = self.create_test_volunteer()
        
        # Add more skills in different categories
        volunteer.append("skills_and_qualifications", {
            "skill_category": "Communication",
            "volunteer_skill": "Public Speaking",
            "proficiency_level": "3 - Intermediate"
        })
        volunteer.append("skills_and_qualifications", {
            "skill_category": "Technical",
            "volunteer_skill": "Database Design",
            "proficiency_level": "2 - Basic"
        })
        volunteer.save()
        
        # Get skills by category
        skills_by_category = volunteer.get_skills_by_category()
        
        # Verify grouping
        self.assertIn("Technical", skills_by_category)
        self.assertIn("Communication", skills_by_category)
        self.assertEqual(len(skills_by_category["Technical"]), 2)
        self.assertEqual(len(skills_by_category["Communication"]), 1)
        
    def test_volunteer_status_tracking(self):
        """Test volunteer status updates based on assignments"""
        volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": "Status Test Volunteer",
            "email": "status.test@example.org",
            "member": self.test_member.name,
            "status": "New",
            "start_date": today()
        })
        volunteer.insert()
        
        # Add an assignment and check if status changes from New to Active
        volunteer.append("active_assignments", {
            "assignment_type": "Team",
            "reference_doctype": "Volunteer Team",
            "reference_name": "Status Test Team",
            "role": "Team Member",
            "start_date": today(),
            "status": "Active"
        })
        volunteer.save()
        volunteer.reload()
        
        # Status should now be Active
        self.assertEqual(volunteer.status, "Active")
        
        # Cleanup
        frappe.delete_doc("Volunteer", volunteer.name)
