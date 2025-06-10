// Copyright (c) 2025, Your Name and contributors
// For license information, please see license.txt

// Import utility modules
frappe.require([
    '/assets/verenigingen/js/member/js_modules/payment-utils.js',
    '/assets/verenigingen/js/member/js_modules/chapter-utils.js',
    '/assets/verenigingen/js/member/js_modules/sepa-utils.js',
    '/assets/verenigingen/js/member/js_modules/termination-utils.js',
    '/assets/verenigingen/js/member/js_modules/volunteer-utils.js',
    '/assets/verenigingen/js/member/js_modules/ui-utils.js'
]);

frappe.ui.form.on('Member', {
    
    // ==================== FORM LIFECYCLE EVENTS ====================
    
    refresh: function(frm) {
        // Initialize UI and custom CSS
        UIUtils.add_custom_css();
        UIUtils.setup_payment_history_grid(frm);
        UIUtils.setup_member_id_display(frm);
        
        // Add action buttons for submitted documents
        if (frm.doc.docstatus === 1) {
            add_payment_buttons(frm);
        }
        
        // Add customer creation button if not exists
        add_customer_buttons(frm);
        
        // Add chapter management buttons
        add_chapter_buttons(frm);
        
        // Add view buttons for related records
        add_view_buttons(frm);
        
        // Add volunteer-related buttons
        add_volunteer_buttons(frm);
        
        // Add termination buttons and status display
        add_termination_buttons(frm);
        
        // Add suspension buttons
        add_suspension_buttons(frm);
        
        // Display termination status
        display_termination_status(frm);
        
        // Display suspension status
        display_suspension_status(frm);
        
        // Add fee management functionality
        add_fee_management_buttons(frm);
        
        // Add member ID management buttons
        add_member_id_buttons(frm);
        
        // Check SEPA mandate status
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.iban) {
            SepaUtils.check_sepa_mandate_status(frm);
        }
        
        // Show volunteer info if exists
        VolunteerUtils.show_volunteer_info(frm);
        
        // Show board memberships if any
        UIUtils.show_board_memberships(frm);
        
        // Load and display current subscription details
        load_subscription_summary(frm);
    },
    
    onload: function(frm) {
        // Set up form behavior on load
        setup_form_behavior(frm);
    },
    
    // ==================== FIELD EVENT HANDLERS ====================
    
    full_name: function(frm) {
        // Auto-generate full name from component fields when individual fields change
        update_full_name_from_components(frm);
    },
    
    first_name: function(frm) {
        update_full_name_from_components(frm);
    },
    
    middle_name: function(frm) {
        update_full_name_from_components(frm);
    },
    
    last_name: function(frm) {
        update_full_name_from_components(frm);
    },
    
    payment_method: function(frm) {
        UIUtils.handle_payment_method_change(frm);
    },
    
    iban: function(frm) {
        if (frm.doc.iban && frm.doc.payment_method === 'Direct Debit') {
            SepaUtils.check_sepa_mandate_status(frm);
        }
    },
    
    pincode: function(frm) {
        // Simple notification when postal code changes
        if (frm.doc.pincode && !frm.doc.primary_chapter) {
            frappe.show_alert({
                message: __('Postal code updated. You may want to assign a chapter based on this location.'),
                indicator: 'blue'
            }, 3);
        }
    }
});

// ==================== CHILD TABLE EVENT HANDLERS ====================

frappe.ui.form.on('Member Payment History', {
    payment_history_add: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.transaction_date) {
            frappe.model.set_value(cdt, cdn, 'transaction_date', frappe.datetime.get_today());
        }
    },
    
    amount: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.outstanding_amount) {
            frappe.model.set_value(cdt, cdn, 'outstanding_amount', row.amount || 0);
        }
    }
});

// ==================== BUTTON SETUP FUNCTIONS ====================

function add_payment_buttons(frm) {
    if (frm.doc.payment_status !== 'Paid') {
        frm.add_custom_button(__('Process Payment'), function() {
            PaymentUtils.process_payment(frm);
        }, __('Actions'));
        
        frm.add_custom_button(__('Mark as Paid'), function() {
            PaymentUtils.mark_as_paid(frm);
        }, __('Actions'));
    }
}

function add_customer_buttons(frm) {
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
}

