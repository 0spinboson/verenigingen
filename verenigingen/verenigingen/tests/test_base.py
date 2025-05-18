# -*- coding: utf-8 -*-
# Copyright (c) 2025, Your Organization and Contributors
# See license.txt

import unittest
import frappe
from frappe.utils import today

class VereningingenTestCase(unittest.TestCase):
    """Base test class for Verenigingen tests with helpful utility methods"""
    
    @classmethod
    def setUpClass(cls):
        """Set up common test environment"""
        super().setUpClass()
        # Disable automatic test record creation
        frappe.flags.make_test_records = False
    
    # Common helper methods can go here
    def create_test_member(self, email=None):
        """Create a test member record"""
        if not email:
            email = f"test_{frappe.utils.random_string(8)}@example.com"
            
        if frappe.db.exists("Member", {"email": email}):
            frappe.delete_doc("Member", frappe.db.get_value("Member", {"email": email}, "name"))
        
        member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Test",
            "last_name": "Member",
            "email": email
        })
        member.insert(ignore_permissions=True)
        return member
    
    def create_test_volunteer(self, member=None):
        """Create a test volunteer record"""
        if not member:
            member = self.create_test_member()
            
        volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "volunteer_name": f"Test Volunteer {frappe.utils.random_string(5)}",
            "email": f"test.volunteer.{frappe.utils.random_string(5)}@example.org",
            "member": member.name,
            "status": "Active",
            "start_date": today()
        })
        volunteer.insert(ignore_permissions=True)
        return volunteer
