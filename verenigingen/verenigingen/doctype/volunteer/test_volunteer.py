# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import unittest
import frappe
from frappe.utils import getdate, add_days, today

class TestVolunteer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tell Frappe not to make test records
        frappe.flags.make_test_records = False
        
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
                
        try:
            frappe.delete_doc("Volunteer Activity", self.test_activity_name)
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
        self.test_member.insert(ignore_permissions=True)
    
    def create_test_interest_categories(self):
        """Create test interest categories"""
        categories = ["Test Category 1", "Test Category 2"]
        for category in categories:
            if not frappe.db.exists("Volunteer Interest Category", category):
                frappe.get_doc({
                    "doctype": "Volunteer Interest Category",
                    "category_name": category,
                    "description": f"Test category {category}"
                }).insert(ignore_permissions=True)

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
        
        self.test_volunteer.insert(ignore_permissions=True)
        return self.test_volunteer
        
    def create_test_activity(self):
        """Create a test volunteer activity"""
        activity = frappe.get_doc({
            "doctype": "Volunteer Activity",
            "volunteer": self.test_volunteer.name,
            "activity_type": "Project",
            "role": "Project Coordinator",
            "description": "Test volunteer activity",
            "status": "Active",
            "start_date": today()
        })
        activity.insert(ignore_permissions=True)
        self.test_activity_name = activity.name
        return activity
        
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
        
    def test_add_activity(self):
        """Test adding an activity to a volunteer"""
        volunteer = self.create_test_volunteer()
        
        # Create an activity
        activity = self.create_test_activity()
        
        # Verify the activity is in the volunteer's aggregated assignments
        assignments = volunteer.get_aggregated_assignments()
        
        activity_found = False
        for assignment in assignments:
            if (assignment["source_type"] == "Activity" and 
                assignment["source_doctype"] == "Volunteer Activity" and
                assignment["source_name"] == activity.name):
                activity_found = True
                break
                
        self.assertTrue(activity_found, "Activity should appear in volunteer's aggregated assignments")
        
    def test_end_activity(self):
        """Test ending an activity"""
        volunteer = self.create_test_volunteer()
        
        # Create an activity
        activity = self.create_test_activity()
        
        # End the activity
        volunteer.end_activity(activity.name, today(), "Test completion")
        
        # Reload activity
        activity.reload()
        
        # Verify status change
        self.assertEqual(activity.status, "Completed")
        self.assertEqual(activity.end_date, today())
        
        # Verify it's no longer in active assignments but in history
        assignments = volunteer.get_aggregated_assignments()
        
        activity_found = False
        for assignment in assignments:
            if (assignment["source_type"] == "Activity" and 
                assignment["source_doctype"] == "Volunteer Activity" and
                assignment["source_name"] == activity.name):
                activity_found = True
                break
                
        self.assertFalse(activity_found, "Activity should not be in active assignments")
        
        # Reload volunteer to check assignment history
        volunteer.reload()
        
        # Check assignment history
        history_entry_found = False
        for entry in volunteer.assignment_history:
            if (entry.reference_doctype == "Volunteer Activity" and 
                entry.reference_name == activity.name):
                history_entry_found = True
                break
                
        self.assertTrue(history_entry_found, "Activity should be in assignment history")
        
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
        # Create a new volunteer with 'New' status
        volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": "Status Test Volunteer",
            "email": "status.test@example.org",
            "member": self.test_member.name,
            "status": "New",
            "start_date": today()
        })
        volunteer.insert(ignore_permissions=True)
        
        # Create an activity for this volunteer
        activity = frappe.get_doc({
            "doctype": "Volunteer Activity",
            "volunteer": volunteer.name,
            "activity_type": "Project",
            "role": "Team Member",
            "status": "Active",
            "start_date": today()
        })
        activity.insert(ignore_permissions=True)
        
        # Reload volunteer to see status changes
        volunteer.reload()
        
        # Status should now be Active
        self.assertEqual(volunteer.status, "Active")
        
        # Cleanup
        frappe.delete_doc("Volunteer Activity", activity.name)
        frappe.delete_doc("Volunteer", volunteer.name)
    
    def test_volunteer_history(self):
        """Test the volunteer history feature"""
        volunteer = self.create_test_volunteer()
        
        # Create an activity
        activity = self.create_test_activity()
        
        # Get volunteer history
        history = volunteer.get_volunteer_history()
        
        # Verify activity is in history
        activity_in_history = False
        for entry in history:
            if (entry["assignment_type"] == "Activity" and 
                "Project Coordinator" in entry["role"]):
                activity_in_history = True
                break
                
        self.assertTrue(activity_in_history, "Activity should appear in volunteer history")
        
        # End the activity
        activity.status = "Completed"
        activity.end_date = today()
        activity.save()
        
        # Get updated history
        volunteer.reload()
        history = volunteer.get_volunteer_history()
        
        # Verify completed activity is in history with correct status
        completed_in_history = False
        for entry in history:
            if (entry["assignment_type"] == "Activity" and 
                "Project Coordinator" in entry["role"] and
                entry["status"] == "Completed"):
                completed_in_history = True
                break
                
        self.assertTrue(completed_in_history, "Completed activity should be in history with correct status")
