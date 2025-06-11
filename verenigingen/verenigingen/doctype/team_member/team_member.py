# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class TeamMember(Document):
    def validate(self):
        """Validate team member data"""
        self.validate_dates()
        self.validate_volunteer()
        self.sync_status_and_active_flag()
        
    def validate_dates(self):
        """Validate start and end dates"""
        if self.to_date and self.from_date and self.to_date < self.from_date:
            frappe.throw(_("End date cannot be before start date"))
            
    def validate_volunteer(self):
        """Ensure a volunteer is assigned"""
        if not self.volunteer:
            frappe.throw(_("A volunteer must be assigned to the team member"))
            
    def sync_status_and_active_flag(self):
        """Ensure is_active and status are in sync"""
        if not self.is_active and self.status == "Active":
            self.status = "Inactive"
        elif self.is_active and self.status != "Active":
            self.is_active = 0