function add_chapter_buttons(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
        callback: function(r) {
            if (r.message) {
                if (frm.doc.primary_chapter) {
                    frm.add_custom_button(__('View Chapter'), function() {
                        frappe.set_route('Form', 'Chapter', frm.doc.primary_chapter);
                    }, __('View'));
                }
                
                frm.add_custom_button(__('Assign Chapter'), function() {
                    frm.set_value('primary_chapter', '');
                    frm.refresh_field('primary_chapter');
                }, __('Actions'));
                
                // Add simple chapter suggestion when no chapter is assigned
                add_simple_chapter_suggestion(frm);
                
                // Add visual indicator for chapter membership
                if (frm.doc.primary_chapter && !frm.doc.__unsaved) {
                    frm.dashboard.add_indicator(__("Member of {0}", [frm.doc.primary_chapter]), "blue");
                }
                
                // Add debug button for postal code matching (development only)
                if (frappe.boot.developer_mode) {
                    frm.add_custom_button(__('Debug Postal Code'), function() {
                        UIUtils.show_debug_postal_code_info(frm);
                    }, __('Debug'));
                }
            }
        }
    });
}

function add_view_buttons(frm) {
    if (frm.doc.customer) {
        frm.add_custom_button(__('Customer'), function() {
            frappe.set_route('Form', 'Customer', frm.doc.customer);
        }, __('View'));
        
        frm.add_custom_button(__('Refresh Financial History'), function() {
            PaymentUtils.refresh_financial_history(frm);
        }, __('Actions'));
        
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
}

function add_volunteer_buttons(frm) {
    // Check if volunteer profile exists
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Volunteer',
            filters: {
                'member': frm.doc.name
            }
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                const volunteer = r.message[0];
                
                frm.add_custom_button(__('View Volunteer Profile'), function() {
                    frappe.set_route('Form', 'Volunteer', volunteer.name);
                }, __('View'));
                
                frm.add_custom_button(__('Volunteer Activities'), function() {
                    VolunteerUtils.show_volunteer_activities(volunteer.name);
                }, __('View'));
                
                frm.add_custom_button(__('Volunteer Assignments'), function() {
                    VolunteerUtils.show_volunteer_assignments(volunteer.name);
                }, __('View'));
            } else {
                frm.add_custom_button(__('Create Volunteer Profile'), function() {
                    VolunteerUtils.create_volunteer_from_member(frm);
                }, __('Actions'));
            }
        }
    });
}

function add_termination_buttons(frm) {
    // Check termination status and permissions first
    frappe.call({
        method: 'verenigingen.permissions.can_terminate_member_api',
        args: {
            member_name: frm.doc.name
        },
        callback: function(perm_result) {
            const can_terminate = perm_result.message;
            
            if (!can_terminate) {
                // User doesn't have permission, don't show termination buttons
                return;
            }
            
            // User has permission, check termination status
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_member_termination_status',
                args: {
                    member: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        const status = r.message;
                        
                        // Add terminate button if no active termination
                        if (!status.has_active_termination) {
                            let button_class = 'btn-danger';
                            let button_text = __('Terminate Membership');
                            
                            let btn = frm.add_custom_button(button_text, function() {
                                TerminationUtils.show_termination_dialog(frm.doc.name, frm.doc.full_name);
                            }, __('Actions'));
                            
                            if (btn && btn.addClass) {
                                btn.addClass(button_class + ' termination-button');
                            }
                        }
                        
                        
                        // Add view termination history button
                        frm.add_custom_button(__('Termination History'), function() {
                            TerminationUtils.show_termination_history(frm.doc.name);
                        }, __('View'));
                    }
                }
            });
        }
    });
}

function add_simple_chapter_suggestion(frm) {
    if (!frm.doc.__islocal && !frm.doc.primary_chapter && !$('.chapter-suggestion-container').length) {
        var $container = $('<div class="chapter-suggestion-container alert alert-info mt-2"></div>');
        $container.html(`
            <p><i class="fa fa-info-circle"></i> ${__("This member doesn't have a chapter assigned yet.")}</p>
            <p class="mb-0"><small class="text-muted">${__("Use the Chapter field above to assign this member to a chapter.")}</small></p>
        `);
        
        $(frm.fields_dict.primary_chapter.wrapper).append($container);
    }
}

