// For license information, please see license.txt

frappe.ui.form.on('Chapter', {
refresh: function(frm) {
    // Add button to view chapter members
    frm.add_custom_button(__('View Members'), function() {
        frappe.set_route('List', 'Member', {'primary_chapter': frm.doc.name});
    }, __('View'));
    
    // Add email buttons
    frm.add_custom_button(__('Email Board Members'), function() {
        send_email_to_board_members(frm);
    }, __('Communication'));
    
    frm.add_custom_button(__('Email All Members'), function() {
        send_email_to_chapter_members(frm);
    }, __('Communication'));
    
    // Add board management buttons
    if (frm.doc.name) {
        frm.add_custom_button(__('Manage Board Members'), function() {
            manage_board_members(frm);
        }, __('Board'));
        
        frm.add_custom_button(__('Transition Board Role'), function() {
            show_transition_dialog(frm);
        }, __('Board'));
        
        frm.add_custom_button(__('View Board History'), function() {
            view_board_history(frm);
        }, __('Board'));
        
        // Add button to sync board members with volunteer system
        frm.add_custom_button(__('Sync with Volunteer System'), function() {
            sync_board_with_volunteer_system(frm);
        }, __('Board'));

        // Add bulk board member management button
        frm.add_custom_button(__('Bulk Remove Board Members'), function() {
            show_bulk_board_member_dialog(frm);
        }, __('Board'));
    }
    
    // Add chapter statistics button
    frm.add_custom_button(__('Chapter Statistics'), function() {
        show_chapter_stats(frm);
    }, __('View'));
    
    // Custom button for board members table
    if (frm.fields_dict['board_members']) {
        frm.fields_dict['board_members'].grid.add_custom_button(__('Add Board Member'), 
            function() {
                add_new_board_member(frm);
            }
        );

        // Add bulk operations button to grid
        frm.fields_dict['board_members'].grid.add_custom_button(__('Bulk Operations'), 
            function() {
                show_bulk_operations_dialog(frm);
            }
        );
        
        // Set up custom delete handling for board members
        frm.fields_dict.board_members.grid.wrapper.on('click', '.grid-delete-row', function(e) {
            var row = $(this).closest('.grid-row');
            if (!row.length) return;
            
            var idx = row.attr('data-idx');
            if (!idx) return;
            
            var board_member = frm.doc.board_members[idx-1]; // idx is 1-based, array is 0-based
            if (!board_member || !board_member.is_active || !board_member.volunteer) return;
            
            // If this is an active board member with a volunteer, update history before deletion
            setTimeout(function() {
                // Automatically update volunteer history before deletion
                update_volunteer_history_from_board_change(frm, board_member);
            }, 100);
        });

        // Add selection functionality to board members grid
        enhance_board_members_grid_with_selection(frm);
    }
    
    // Add postal code visualization
    if (frm.doc.postal_codes) {
        show_postal_code_preview(frm);
    }
    
    // Add members summary section
    update_members_summary(frm);
}
});

// Add to Chapter Board Member child table
frappe.ui.form.on('Chapter Board Member', {
    volunteer: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.volunteer) {
            // Fetch volunteer details
            frappe.db.get_doc("Volunteer", row.volunteer).then(doc => {
                frappe.model.set_value(cdt, cdn, 'volunteer_name', doc.volunteer_name);
                frappe.model.set_value(cdt, cdn, 'email', doc.email);
                
                // Check if volunteer has a member record
                if (doc.member) {
                    // Add volunteer's member to chapter's members if not already there
                    add_board_member_to_members(frm, row.volunteer);
                } else {
                    // Alert that this volunteer doesn't have a member record
                    frappe.show_alert({
                        message: __("Warning: This volunteer doesn't have an associated member record."),
                        indicator: 'orange'
                    }, 5);
                }
            });
        }
    },
    
    chapter_role: function(frm, cdt, cdn) {
        // Check for duplicate roles
        var row = locals[cdt][cdn];
        if (row.chapter_role && row.is_active) {
            check_for_duplicate_roles(frm, row);
        }
    },
    
    from_date: function(frm, cdt, cdn) {
        // Date validation
        var row = locals[cdt][cdn];
        if (row.to_date && row.from_date > row.to_date) {
            frappe.msgprint(__("Start date cannot be after end date"));
            frappe.model.set_value(cdt, cdn, 'from_date', row.to_date);
        }
    },
    
    to_date: function(frm, cdt, cdn) {
        // Date validation
        var row = locals[cdt][cdn];
        if (row.from_date && row.to_date && row.from_date > row.to_date) {
            frappe.msgprint(__("End date cannot be before start date"));
            frappe.model.set_value(cdt, cdn, 'to_date', row.from_date);
        }
    },

    is_active: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.is_active) {
            check_for_duplicate_roles(frm, row);
        } else {
            // When deactivating, handle the board member removal
            handle_board_member_deactivation(frm, row);
        }
    }
});

