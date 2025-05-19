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
        self.sync_status_and_active_flag()
        
    def before_save(self):
        """This is called just before saving the document"""
        self.sync_status_and_active_flag()
        
    def sync_status_and_active_flag(self):
        """Ensure status and is_active flag are in sync"""
        # First sync the is_active flag based on status
        if self.status == "Active" and not self.is_active:
            self.is_active = 1
        elif self.status in ["Suspended", "Cancelled", "Expired"] and self.is_active:
            self.is_active = 0
        
        # Then sync the status based on is_active flag
        # But don't override these terminal/special states
        if self.status not in ["Cancelled", "Expired", "Draft"]:
            if self.is_active and self.status != "Active":
                self.status = "Active"
            elif not self.is_active and self.status != "Suspended":
                self.status = "Suspended"
        
        # Finally, check date-based status (this overrides previous steps)
        if self.expiry_date and getdate(self.expiry_date) < getdate(today()):
            self.status = "Expired"
            self.is_active = 0
    
    def validate_dates(self):
        # Ensure sign date is not in the future
        if self.sign_date and getdate(self.sign_date) > getdate(today()):
            frappe.throw(_("Mandate sign date cannot be in the future"))
        
        # Ensure expiry date is after sign date
        if self.expiry_date and self.sign_date:
            if getdate(self.expiry_date) < getdate(self.sign_date):
                frappe.throw(_("Expiry date cannot be before sign date"))
    
    def validate_iban(self):
        # Basic IBAN validation
        if self.iban:
            # Remove spaces and convert to uppercase
            iban = self.iban.replace(' ', '').upper()
            self.iban = iban
            
            # Basic length check (varies by country)
            if len(iban) < 15 or len(iban) > 34:
                frappe.throw(_("Invalid IBAN length"))
    
    def on_update(self):
        """
        When a mandate is updated to Active status and is used for memberships,
        check if it should be set as the current mandate
        """
        if self.member and self.status == "Active" and self.is_active and self.used_for_memberships:
            # Find if this mandate is already linked to the member
            member = frappe.get_doc("Member", self.member)
            
            # Check if this mandate is in the member's mandate list
            mandate_exists = False
            is_already_current = False
            
            for mandate_link in member.sepa_mandates:
                if mandate_link.sepa_mandate == self.name:
                    mandate_exists = True
                    if mandate_link.is_current:
                        is_already_current = True
                    break
            
            # If mandate isn't linked, add it
            if not mandate_exists:
                # Check if there are other active mandates
                other_active_mandates = any(
                    link.status == "Active" and link.is_current 
                    for link in member.sepa_mandates
                )
                
                # Add this mandate as the current one if no other active current mandates
                member.append("sepa_mandates", {
                    "sepa_mandate": self.name,
                    "is_current": not other_active_mandates
                })
                member.save(ignore_permissions=True)
            
            # If this is the only active mandate, set it as current
            elif not is_already_current:
                other_mandates = frappe.get_all(
                    "SEPA Mandate",
                    filters={
                        "member": self.member,
                        "status": "Active",
                        "is_active": 1,
                        "name": ["!=", self.name]
                    }
                )
                
                if not other_mandates:
                    # Set this as the current mandate in the member's mandate list
                    for mandate_link in member.sepa_mandates:
                        if mandate_link.sepa_mandate == self.name:
                            mandate_link.is_current = 1
                        else:
                            mandate_link.is_current = 0
                    
                    member.save(ignore_permissions=True)