// ==================== FORM SETUP FUNCTIONS ====================

function setup_form_behavior(frm) {
    // Set up member ID field behavior
    if (frm.doc.member_id) {
        frm.set_df_property('member_id', 'read_only', 1);
    }
    
    // Set up payment method dependent fields
    UIUtils.handle_payment_method_change(frm);
    
    // Set up organization user creation if enabled
    setup_organization_user_creation(frm);
}

function setup_organization_user_creation(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.verenigingen_settings.verenigingen_settings.get_organization_email_domain',
        callback: function(r) {
            if (r.message && r.message.organization_email_domain) {
                if (!frm.doc.user && frm.doc.docstatus === 1) {
                    frm.add_custom_button(__('Create Organization User'), function() {
                        UIUtils.create_organization_user(frm);
                    }, __('Actions'));
                }
            }
        }
    });
}


function add_member_id_buttons(frm) {
    // Check if user has permission to manage member IDs
    const user_roles = frappe.user_roles || [];
    const can_manage_member_ids = user_roles.includes('System Manager') || user_roles.includes('Membership Manager');
    
    if (!can_manage_member_ids) {
        return; // User doesn't have permission
    }
    
    // Add "Assign Member ID" button if member doesn't have one
    if (!frm.doc.member_id) {
        frm.add_custom_button(__('Assign Member ID'), function() {
            frappe.confirm(
                __('Are you sure you want to assign a member ID to {0}?', [frm.doc.full_name]),
                function() {
                    frm.call({
                        method: 'assign_member_id',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                }, 5);
                            } else if (r.message && r.message.message) {
                                frappe.msgprint(r.message.message);
                            }
                        }
                    });
                }
            );
        }, __('Member ID'));
    }
    
    // Add "View Member ID Statistics" button for System Managers
    if (user_roles.includes('System Manager')) {
        frm.add_custom_button(__('Member ID Statistics'), function() {
            show_member_id_statistics_dialog();
        }, __('Member ID'));
        
        frm.add_custom_button(__('Preview Next ID'), function() {
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member_id_manager.get_next_member_id_preview',
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__('Next member ID that will be assigned: {0}', [r.message.next_id]));
                    }
                }
            });
        }, __('Member ID'));
    }
}

function show_member_id_statistics_dialog() {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member_id_manager.get_member_id_statistics',
        callback: function(r) {
            if (r.message) {
                const stats = r.message;
                let html = `
                    <div class="member-id-stats">
                        <h4>Member ID Statistics</h4>
                        <table class="table table-bordered">
                            <tr><td><strong>Next ID to be assigned:</strong></td><td>${stats.next_id}</td></tr>
                            <tr><td><strong>Current counter value:</strong></td><td>${stats.current_counter}</td></tr>
                            <tr><td><strong>Highest assigned ID:</strong></td><td>${stats.highest_assigned}</td></tr>
                            <tr><td><strong>Total members with numeric IDs:</strong></td><td>${stats.total_with_numeric_ids}</td></tr>
                            <tr><td><strong>Gap count:</strong></td><td>${stats.gap_count}</td></tr>
                `;
                
                if (stats.gaps && stats.gaps.length > 0) {
                    html += `<tr><td><strong>Available gaps (first 10):</strong></td><td>${stats.gaps.join(', ')}</td></tr>`;
                }
                
                html += `</table></div>`;
                
                const dialog = new frappe.ui.Dialog({
                    title: __('Member ID Statistics'),
                    size: 'large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            options: html
                        }
                    ]
                });
                
                dialog.show();
            }
        }
    });
}

function add_fee_management_buttons(frm) {
    if (frm.doc.docstatus === 1) {
        // Add button to view current fee info
        frm.add_custom_button(__('View Fee Details'), function() {
            show_fee_details_dialog(frm);
        }, __('Fee Management'));
        
        // Add button to change fee if user has permission
        if (frappe.user.has_role(['System Manager', 'Membership Manager'])) {
            frm.add_custom_button(__('Override Membership Fee'), function() {
                show_fee_override_dialog(frm);
            }, __('Fee Management'));
        }
        
        // Add button to refresh subscription history
        if (frm.doc.customer) {
            frm.add_custom_button(__('Refresh Subscription History'), function() {
                refresh_subscription_history(frm);
            }, __('Fee Management'));
            
            frm.add_custom_button(__('Refresh Subscription Summary'), function() {
                load_subscription_summary(frm);
            }, __('Fee Management'));
        }
    }
}

