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

# File: verenigingen/verenigingen/doctype/appeal_communication_entry/appeal_communication_entry.py
import frappe  
from frappe.model.document import Document

class AppealCommunicationEntry(Document):
    def validate(self):
        # Ensure communication date is set
        if not self.communication_date:
            self.communication_date = frappe.utils.now()

# File: verenigingen/verenigingen/doctype/termination_audit_entry/termination_audit_entry.py
import frappe
from frappe.model.document import Document

class TerminationAuditEntry(Document):
    def validate(self):
        # Set timestamp if not provided
        if not self.timestamp:
            self.timestamp = frappe.utils.now()
        
        # Set user if not provided
        if not self.user:
            self.user = frappe.session.user
