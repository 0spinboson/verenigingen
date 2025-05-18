# -*- coding: utf-8 -*-
# Copyright (c) 2025, Your Organization and Contributors
# See license.txt

import frappe
from frappe.utils import today, add_days
from verenigingen.verenigingen.tests.test_base import VereningingenTestCase

class TestVolunteerActivity(VereningingenTestCase):
    def setUp(self):
        # Initialize the docs to delete list
        self._docs_to_delete = []
        
        # Create test data
        self.test_member = self.create_test_member()
        self._docs_to_delete.append(("Member", self.test_member.name))
        
        self.test_volunteer = self.create_test_volunteer(self.test_member)
        self._docs_to_delete.append(("Volunteer", self.test_volunteer.name))
        
    def tearDown(self):
        # Clean up test data
        for doctype, name in self._docs_to_delete:
            try:
                frappe.delete_doc(doctype, name, force=True)
            except Exception:
                pass
    
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
        self._docs_to_delete.append(("Volunteer Activity", activity.name))
        return activity
    
    def test_activity_creation(self):
        """Test creating a volunteer activity"""
        activity = self.create_test_activity()
        
        # Basic validation
        self.assertEqual(activity.volunteer, self.test_volunteer.name)
        self.assertEqual(activity.status, "Active")
