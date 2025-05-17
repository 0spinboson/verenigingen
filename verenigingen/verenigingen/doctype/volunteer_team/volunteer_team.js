// Copyright (c) 2025, Your Organization and contributors
// For license information, please see license.txt

frappe.ui.form.on('Volunteer Team', {
    refresh: function(frm) {
        // Add button to view team members
        if (!frm.is_new()) {
            // Add button to view volunteers
            frm.add_custom_button(__('View Volunteers'), function() {
                // Get all volunteer links from team members
                var volunteers = frm.doc.team_members
                    .filter(m => m.volunteer)
                    .map(m => m.volunteer);
                
                if (volunteers.length) {
                    frappe.route_options = {
                        "name": ["in", volunteers]
                    };
                    frappe.set_route("List", "Volunteer");
                } else {
                    frappe.msgprint(__("No volunteers found in this team"));
                }
            }, __("View"));
            
            // Add button to add new team member
            frm.add_custom_button(__('Add Team Member'), function() {
                add_team_member(frm);
            }, __("Actions"));
        }
        
        // Add custom button for team members table
        if (frm.fields_dict['team_members']) {
            frm.fields_dict['team_members'].grid.add_custom_button(__('Add Member'), 
                function() {
                    add_team_member(frm);
                }
            );
        }
    },
    
    team_type: function(frm) {
        // When team type changes, update title in roles
        if (frm.doc.team_type) {
            const type_titles = {
                'Committee': 'Committee Member',
                'Working Group': 'Working Group Member',
                'Task Force': 'Task Force Member',
                'Project Team': 'Project Team Member',
                'Other': 'Team Member'
            };
            
            const leader_titles = {
                'Committee': 'Committee Chair',
                'Working Group': 'Working Group Lead',
                'Task Force': 'Task Force Lead',
                'Project Team': 'Project Manager',
                'Other': 'Team Leader'
            };
            
            // Update existing member roles if they match the default pattern
            if (frm.doc.team_members && frm.doc.team_members.length) {
                frm.doc.team_members.forEach(function(member) {
                    // Only update if role follows the previous pattern
                    if (member.role_type === 'Team Leader' && 
                        member.role.match(/Chair|Lead|Leader|Manager/)) {
                        frappe.model.set_value(member.doctype, member.name, 'role', leader_titles[frm.doc.team_type]);
                    } else if (member.role_type === 'Team Member' && 
                               member.role.match(/Member/)) {
                        frappe.model.set_value(member.doctype, member.name, 'role', type_titles[frm.doc.team_type]);
                    }
                });
                
                frm.refresh_field('team_members');
            }
        }
    }
});

// Handler for Volunteer Team Member child table
frappe.ui.form.on('Volunteer Team Member', {
    volunteer: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.volunteer) {
            // Fetch volunteer details
            frappe.db.get_doc("Volunteer", row.volunteer).then(doc => {
                frappe.model.set_value(cdt, cdn, 'volunteer_name', doc.volunteer_name);
                
                // If no role is set, set default based on team type
                if (!row.role) {
                    const default_role = row.role_type === 'Team Leader' ? 
                        get_leader_title(frm.doc.team_type) : 
                        get_member_title(frm.doc.team_type);
                    
                    frappe.model.set_value(cdt, cdn, 'role', default_role);
                }
            });
        }
    },
    
    role_type: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // Set default role based on role type and team type
        if (row.role_type === 'Team Leader') {
            frappe.model.set_value(cdt, cdn, 'role', get_leader_title(frm.doc.team_type));
        } else {
            frappe.model.set_value(cdt, cdn, 'role', get_member_title(frm.doc.team_type));
        }
    },
    
    status: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        // If setting to inactive/completed, set end date if not already set
        if (row.status !== 'Active' && !row.to_date) {
            frappe.model.set_value(cdt, cdn, 'to_date', frappe.datetime.get_today());
        }
    }
});

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

// Function to add a team member
function add_team_member(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Add Team Member'),
        fields: [
            {
                fieldname: 'volunteer',
                fieldtype: 'Link',
                label: __('Volunteer'),
                options: 'Volunteer',
                reqd: 1
            },
            {
                fieldname: 'role_type',
                fieldtype: 'Select',
                label: __('Role Type'),
                options: 'Team Leader\nTeam Member',
                default: 'Team Member',
                reqd: 1
            },
            {
                fieldname: 'role',
                fieldtype: 'Data',
                label: __('Role'),
                depends_on: 'volunteer'
            },
            {
                fieldname: 'dates_section',
                fieldtype: 'Section Break',
                label: __('Dates')
            },
            {
                fieldname: 'from_date',
                fieldtype: 'Date',
                label: __('From Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'to_date',
                fieldtype: 'Date',
                label: __('To Date')
            },
            {
                fieldname: 'notes',
                fieldtype: 'Small Text',
                label: __('Notes')
            }
        ],
        primary_action_label: __('Add'),
        primary_action: function() {
            const values = d.get_values();
            
            // If role is empty, set default based on team type and role type
            if (!values.role) {
                values.role = values.role_type === 'Team Leader' ? 
                    get_leader_title(frm.doc.team_type) : 
                    get_member_title(frm.doc.team_type);
            }
            
            // Add to team members
            const child = frm.add_child('team_members');
            Object.assign(child, {
                volunteer: values.volunteer,
                role_type: values.role_type,
                role: values.role,
                from_date: values.from_date,
                to_date: values.to_date,
                notes: values.notes,
                status: 'Active'
            });
            
            // Fetch volunteer name
            frappe.db.get_value('Volunteer', values.volunteer, 'volunteer_name', function(r) {
                if (r && r.volunteer_name) {
                    frappe.model.set_value(child.doctype, child.name, 'volunteer_name', r.volunteer_name);
                }
                
                frm.refresh_field('team_members');
                frm.save();
                d.hide();
            });
        }
    });
    
    d.show();
    
    // Update default role when volunteer or role type changes
    d.fields_dict.volunteer.df.onchange = function() {
        const role_type = d.get_value('role_type');
        const default_role = role_type === 'Team Leader' ? 
            get_leader_title(frm.doc.team_type) : 
            get_member_title(frm.doc.team_type);
        
        d.set_value('role', default_role);
    };
    
    d.fields_dict.role_type.df.onchange = function() {
        const role_type = d.get_value('role_type');
        const default_role = role_type === 'Team Leader' ? 
            get_leader_title(frm.doc.team_type) : 
            get_member_title(frm.doc.team_type);
        
        d.set_value('role', default_role);
    };
}