// Function to enhance board members grid with selection functionality
function enhance_board_members_grid_with_selection(frm) {
    // Add CSS for selection styling
    if (!$('#board-member-selection-css').length) {
        $('<style id="board-member-selection-css">' +
          '.board-member-selected { background-color: #e8f4fd !important; }' +
          '.board-member-checkbox { margin-right: 10px; }' +
          '.bulk-actions-bar { background: #f8f9fa; padding: 10px; margin-bottom: 10px; border-radius: 4px; }' +
          '</style>').appendTo('head');
    }

    // Add selection controls above the grid
    setTimeout(function() {
        var $grid = frm.fields_dict.board_members.grid.wrapper;
        var $existing_bar = $grid.find('.bulk-actions-bar');
        
        if ($existing_bar.length === 0) {
            var $bulk_bar = $('<div class="bulk-actions-bar" style="display: none;">' +
                '<button class="btn btn-xs btn-default" onclick="select_all_active_board_members(\'' + frm.docname + '\')">' + __('Select All Active') + '</button> ' +
                '<button class="btn btn-xs btn-default" onclick="deselect_all_board_members(\'' + frm.docname + '\')">' + __('Deselect All') + '</button> ' +
                '<span style="margin: 0 15px;">|</span>' +
                '<button class="btn btn-xs btn-danger" onclick="bulk_remove_selected_board_members(\'' + frm.docname + '\')">' + __('Remove Selected') + '</button> ' +
                '<button class="btn btn-xs btn-warning" onclick="bulk_deactivate_selected_board_members(\'' + frm.docname + '\')">' + __('Deactivate Selected') + '</button>' +
                '</div>');
            
            $grid.find('.grid-body').before($bulk_bar);
        }

        // Add checkboxes to each row
        add_selection_checkboxes_to_board_members(frm);
    }, 500);
}

// Function to add checkboxes to board member rows
function add_selection_checkboxes_to_board_members(frm) {
    var $grid = frm.fields_dict.board_members.grid.wrapper;
    
    $grid.find('.grid-row').each(function() {
        var $row = $(this);
        var idx = $row.attr('data-idx');
        
        if (idx && !$row.find('.board-member-checkbox').length) {
            var board_member = frm.doc.board_members[idx-1];
            if (board_member && board_member.is_active) {
                var $checkbox = $('<input type="checkbox" class="board-member-checkbox" data-idx="' + idx + '">');
                
                $checkbox.change(function() {
                    var is_checked = $(this).is(':checked');
                    if (is_checked) {
                        $row.addClass('board-member-selected');
                    } else {
                        $row.removeClass('board-member-selected');
                    }
                    
                    // Show/hide bulk actions bar
                    var selected_count = $grid.find('.board-member-checkbox:checked').length;
                    if (selected_count > 0) {
                        $grid.find('.bulk-actions-bar').show();
                    } else {
                        $grid.find('.bulk-actions-bar').hide();
                    }
                });
                
                $row.find('.data-row').first().prepend($checkbox);
            }
        }
    });
}

// Global functions for selection (need to be global for onclick handlers)
window.select_all_active_board_members = function(docname) {
    var frm = frappe.get_form('Chapter', docname);
    var $grid = frm.fields_dict.board_members.grid.wrapper;
    
    $grid.find('.board-member-checkbox').each(function() {
        var idx = $(this).attr('data-idx');
        var board_member = frm.doc.board_members[idx-1];
        if (board_member && board_member.is_active) {
            $(this).prop('checked', true).trigger('change');
        }
    });
};

window.deselect_all_board_members = function(docname) {
    var frm = frappe.get_form('Chapter', docname);
    var $grid = frm.fields_dict.board_members.grid.wrapper;
    
    $grid.find('.board-member-checkbox:checked').prop('checked', false).trigger('change');
};

window.bulk_remove_selected_board_members = function(docname) {
    var frm = frappe.get_form('Chapter', docname);
    var selected_members = get_selected_board_members(frm);
    
    if (selected_members.length === 0) {
        frappe.msgprint(__('No board members selected'));
        return;
    }
    
    show_bulk_removal_dialog(frm, selected_members, 'remove');
};

window.bulk_deactivate_selected_board_members = function(docname) {
    var frm = frappe.get_form('Chapter', docname);
    var selected_members = get_selected_board_members(frm);
    
    if (selected_members.length === 0) {
        frappe.msgprint(__('No board members selected'));
        return;
    }
    
    show_bulk_removal_dialog(frm, selected_members, 'deactivate');
};

