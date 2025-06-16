// Copyright (c) 2025, Your Name and contributors
// For license information, please see license.txt
// Cache buster: v2025-01-13-001

// Test if this file is loading
console.log('Member.js file is loading - v2025-01-13-001');

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
        // Test if JavaScript is loading
        console.log('Member form refresh event triggered for:', frm.doc.name || 'new document');
        
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
        
        // Add user account management buttons
        add_user_account_buttons(frm);
        
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
        
        // Display amendment status
        display_amendment_status(frm);
        
        // Display suspension status
        display_suspension_status(frm);
        
        // Add fee management functionality
        add_fee_management_buttons(frm);
        
        // Ensure fee management section visibility
        ensure_fee_management_section_visibility(frm);
        
        // Also ensure visibility after a short delay (in case form is still loading)
        setTimeout(() => {
            ensure_fee_management_section_visibility(frm);
        }, 500);
        
        // Add member ID management buttons
        add_member_id_buttons(frm);
        
        // Button to manually refresh fee section visibility
        if (frappe.user.has_role(['System Manager', 'Membership Manager', 'Verenigingen Administrator'])) {
            frm.add_custom_button(__('Refresh Fee Section'), function() {
                ensure_fee_management_section_visibility(frm);
                frappe.show_alert('Fee section visibility refreshed', 3);
            }, __('Fee Management'));
            
        }
        
        // Check SEPA mandate status (debounced to avoid multiple rapid calls)
        check_sepa_mandate_status_debounced(frm);
        
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
        
        // Initialize IBAN tracking for change detection
        frm._previous_iban = frm.doc.iban;
        
        // Ensure fee management section visibility on load
        ensure_fee_management_section_visibility(frm);
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
        // Only update UI elements, don't prompt for mandate creation during field changes
        check_sepa_mandate_status_debounced(frm);
    },
    
    iban: function(frm) {
        // Auto-derive BIC from IBAN if BIC is empty
        if (frm.doc.iban && !frm.doc.bic) {
            // Clean the IBAN first
            const cleanIban = frm.doc.iban.replace(/\s+/g, '').toUpperCase();
            
            // Only update IBAN if it actually changed (to prevent recursion)
            if (cleanIban !== frm.doc.iban) {
                frm.set_value('iban', cleanIban);
                return; // Exit and let the next trigger handle BIC derivation
            }
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.derive_bic_from_iban',
                args: {
                    iban: cleanIban
                },
                callback: function(r) {
                    if (r.message && r.message.bic) {
                        frm.set_value('bic', r.message.bic);
                        frappe.show_alert({
                            message: __('BIC/SWIFT code automatically derived: {0}', [r.message.bic]),
                            indicator: 'blue'
                        }, 3);
                    } else if (cleanIban.length >= 4) {
                        // Show message for unsupported bank/country
                        frappe.show_alert({
                            message: __('Could not automatically derive BIC for this IBAN. Please enter manually.'),
                            indicator: 'orange'
                        }, 4);
                    }
                },
                error: function(r) {
                    console.error('Error deriving BIC from IBAN:', r);
                }
            });
        }
        
        // Update UI elements to show current SEPA status
        // Mandate discrepancy checking is now handled by scheduled task
        check_sepa_mandate_status_debounced(frm);
    },
    
    pincode: function(frm) {
        // Simple notification when postal code changes
        if (frm.doc.pincode && !frm.doc.current_chapter_display) {
            frappe.show_alert({
                message: __('Postal code updated. You may want to assign a chapter based on this location.'),
                indicator: 'blue'
            }, 3);
        }
    },
    
    after_save: function(frm) {
        // SEPA mandate discrepancy checking is now handled by scheduled task
        // No real-time processing needed here
        
        // Still show basic UI updates after save
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.iban && !frm.doc.__islocal) {
            // Just update the UI to show current SEPA status
            check_sepa_mandate_status_debounced(frm);
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

function add_user_account_buttons(frm) {
    // Only show user account buttons for members with email addresses
    if (!frm.doc.email) {
        return;
    }
    
    if (!frm.doc.user) {
        // Show create user account button if no user exists
        frm.add_custom_button(__('Create User Account'), function() {
            frappe.confirm(
                __('Create a user account for {0} to access member portal pages?', [frm.doc.full_name]),
                function() {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.member.member.create_member_user_account',
                        args: {
                            member_name: frm.doc.name,
                            send_welcome_email: true
                        },
                        callback: function(r) {
                            if (r.message) {
                                if (r.message.success) {
                                    frappe.show_alert({
                                        message: r.message.message,
                                        indicator: 'green'
                                    }, 5);
                                    frm.refresh();
                                } else {
                                    frappe.msgprint({
                                        message: r.message.error || r.message.message,
                                        indicator: 'red'
                                    });
                                }
                            }
                        }
                    });
                }
            );
        }, __('Actions'));
    } else {
        // Show user account info if user exists
        frm.add_custom_button(__('View User Account'), function() {
            frappe.set_route('Form', 'User', frm.doc.user);
        }, __('View'));
        
        // Add dashboard indicator for user account
        frm.dashboard.add_indicator(__("Has User Account"), "green");
    }
}

