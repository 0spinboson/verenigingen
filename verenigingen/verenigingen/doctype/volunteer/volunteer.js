// Copyright (c) 2025, Your Organization and contributors
// For license information, please see license.txt

frappe.ui.form.on('Volunteer', {
    validate: function(frm) {
        // Ensure data is properly saved in child tables
        if(frm.doc.active_assignments && frm.doc.active_assignments.length > 0) {
            frm.doc.active_assignments.forEach(function(row, idx) {
                if(row.reference_doctype && !row.reference_name) {
                    frappe.msgprint(__("Please select reference name for row {0} in assignments", [idx+1]));
                    frappe.validated = false;
                }
            });
        }
    },
    
    after_save: function(frm) {
        // Explicitly refresh grid to ensure data is shown
        frm.refresh_field('active_assignments');
        frm.refresh_field('assignment_history');
        frm.refresh_field('skills_and_qualifications');
    }
    refresh: function(frm) {
        // Set up dynamic link for address and contact
        frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Volunteer'};
        
        // Toggle address and contact display
        frm.toggle_display(['address_html', 'contact_html'], !frm.doc.__islocal);

        // Load address and contact information
        if(!frm.doc.__islocal) {
            frappe.contacts.render_address_and_contact(frm);
            
            // Add button to view member record
            if(frm.doc.member) {
                frm.add_custom_button(__('View Member'), function() {
                    frappe.set_route('Form', 'Member', frm.doc.member);
                }, __('Links'));
            }
            
            // Add buttons to view chapter and team references
            add_reference_buttons(frm);
            
            // Add button to view volunteer assignments timeline
            frm.add_custom_button(__('View Timeline'), function() {
                show_volunteer_timeline(frm);
            }, __('View'));
            
            // Add button to create new volunteer assignment
            frm.add_custom_button(__('Add Assignment'), function() {
                create_new_assignment(frm);
            }, __('Actions'));
            
            // Add button to generate volunteer report
            frm.add_custom_button(__('Volunteer Report'), function() {
                generate_volunteer_report(frm);
            }, __('View'));
        } else {
            frappe.contacts.clear_address_and_contact(frm);
        }
        
        // Add custom button for grid views
        if(frm.fields_dict.active_assignments) {
            frm.fields_dict.active_assignments.grid.add_custom_button(__('End Assignment'), 
                function() {
                    end_selected_assignment(frm);
                }
            );
        }
        
        // Add skills grid custom button
        if(frm.fields_dict.skills_and_qualifications) {
            frm.fields_dict.skills_and_qualifications.grid.add_custom_button(__('Add Skill'), 
                function() {
                    add_new_skill(frm);
                }
            );
        }
        
        // Set up filters for reference_doctype in assignment grid
        frm.set_query("reference_doctype", "active_assignments", function() {
            return {
                filters: {
                    "name": ["in", ["Chapter", "Volunteer Team", "Event", "Commission"]]
                }
            };
        });
        
        // Set up filters for reference_name in assignment grid
        frm.set_query("reference_name", "active_assignments", function(doc, cdt, cdn) {
            var child = locals[cdt][cdn];
            
            if(!child.reference_doctype) {
                return {
                    filters: { "name": ["=", ""] } // No matches if no doctype selected
                };
            }
            
            var filters = {};
            
            // Apply filters based on assignment type and reference doctype
            if(child.assignment_type === "Board Position") {
                if(child.reference_doctype === "Chapter") {
                    filters["published"] = 1;
                }
            }
            else if(child.assignment_type === "Team" || child.assignment_type === "Committee") {
                if(child.reference_doctype === "Volunteer Team") {
                    filters["status"] = "Active";
                    
                    // Optionally filter by team type for committees
                    if(child.assignment_type === "Committee") {
                        filters["team_type"] = "Committee";
                    }
                }
            }
            else if(child.assignment_type === "Event") {
                if(child.reference_doctype === "Event") {
                    // Only show future or current events
                    var today = frappe.datetime.get_today();
                    filters["end_date"] = [">=", today];
                }
            }
            
            return {
                filters: filters
            };
        });

        // Also set up filters for the history section
        frm.set_query("reference_doctype", "assignment_history", function() {
            return {
                filters: {
                    "name": ["in", ["Chapter", "Volunteer Team", "Event", "Commission"]]
                }
            };
        });
        
        frm.set_query("reference_name", "assignment_history", function(doc, cdt, cdn) {
            var child = locals[cdt][cdn];
            
            if(!child.reference_doctype) {
                return { filters: { "name": ["=", ""] } };
            }
            
            return { filters: {} }; // No filters for history items, as they may be inactive/archived
        });
    },
    
    member: function(frm) {
        // When member is selected, fetch relevant information
        if(frm.doc.member) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Member',
                    name: frm.doc.member
                },
                callback: function(response) {
                    if(response.message) {
                        var member = response.message;
                        
                        // If this is a new record, update fields from member
                        if(frm.doc.__islocal) {
                            frm.set_value('volunteer_name', member.full_name);
                            
                            // Generate organization email based on full name
                            frappe.call({
                                method: 'frappe.client.get_value',
                                args: {
                                    doctype: 'Verenigingen Settings',
                                    fieldname: 'organization_email_domain'
                                },
                                callback: function(r) {
                                    // Default domain if not set
                                    const domain = r.message && r.message.organization_email_domain 
                                        ? r.message.organization_email_domain 
                                        : 'example.org';
                                    
                                    // Generate organization email based on full name
                                    // Replace spaces with dots and convert to lowercase
                                    const nameForEmail = member.full_name 
                                        ? member.full_name.replace(/\s+/g, '.').toLowerCase()
                                        : '';
                                    
                                    // Construct organization email
                                    const orgEmail = nameForEmail ? `${nameForEmail}@${domain}` : '';
                                    
                                    if(orgEmail) {
                                        frm.set_value('email', orgEmail);
                                    }
                                }
                            });
                        }
                        
                        // Check if member is a board member
                        frappe.call({
                            method: 'verenigingen.verenigingen.doctype.member.member.get_board_memberships',
                            args: {
                                member_name: frm.doc.member
                            },
                            callback: function(r) {
                                if(r.message && r.message.length) {
                                    // If member has board memberships, suggest adding them as assignments
                                    frappe.confirm(
                                        __('This member has {0} board position(s). Would you like to add them as volunteer assignments?', [r.message.length]),
                                        function() {
                                            // Yes - add board positions as assignments
                                            add_board_positions_as_assignments(frm, r.message);
                                        }
                                    );
                                }
                            }
                        });
                    }
                }
            });
        }
    }
});