// Function to get selected board members
function get_selected_board_members(frm) {
    var selected = [];
    var $grid = frm.fields_dict.board_members.grid.wrapper;
    
    $grid.find('.board-member-checkbox:checked').each(function() {
        var idx = $(this).attr('data-idx');
        var board_member = frm.doc.board_members[idx-1];
        if (board_member) {
            selected.push({
                idx: idx,
                volunteer: board_member.volunteer,
                volunteer_name: board_member.volunteer_name,
                chapter_role: board_member.chapter_role,
                from_date: board_member.from_date,
                data: board_member
            });
        }
    });
    
    return selected;
}

// Function to show bulk removal dialog
function show_bulk_removal_dialog(frm, selected_members, action) {
    var action_label = action === 'remove' ? __('Remove') : __('Deactivate');
    var action_description = action === 'remove' ? 
        __('This will permanently remove the selected board members from the chapter.') :
        __('This will deactivate the selected board members (they will remain in the list but marked as inactive).');
    
    var members_list = selected_members.map(function(member) {
        return '• ' + member.volunteer_name + ' (' + member.chapter_role + ')';
    }).join('\n');
    
    var d = new frappe.ui.Dialog({
        title: action_label + ' ' + __('Board Members'),
        fields: [
            {
                fieldtype: 'HTML',
                options: '<p>' + action_description + '</p>' +
                        '<p><strong>' + __('Selected Members:') + '</strong></p>' +
                        '<pre>' + members_list + '</pre>'
            },
            {
                fieldname: 'end_date',
                fieldtype: 'Date',
                label: __('End Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'reason',
                fieldtype: 'Small Text',
                label: __('Reason for ') + action_label.toLowerCase(),
                description: __('Optional reason for this action')
            }
        ],
        primary_action_label: action_label + ' ' + selected_members.length + ' ' + __('Members'),
        primary_action: function() {
            var values = d.get_values();
            
            // Prepare data for bulk operation
            var bulk_data = selected_members.map(function(member) {
                return {
                    volunteer: member.volunteer,
                    chapter_role: member.chapter_role,
                    from_date: member.from_date,
                    end_date: values.end_date,
                    reason: values.reason
                };
            });
            
            // Call appropriate bulk method
            var method = action === 'remove' ? 'bulk_remove_board_members' : 'bulk_deactivate_board_members';
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.chapter.chapter.' + method,
                args: {
                    chapter_name: frm.doc.name,
                    board_members: bulk_data
                },
                freeze: true,
                freeze_message: __(action === 'remove' ? 'Removing' : 'Deactivating') + ' ' + __('board members...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('{0} board members {1} successfully', [r.message.processed, action === 'remove' ? 'removed' : 'deactivated']),
                            indicator: 'green'
                        }, 5);
                        
                        d.hide();
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Error processing board members. Please check the error log.'));
                    }
                },
                error: function() {
                    frappe.msgprint(__('Failed to process board members. Please try again.'));
                }
            });
        }
    });
    
    d.show();
}

// Function to show bulk board member dialog (alternative approach)
function show_bulk_board_member_dialog(frm) {
    if (!frm.doc.board_members || frm.doc.board_members.length === 0) {
        frappe.msgprint(__('No board members found'));
        return;
    }
    
    var active_members = frm.doc.board_members.filter(function(member) {
        return member.is_active;
    });
    
    if (active_members.length === 0) {
        frappe.msgprint(__('No active board members found'));
        return;
    }
    
    // Create options for multiselect
    var member_options = active_members.map(function(member) {
        return {
            label: member.volunteer_name + ' (' + member.chapter_role + ')',
            value: member.volunteer,
            description: 'From: ' + frappe.datetime.str_to_user(member.from_date)
        };
    });
    
    var d = new frappe.ui.Dialog({
        title: __('Bulk Board Member Operations'),
        fields: [
            {
                fieldname: 'selected_members',
                fieldtype: 'MultiSelectPills',
                label: __('Select Board Members'),
                options: member_options,
                reqd: 1
            },
            {
                fieldname: 'action',
                fieldtype: 'Select',
                label: __('Action'),
                options: 'Deactivate\nRemove',
                default: 'Deactivate',
                reqd: 1
            },
            {
                fieldname: 'end_date',
                fieldtype: 'Date',
                label: __('End Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'reason',
                fieldtype: 'Small Text',
                label: __('Reason'),
                description: __('Optional reason for this action')
            }
        ],
        primary_action_label: __('Process Selected Members'),
        primary_action: function() {
            var values = d.get_values();
            
            if (!values.selected_members || values.selected_members.length === 0) {
                frappe.msgprint(__('Please select at least one board member'));
                return;
            }
            
            // Find selected board members data
            var selected_data = [];
            values.selected_members.forEach(function(volunteer_id) {
                var member = active_members.find(function(m) { return m.volunteer === volunteer_id; });
                if (member) {
                    selected_data.push({
                        volunteer: member.volunteer,
                        chapter_role: member.chapter_role,
                        from_date: member.from_date,
                        end_date: values.end_date,
                        reason: values.reason
                    });
                }
            });
            
            var method = values.action === 'Remove' ? 'bulk_remove_board_members' : 'bulk_deactivate_board_members';
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.chapter.chapter.' + method,
                args: {
                    chapter_name: frm.doc.name,
                    board_members: selected_data
                },
                freeze: true,
                freeze_message: __('Processing board members...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('{0} board members processed successfully', [r.message.processed]),
                            indicator: 'green'
                        }, 5);
                        
                        d.hide();
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Error processing board members. Please check the error log.'));
                    }
                }
            });
        }
    });
    
    d.show();
}

