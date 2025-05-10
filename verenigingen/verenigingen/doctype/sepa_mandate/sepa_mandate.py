# Copyright (c) 2025, Your Name and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

class SEPAMandate(Document):
    def validate(self):
        self.validate_dates()
        self.validate_iban()
        self.set_status()
    
    def validate_dates(self):
        # Ensure sign date is not in the future
        if self.sign_date and getdate(self.sign_date) > getdate(today()):
            frappe.throw(_("Mandate sign date cannot be in the future"))
        
        # Ensure expiry date is after sign date
        if self.expiry_date and self.sign_date:
            if getdate(self.expiry_date) < getdate(self.sign_date):
                frappe.throw(_("Expiry date cannot be before sign date"))
    
    def validate_iban(self):
        # Basic IBAN validation (you might want to add more sophisticated validation)
        if self.iban:
            # Remove spaces and convert to uppercase
            iban = self.iban.replace(' ', '').upper()
            self.iban = iban
            
            # Basic length check (varies by country)
            if len(iban) < 15 or len(iban) > 34:
                frappe.throw(_("Invalid IBAN length"))
    
    def set_status(self):
        # Auto-set status based on dates
        if self.status not in ["Cancelled", "Suspended"]:
            if self.expiry_date and getdate(self.expiry_date) < getdate(today()):
                self.status = "Expired"
            elif not self.is_active:
                self.status = "Suspended"
            else:
                self.status = "Active"
    
    def on_update(self):
        # If this is the only active mandate for a member and used_for_memberships is true,
        # set it as default
        if self.member and self.status == "Active" and self.used_for_memberships:
            other_mandates = frappe.get_all(
                "SEPA Mandate",
                filters={
                    "member": self.member,
                    "status": "Active",
                    "name": ["!=", self.name]
                }
            )
            
            if not other_mandates:
                # This is the only active mandate, set as default
                member = frappe.get_doc("Member", self.member)
                member.default_sepa_mandate = self.name
                member.save(ignore_permissions=True)
