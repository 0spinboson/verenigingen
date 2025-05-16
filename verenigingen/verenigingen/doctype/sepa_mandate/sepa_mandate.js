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

# Function to get IBAN from a mandate
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