// Function to show bulk operations dialog (grid-based)
function show_bulk_operations_dialog(frm) {
    // Refresh the selection UI first
    setTimeout(function() {
        enhance_board_members_grid_with_selection(frm);
    }, 100);
    
    frappe.msgprint({
        title: __('Bulk Operations'),
        message: __('Use the checkboxes next to board members to select them, then use the bulk action buttons that appear above the grid.'),
        indicator: 'blue'
    });
}

// Function to handle board member deactivation
function handle_board_member_deactivation(frm, row) {
    // Set to_date if not already set
    if (!row.to_date) {
        frappe.model.set_value(row.doctype, row.name, 'to_date', frappe.datetime.get_today());
    }
    
    // Show confirmation to user
    frappe.show_alert({
        message: __("Board member deactivated. End date set to today."),
        indicator: 'orange'
    }, 5);
    
    // Only prompt for volunteer history if we have a volunteer
    if (row.volunteer) {
        // Automatically update volunteer history (no user prompt needed)
        update_volunteer_history_from_board_change(frm, row);
    }
}

// Function to update volunteer history from board changes
function update_volunteer_history_from_board_change(frm, board_member) {
    if (!board_member.volunteer) {
        return;
    }
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.chapter.chapter.update_volunteer_assignment_history',
        args: {
            'volunteer_id': board_member.volunteer,
            'chapter_name': frm.doc.name,
            'role': board_member.chapter_role,
            'start_date': board_member.from_date,
            'end_date': board_member.to_date || frappe.datetime.get_today()
        },
        callback: function(r) {
            if (r.message) {
                frappe.show_alert({
                    message: __("Board assignment recorded in volunteer history"),
                    indicator: 'green'
                }, 3);
            } else {
                frappe.show_alert({
                    message: __("Failed to update volunteer history. Please check the logs."),
                    indicator: 'red'
                }, 5);
            }
        },
        error: function(r) {
            console.error("Error updating volunteer history:", r);
            frappe.show_alert({
                message: __("Error updating volunteer history. Please try again."),
                indicator: 'red'
            }, 5);
        }
    });
}

// Function to add a board member to the chapter's members list
function add_board_member_to_members(frm, volunteer_id) {
    // First, we need to get the member associated with this volunteer
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Volunteer',
            filters: { name: volunteer_id },
            fieldname: 'member'
        },
        callback: function(r) {
            if (!r.message || !r.message.member) {
                frappe.msgprint(__("Could not find member associated with this volunteer"));
                return;
            }
            
            let member_id = r.message.member;
            
            // Check if the member is already in the members list
            let already_member = false;
            let member_entry = null;
            
            if (frm.doc.members) {
                for (let i = 0; i < frm.doc.members.length; i++) {
                    if (frm.doc.members[i].member === member_id) {
                        already_member = true;
                        member_entry = frm.doc.members[i];
                        break;
                    }
                }
            }
            
            // If already a member, just make sure they're enabled
            if (already_member) {
                if (!member_entry.enabled) {
                    // Re-enable if disabled
                    frappe.model.set_value(member_entry.doctype, member_entry.name, 'enabled', 1);
                    frappe.model.set_value(member_entry.doctype, member_entry.name, 'leave_reason', null);
                    
                    frm.refresh_field("members");
                    
                    frappe.show_alert({
                        message: __("Board member's chapter membership has been re-enabled"),
                        indicator: "green"
                    }, 5);
                }
            } else {
                // Not a member yet, add them
                frappe.db.get_doc("Member", member_id).then(member_doc => {
                    let new_member = frm.add_child("members");
                    new_member.member = member_id;
                    new_member.member_name = member_doc.full_name;
                    new_member.enabled = 1;
                    
                    frm.refresh_field("members");
                    
                    frappe.show_alert({
                        message: __("Board member {0} added to chapter members list", [member_doc.full_name]),
                        indicator: "green"
                    }, 5);
                });
            }
        }
    });
}

