frappe.ui.form.on('Member', {
    refresh: function(frm) {
        if (frm.fields_dict.payment_history) {
            $(frm.fields_dict.payment_history.grid.wrapper).addClass('payment-history-grid');
        }
        // Add buttons to create customer and user
        if (frm.doc.docstatus === 1) {
            // Add payment processing button
            if (frm.doc.payment_status !== 'Paid') {
                frm.add_custom_button(__('Process Payment'), function() {
                    process_payment(frm);
                }, __('Actions'));
            }
            frm.fields_dict.payment_history.grid.grid_rows.forEach(row => {
                format_payment_history_row(row);
            });
            
            // Add mark as paid button
            if (frm.doc.payment_status !== 'Paid') {
                frm.add_custom_button(__('Mark as Paid'), function() {
                    mark_as_paid(frm);
                }, __('Actions'));
            }
        }
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

            frm.add_custom_button(__('Refresh Financial History'), function() {
                frappe.show_alert({
                    message: __("Refreshing financial history..."),
                    indicator: 'blue'
                });
                
                frappe.call({
                    method: "load_payment_history",
                    doc: frm.doc,
                    callback: function(r) {
                        frm.refresh_field("payment_history");
                        
                        // Count records by type
                        let records = frm.doc.payment_history || [];
                        let stats = {
                            total: records.length,
                            invoices: 0,
                            membership_invoices: 0,
                            unreconciled: 0,
                            donations: 0,
                            paid: 0,
                            unpaid: 0,
                            overdue: 0,
                            total_amount: 0,
                            outstanding: 0
                        };
                        
                        records.forEach(record => {
                            stats.total_amount += flt(record.amount || 0);
                            stats.outstanding += flt(record.outstanding_amount || 0);
                            
                            if (record.transaction_type === "Regular Invoice") {
                                stats.invoices++;
                                if (record.payment_status === "Paid") stats.paid++;
                                else if (record.payment_status === "Overdue") stats.overdue++;
                                else if (["Unpaid", "Partially Paid"].includes(record.payment_status)) stats.unpaid++;
                            } 
                            else if (record.transaction_type === "Membership Invoice") {
                                stats.membership_invoices++;
                                if (record.payment_status === "Paid") stats.paid++;
                                else if (record.payment_status === "Overdue") stats.overdue++;
                                else if (["Unpaid", "Partially Paid"].includes(record.payment_status)) stats.unpaid++;
                            }
                            else if (record.transaction_type === "Donation Payment") {
                                stats.donations++;
                            }
                            else if (record.transaction_type === "Unreconciled Payment") {
                                stats.unreconciled++;
                            }
                        });
                        
                        // Show a more detailed message
                        let message = `<div>Financial history refreshed:<br>
                            ${stats.invoices + stats.membership_invoices} invoices (${stats.membership_invoices} membership, ${stats.paid} paid, ${stats.unpaid} unpaid, ${stats.overdue} overdue)<br>
                            ${stats.unreconciled} unreconciled payments, ${stats.donations} linked to donations<br>
                            Total: ${format_currency(stats.total_amount)}, Outstanding: ${format_currency(stats.outstanding)}</div>`;
                            
                        frappe.show_alert({
                            message: message,
                            indicator: stats.outstanding > 0 ? 'orange' : 'green'
                        }, 10);
                    }
                });
            }, __('Actions'));
            
            // Add link button to view all donations for this customer
            frm.add_custom_button(__('View Donations'), function() {
                frappe.call({
                    method: "verenigingen.verenigingen.doctype.member.member.get_linked_donations",
                    args: {
                        "member": frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.donor) {
                            frappe.route_options = {
                                "donor": r.message.donor
                            };
                            frappe.set_route("List", "Donation");
                        } else {
                            frappe.msgprint(__("No donor record linked to this member."));
                        }
                    }
                });
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
    ppayment_method: function(frm) {
        // Show/hide bank details based on payment method
        const is_direct_debit = frm.doc.payment_method === 'Direct Debit';
        frm.toggle_display(['bank_details_section'], is_direct_debit);
    },
    iban: function(frm) {
        // When IBAN changes, check if we need to create a new SEPA mandate
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.iban) {
            // First, format the IBAN
            const formattedIban = formatIBAN(frm.doc.iban);
            if (formattedIban !== frm.doc.iban) {
                frm.set_value('iban', formattedIban);
                return; // This will trigger this function again with the formatted IBAN
            }
            
            // Check if we have any active mandate with this IBAN
            let existingMandateWithSameIBAN = false;
            if (frm.doc.sepa_mandates && frm.doc.sepa_mandates.length) {
                existingMandateWithSameIBAN = frm.doc.sepa_mandates.some(mandate => {
                    return get_doc_mandate_iban(mandate.sepa_mandate) === frm.doc.iban && mandate.status === 'Active';
                });
            }
            
            // If no existing mandate with this IBAN, prompt to create new one
            if (!existingMandateWithSameIBAN) {
                // Deactivate any current mandates
                frm.doc.sepa_mandates.forEach(function(mandate) {
                    if (mandate.is_current && mandate.status === 'Active') {
                        frappe.db.set_value('SEPA Mandate', mandate.sepa_mandate, {
                            'status': 'Suspended',
                            'is_active': 0
                        });
                        frappe.model.set_value(mandate.doctype, mandate.name, 'status', 'Suspended');
                        frappe.model.set_value(mandate.doctype, mandate.name, 'is_current', 0);
                    }
                });
                
                // Prompt to create new mandate
                promptCreateMandate(frm);
            }
        }
    },
    bank_account_name: function(frm) {
        // Update account holder name when bank account name changes
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.bank_account_name && frm.doc.iban) {
            // Check if we need to create a mandate
            const hasMandateWithCurrentIBAN = frm.doc.sepa_mandates && frm.doc.sepa_mandates.some(mandate => {
                return get_doc_mandate_iban(mandate.sepa_mandate) === frm.doc.iban && 
                       mandate.status === 'Active' && 
                       mandate.is_current;
            });
            
            if (!hasMandateWithCurrentIBAN) {
                promptCreateMandate(frm);
            }
        }
    }
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

function process_payment(frm) {
    frappe.call({
        method: 'process_payment',
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                frm.reload_doc();
                frappe.msgprint(__('Payment processing initiated'));
            }
        }
    });
}

