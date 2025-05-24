# File: verenigingen/verenigingen/doctype/appeal_communication_entry/appeal_communication_entry.py
import frappe  
from frappe.model.document import Document

class AppealCommunicationEntry(Document):
    def validate(self):
        # Ensure communication date is set
        if not self.communication_date:
            self.communication_date = frappe.utils.now()