// Function to send email to board members
function send_email_to_board_members(frm) {
    if (!frm.doc.board_members || !frm.doc.board_members.length) {
        frappe.msgprint(__('No board members to email'));
        return;
    }
    
    var board_members = frm.doc.board_members.filter(function(member) {
        return member.is_active && member.email;
    }).map(function(member) {
        return member.email;
    });
    
    if (!board_members.length) {
        frappe.msgprint(__('No active board members with email addresses'));
        return;
    }
    
    var d = new frappe.ui.Dialog({
        title: __('Email Board Members'),
        fields: [
            {
                label: __('Subject'),
                fieldname: 'subject',
                fieldtype: 'Data',
                reqd: 1,
                default: __('Message from Chapter ') + frm.doc.name
            },
            {
                label: __('Message'),
                fieldname: 'message',
                fieldtype: 'Text Editor',
                reqd: 1
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function() {
            var values = d.get_values();
            
            frappe.call({
                method: 'frappe.core.doctype.communication.email.make',
                args: {
                    recipients: board_members.join(','),
                    subject: values.subject,
                    content: values.message,
                    doctype: frm.doctype,
                    name: frm.docname,
                    send_email: 1
                },
                callback: function(r) {
                    if(!r.exc) {
                        frappe.msgprint(__('Email sent to board members'));
                        d.hide();
                    }
                }
            });
        }
    });
    
    d.show();
}

// Function to send email to all chapter members
function send_email_to_chapter_members(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Member',
            filters: {
                'primary_chapter': frm.doc.name
            },
            fields: ['name', 'full_name', 'email']
        },
        callback: function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint(__('No members found for this chapter'));
                return;
            }
            
            var members = r.message.filter(function(member) {
                return member.email;
            });
            
            if (!members.length) {
                frappe.msgprint(__('No members with email addresses found'));
                return;
            }
            
            var d = new frappe.ui.Dialog({
                title: __('Email Chapter Members'),
                fields: [
                    {
                        label: __('Subject'),
                        fieldname: 'subject',
                        fieldtype: 'Data',
                        reqd: 1,
                        default: __('Message from Chapter ') + frm.doc.name
                    },
                    {
                        label: __('Message'),
                        fieldname: 'message',
                        fieldtype: 'Text Editor',
                        reqd: 1
                    }
                ],
                primary_action_label: __('Send'),
                primary_action: function() {
                    var values = d.get_values();
                    
                    frappe.call({
                        method: 'frappe.core.doctype.communication.email.make',
                        args: {
                            recipients: members.map(function(m) { return m.email; }).join(','),
                            subject: values.subject,
                            content: values.message,
                            doctype: frm.doctype,
                            name: frm.docname,
                            send_email: 1
                        },
                        callback: function(r) {
                            if(!r.exc) {
                                frappe.msgprint(__('Email sent to chapter members'));
                                d.hide();
                            }
                        }
                    });
                }
            });
            
            d.show();
        }
    });
}

// Function to check for duplicate active roles
function check_for_duplicate_roles(frm, current_row) {
    // First check if this role requires uniqueness
    frappe.db.get_value('Chapter Role', current_row.chapter_role, 'is_unique', function(r) {
        if (r && r.is_unique) {
            // This is a unique role, check for duplicates
            var found_duplicate = false;
            
            frm.doc.board_members.forEach(function(member) {
                if (member.is_active && member.chapter_role && 
                    member.name !== current_row.name && 
                    member.chapter_role === current_row.chapter_role) {
                    
                    found_duplicate = true;
                    
                    frappe.msgprint(__("Role '{0}' is already assigned to {1}. This role can only be assigned to one person at a time.", 
                        [current_row.chapter_role, member.volunteer_name]));
                    
                    // Ask if user wants to deactivate the existing role
                    frappe.confirm(
                        __('Do you want to deactivate the existing assignment to {0}?', [member.volunteer_name]),
                        function() {
                            // Yes - deactivate existing role
                            frappe.model.set_value(member.doctype, member.name, 'is_active', 0);
                            frappe.model.set_value(member.doctype, member.name, 'to_date', frappe.datetime.get_today());
                        }
                    );
                }
            });
            
            // If no duplicate found, everything is fine
            if (!found_duplicate) {
                frappe.show_alert({
                    message: __("Role '{0}' assigned to {1}", [current_row.chapter_role, current_row.volunteer_name]),
                    indicator: 'green'
                }, 3);
            }
        } else {
            // Non-unique role, just display a confirmation
            frappe.show_alert({
                message: __("Role '{0}' assigned to {1}", [current_row.chapter_role, current_row.volunteer_name]),
                indicator: 'green'
            }, 3);
        }
    });
}

