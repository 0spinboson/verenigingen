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
        
        // In the refresh function in member.js
        if (frm.doc.customer) {
            // Your existing buttons that require customer to be set
            frm.add_custom_button(__('Customer'), function() {
                frappe.set_route('Form', 'Customer', frm.doc.customer);
            }, __('View'));
    
            // Add the new button in the same condition block
            frm.add_custom_button(__('Refresh Payment History'), function() {
                frappe.call({
                    method: "load_payment_history",
                    doc: frm.doc,
                    callback: function() {
                        frm.refresh_field("payment_history");
                        frappe.show_alert(__("Payment history refreshed"));
                    }
                });
            }, __('Actions'));
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
        
        frm.add_custom_button(__('Create Volunteer'), function() {
            // First get the email domain from settings
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
                    const nameForEmail = frm.doc.full_name 
                        ? frm.doc.full_name.replace(/\s+/g, '.').toLowerCase()
                        : '';
                
                    // Construct organization email
                    const orgEmail = nameForEmail ? `${nameForEmail}@${domain}` : '';
                
                    // Set route options for creating volunteer
                    frappe.route_options = {
                        'volunteer_name': frm.doc.full_name,
                        'member': frm.doc.name,
                        'preferred_pronouns': frm.doc.pronouns,
                        'email': orgEmail,  // Organization email
                        'personal_email': frm.doc.email || ''  // Personal email from member
                    };
                
                    // Create new volunteer doc
                    frappe.new_doc('Volunteer');
                }
            });
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
        
        // SEPA Mandate Management Buttons
        if (!frm.is_new()) {
            // Add button to create new SEPA mandate
            frm.add_custom_button(__('Create SEPA Mandate'), function() {
                frappe.call({
                    method: 'create_sepa_mandate',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            frappe.set_route('Form', 'SEPA Mandate', r.message);
                        }
                    }
                });
            }, __('Actions'));
            
            // Add button to view SEPA mandates
            frm.add_custom_button(__('View SEPA Mandates'), function() {
                frappe.set_route('List', 'SEPA Mandate', {
                    'member': frm.doc.name
                });
            }, __('View'));
            
            // If there's a default mandate, add button to view it
            if (frm.doc.default_sepa_mandate) {
                frm.add_custom_button(__('Default SEPA Mandate'), function() {
                    frappe.set_route('Form', 'SEPA Mandate', frm.doc.default_sepa_mandate);
                }, __('View'));
            }
            
            // Add custom button for SEPA mandates grid
            if (frm.fields_dict['sepa_mandates']) {
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
        }

        // Attach triggers to name fields dynamically
        ['first_name', 'middle_name', 'last_name'].forEach(field => {
            frm.fields_dict[field].df.onchange = () => frm.trigger('update_full_name');
        });
    },
    
    onload: function(frm) {
        if (!frm.is_new()) {
            // Check if member has active SEPA mandates
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.check_sepa_mandate_status',
                args: {
                    member: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        if (!r.message.has_active_mandate) {
                            frm.dashboard.add_indicator(
                                __('No Active SEPA Mandate'), 
                                'orange'
                            );
                        } else if (r.message.expiring_soon) {
                            frm.dashboard.add_indicator(
                                __('SEPA Mandate Expiring Soon'), 
                                'yellow'
                            );
                        }
                    }
                }
            });
        }
    },
    
    update_full_name: function(frm) {
        // Build full name from components
        let full_name = [
            frm.doc.first_name,
            frm.doc.middle_name,
            frm.doc.last_name
        ].filter(Boolean).join(' ');
        
        frm.set_value('full_name', full_name);
    },
    payment_method: function(frm) {
        // Show/hide bank details based on payment method
        const is_direct_debit = frm.doc.payment_method === 'Direct Debit';
        frm.toggle_display(['bank_details_section'], is_direct_debit);
        frm.toggle_reqd(['sepa_mandate'], is_direct_debit);
        
        // Auto-populate bank details from SEPA mandate
        if (is_direct_debit && frm.doc.sepa_mandate) {
            frappe.db.get_doc('SEPA Mandate', frm.doc.sepa_mandate)
                .then(mandate => {
                    frm.set_value('iban', mandate.iban);
                    frm.set_value('bic', mandate.bic);
                    frm.set_value('bank_account_name', mandate.account_holder_name);
                });
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

// Handlers for the Member SEPA Mandate Link child table
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