function show_fee_details_dialog(frm) {
    frappe.call({
        method: 'get_current_membership_fee',
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                const fee_info = r.message;
                let html = `
                    <div class="fee-details">
                        <h4>Current Membership Fee Information</h4>
                        <table class="table table-bordered">
                            <tr><td><strong>Current Amount:</strong></td><td>${format_currency(fee_info.amount)}</td></tr>
                            <tr><td><strong>Source:</strong></td><td>${get_fee_source_label(fee_info.source)}</td></tr>
                `;
                
                if (fee_info.source === 'custom_override' && fee_info.reason) {
                    html += `<tr><td><strong>Override Reason:</strong></td><td>${fee_info.reason}</td></tr>`;
                }
                
                if (fee_info.membership_type) {
                    html += `<tr><td><strong>Membership Type:</strong></td><td>${fee_info.membership_type}</td></tr>`;
                }
                
                html += `</table></div>`;
                
                const dialog = new frappe.ui.Dialog({
                    title: __('Membership Fee Details'),
                    size: 'large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            options: html
                        }
                    ]
                });
                
                dialog.show();
            }
        }
    });
}

function show_fee_override_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Override Membership Fee'),
        size: 'large',
        fields: [
            {
                fieldtype: 'Currency',
                fieldname: 'new_fee_amount',
                label: __('New Fee Amount'),
                reqd: 1,
                description: __('Enter the new membership fee amount for this member')
            },
            {
                fieldtype: 'Small Text',
                fieldname: 'override_reason',
                label: __('Reason for Override'),
                reqd: 1,
                description: __('Explain why this member needs a different fee amount')
            },
            {
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        <h5>Important Notes:</h5>
                        <ul>
                            <li>This will update the member's subscription with the new amount</li>
                            <li>The change will be recorded in the fee change history</li>
                            <li>Active subscriptions will be cancelled and recreated</li>
                        </ul>
                    </div>
                `
            }
        ],
        primary_action_label: __('Apply Fee Override'),
        primary_action: function(values) {
            frappe.confirm(
                __('Are you sure you want to override the membership fee to {0}?', [format_currency(values.new_fee_amount)]),
                function() {
                    frm.set_value('membership_fee_override', values.new_fee_amount);
                    frm.set_value('fee_override_reason', values.override_reason);
                    
                    frm.save().then(() => {
                        dialog.hide();
                        frappe.show_alert({
                            message: __('Membership fee override applied successfully'),
                            indicator: 'green'
                        }, 5);
                    });
                }
            );
        }
    });
    
    dialog.show();
}

function get_fee_source_label(source) {
    const labels = {
        'custom_override': 'Custom Override',
        'membership_type': 'Membership Type Default',
        'none': 'No Fee Set'
    };
    return labels[source] || source;
}

function refresh_subscription_history(frm) {
    frappe.call({
        method: 'refresh_subscription_history',
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                frm.reload_doc();
                frappe.show_alert({
                    message: r.message.message || 'Subscription history refreshed',
                    indicator: 'green'
                }, 3);
            }
        }
    });
}

function display_termination_status(frm) {
    if (!frm.doc.name) return;
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_member_termination_status',
        args: {
            member: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                const status = r.message;
                
                // Update termination status HTML field
                update_termination_status_html(frm, status);
                
                // Add dashboard indicators
                add_termination_dashboard_indicators(frm, status);
            }
        }
    });
}

function update_termination_status_html(frm, status) {
    let html = '<div class="termination-status-display">';
    
    if (status.is_terminated && status.executed_requests && status.executed_requests.length > 0) {
        const term_data = status.executed_requests[0];
        html += `
            <div class="alert alert-danger">
                <h5><i class="fa fa-exclamation-triangle"></i> Membership Terminated</h5>
                <p><strong>Termination Type:</strong> ${term_data.termination_type}</p>
                <p><strong>Execution Date:</strong> ${frappe.datetime.str_to_user(term_data.execution_date)}</p>
                <p><strong>Request:</strong> <a href="/app/membership-termination-request/${term_data.name}">${term_data.name}</a></p>
            </div>
        `;
        
        
    } else if (status.pending_requests && status.pending_requests.length > 0) {
        const pending = status.pending_requests[0];
        const status_colors = {
            'Draft': 'warning',
            'Pending Approval': 'warning',
            'Approved': 'info'
        };
        const alert_class = status_colors[pending.status] || 'secondary';
        
        html += `
            <div class="alert alert-${alert_class}">
                <h5><i class="fa fa-clock-o"></i> Termination Request Pending</h5>
                <p><strong>Status:</strong> ${pending.status}</p>
                <p><strong>Type:</strong> ${pending.termination_type}</p>
                <p><strong>Request Date:</strong> ${frappe.datetime.str_to_user(pending.request_date)}</p>
                <p><strong>Request:</strong> <a href="/app/membership-termination-request/${pending.name}">${pending.name}</a></p>
            </div>
        `;
        
    } else {
        html += `
            <div class="alert alert-success">
                <h6><i class="fa fa-check-circle"></i> Active Membership</h6>
                <p>No termination requests or actions on record.</p>
            </div>
        `;
    }
    
    html += '</div>';
    
    // Update the HTML field
    if (frm.fields_dict.termination_status_html) {
        frm.fields_dict.termination_status_html.html(html);
    }
}

function add_termination_dashboard_indicators(frm, status) {
    if (status.is_terminated && status.executed_requests && status.executed_requests.length > 0) {
        const term_data = status.executed_requests[0];
        
        frm.dashboard.add_indicator(
            __('Membership Terminated'), 
            'red'
        );
        
        if (term_data.execution_date) {
            frm.dashboard.add_indicator(
                __('Terminated on {0}', [frappe.datetime.str_to_user(term_data.execution_date)]), 
                'grey'
            );
        }
        
    } else if (status.pending_requests && status.pending_requests.length > 0) {
        const pending = status.pending_requests[0];
        
        if (pending.status === 'Pending Approval') {
            frm.dashboard.add_indicator(
                __('Termination Pending Approval'), 
                'orange'
            );
        } else if (pending.status === 'Approved') {
            frm.dashboard.add_indicator(
                __('Termination Approved - Awaiting Execution'), 
                'yellow'
            );
        }
    }
}

// ==================== SUBSCRIPTION SUMMARY FUNCTIONS ====================

function load_subscription_summary(frm) {
    if (!frm.doc.customer || !frm.doc.name) {
        return;
    }
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.get_current_subscription_details',
        args: {
            member: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                update_subscription_summary_display(frm, r.message);
            }
        }
    });
}

function update_subscription_summary_display(frm, subscription_data) {
    let html = '<div class="subscription-summary-display">';
    
    if (subscription_data.error) {
        html += `
            <div class="alert alert-warning">
                <h6><i class="fa fa-exclamation-triangle"></i> Error Loading Subscriptions</h6>
                <p>${subscription_data.error}</p>
            </div>
        `;
    } else if (!subscription_data.has_subscription) {
        html += `
            <div class="alert alert-info">
                <h6><i class="fa fa-info-circle"></i> No Active Subscriptions</h6>
                <p>${subscription_data.message || 'This member has no active subscription plans.'}</p>
            </div>
        `;
    } else {
        html += `
            <div class="alert alert-success">
                <h6><i class="fa fa-check-circle"></i> Active Subscriptions (${subscription_data.count})</h6>
            </div>
        `;
        
        subscription_data.subscriptions.forEach(function(subscription) {
            html += `
                <div class="card mb-3">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <a href="/app/subscription/${subscription.name}">${subscription.name}</a>
                            <span class="badge badge-success float-right">${subscription.status}</span>
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <p><strong>Period:</strong> ${frappe.datetime.str_to_user(subscription.start_date)} - ${subscription.end_date ? frappe.datetime.str_to_user(subscription.end_date) : 'Ongoing'}</p>
                                <p><strong>Current Billing:</strong> ${frappe.datetime.str_to_user(subscription.current_invoice_start)} - ${frappe.datetime.str_to_user(subscription.current_invoice_end)}</p>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Total Amount:</strong> ${format_currency(subscription.total_amount)}</p>
                            </div>
                        </div>
            `;
            
            if (subscription.plans && subscription.plans.length > 0) {
                html += `
                    <h6>Subscription Plans:</h6>
                    <div class="table-responsive">
                        <table class="table table-sm table-bordered">
                            <thead>
                                <tr>
                                    <th>Plan</th>
                                    <th>Amount</th>
                                    <th>Billing Frequency</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                
                subscription.plans.forEach(function(plan) {
                    let billing_text = plan.billing_interval_count > 1 
                        ? `Every ${plan.billing_interval_count} ${plan.billing_interval}s`
                        : `${plan.billing_interval}ly`;
                    
                    html += `
                        <tr>
                            <td>${plan.plan_name}</td>
                            <td>${format_currency(plan.price, plan.currency)}</td>
                            <td>${billing_text}</td>
                        </tr>
                    `;
                });
                
                html += `
                            </tbody>
                        </table>
                    </div>
                `;
            }
            
            html += `
                    </div>
                </div>
            `;
        });
    }
    
    html += '</div>';
    
    // Update the HTML field
    if (frm.fields_dict.current_subscription_summary) {
        frm.fields_dict.current_subscription_summary.html(html);
    }
}