// Function to validate board members on save
function validate_board_members(frm) {
    // Load all unique roles first
    return new Promise(function(resolve, reject) {
        frappe.db.get_list('Chapter Role', {
            fields: ['name', 'is_unique'],
            filters: { 'is_active': 1 }
        }).then(function(roles) {
            // Create a dictionary of roles that are unique
            var unique_roles = {};
            roles.forEach(function(role) {
                if (role.is_unique) {
                    unique_roles[role.name] = true;
                }
            });
            
            // Check for duplicate active roles on save (only for unique roles)
            var active_unique_roles = {};
            var has_error = false;
            
            frm.doc.board_members.forEach(function(member) {
                if (member.is_active && member.chapter_role) {
                    // Only enforce uniqueness for roles marked as unique
                    if (unique_roles[member.chapter_role]) {
                        if (active_unique_roles[member.chapter_role]) {
                            frappe.msgprint(__("Unique role '{0}' is assigned to multiple active board members", [member.chapter_role]));
                            has_error = true;
                        }
                        active_unique_roles[member.chapter_role] = member.volunteer;
                    }
                    
                    // Check dates
                    if (member.to_date && 
                        frappe.datetime.str_to_obj(member.from_date) > frappe.datetime.str_to_obj(member.to_date)) {
                        frappe.msgprint(__("Board member {0} has start date after end date", [member.volunteer_name]));
                        has_error = true;
                    }
                }
            });
            
            resolve(!has_error);
        });
    });
}

// Function to add a new board member
function add_new_board_member(frm) {
    // Get chapter roles
    frappe.db.get_list('Chapter Role', {
        fields: ['name', 'permissions_level'],
        filters: { 'is_active': 1 }
    }).then(roles => {
        if (!roles || !roles.length) {
            frappe.msgprint(__('No active chapter roles found. Please create roles first.'));
            return;
        }
        
        // Create dialog
        var d = new frappe.ui.Dialog({
            title: __('Add New Board Member'),
            fields: [
                {
                    fieldname: 'volunteer',
                    fieldtype: 'Link',
                    label: __('Volunteer'),
                    options: 'Volunteer',
                    reqd: 1,
                    get_query: function() {
                        return {
                            query: "verenigingen.verenigingen.doctype.chapter.chapter.get_volunteers_for_chapter",
                            filters: {
                                'chapter': frm.doc.name
                            }
                        };
                    }
                },
                {
                    fieldname: 'chapter_role',
                    fieldtype: 'Link',
                    label: __('Board Role'),
                    options: 'Chapter Role',
                    reqd: 1
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
                }
            ],
            primary_action_label: __('Add'),
            primary_action: function(values) {
                // Add new row to board_members
                var child = frm.add_child('board_members');
                frappe.model.set_value(child.doctype, child.name, 'volunteer', values.volunteer);
                frappe.model.set_value(child.doctype, child.name, 'chapter_role', values.chapter_role);
                frappe.model.set_value(child.doctype, child.name, 'from_date', values.from_date);
                frappe.model.set_value(child.doctype, child.name, 'to_date', values.to_date);
                frappe.model.set_value(child.doctype, child.name, 'is_active', 1);
                
                // Fetch volunteer details
                frappe.db.get_doc("Volunteer", values.volunteer).then(doc => {
                    frappe.model.set_value(child.doctype, child.name, 'volunteer_name', doc.volunteer_name);
                    frappe.model.set_value(child.doctype, child.name, 'email', doc.email);
                    
                    frm.refresh_field('board_members');
                    d.hide();
                    
                    // Add board member to chapter's members list
                    add_board_member_to_members(frm, values.volunteer);
                    
                    // Check if there are other active members with the same role
                    check_for_duplicate_roles(frm, child);
                });
            }
        });
        
        d.show();
    });
}

// Function to manage board members
function manage_board_members(frm) {
    // Get chapter roles
    frappe.db.get_list('Chapter Role', {
        fields: ['name', 'permissions_level'],
        filters: { 'is_active': 1 }
    }).then(roles => {
        if (!roles || !roles.length) {
            frappe.msgprint(__('No active chapter roles found. Please create roles first.'));
            return;
        }
        
        // Create dialog
        var d = new frappe.ui.Dialog({
            title: __('Manage Board Members'),
            fields: [
                {
                    fieldname: 'member_section',
                    fieldtype: 'Section Break',
                    label: __('Add New Board Member')
                },
                {
                    fieldname: 'volunteer',  // Changed from 'member' to 'volunteer'
                    fieldtype: 'Link',
                    label: __('Volunteer'),  // Changed label
                    options: 'Volunteer',   // Changed options
                    reqd: 1,
                    get_query: function() {
                        return {
                            query: "verenigingen.verenigingen.doctype.chapter.chapter.get_volunteers_for_chapter",
                            filters: {
                                'chapter': frm.doc.name
                            }
                        };
                    }
                },
                {
                    fieldname: 'chapter_role',
                    fieldtype: 'Link',
                    label: __('Board Role'),
                    options: 'Chapter Role',
                    reqd: 1
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
                }
            ],
            primary_action_label: __('Add Board Member'),
            primary_action: function(values) {
                // Call the server method to add board member
                frappe.call({
                    method: 'add_board_member',
                    doc: frm.doc,
                    args: {
                        volunteer: values.volunteer,  // Changed from 'member' to 'volunteer'
                        role: values.chapter_role,
                        from_date: values.from_date,
                        to_date: values.to_date
                    },
                    callback: function(r) {
                        if (r.message) {
                            d.hide();
                            frm.reload_doc();
                        }
                    }
                });
            }
        });
        
        d.show();
    });
}