function add_chapter_buttons(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
        callback: function(r) {
            if (r.message) {
                if (frm.doc.current_chapter_display) {
                    frm.add_custom_button(__('View Chapter'), function() {
                        frappe.set_route('Form', 'Chapter', frm.doc.current_chapter_display);
                    }, __('View'));
                }
                
                frm.add_custom_button(__('Assign Chapter'), function() {
                    frm.set_value('current_chapter_display', '');
                    frm.refresh_field('current_chapter_display');
                }, __('Actions'));
                
                // Add simple chapter suggestion when no chapter is assigned
                add_simple_chapter_suggestion(frm);
                
                // Add visual indicator for chapter membership
                if (frm.doc.current_chapter_display && !frm.doc.__unsaved) {
                    frm.dashboard.add_indicator(__("Member of {0}", [frm.doc.current_chapter_display]), "blue");
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
    if (!frm.doc.__islocal && !frm.doc.current_chapter_display && !$('.chapter-suggestion-container').length) {
        var $container = $('<div class="chapter-suggestion-container alert alert-info mt-2"></div>');
        $container.html(`
            <p><i class="fa fa-info-circle"></i> ${__("This member doesn't have a chapter assigned yet.")}</p>
            <p class="mb-0"><small class="text-muted">${__("Use the Chapter field above to assign this member to a chapter.")}</small></p>
        `);
        
        $(frm.fields_dict.current_chapter_display.wrapper).append($container);
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
                        method: 'ensure_member_id',
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
        
        frm.add_custom_button(__('Debug Member ID Assignment'), function() {
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.debug_member_id_assignment',
                args: {
                    member_name: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        let message = '<h4>Member ID Assignment Debug Info</h4><table class="table table-bordered">';
                        for (let key in r.message) {
                            message += `<tr><td><strong>${key}:</strong></td><td>${r.message[key]}</td></tr>`;
                        }
                        message += '</table>';
                        
                        frappe.msgprint({
                            title: __('Debug Information'),
                            message: message,
                            wide: true
                        });
                    }
                }
            });
        }, __('Member ID'));
        
        // Add force assign button for System Managers
        if (user_roles.includes('System Manager')) {
            frm.add_custom_button(__('Force Assign Member ID'), function() {
                frappe.confirm(
                    __('Force assign a member ID to {0}? This bypasses normal assignment rules.', [frm.doc.full_name]),
                    function() {
                        frm.call({
                            method: 'force_assign_member_id',
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
        if (frappe.user.has_role(['System Manager', 'Membership Manager', 'Verenigingen Administrator'])) {
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

function ensure_fee_management_section_visibility(frm) {
    // Ensure fee management section is visible for authorized users
    const hasRequiredRole = frappe.user.has_role(['System Manager', 'Membership Manager', 'Verenigingen Administrator']);
    const shouldShow = !frm.doc.__islocal && hasRequiredRole;
    
    if (shouldShow) {
        // Force show the section and all related fields
        frm.set_df_property('fee_management_section', 'hidden', 0);
        frm.set_df_property('fee_management_section', 'depends_on', '');
        frm.set_df_property('membership_fee_override', 'hidden', 0);
        frm.set_df_property('fee_override_reason', 'hidden', 0);
        frm.set_df_property('fee_override_date', 'hidden', 0);
        frm.set_df_property('fee_override_by', 'hidden', 0);
        frm.set_df_property('fee_change_history_section', 'hidden', 0);
        frm.set_df_property('fee_change_history', 'hidden', 0);
        
        // Also use toggle_display as backup
        frm.toggle_display('fee_management_section', true);
        frm.toggle_display('membership_fee_override', true);
        frm.toggle_display('fee_override_reason', true);
        frm.toggle_display('fee_override_date', true);
        frm.toggle_display('fee_override_by', true);
        frm.toggle_display('fee_change_history_section', true);
        frm.toggle_display('fee_change_history', true);
        
        // Force refresh the fields
        frm.refresh_field('membership_fee_override');
        frm.refresh_field('fee_override_reason');
        frm.refresh_field('fee_override_date');
        frm.refresh_field('fee_override_by');
        frm.refresh_field('fee_change_history');
        
        // Direct DOM manipulation to ensure visibility
        setTimeout(() => {
            $('[data-fieldname="fee_management_section"]').show();
            $('[data-fieldname="membership_fee_override"]').show();
            $('[data-fieldname="fee_override_reason"]').show();
            $('[data-fieldname="fee_override_date"]').show();
            $('[data-fieldname="fee_override_by"]').show();
        }, 100);
    } else {
        frm.toggle_display('fee_management_section', false);
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

function display_amendment_status(frm) {
    if (!frm.doc.name) return;
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.membership_amendment_request.membership_amendment_request.get_member_pending_contribution_amendments',
        args: {
            member_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                const amendments = r.message;
                let amendment_html = '<div class="amendment-status-container" style="margin: 10px 0;">';
                
                for (let amendment of amendments) {
                    let status_color = 'orange';
                    let alert_class = 'alert-warning';
                    if (amendment.status === 'Approved') {
                        status_color = 'green';
                        alert_class = 'alert-success';
                    }
                    if (amendment.status === 'Rejected') {
                        status_color = 'red';
                        alert_class = 'alert-danger';
                    }
                    
                    amendment_html += `
                        <div class="alert ${alert_class}" style="padding: 12px; margin: 8px 0; border-left: 4px solid var(--${status_color});">
                            <div class="row">
                                <div class="col-md-8">
                                    <h6 style="margin: 0 0 5px 0;"><i class="fa fa-edit"></i> ${amendment.amendment_type}</h6>
                                    <p style="margin: 0;"><strong>Amount:</strong> ${frappe.format(amendment.requested_amount, {fieldtype: 'Currency'})}</p>
                                    <p style="margin: 5px 0 0 0;"><small><strong>Reason:</strong> ${amendment.reason}</small></p>
                                </div>
                                <div class="col-md-4 text-right">
                                    <span class="badge badge-${status_color} badge-lg" style="font-size: 12px; padding: 4px 8px;">${amendment.status}</span>
                                    <br><small style="color: #666;">Effective: ${frappe.datetime.str_to_user(amendment.effective_date)}</small>
                                    <br><a href="/app/membership-amendment-request/${amendment.name}" class="btn btn-xs btn-default" style="margin-top: 5px;">
                                        View Amendment
                                    </a>
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                amendment_html += '</div>';
                
                // Try injecting the content directly as a dashboard element as a fallback
                let amendment_displayed = false;
                
                // First try the standard HTML field approach
                if (frm.fields_dict.amendment_status_html) {
                    try {
                        frm.fields_dict.amendment_status_html.$wrapper.html(amendment_html);
                        frm.set_df_property('amendment_status_section', 'depends_on', '');
                        frm.set_df_property('amendment_status_section', 'hidden', 0);
                        frm.toggle_display('amendment_status_section', true);
                        frm.toggle_display('amendment_status_html', true);
                        
                        // Try to expand collapsible section
                        setTimeout(() => {
                            const sectionField = frm.get_field('amendment_status_section');
                            if (sectionField && sectionField.collapse) {
                                sectionField.collapse(false);
                            }
                            
                            const sectionEl = $('[data-fieldname="amendment_status_section"]');
                            const collapseToggle = sectionEl.find('.collapse-indicator, .octicon-chevron-down, .octicon-chevron-right');
                            if (collapseToggle.length > 0) {
                                collapseToggle.click();
                            }
                            
                            // Check if it's actually visible after all attempts
                            const htmlEl = $('[data-fieldname="amendment_status_html"]');
                            if (htmlEl.is(':visible')) {
                                amendment_displayed = true;
                            }
                        }, 200);
                        
                    } catch (e) {
                        console.error('Error setting HTML field:', e);
                    }
                }
                
                // Fallback: Add as dashboard comment if HTML field doesn't work
                setTimeout(() => {
                    if (!amendment_displayed) {
                        // Clear any existing amendment dashboard elements
                        frm.dashboard.clear_comment();
                        
                        // Add as dashboard element
                        const dashboard_html = `
                            <div class="alert alert-info" style="margin: 10px 0;">
                                <h5><i class="fa fa-info-circle"></i> Pending Fee Amendment</h5>
                                ${amendment_html}
                            </div>
                        `;
                        
                        frm.dashboard.add_comment(dashboard_html, 'blue', true);
                    }
                }, 500);
                
                // Add dashboard indicator
                frm.dashboard.add_indicator(
                    __('Pending Amendments: {0}', [amendments.length]), 
                    'orange'
                );
            } else {
                // Hide the section if no amendments
                if (frm.fields_dict.amendment_status_html) {
                    frm.toggle_display('amendment_status_section', false);
                    frm.toggle_display('amendment_status_html', false);
                }
            }
        },
        error: function(r) {
            console.error('Error loading amendment status:', r);
            // Hide the section on error
            if (frm.fields_dict.amendment_status_html) {
                frm.toggle_display('amendment_status_section', false);
            }
        }
    });
}

// ==================== SEPA MANDATE OPTIMIZATION ====================

// Debounced SEPA mandate status check to avoid rapid API calls
let sepa_check_timeout;
function check_sepa_mandate_status_debounced(frm) {
    // Clear any existing timeout
    if (sepa_check_timeout) {
        clearTimeout(sepa_check_timeout);
    }
    
    // Set a new timeout to check SEPA status after 300ms of inactivity
    sepa_check_timeout = setTimeout(function() {
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.iban) {
            SepaUtils.check_sepa_mandate_status(frm);
        } else {
            // Clear SEPA UI if conditions aren't met
            if (window.SepaUtils && window.SepaUtils.clear_sepa_ui_elements) {
                SepaUtils.clear_sepa_ui_elements(frm);
            }
        }
    }, 300);
}

function check_sepa_mandate_and_prompt_creation(frm, context = 'general') {
    // Simplified function - only update UI, no more real-time prompting
    // SEPA mandate discrepancy checking is now handled by scheduled task
    
    if (!frm.doc.iban || frm.doc.payment_method !== 'Direct Debit') {
        return;
    }
    
    // Just update the UI to show current SEPA status
    if (window.SepaUtils && window.SepaUtils.check_sepa_mandate_status) {
        SepaUtils.check_sepa_mandate_status(frm);
    }
}