// Copyright (c) 2025, Your Name and contributors
// For license information, please see license.txt

frappe.ui.form.on('SEPA Mandate', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.status === 'Active' && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Suspend'), function() {
                frm.set_value('status', 'Suspended');
                frm.set_value('is_active', 0);
                frm.save();
            }, __('Actions'));
        }
        
        if (frm.doc.status === 'Suspended' && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Reactivate'), function() {
                frm.set_value('status', 'Active');
                frm.set_value('is_active', 1);
                frm.save();
            }, __('Actions'));
        }
        
        // Add button to view related member
        if (frm.doc.member) {
            frm.add_custom_button(__('Member'), function() {
                frappe.set_route('Form', 'Member', frm.doc.member);
            }, __('View'));
        }
    },
    
    sign_date: function(frm) {
        // Validate sign date
        if (frm.doc.sign_date) {
            const today = frappe.datetime.get_today();
            if (frappe.datetime.str_to_obj(frm.doc.sign_date) > frappe.datetime.str_to_obj(today)) {
                frappe.msgprint(__('Sign date cannot be in the future'));
                frm.set_value('sign_date', today);
            }
        }
    },
    
    iban: function(frm) {
        // Format IBAN
        if (frm.doc.iban) {
            // Remove spaces and convert to uppercase
            let iban = frm.doc.iban.replace(/\s/g, '').toUpperCase();
            // Add spaces every 4 characters for readability
            iban = iban.replace(/(.{4})/g, '$1 ').trim();
            frm.set_value('iban', iban);
        }
    }
});