// Function to show board role transition dialog
function show_transition_dialog(frm) {
    // Get active board members
    var active_members = get_active_board_members(frm);
    
    if (!active_members || active_members.length === 0) {
        frappe.msgprint(__('No active board members found'));
        return;
    }
    
    // Create dialog for board role transitions
    var d = new frappe.ui.Dialog({
        title: __('Transition Board Role'),
        fields: [
            {
                fieldname: 'current_volunteer',
                fieldtype: 'Select',
                label: __('Current Board Member'),
                options: active_members,
                reqd: 1
            },
            {
                fieldname: 'new_role',
                fieldtype: 'Link',
                label: __('New Role'),
                options: 'Chapter Role',
                reqd: 1
            },
            {
                fieldname: 'transition_date',
                fieldtype: 'Date',
                label: __('Transition Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            }
        ],
        primary_action_label: __('Transition Role'),
        primary_action: function(values) {
            // Extract member name from the select option
            var volunteer = values.current_volunteer.split(' | ')[0];
            
            // Call the server method to transition role
            frappe.call({
                method: 'transition_board_role',
                doc: frm.doc,
                args: {
                    volunteer: volunteer,
                    new_role: values.new_role,
                    transition_date: values.transition_date
                },
                callback: function(r) {
                    if (r.message) {
                        d.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    
    d.show();
}

// Function to view board history
function view_board_history(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.chapter.chapter.get_chapter_board_history',
        args: {
            chapter_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint(__('No board history found'));
                return;
            }
            
            // Create a table to show the history
            var history = r.message;
            var html = '<div class="board-history"><table class="table table-bordered">';
            html += '<thead><tr><th>Member</th><th>Role</th><th>From Date</th><th>To Date</th><th>Status</th></tr></thead>';
            html += '<tbody>';
            
            history.forEach(function(entry) {
                var status = entry.is_active ? 'Active' : 'Inactive';
                var status_color = entry.is_active ? 'green' : 'gray';
                
                html += '<tr>';
                html += '<td>' + entry.member_name + '</td>';
                html += '<td>' + entry.role + '</td>';
                html += '<td>' + frappe.datetime.str_to_user(entry.from_date) + '</td>';
                html += '<td>' + (entry.to_date ? frappe.datetime.str_to_user(entry.to_date) : '') + '</td>';
                html += '<td><span class="indicator ' + status_color + '">' + status + '</span></td>';
                html += '</tr>';
            });
            
            html += '</tbody></table></div>';
            
            var d = new frappe.ui.Dialog({
                title: __('Board History - {0}', [frm.doc.name]),
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
        }
    });
}

// Function to show chapter statistics
function show_chapter_stats(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.chapter.chapter.get_chapter_stats',
        args: {
            chapter_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint(__('Could not retrieve chapter statistics'));
                return;
            }
            
            var stats = r.message;
            var html = '<div class="chapter-stats">';
            
            // Overview section
            html += '<div class="stats-section"><h4>Overview</h4>';
            html += '<div class="row">';
            html += '<div class="col-sm-6"><div class="stat-item"><div class="stat-number">' + stats.member_count + '</div><div class="stat-label">Members</div></div></div>';
            html += '<div class="col-sm-6"><div class="stat-item"><div class="stat-number">' + stats.board_count + '</div><div class="stat-label">Board Members</div></div></div>';
            html += '</div></div>';
            
            // Recent memberships section
            if (stats.recent_memberships && stats.recent_memberships.length) {
                html += '<div class="stats-section"><h4>Recent Memberships</h4>';
                html += '<table class="table table-condensed">';
                html += '<thead><tr><th>Member</th><th>Start Date</th><th>Status</th></tr></thead>';
                html += '<tbody>';
                
                stats.recent_memberships.forEach(function(membership) {
                    html += '<tr>';
                    html += '<td>' + membership.member + '</td>';
                    html += '<td>' + frappe.format_date(membership.start_date) + '</td>';
                    html += '<td>' + membership.status + '</td>';
                    html += '</tr>';
                });
                
                html += '</tbody></table></div>';
            }
            
            html += '<div class="text-muted small">Last updated: ' + stats.last_updated + '</div>';
            html += '</div>';
            
            var d = new frappe.ui.Dialog({
                title: __('Chapter Statistics - {0}', [frm.doc.name]),
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
        }
    });
}

// Function to get active board members for select field
function get_active_board_members(frm) {
    // Return a string of options for select field
    var options = [];
    
    if (frm.doc.board_members) {
        frm.doc.board_members.forEach(function(member) {
            if (member.is_active) {
                options.push(member.volunteer + ' | ' + member.volunteer_name + ' (' + member.chapter_role + ')');
            }
        });
    }
    
    return options.join('\n');
}

// Function to create a volunteer record from board member
function create_volunteer_record(frm, member) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.volunteer.volunteer.create_volunteer_from_member',
        args: {
            member_doc: member
        },
        callback: function(r) {
            if (r.message) {
                frappe.show_alert({
                    message: __("Volunteer record created successfully."),
                    indicator: 'green'
                }, 5);
                
                // Refresh the form to ensure data is updated
                frm.refresh();
            }
        }
    });
}

// Function to sync all board members with volunteer system
function sync_board_with_volunteer_system(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.volunteer.volunteer.sync_chapter_board_members',
        callback: function(r) {
            if (r.message) {
                frappe.show_alert({
                    message: __("Synced {0} board members with volunteer system.", [r.message.updated_count]),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

// Function to validate postal codes
function validate_postal_codes(frm) {
    if (!frm.doc.postal_codes) {
        return;
    }
    
    // Split by commas and check each pattern
    var patterns = frm.doc.postal_codes.split(',').map(function(p) { return p.trim(); });
    var valid_patterns = [];
    var invalid_patterns = [];
    
    patterns.forEach(function(pattern) {
        // Check for range pattern (e.g. 1000-1099)
        if (pattern.includes('-')) {
            var parts = pattern.split('-');
            if (parts.length === 2 && /^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1])) {
                valid_patterns.push(pattern);
            } else {
                invalid_patterns.push(pattern);
            }
        }
        // Check for wildcard pattern (e.g. 10*)
        else if (pattern.includes('*')) {
            var base = pattern.replace('*', '');
            if (/^\d+$/.test(base)) {
                valid_patterns.push(pattern);
            } else {
                invalid_patterns.push(pattern);
            }
        }
        // Simple postal code
        else if (/^\d+$/.test(pattern) || /^[a-zA-Z0-9]+$/.test(pattern)) {
            valid_patterns.push(pattern);
        }
        else {
            invalid_patterns.push(pattern);
        }
    });
    
    // Show warning for invalid patterns
    if (invalid_patterns.length > 0) {
        frappe.msgprint({
            title: __('Invalid Postal Code Patterns'),
            indicator: 'orange',
            message: __('The following postal code patterns are invalid and will be ignored: {0}', [invalid_patterns.join(', ')])
        });
    }
}

// Function to show postal code preview
function show_postal_code_preview(frm) {
    if (!frm.doc.postal_codes) {
        return;
    }
    
    // Find or create the preview section
    var $wrapper = frm.get_field('postal_codes').$wrapper;
    var $preview = $wrapper.find('.postal-code-preview');
    
    if (!$preview.length) {
        $preview = $('<div class="postal-code-preview alert alert-info mt-3"></div>');
        $wrapper.append($preview);
    }
    
    // Parse the patterns
    var patterns = frm.doc.postal_codes.split(',').map(function(p) { return p.trim(); });
    var html = '<strong>' + __('Chapter covers the following areas:') + '</strong><ul class="mt-2">';
    
    patterns.forEach(function(pattern) {
        if (pattern.includes('-')) {
            var parts = pattern.split('-');
            html += '<li>' + __('Range: {0} to {1}', [parts[0], parts[1]]) + '</li>';
        }
        else if (pattern.includes('*')) {
            var base = pattern.replace('*', '');
            html += '<li>' + __('All codes starting with: {0}', [base]) + '</li>';
        }
        else {
            html += '<li>' + __('Exact code: {0}', [pattern]) + '</li>';
        }
    });
    
    html += '</ul>';
    $preview.html(html);
}

// Function to update the members summary section
function update_members_summary(frm) {
    if (!frm.doc.name) {
        return;
    }
    
    // Get chapter members count
    frappe.call({
        method: 'frappe.client.get_count',
        args: {
            doctype: 'Member',
            filters: { 'primary_chapter': frm.doc.name }
        },
        callback: function(r) {
            if (r.message !== undefined) {
                // Create or update the members summary
                var $header = frm.fields_dict.chapter_members.$wrapper.find('.form-section-heading');
                var summary = ` <span class="text-muted">(${r.message} members)</span>`;
                
                // Check if summary already exists and update it
                if ($header.find('.member-count').length) {
                    $header.find('.member-count').html(summary);
                } else {
                    $header.append(`<span class="member-count">${summary}</span>`);
                }
            }
        }
    });
}
