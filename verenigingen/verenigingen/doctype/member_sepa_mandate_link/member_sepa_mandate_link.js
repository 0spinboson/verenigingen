// Copyright (c) 2025, Your Name and contributors
// For license information, please see license.txt

frappe.ui.form.on('Member SEPA Mandate Link', {
    sepa_mandate: function(frm, cdt, cdn) {
        // When a mandate is selected, fetch its details
        const row = locals[cdt][cdn];
        
        if (row.sepa_mandate) {
            frappe.db.get_value('SEPA Mandate', row.sepa_mandate, 
                ['mandate_id', 'status', 'sign_date', 'expiry_date'], 
                function(r) {
                    if (r) {
                        frappe.model.set_value(cdt, cdn, 'mandate_reference', r.mandate_id);
                        frappe.model.set_value(cdt, cdn, 'status', r.status);
                        frappe.model.set_value(cdt, cdn, 'valid_from', r.sign_date);
                        frappe.model.set_value(cdt, cdn, 'valid_until', r.expiry_date);
                    }
                }
            );
        }
    },
    
    is_default: function(frm, cdt, cdn) {
        // When setting a mandate as default, unset others
        const row = locals[cdt][cdn];
        
        if (row.is_default) {
            // Update parent's default_sepa_mandate field
            frm.set_value('default_sepa_mandate', row.sepa_mandate);
            
            // Unset default on other mandates
            frm.doc.sepa_mandates.forEach(function(mandate) {
                if (mandate.name !== cdn && mandate.is_default) {
                    frappe.model.set_value(mandate.doctype, mandate.name, 'is_default', 0);
                }
            });
        }
    }
});

// Also add handlers to the Member form for the SEPA mandates table
frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Add button to create new SEPA mandate
        if (frm.doc.name) {
            frm.fields_dict['sepa_mandates'].grid.add_custom_button(__('Create New Mandate'), 
                function() {
                    frappe.new_doc('SEPA Mandate', {
                        'member': frm.doc.name,
                        'member_name': frm.doc.full_name,
                        'account_holder_name': frm.doc.full_name
                    });
                }
            );
        }
    },
    
    default_sepa_mandate: function(frm) {
        // When default mandate is changed, update the table
        if (frm.doc.default_sepa_mandate) {
            let found = false;
            
            frm.doc.sepa_mandates.forEach(function(mandate) {
                if (mandate.sepa_mandate === frm.doc.default_sepa_mandate) {
                    frappe.model.set_value(mandate.doctype, mandate.name, 'is_default', 1);
                    found = true;
                } else if (mandate.is_default) {
                    frappe.model.set_value(mandate.doctype, mandate.name, 'is_default', 0);
                }
            });
            
            // If the selected default mandate is not in the table, add it
            if (!found && frm.doc.default_sepa_mandate) {
                const new_row = frm.add_child('sepa_mandates');
                new_row.sepa_mandate = frm.doc.default_sepa_mandate;
                new_row.is_default = 1;
                frm.refresh_field('sepa_mandates');
            }
        }
    }
});
