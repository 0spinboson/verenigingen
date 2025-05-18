# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

from frappe.model.document import Document

class TeamMember(Document):
    def validate(self):
        """Validate dates"""
        if self.to_date and self.from_date and self.to_date < self.from_date:
            frappe.throw(_("End date cannot be before start date"))
            
        # Ensure is_active and status are in sync
        if not self.is_active and self.status == "Active":
            self.status = "Inactive"
        elif self.is_active and self.status != "Active":
            self.is_active = 0
