// Copyright (c) 2025, Your Organization and contributors
// For license information, please see license.txt

frappe.ui.form.on('Volunteer Team Member', {
    volunteer: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.volunteer) {
            // Fetch volunteer details
            frappe.db.get_doc("Volunteer", row.volunteer).then(doc => {
                frappe.model.set_value(cdt, cdn, 'volunteer_name', doc.volunteer_name);
            });
        }
    },
    
    role_type: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        var parent = frappe.get_doc(frm.doctype, frm.docname);
        
        // Set default role based on role type and team type
        if (parent && parent.team_type) {
            if (row.role_type === 'Team Leader') {
                var leader_title = get_leader_title(parent.team_type);
                frappe.model.set_value(cdt, cdn, 'role', leader_title);
            } else {
                var member_title = get_member_title(parent.team_type);
                frappe.model.set_value(cdt, cdn, 'role', member_title);
            }
        }
    },
    
    status: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        // If setting to inactive/completed, set end date if not already set
        if (row.status !== 'Active' && !row.to_date) {
            frappe.model.set_value(cdt, cdn, 'to_date', frappe.datetime.get_today());
        }
    }
});

// Helper functions

// Helper function to get leader title based on team type
function get_leader_title(team_type) {
    const leader_titles = {
        'Committee': 'Committee Chair',
        'Working Group': 'Working Group Lead',
        'Task Force': 'Task Force Lead',
        'Project Team': 'Project Manager',
        'Other': 'Team Leader'
    };
    
    return leader_titles[team_type] || 'Team Leader';
}

// Helper function to get member title based on team type
function get_member_title(team_type) {
    const member_titles = {
        'Committee': 'Committee Member',
        'Working Group': 'Working Group Member',
        'Task Force': 'Task Force Member',
        'Project Team': 'Project Team Member',
        'Other': 'Team Member'
    };
    
    return member_titles[team_type] || 'Team Member';
}