function mark_as_paid(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Mark as Paid'),
        fields: [
            {
                fieldname: 'payment_date',
                fieldtype: 'Date',
                label: __('Payment Date'),
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                fieldname: 'amount',
                fieldtype: 'Currency',
                label: __('Amount'),
                default: frm.doc.payment_amount,
                reqd: 1
            }
        ],
        primary_action_label: __('Mark as Paid'),
        primary_action: function(values) {
            frappe.call({
                method: 'mark_as_paid',
                doc: frm.doc,
                args: {
                    payment_date: values.payment_date,
                    amount: values.amount
                },
                callback: function(r) {
                    if (r.message) {
                        dialog.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    
    dialog.show();
}
frappe.ui.form.on('Member Payment History', {
    payment_history_add: function(frm, cdt, cdn) {
        // Format new rows as they're added
        let grid_row = frm.fields_dict.payment_history.grid.grid_rows_by_docname[cdn];
        format_payment_history_row(grid_row);
    }
});

// Helper function to format payment history grid rows
function format_payment_history_row(grid_row) {
    if (!grid_row || !grid_row.doc) return;
    
    setTimeout(() => {
        try {
            // Get all cells in the row
            const cells = grid_row.row.find('.grid-row-column');
            if (!cells.length) return;
            
            // Add special styling based on record type
            const transaction_type = grid_row.doc.transaction_type;
            
            // Add visual indicator to the row
            $(grid_row.row).attr('data-type', transaction_type);
            
            // Style unreconciled payments differently
            if (transaction_type === "Unreconciled Payment") {
                $(grid_row.row).addClass('unreconciled-row');
                $(grid_row.row).css({
                    'background-color': '#f5f7fa',  // Light gray background
                    'font-style': 'italic'
                });
            }
            
            // Style donation payments differently
            if (transaction_type === "Donation Payment") {
                $(grid_row.row).addClass('donation-row');
                $(grid_row.row).css({
                    'background-color': '#fcf8e3',  // Light yellow background
                    'font-style': 'italic'
                });
            }
            
            // Format transaction type with appropriate icon
            let type_idx = grid_row.grid.fields.findIndex(f => f.fieldname === 'transaction_type');
            if (type_idx >= 0 && cells[type_idx]) {
                let type_icon = 'file-text';
                let icon_color = 'text-muted';
                
                if (transaction_type === 'Membership Invoice') {
                    type_icon = 'users';
                    icon_color = 'text-primary';
                }
                else if (transaction_type === 'Donation Payment') {
                    type_icon = 'heart';
                    icon_color = 'text-danger';
                }
                else if (transaction_type === 'Unreconciled Payment') {
                    type_icon = 'question-circle';
                    icon_color = 'text-muted';
                }
                
                const type_html = `<span>
                    <i class="fa fa-${type_icon} ${icon_color}" style="margin-right: 5px;"></i>
                    ${transaction_type || ''}
                </span>`;
                $(cells[type_idx]).html(type_html);
            }
            
            // Format invoice status with color if it exists
            const status = grid_row.doc.status;
            let status_idx = grid_row.grid.fields.findIndex(f => f.fieldname === 'status');
            if (status_idx >= 0 && cells[status_idx] && status && status !== 'N/A') {
                let status_color = 'gray';
                if (status === 'Paid') status_color = 'green';
                else if (status === 'Overdue') status_color = 'red';
                else if (status === 'Unpaid') status_color = 'orange';
                
                const status_html = `<span class="indicator ${status_color}">${status || ''}</span>`;
                $(cells[status_idx]).html(status_html);
            }
            
            // Format payment status with color
            const payment_status = grid_row.doc.payment_status;
            let payment_status_idx = grid_row.grid.fields.findIndex(f => f.fieldname === 'payment_status');
            if (payment_status_idx >= 0 && cells[payment_status_idx]) {
                let status_color = 'gray';
                if (payment_status === 'Paid') status_color = 'green';
                else if (payment_status === 'Overdue') status_color = 'red';
                else if (payment_status === 'Unpaid') status_color = 'orange';
                else if (payment_status === 'Partially Paid') status_color = 'blue';
                
                const status_html = `<span class="indicator ${status_color}">${payment_status || ''}</span>`;
                $(cells[payment_status_idx]).html(status_html);
            }
            
            // Format mandate status if it exists
            if (grid_row.doc.has_mandate) {
                const mandate_status = grid_row.doc.mandate_status;
                let mandate_idx = grid_row.grid.fields.findIndex(f => f.fieldname === 'mandate_status');
                if (mandate_idx >= 0 && cells[mandate_idx]) {
                    let mandate_color = 'gray';
                    if (mandate_status === 'Active') mandate_color = 'green';
                    else if (mandate_status === 'Expired' || mandate_status === 'Cancelled') mandate_color = 'red';
                    else if (mandate_status === 'Suspended') mandate_color = 'orange';
                    
                    const mandate_html = `<span class="indicator ${mandate_color}">${mandate_status || ''}</span>`;
                    $(cells[mandate_idx]).html(mandate_html);
                }
            }
            
            // Add reference document link if exists
            if (grid_row.doc.reference_doctype && grid_row.doc.reference_name) {
                let ref_type_idx = grid_row.grid.fields.findIndex(f => f.fieldname === 'reference_doctype');
                let ref_name_idx = grid_row.grid.fields.findIndex(f => f.fieldname === 'reference_name');
                
                if (ref_name_idx >= 0 && cells[ref_name_idx]) {
                    const ref_html = `<a href="/app/${grid_row.doc.reference_doctype.toLowerCase().replace(/ /g, '-')}/${grid_row.doc.reference_name}">${grid_row.doc.reference_name}</a>`;
                    $(cells[ref_name_idx]).html(ref_html);
                }
            }
            
        } catch (e) {
            console.error('Error formatting payment history row:', e);
        }
    }, 100);
}