// Functions for Volunteer Assignment
frappe.ui.form.on('Volunteer Assignment', {
    form_render: function(frm, cdt, cdn) {
        // Customize form rendering
    },
    
    assignment_type: function(frm, cdt, cdn) {
        // Handle changes to assignment type
        var assignment = locals[cdt][cdn];
        
        if(assignment.assignment_type === 'Board Position') {
            // Set reference to Chapter
            frappe.model.set_value(cdt, cdn, 'reference_doctype', 'Chapter');
        } else if(assignment.assignment_type === 'Team') {
            // Set reference to Volunteer Team
            frappe.model.set_value(cdt, cdn, 'reference_doctype', 'Volunteer Team');
        } else if(assignment.assignment_type === 'Event') {
            // Set reference to Event
            frappe.model.set_value(cdt, cdn, 'reference_doctype', 'Event');
        } else if(assignment.assignment_type === 'Committee') {
            // Set reference to Volunteer Team with Committee filter
            frappe.model.set_value(cdt, cdn, 'reference_doctype', 'Volunteer Team');
        } else if(assignment.assignment_type === 'Commission') {
            // Set reference to Commission
            frappe.model.set_value(cdt, cdn, 'reference_doctype', 'Commission');
        }
        
        // Refresh the field to update UI
        frm.refresh_field('active_assignments');
    },
    
    reference_doctype: function(frm, cdt, cdn) {
        // When reference doctype changes, clear the reference name
        frappe.model.set_value(cdt, cdn, 'reference_name', '');
        
        // Refresh the parent form to update UI and apply filters
        frm.refresh_field('active_assignments');
        
        // Force a re-query of the reference_name field to apply the latest filters
        var child = locals[cdt][cdn];
        if(child.reference_doctype) {
            setTimeout(function() {
                // This forces the dynamic link to refresh its options
                frm.fields_dict.active_assignments.grid.grid_rows_by_docname[cdn].refresh_field('reference_name');
            }, 300);
        }
    }
});

