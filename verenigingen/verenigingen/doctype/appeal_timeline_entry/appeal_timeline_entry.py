# File: verenigingen/verenigingen/doctype/appeal_timeline_entry/appeal_timeline_entry.py
import frappe
from frappe.model.document import Document

class AppealTimelineEntry(Document):
    def validate(self):
        # Set defaults
        if not self.completion_status:
            self.completion_status = "Completed"
        
        if not self.responsible_party:
            self.responsible_party = frappe.session.user
