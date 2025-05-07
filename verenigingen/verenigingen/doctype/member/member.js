frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Add buttons to create customer and user
        if (!frm.doc.customer) {
            frm.add_custom_button(__('Create Customer'), function() {
                frm.call({
                    doc: frm.doc,
                    method: 'create_customer',
                    callback: function(r) {
                        if (r.message) {
                            frm.refresh();
                        }
                    }
                });
            }, __('Actions'));
        }
        if (frm.doc.customer) {
            frm.add_custom_button(__('Payment History'), function() {
                frappe.route_options = {
                    'party_type': 'Customer',
                    'party': frm.doc.customer
                };
                frappe.set_route('List', 'Payment Entry');
            }, __('View'));
        }
        
        // Add button to view chapter if member has a primary chapter
        if (frm.doc.primary_chapter) {
            frm.add_custom_button(__('View Chapter'), function() {
                frappe.set_route('Form', 'Chapter', frm.doc.primary_chapter);
            }, __('View'));
        }
        
        // Add button to change primary chapter
        frm.add_custom_button(__('Change Primary Chapter'), function() {
            change_primary_chapter(frm);
        }, __('Actions'));
        
        // Check if user is a board member of any chapter
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.member.member.get_board_memberships',
            args: {
                member_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message && r.message.length) {
                // Show board memberships
                    var html = '<div class="board-memberships"><h4>Board Positions</h4><ul>';

                    r.message.forEach(function(board) {
                        html += '<li><strong>' + board.chapter_role + '</strong> at <a href="/app/chapter/' + 
                                board.parent + '">' + board.parent + '</a></li>';
                    });

                    html += '</ul></div>';

                    $(frm.fields_dict.board_memberships_html.wrapper).html(html);
                }
            }
        });
        
        // Add button to create user
        if (!frm.doc.user && frm.doc.email) {
            frm.add_custom_button(__('Create User'), function() {
                frm.call({
                    doc: frm.doc,
                    method: 'create_user',
                    callback: function(r) {
                        if (r.message) {
                            frm.refresh();
                        }
                    }
                });
            }, __('Actions'));
        }
        
        // Add button to create a Volunteer
        frm.add_custom_button(__('Create Volunteer'), function() {
            // First approach: Use a different method that works more reliably
            frappe.route_options = {
                'volunteer_name': frm.doc.full_name,
                'member': frm.doc.name,
                'preferred_pronouns': frm.doc.pronouns,
                'email': frm.doc.email || ''
            };
            frappe.new_doc('Volunteer');
    
        // Alternative approach (if the above doesn't work):
        /*
        frappe.model.with_doctype('Volunteer', function() {
            var doc = frappe.model.get_new_doc('Volunteer');
            doc.volunteer_name = frm.doc.full_name;
            doc.member = frm.doc.name;
            doc.preferred_pronouns = frm.doc.pronouns;
            doc.email = frm.doc.email || '';
            frappe.ui.form.make_quick_entry('Volunteer', null, null, doc);
        });
        */
        }, __('Actions'));
        
        // Add button to create a new membership
        frm.add_custom_button(__('Create Membership'), function() {
            frappe.new_doc('Membership', {
                'member': frm.doc.name,
                'member_name': frm.doc.full_name,
                'email': frm.doc.email,
                'mobile_no': frm.doc.mobile_no,
                'start_date': frappe.datetime.get_today()
            });
        }, __('Actions'));
        
        // Add button to view memberships
        frm.add_custom_button(__('View Memberships'), function() {
            frappe.set_route('List', 'Membership', {'member': frm.doc.name});
        }, __('View'));
        
        // Add button to view linked customer
        if (frm.doc.customer) {
            frm.add_custom_button(__('Customer'), function() {
                frappe.set_route('Form', 'Customer', frm.doc.customer);
            }, __('View'));
        }
        
        // Add button to view linked user
        if (frm.doc.user) {
            frm.add_custom_button(__('User'), function() {
                frappe.set_route('Form', 'User', frm.doc.user);
            }, __('View'));
        }
        
        // Add button to view current membership
        if (frm.doc.current_membership_details) {
            frm.add_custom_button(__('Current Membership'), function() {
                frappe.set_route('Form', 'Membership', frm.doc.current_membership_details);
            }, __('View'));
        }
        
        // Add button to view existing volunteer record if any
        frm.add_custom_button(__('View Volunteer'), function() {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Volunteer',
                    filters: {
                        'member': frm.doc.name
                    },
                    fields: ['name']
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        frappe.set_route('Form', 'Volunteer', r.message[0].name);
                    } else {
                        frappe.msgprint(__('No volunteer record found for this member. Please create one first.'));
                    }
                }
            });
        }, __('View'));
    },
    
    primary_chapter: function(frm) {
        // Refresh when primary chapter changes
        frm.refresh();
    },
    
    first_name: function(frm) {
        // Automatically update full name
        frm.trigger('update_full_name');
    },
    
    middle_name: function(frm) {
        // Automatically update full name
        frm.trigger('update_full_name');
    },
    
    last_name: function(frm) {
        // Automatically update full name
        frm.trigger('update_full_name');
    },
    
    update_full_name: function(frm) {
        // Build full name from components
        let full_name = [
            frm.doc.first_name,
            frm.doc.middle_name,
            frm.doc.last_name
        ].filter(Boolean).join(' ');
        
        frm.set_value('full_name', full_name);
    }
});

// Function to change primary chapter
function change_primary_chapter(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Chapter',
            filters: {
                'published': 1
            },
            fields: ['name']
        },
        callback: function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint(__('No active chapters found'));
                return;
            }
            
            var chapters = r.message.map(function(c) { return c.name; });
            
            var d = new frappe.ui.Dialog({
                title: __('Change Primary Chapter'),
                fields: [
                    {
                        label: __('New Primary Chapter'),
                        fieldname: 'chapter',
                        fieldtype: 'Select',
                        options: chapters,
                        reqd: 1,
                        default: frm.doc.primary_chapter
                    },
                    {
                        label: __('Reason for Change'),
                        fieldname: 'reason',
                        fieldtype: 'Small Text'
                    }
                ],
                primary_action_label: __('Update'),
                primary_action: function() {
                    var values = d.get_values();
                    
                    if (values.chapter === frm.doc.primary_chapter) {
                        frappe.msgprint(__('No change in primary chapter'));
                        d.hide();
                        return;
                    }
                    
                    frappe.call({
                        method: 'frappe.client.set_value',
                        args: {
                            doctype: 'Member',
                            name: frm.doc.name,
                            fieldname: 'primary_chapter',
                            value: values.chapter
                        },
                        callback: function(r) {
                            if(!r.exc) {
                                // Log the change if a reason was provided
                                if (values.reason) {
                                    frappe.call({
                                        method: 'frappe.client.insert',
                                        args: {
                                            doc: {
                                                doctype: 'Comment',
                                                comment_type: 'Info',
                                                reference_doctype: 'Member',
                                                reference_name: frm.doc.name,
                                                content: __('Changed primary chapter from {0} to {1}. Reason: {2}', 
                                                    [frm.doc.primary_chapter, values.chapter, values.reason])
                                            }
                                        }
                                    });
                                }
                                
                                frappe.msgprint(__('Primary chapter updated'));
                                frm.reload_doc();
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