// Helper functions for volunteer management

function add_reference_buttons(frm) {
    // Add buttons to view related records
    var added_refs = {};
    
    // Add buttons for active assignments
    if(frm.doc.active_assignments) {
        frm.doc.active_assignments.forEach(function(assignment) {
            if(assignment.reference_doctype && assignment.reference_name) {
                var ref_key = assignment.reference_doctype + '::' + assignment.reference_name;
                
                if(!added_refs[ref_key]) {
                    frm.add_custom_button(__('{0}: {1}', [assignment.assignment_type, assignment.reference_name]), function() {
                        frappe.set_route('Form', assignment.reference_doctype, assignment.reference_name);
                    }, __('View References'));
                    
                    added_refs[ref_key] = true;
                }
            }
        });
    }
}

function show_volunteer_timeline(frm) {
    // Display a timeline visualization of volunteer history
    frappe.call({
        method: 'get_volunteer_history',
        doc: frm.doc,
        callback: function(r) {
            if(r.message) {
                var history = r.message;
                
                // Create a formatted HTML timeline
                var html = '<div class="timeline-view">';
                html += '<h4>' + __('Volunteer History Timeline') + '</h4>';
                html += '<div class="timeline-items">';
                
                history.forEach(function(item) {
                    var status_color = item.is_active ? 'green' : 'grey';
                    if(item.status === 'Cancelled') status_color = 'red';
                    
                    html += '<div class="timeline-item">';
                    html += '<div class="timeline-dot" style="background-color: var(--' + status_color + ');"></div>';
                    html += '<div class="timeline-content">';
                    html += '<div class="timeline-title">' + item.role + ' (' + item.assignment_type + ')</div>';
                    html += '<div class="timeline-reference">' + (item.reference || '') + '</div>';
                    html += '<div class="timeline-dates">' + frappe.datetime.str_to_user(item.start_date) + 
                           (item.end_date ? ' to ' + frappe.datetime.str_to_user(item.end_date) : ' to Present') + '</div>';
                    html += '<div class="timeline-status"><span class="indicator ' + status_color + '">' + 
                           (item.is_active ? 'Active' : item.status) + '</span></div>';
                    html += '</div>'; // timeline-content
                    html += '</div>'; // timeline-item
                });
                
                html += '</div>'; // timeline-items
                html += '</div>'; // timeline-view
                
                // Show the timeline in a dialog
                var d = new frappe.ui.Dialog({
                    title: __('Volunteer History for {0}', [frm.doc.volunteer_name]),
                    fields: [{
                        fieldtype: 'HTML',
                        options: html
                    }],
                    primary_action_label: __('Close'),
                    primary_action: function() {
                        d.hide();
                    }
                });
                
                d.show();
                
                // Add some custom CSS for the timeline
                d.$wrapper.find('.timeline-view').css({
                    'max-height': '400px',
                    'overflow-y': 'auto',
                    'padding': '10px'
                });
                
                d.$wrapper.find('.timeline-items').css({
                    'position': 'relative',
                    'border-left': '2px solid var(--gray-400)',
                    'margin-left': '10px',
                    'padding-left': '20px'
                });
                
                d.$wrapper.find('.timeline-item').css({
                    'margin-bottom': '20px',
                    'position': 'relative'
                });
                
                d.$wrapper.find('.timeline-dot').css({
                    'width': '12px',
                    'height': '12px',
                    'border-radius': '50%',
                    'position': 'absolute',
                    'left': '-27px',
                    'top': '5px'
                });
                
                d.$wrapper.find('.timeline-title').css({
                    'font-weight': 'bold',
                    'font-size': '14px'
                });
                
                d.$wrapper.find('.timeline-reference').css({
                    'color': 'var(--text-muted)',
                    'font-size': '12px'
                });
                
                d.$wrapper.find('.timeline-dates').css({
                    'margin-top': '5px',
                    'font-size': '12px'
                });
            }
        }
    });
}

