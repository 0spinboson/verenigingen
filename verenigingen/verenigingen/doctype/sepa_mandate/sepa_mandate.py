# Copyright (c) 2025, Your Name and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

function promptCreateMandate(frm) {
    if (!frm.doc.iban || !frm.doc.bank_account_name) {
        frappe.msgprint(__('Please enter both IBAN and Account Holder Name before creating a SEPA mandate'));
        return;
    }
    
    frappe.confirm(
        __('Would you like to create a new SEPA mandate for this bank account?'),
        function() {
            // Yes - show dialog for mandate type
            selectMandateType(frm);
        },
        function() {
            // No - do nothing
            frappe.show_alert(__('No SEPA mandate created. Payment by direct debit requires a mandate.'), 5);
        }
    );
}

// Function to select mandate type (one-off or continuous)
function selectMandateType(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Create SEPA Mandate'),
        fields: [
            {
                label: __('Mandate Type'),
                fieldname: 'mandate_type',
                fieldtype: 'Select',
                options: [
                    {label: __('One-off payment'), value: 'OOFF'},
                    {label: __('Recurring payments'), value: 'RCUR'}
                ],
                default: 'RCUR',
                reqd: 1
            },
            {
                label: __('Sign Date'),
                fieldname: 'sign_date',
                fieldtype: 'Date',
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: __('Used for'),
                fieldname: 'usage_section',
                fieldtype: 'Section Break'
            },
            {
                label: __('Memberships'),
                fieldname: 'used_for_memberships',
                fieldtype: 'Check',
                default: 1
            },
            {
                label: __('Donations'),
                fieldname: 'used_for_donations',
                fieldtype: 'Check',
                default: 0
            }
        ],
        primary_action_label: __('Create'),
        primary_action(values) {
            createSEPAMandate(frm, values);
            d.hide();
        }
    });
    
    d.show();
}

// Function to create SEPA mandate
function createSEPAMandate(frm, values) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.create_sepa_mandate_from_bank_details',
        args: {
            member: frm.doc.name,
            iban: frm.doc.iban,
            bic: frm.doc.bic || '',
            account_holder_name: frm.doc.bank_account_name,
            mandate_type: values.mandate_type,
            sign_date: values.sign_date,
            used_for_memberships: values.used_for_memberships,
            used_for_donations: values.used_for_donations
        },
        callback: function(r) {
            if (r.message) {
                // Add mandate to the table
                const new_row = frm.add_child('sepa_mandates');
                new_row.sepa_mandate = r.message;
                new_row.is_current = 1;
                frm.refresh_field('sepa_mandates');
                
                frappe.show_alert({
                    message: __('SEPA Mandate created successfully'),
                    indicator: 'green'
                }, 5);
                
                // Fetch mandate details to update the row
                frappe.db.get_doc('SEPA Mandate', r.message)
                    .then(mandate => {
                        frappe.model.set_value(new_row.doctype, new_row.name, 'mandate_reference', mandate.mandate_id);
                        frappe.model.set_value(new_row.doctype, new_row.name, 'status', mandate.status);
                        frappe.model.set_value(new_row.doctype, new_row.name, 'valid_from', mandate.sign_date);
                        frappe.model.set_value(new_row.doctype, new_row.name, 'valid_until', mandate.expiry_date);
                        frm.refresh_field('sepa_mandates');
                    });
            }
        }
    });
}

// Function to format IBAN
function formatIBAN(iban) {
    if (!iban) return '';
    
    // Remove spaces and convert to uppercase
    iban = iban.replace(/\s+/g, '').toUpperCase();
    
    // Format with spaces every 4 characters
    return iban.replace(/(.{4})/g, '$1 ').trim();
}

// Function to get IBAN from a mandate
function get_doc_mandate_iban(mandate_name) {
    // This is an async operation but we just want a simple check,
    // so we'll use the result when it comes back
    frappe.db.get_value('SEPA Mandate', mandate_name, 'iban')
        .then(r => {
            if (r && r.message) {
                return r.message.iban;
            }
            return '';
        });
}

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