// ==================== NAME HANDLING FUNCTIONS ====================

function update_full_name_from_components(frm) {
    // Build full name with proper handling of name particles (tussenvoegsels)
    let name_parts = [];
    
    if (frm.doc.first_name && frm.doc.first_name.trim()) {
        name_parts.push(frm.doc.first_name.trim());
    }
    
    // Handle name particles (tussenvoegsels) - these should be lowercase when in the middle
    if (frm.doc.middle_name && frm.doc.middle_name.trim()) {
        let particles = frm.doc.middle_name.trim();
        // Ensure particles are lowercase when between first and last name
        name_parts.push(particles.toLowerCase());
    }
    
    if (frm.doc.last_name && frm.doc.last_name.trim()) {
        name_parts.push(frm.doc.last_name.trim());
    }
    
    let full_name = name_parts.join(' ');
    
    // Only update if the generated name is different and not empty
    if (full_name && frm.doc.full_name !== full_name) {
        frm.set_value('full_name', full_name);
    }
}

// ==================== SUSPENSION FUNCTIONS ====================

function add_suspension_buttons(frm) {
    if (!frm.doc.name) return;
    
    // Check if user can perform suspension actions
    frappe.call({
        method: 'verenigingen.api.suspension_api.can_suspend_member',
        args: {
            member_name: frm.doc.name
        },
        callback: function(perm_result) {
            const can_suspend = perm_result.message;
            
            if (!can_suspend) {
                return; // No permission, don't show buttons
            }
            
            // Get current suspension status
            frappe.call({
                method: 'verenigingen.api.suspension_api.get_suspension_status',
                args: {
                    member_name: frm.doc.name
                },
                callback: function(status_result) {
                    if (status_result.message) {
                        const status = status_result.message;
                        
                        if (status.is_suspended) {
                            // Member is suspended - show unsuspend button
                            let btn = frm.add_custom_button(__('Unsuspend Member'), function() {
                                show_unsuspension_dialog(frm);
                            }, __('Actions'));
                            
                            if (btn && btn.addClass) {
                                btn.addClass('btn-success suspension-button');
                            }
                        } else {
                            // Member is not suspended - show suspend button
                            let btn = frm.add_custom_button(__('Suspend Member'), function() {
                                show_suspension_dialog(frm);
                            }, __('Actions'));
                            
                            if (btn && btn.addClass) {
                                btn.addClass('btn-warning suspension-button');
                            }
                        }
                    }
                }
            });
        }
    });
}