function create_new_assignment(frm) {
    // Dialog to create a new volunteer assignment
    var d = new frappe.ui.Dialog({
        title: __('Add New Volunteer Assignment'),
        fields: [
            {
                fieldname: 'assignment_type',
                fieldtype: 'Select',
                label: __('Assignment Type'),
                options: 'Board Position\nCommittee\nTeam\nProject\nEvent\nCommission\nOther',
                reqd: 1,
                onchange: function() {
                    var assignment_type = d.get_value('assignment_type');
                    
                    // Change reference doctype based on assignment type
                    var ref_doctype_field = d.fields_dict.reference_doctype;
                    
                    if(assignment_type === 'Board Position') {
                        ref_doctype_field.set_value('Chapter');
                    } else if(assignment_type === 'Team') {
                        ref_doctype_field.set_value('Volunteer Team');
                    } else if(assignment_type === 'Committee') {
                        ref_doctype_field.set_value('Volunteer Team');
                    } else if(assignment_type === 'Event') {
                        ref_doctype_field.set_value('Event');
                    } else if(assignment_type === 'Commission') {
                        ref_doctype_field.set_value('Commission');
                    } else {
                        ref_doctype_field.set_value('');
                    }
                }
            },
            {
                fieldname: 'reference_doctype',
                fieldtype: 'Link',
                label: __('Related To'),
                options: 'DocType',
                get_query: function() {
                    return {
                        filters: {
                            "name": ["in", ["Chapter", "Volunteer Team", "Event", "Commission"]]
                        }
                    };
                }
            },
            {
                fieldname: 'reference_name',
                fieldtype: 'Dynamic Link',
                label: __('Reference Name'),
                options: 'reference_doctype',
                get_query: function() {
                    var assignment_type = d.get_value('assignment_type');
                    var reference_doctype = d.get_value('reference_doctype');
                    
                    var filters = {};
                    
                    if(assignment_type === 'Board Position' && reference_doctype === 'Chapter') {
                        filters["published"] = 1;
                    }
                    else if((assignment_type === 'Team' || assignment_type === 'Committee') && 
                           reference_doctype === 'Volunteer Team') {
                        filters["status"] = "Active";
                        
                        if(assignment_type === 'Committee') {
                            filters["team_type"] = "Committee";
                        }
                    }
                    
                    return { filters: filters };
                }
            },
            {
                fieldname: 'role',
                fieldtype: 'Data',
                label: __('Role/Position'),
                reqd: 1
            },
            {
                fieldname: 'dates_section',
                fieldtype: 'Section Break',
                label: __('Dates')
            },
            {
                fieldname: 'start_date',
                fieldtype: 'Date',
                label: __('Start Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'end_date',
                fieldtype: 'Date',
                label: __('End Date')
            },
            {
                fieldname: 'details_section',
                fieldtype: 'Section Break',
                label: __('Additional Details')
            },
            {
                fieldname: 'estimated_hours',
                fieldtype: 'Float',
                label: __('Estimated Hours')
            },
            {
                fieldname: 'notes',
                fieldtype: 'Small Text',
                label: __('Notes')
            }
        ],
        primary_action_label: __('Add'),
        primary_action: function() {
            var values = d.get_values();
            
            // Add assignment to the grid
            var child = frm.add_child('active_assignments');
            $.extend(child, values);
            
            // Refresh the grid
            frm.refresh_field('active_assignments');
            
            // Save the document
            frm.save();
            
            d.hide();
        }
    });
    
    d.show();
}

function end_selected_assignment(frm) {
    // End a selected assignment from the grid
    var selected = frm.fields_dict.active_assignments.grid.get_selected();
    
    if(!selected.length) {
        frappe.msgprint(__('Please select an assignment to end'));
        return;
    }
    
    // Get the selected assignment
    var idx = selected[0];
    var assignment = frm.doc.active_assignments[idx - 1];
    
    var d = new frappe.ui.Dialog({
        title: __('End Assignment'),
        fields: [
            {
                fieldname: 'end_date',
                fieldtype: 'Date',
                label: __('End Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'accomplishments',
                fieldtype: 'Small Text',
                label: __('Accomplishments')
            },
            {
                fieldname: 'notes',
                fieldtype: 'Small Text',
                label: __('Notes')
            }
        ],
        primary_action_label: __('End Assignment'),
        primary_action: function() {
            var values = d.get_values();
            
            // Call the method to end the assignment
            frappe.call({
                method: 'end_assignment',
                doc: frm.doc,
                args: {
                    assignment_idx: idx,
                    end_date: values.end_date,
                    notes: values.notes
                },
                callback: function(r) {
                    if(r.message) {
                        frappe.show_alert({
                            message: __('Assignment ended successfully'),
                            indicator: 'green'
                        });
                        frm.refresh();
                    }
                }
            });
            
            d.hide();
        }
    });
    
    d.show();
}

function add_new_skill(frm) {
    // Dialog to add a new skill
    var d = new frappe.ui.Dialog({
        title: __('Add New Skill'),
        fields: [
            {
                fieldname: 'skill_category',
                fieldtype: 'Select',
                label: __('Skill Category'),
                options: 'Technical\nOrganizational\nCommunication\nLeadership\nFinancial\nEvent Planning\nOther',
                reqd: 1
            },
            {
                fieldname: 'volunteer_skill',
                fieldtype: 'Data',
                label: __('Skill'),
                reqd: 1
            },
            {
                fieldname: 'proficiency_level',
                fieldtype: 'Select',
                label: __('Proficiency Level'),
                options: '1 - Beginner\n2 - Basic\n3 - Intermediate\n4 - Advanced\n5 - Expert',
                default: '3 - Intermediate'
            },
            {
                fieldname: 'experience_years',
                fieldtype: 'Int',
                label: __('Years of Experience')
            },
            {
                fieldname: 'certifications',
                fieldtype: 'Small Text',
                label: __('Relevant Certifications')
            }
        ],
        primary_action_label: __('Add'),
        primary_action: function() {
            var values = d.get_values();
            
            // Add skill to the grid
            var child = frm.add_child('skills_and_qualifications');
            $.extend(child, values);
            
            // Refresh the grid
            frm.refresh_field('skills_and_qualifications');
            
            d.hide();
        }
    });
    
    d.show();
}

function add_board_positions_as_assignments(frm, board_memberships) {
    // Add board positions as volunteer assignments
    if(!board_memberships || !board_memberships.length) return;
    
    // Add each board membership as an assignment
    var count = 0;
    
    // Check which positions are already added
    var existing_positions = {};
    if(frm.doc.active_assignments) {
        frm.doc.active_assignments.forEach(function(assignment) {
            if(assignment.assignment_type === 'Board Position' && 
               assignment.reference_doctype === 'Chapter') {
                existing_positions[assignment.reference_name + '::' + assignment.role] = true;
            }
        });
    }
    
    // Add new positions
    board_memberships.forEach(function(board) {
        var position_key = board.parent + '::' + board.chapter_role;
        
        if(!existing_positions[position_key]) {
            var child = frm.add_child('active_assignments');
            frappe.model.set_value(child.doctype, child.name, 'assignment_type', 'Board Position');
            frappe.model.set_value(child.doctype, child.name, 'reference_doctype', 'Chapter');
            frappe.model.set_value(child.doctype, child.name, 'reference_name', board.parent);
            frappe.model.set_value(child.doctype, child.name, 'role', board.chapter_role);
            frappe.model.set_value(child.doctype, child.name, 'start_date', frappe.datetime.get_today());
            frappe.model.set_value(child.doctype, child.name, 'status', 'Active');
            
            count++;
        }
    });
    
    if(count > 0) {
        // Refresh the form
        frm.refresh_field('active_assignments');
        
        frappe.show_alert({
            message: __('Added {0} board positions as volunteer assignments', [count]),
            indicator: 'green'
        });
        
        frm.dirty();
    } else {
        frappe.show_alert({
            message: __('All board positions are already in the volunteer assignments'),
            indicator: 'blue'
        });
    }
}

function generate_volunteer_report(frm) {
    // Generate a comprehensive volunteer report
    frappe.call({
        method: 'get_skills_by_category',
        doc: frm.doc,
        callback: function(r) {
            if(r.message) {
                var skills_by_category = r.message;
                
                // Create HTML for the report
                var html = '<div class="volunteer-report">';
                html += '<h3>' + __('Volunteer Report for {0}', [frm.doc.volunteer_name]) + '</h3>';
                
                // Basic information section
                html += '<div class="report-section"><h4>' + __('Basic Information') + '</h4>';
                html += '<table class="table table-condensed">';
                html += '<tr><td><strong>' + __('Name') + '</strong></td><td>' + frm.doc.volunteer_name + '</td></tr>';
                html += '<tr><td><strong>' + __('Status') + '</strong></td><td>' + frm.doc.status + '</td></tr>';
                html += '<tr><td><strong>' + __('Volunteer Since') + '</strong></td><td>' + 
                       frappe.datetime.str_to_user(frm.doc.start_date) + '</td></tr>';
                html += '<tr><td><strong>' + __('Commitment Level') + '</strong></td><td>' + 
                       (frm.doc.commitment_level || 'Not specified') + '</td></tr>';
                html += '<tr><td><strong>' + __('Experience Level') + '</strong></td><td>' + 
                       (frm.doc.experience_level || 'Not specified') + '</td></tr>';
                html += '<tr><td><strong>' + __('Work Style') + '</strong></td><td>' + 
                       (frm.doc.preferred_work_style || 'Not specified') + '</td></tr>';
                html += '</table></div>';
                
                // Current assignments section
                html += '<div class="report-section"><h4>' + __('Current Assignments') + '</h4>';
                
                if(frm.doc.active_assignments && frm.doc.active_assignments.length) {
                    html += '<table class="table table-condensed">';
                    html += '<thead><tr><th>' + __('Role') + '</th><th>' + __('Type') + '</th><th>' + 
                           __('Reference') + '</th><th>' + __('Since') + '</th></tr></thead>';
                    html += '<tbody>';
                    
                    frm.doc.active_assignments.forEach(function(assignment) {
                        html += '<tr>';
                        html += '<td>' + assignment.role + '</td>';
                        html += '<td>' + assignment.assignment_type + '</td>';
                        html += '<td>' + (assignment.reference_name || '') + '</td>';
                        html += '<td>' + frappe.datetime.str_to_user(assignment.start_date) + '</td>';
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table>';
                } else {
                    html += '<p>' + __('No active assignments') + '</p>';
                }
                
                html += '</div>';
                
                // Skills section
                html += '<div class="report-section"><h4>' + __('Skills and Qualifications') + '</h4>';
                
                if(Object.keys(skills_by_category).length) {
                    html += '<div class="row">';
                    
                    for(var category in skills_by_category) {
                        html += '<div class="col-sm-6 col-md-4">';
                        html += '<div class="skill-category"><h5>' + category + '</h5>';
                        html += '<ul class="list-unstyled">';
                        
                        skills_by_category[category].forEach(function(skill) {
                            html += '<li><span class="skill-name">' + skill.skill + '</span> <span class="skill-level">' + 
                                   skill.level + '</span></li>';
                        });
                        
                        html += '</ul></div></div>';
                    }
                    
                    html += '</div>';
                } else {
                    html += '<p>' + __('No skills recorded') + '</p>';
                }
                
                html += '</div>';
                
                // Areas of interest section
                if(frm.doc.interests && frm.doc.interests.length) {
                    html += '<div class="report-section"><h4>' + __('Areas of Interest') + '</h4>';
                    html += '<ul class="list-inline">';
                    
                    frm.doc.interests.forEach(function(interest) {
                        html += '<li class="interest-tag">' + interest.interest_area + '</li>';
                    });
                    
                    html += '</ul></div>';
                }
                
                // Footer
                html += '<div class="report-footer text-muted small">' + 
                       __('Report generated on {0}', [frappe.datetime.now_date()]) + '</div>';
                
                html += '</div>'; // volunteer-report
                
                // Show the report in a dialog
                var d = new frappe.ui.Dialog({
                    title: __('Volunteer Report'),
                    fields: [{
                        fieldtype: 'HTML',
                        options: html
                    }],
                    primary_action_label: __('Print'),
                    primary_action: function() {
                        // Print the report
                        var w = window.open();
                        w.document.write('<html><head><title>' + 
                                        __('Volunteer Report - {0}', [frm.doc.volunteer_name]) + 
                                        '</title>');
                        w.document.write('<style>');
                        w.document.write('body { font-family: Arial, sans-serif; margin: 20px; }');
                        w.document.write('.volunteer-report { max-width: 800px; margin: 0 auto; }');
                        w.document.write('.report-section { margin-bottom: 20px; }');
                        w.document.write('.skill-category { border: 1px solid #ddd; padding: 10px; margin-bottom: 10px; }');
                        w.document.write('.skill-level { background-color: #f0f0f0; padding: 2px 6px; border-radius: 10px; font-size: 0.9em; }');
                        w.document.write('.interest-tag { display: inline-block; background-color: #f0f0f0; padding: 3px 8px; margin: 3px; border-radius: 10px; }');
                        w.document.write('.report-footer { margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }');
                        w.document.write('table { width: 100%; border-collapse: collapse; }');
                        w.document.write('th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }');
                        w.document.write('</style></head><body>');
                        w.document.write(html);
                        w.document.write('</body></html>');
                        w.print();
                        w.close();
                    },
                    secondary_action_label: __('Close'),
                    secondary_action: function() {
                        d.hide();
                    }
                });
                
                d.show();
                
                // Add some custom CSS for the report
                d.$wrapper.find('.volunteer-report').css({
                    'max-height': '500px',
                    'overflow-y': 'auto',
                    'padding': '10px'
                });
                
                d.$wrapper.find('.report-section').css({
                    'margin-bottom': '25px',
                    'border-bottom': '1px solid var(--gray-200)',
                    'padding-bottom': '15px'
                });
                
                d.$wrapper.find('.skill-category').css({
                    'border': '1px solid var(--gray-200)',
                    'border-radius': '4px',
                    'padding': '10px',
                    'margin-bottom': '10px'
                });
                
                d.$wrapper.find('.skill-level').css({
                    'background-color': 'var(--gray-100)',
                    'padding': '2px 6px',
                    'border-radius': '10px',
                    'font-size': '0.9em'
                });
                
                d.$wrapper.find('.interest-tag').css({
                    'display': 'inline-block',
                    'background-color': 'var(--gray-100)',
                    'padding': '3px 8px',
                    'margin': '3px',
                    'border-radius': '10px'
                });
            }
        }
    });
}
