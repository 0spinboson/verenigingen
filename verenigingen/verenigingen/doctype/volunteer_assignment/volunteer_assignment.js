// Copyright (c) 2025, Your Organization and contributors
// For license information, please see license.txt

frappe.ui.form.on('Volunteer Assignment', {
    // Since this is a child table DocType, we're adding more functionality
    // directly in the parent form's JS file (volunteer.js)
    
    reference_doctype: function(frm, cdt, cdn) {
        // When reference doctype changes, clear the reference name
        frappe.model.set_value(cdt, cdn, 'reference_name', '');
    }
});