function show_suspension_dialog(frm) {
    // First get suspension preview
    frappe.call({
        method: 'verenigingen.api.suspension_api.get_suspension_preview',
        args: {
            member_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                const preview = r.message;
                
                let preview_html = `
                    <div class="suspension-preview">
                        <h5>Suspension Impact</h5>
                        <ul>
                            <li><strong>Member Status:</strong> ${preview.member_status} → Suspended</li>
                `;
                
                if (preview.has_user_account) {
                    preview_html += `<li><strong>User Account:</strong> Will be disabled</li>`;
                }
                
                if (preview.active_teams > 0) {
                    preview_html += `<li><strong>Team Memberships:</strong> ${preview.active_teams} team(s) will be suspended</li>`;
                    if (preview.team_details && preview.team_details.length > 0) {
                        preview_html += `<li><strong>Teams:</strong> `;
                        preview_html += preview.team_details.map(t => `${t.team} (${t.role})`).join(', ');
                        preview_html += `</li>`;
                    }
                }
                
                if (preview.active_memberships > 0) {
                    preview_html += `<li><strong>Active Memberships:</strong> ${preview.active_memberships} membership(s) remain active</li>`;
                }
                
                preview_html += `</ul></div>`;
                
                const dialog = new frappe.ui.Dialog({
                    title: __('Suspend Member: {0}', [frm.doc.full_name]),
                    size: 'large',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            options: preview_html
                        },
                        {
                            fieldtype: 'Section Break',
                            label: __('Suspension Details')
                        },
                        {
                            fieldname: 'suspension_reason',
                            fieldtype: 'Small Text',
                            label: __('Reason for Suspension'),
                            reqd: 1,
                            description: __('Explain why this member is being suspended')
                        },
                        {
                            fieldtype: 'Column Break'
                        },
                        {
                            fieldname: 'suspend_user',
                            fieldtype: 'Check',
                            label: __('Suspend User Account'),
                            default: 1,
                            description: __('Disable the member\'s backend user account')
                        },
                        {
                            fieldname: 'suspend_teams',
                            fieldtype: 'Check',
                            label: __('Suspend Team Memberships'),
                            default: 1,
                            description: __('Remove member from all teams')
                        }
                    ],
                    primary_action_label: __('Suspend Member'),
                    primary_action: function(values) {
                        frappe.confirm(
                            __('Are you sure you want to suspend {0}?', [frm.doc.full_name]),
                            function() {
                                frappe.call({
                                    method: 'verenigingen.api.suspension_api.suspend_member',
                                    args: {
                                        member_name: frm.doc.name,
                                        suspension_reason: values.suspension_reason,
                                        suspend_user: values.suspend_user,
                                        suspend_teams: values.suspend_teams
                                    },
                                    callback: function(r) {
                                        if (r.message && r.message.success) {
                                            dialog.hide();
                                            frm.reload_doc();
                                        }
                                    }
                                });
                            }
                        );
                    }
                });
                
                dialog.show();
            }
        }
    });
}

function show_unsuspension_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Unsuspend Member: {0}', [frm.doc.full_name]),
        fields: [
            {
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        <h5>Unsuspension Process</h5>
                        <ul>
                            <li>Member status will be restored to previous state</li>
                            <li>User account will be reactivated</li>
                            <li>Team memberships require manual restoration</li>
                        </ul>
                    </div>
                `
            },
            {
                fieldname: 'unsuspension_reason',
                fieldtype: 'Small Text',
                label: __('Reason for Unsuspension'),
                reqd: 1,
                description: __('Explain why this member is being unsuspended')
            }
        ],
        primary_action_label: __('Unsuspend Member'),
        primary_action: function(values) {
            frappe.confirm(
                __('Are you sure you want to unsuspend {0}?', [frm.doc.full_name]),
                function() {
                    frappe.call({
                        method: 'verenigingen.api.suspension_api.unsuspend_member',
                        args: {
                            member_name: frm.doc.name,
                            unsuspension_reason: values.unsuspension_reason
                        },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                dialog.hide();
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }
    });
    
    dialog.show();
}

function display_suspension_status(frm) {
    if (!frm.doc.name) return;
    
    frappe.call({
        method: 'verenigingen.api.suspension_api.get_suspension_status',
        args: {
            member_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                const status = r.message;
                
                if (status.is_suspended) {
                    // Add dashboard indicator for suspended member
                    frm.dashboard.add_indicator(
                        __('Member Suspended'), 
                        'orange'
                    );
                    
                    if (status.user_suspended) {
                        frm.dashboard.add_indicator(
                            __('User Account Disabled'), 
                            'red'
                        );
                    }
                    
                    if (status.active_teams === 0) {
                        frm.dashboard.add_indicator(
                            __('No Active Teams'), 
                            'grey'
                        );
                    }
                }
            }
        }
    });
}