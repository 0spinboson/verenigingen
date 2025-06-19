// Member form utilities - review functionality integrated into main member.js

// Define minimal UIUtils to prevent errors
window.UIUtils = window.UIUtils || {
    add_custom_css: function() {
        if (!$('#member-custom-css').length) {
            $('head').append(`
                <style id="member-custom-css">
                    .volunteer-info-card {
                        border: 1px solid #dee2e6;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    .board-memberships {
                        background: #f8f9fa;
                        padding: 10px;
                        border-radius: 5px;
                        margin: 10px 0;
                    }
                </style>
            `);
        }
    },
    setup_payment_history_grid: function(frm) {
        // Basic implementation
        if (frm.fields_dict.payment_history) {
            $(frm.fields_dict.payment_history.grid.wrapper).addClass('payment-history-grid');
        }
    },
    setup_member_id_display: function(frm) {
        // Basic implementation - just set read-only, skip styling to avoid errors
        if (frm.doc.member_id) {
            try {
                frm.set_df_property('member_id', 'read_only', 1);
                console.debug('Member ID set to read-only');
            } catch (e) {
                console.debug('Failed to set member_id read-only:', e);
            }
        }
    },
    show_board_memberships: function(frm) {
        // Placeholder - can be enhanced later
        console.log('Board memberships functionality placeholder');
    },
    setup_contact_requests_section: function(frm) {
        // Add contact requests section to member form
        if (!frm.is_new() && frm.doc.name) {
            frm.add_custom_button(__('Contact Requests'), function() {
                frappe.route_options = {"member": frm.doc.name};
                frappe.set_route("List", "Member Contact Request");
            }, __("View"));
            
            // Load and display recent contact requests
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member_contact_request.member_contact_request.get_member_contact_requests',
                args: {
                    member: frm.doc.name,
                    limit: 5
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        UIUtils.render_contact_requests_summary(frm, r.message);
                    }
                }
            });
        }
    },
    render_contact_requests_summary: function(frm, requests) {
        // Create a summary of recent contact requests
        let html = `
            <div class="contact-requests-summary">
                <h5>${__("Recent Contact Requests")}</h5>
                <div class="requests-list">
        `;
        
        requests.forEach(function(request) {
            const status_color = {
                'Open': 'orange',
                'In Progress': 'blue', 
                'Resolved': 'green',
                'Closed': 'gray'
            }[request.status] || 'gray';
            
            html += `
                <div class="request-item" style="padding: 8px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${request.subject}</strong><br>
                        <small style="color: #666;">${request.request_type} • ${moment(request.request_date).format('MMM DD, YYYY')}</small>
                    </div>
                    <span class="indicator ${status_color}">${request.status}</span>
                </div>
            `;
        });
        
        html += `
                </div>
                <div style="margin-top: 10px;">
                    <button class="btn btn-xs btn-default" onclick="frappe.set_route('List', 'Member Contact Request', {'member': '${frm.doc.name}'})">
                        ${__("View All Contact Requests")}
                    </button>
                </div>
            </div>
        `;
        
        // Add to the form - we'll add this to the dashboard area
        if (!frm.contact_requests_wrapper) {
            frm.contact_requests_wrapper = $('<div>').appendTo(frm.layout.wrapper.find('.form-dashboard'));
        }
        frm.contact_requests_wrapper.html(html);
    },
    handle_payment_method_change: function(frm) {
        // Basic implementation
        const is_direct_debit = frm.doc.payment_method === 'Direct Debit';
        const show_bank_details = ['Direct Debit', 'Bank Transfer'].includes(frm.doc.payment_method);
        
        frm.toggle_reqd('iban', is_direct_debit);
        frm.toggle_display('iban', show_bank_details);
        frm.toggle_display('bic', show_bank_details);
        frm.toggle_display('bank_name', show_bank_details);
    },
    create_organization_user: function(frm) {
        frappe.msgprint('Organization user creation functionality will be available after full utilities load.');
    },
    show_debug_postal_code_info: function(frm) {
        console.log('Debug postal code info placeholder');
    }
};

// Define minimal other Utils to prevent errors
window.SepaUtils = window.SepaUtils || {
    check_sepa_mandate_status: function(frm) {
        console.log('SEPA mandate status check placeholder');
    },
    create_sepa_mandate_with_dialog: function(frm) {
        frappe.msgprint('SEPA mandate creation will be available after full utilities load.');
    }
};

window.ChapterUtils = window.ChapterUtils || {
    suggest_chapter_from_address: function(frm) {
        console.log('Chapter suggestion placeholder');
    },
    suggest_chapter_for_member: function(frm) {
        console.log('Chapter suggestion placeholder');
    }
};

window.VolunteerUtils = window.VolunteerUtils || {
    show_volunteer_info: function(frm) {
        console.log('Volunteer info placeholder');
    },
    show_volunteer_activities: function(name) {
        console.log('Volunteer activities placeholder');
    },
    show_volunteer_assignments: function(name) {
        console.log('Volunteer assignments placeholder');
    },
    create_volunteer_from_member: function(frm) {
        // Original implementation: Get organization email domain and set route options
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
    }
};

window.PaymentUtils = window.PaymentUtils || {
    process_payment: function(frm) {
        frappe.msgprint('Payment processing will be available after full utilities load.');
    },
    mark_as_paid: function(frm) {
        frappe.msgprint('Mark as paid will be available after full utilities load.');
    },
    refresh_financial_history: function(frm) {
        console.log('Financial history refresh placeholder');
    }
};

window.TerminationUtils = window.TerminationUtils || {
    show_termination_dialog: function(member, name) {
        frappe.msgprint('Termination functionality will be available after full utilities load.');
    },
    show_termination_history: function(member) {
        console.log('Termination history placeholder');
    }
};

// Initialize verenigingen namespace
frappe.provide("verenigingen.member_form");

verenigingen.member_form = {
    initialize_member_form: function(frm) {
        console.log('Initializing member form with contact requests');
        
        // Set up basic UI
        if (window.UIUtils) {
            UIUtils.add_custom_css();
            UIUtils.setup_member_id_display(frm);
            UIUtils.setup_payment_history_grid(frm);
            UIUtils.setup_contact_requests_section(frm);
        }
        
        // Set up form buttons and actions
        if (!frm.is_new()) {
            this.setup_custom_buttons(frm);
        }
    },
    
    setup_custom_buttons: function(frm) {
        // Add buttons for member-specific actions
        if (frm.doc.name) {
            // Contact request button is already added in UIUtils.setup_contact_requests_section
            
            // Add volunteer creation button if not already a volunteer
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Volunteer',
                    filters: {'member': frm.doc.name},
                    fieldname: 'name'
                },
                callback: function(r) {
                    if (!r.message) {
                        frm.add_custom_button(__('Create Volunteer'), function() {
                            VolunteerUtils.create_volunteer_from_member(frm);
                        }, __("Actions"));
                    }
                }
            });
        }
    }
};

frappe.ui.form.on('Member', {
    
    // ==================== FORM LIFECYCLE EVENTS ====================
    
    refresh: function(frm) {
        console.log('Member form refresh - initializing');
        
        // Prevent multiple initializations
        if (frm._member_form_initialized) {
            console.log('Member form already initialized, skipping');
            return;
        }
        
        // Initialize member form (utilities loaded at top level)
        verenigingen.member_form.initialize_member_form(frm);
        frm._member_form_initialized = true;
    },
    
    onload: function(frm) {
        // Set up form behavior on load
        setup_form_behavior(frm);
    },
    
    // ==================== FIELD EVENT HANDLERS ====================
    
    full_name: function(frm) {
        if (frm.doc.full_name) {
            let full_name = [frm.doc.first_name, frm.doc.middle_name, frm.doc.last_name]
                .filter(name => name && name.trim())
                .join(' ');
            
            if (frm.doc.full_name !== full_name && full_name) {
                frm.set_value('full_name', full_name);
            }
        }
    },
    
    payment_method: function(frm) {
        if (window.UIUtils) {
            UIUtils.handle_payment_method_change(frm);
        }
    },
    
    iban: function(frm) {
        if (frm.doc.iban && frm.doc.payment_method === 'Direct Debit' && window.SepaUtils) {
            SepaUtils.check_sepa_mandate_status(frm);
        }
    },
    
    pincode: function(frm) {
        // Auto-suggest chapter when postal code changes
        if (frm.doc.pincode && window.ChapterUtils) {
            setTimeout(() => {
                ChapterUtils.suggest_chapter_from_address(frm);
            }, 1000);
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
    if (frm.doc.payment_status !== 'Paid' && window.PaymentUtils) {
        frm.add_custom_button(__('Process Payment'), function() {
            PaymentUtils.process_payment(frm);
        }, __('Actions'));
        
        frm.add_custom_button(__('Mark as Paid'), function() {
            PaymentUtils.mark_as_paid(frm);
        }, __('Actions'));
    }
}

function add_customer_buttons(frm) {
    if (!frm.doc.customer && !frm.custom_buttons[__('Create Customer')]) {
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

function add_membership_buttons(frm) {
    // Add button to create a new membership (original implementation)
    if (!frm.custom_buttons[__('Create Membership')]) {
        frm.add_custom_button(__('Create Membership'), function() {
            frappe.new_doc('Membership', {
                'member': frm.doc.name,
                'member_name': frm.doc.full_name,
                'email': frm.doc.email,
                'mobile_no': frm.doc.mobile_no,
                'start_date': frappe.datetime.get_today()
            });
        }, __('Actions'));
    }
    
    // Add button to view memberships
    if (!frm.custom_buttons[__('View Memberships')]) {
        frm.add_custom_button(__('View Memberships'), function() {
            frappe.set_route('List', 'Membership', {'member': frm.doc.name});
        }, __('View'));
    }
    
    // Add button to view current membership
    if (frm.doc.current_membership_details && !frm.custom_buttons[__('Current Membership')]) {
        frm.add_custom_button(__('Current Membership'), function() {
            frappe.set_route('Form', 'Membership', frm.doc.current_membership_details);
        }, __('View'));
    }
}

function add_chapter_buttons(frm) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
        callback: function(r) {
            if (r.message) {
                // Get member's current chapters and add view button if they have any
                get_member_current_chapters(frm.doc.name).then((chapters) => {
                    if (chapters.length > 0) {
                        if (chapters.length === 1) {
                            frm.add_custom_button(__('View Chapter'), function() {
                                frappe.set_route('Form', 'Chapter', chapters[0]);
                            }, __('View'));
                        } else {
                            // Multiple chapters - add dropdown
                            const chapter_dropdown = frm.add_custom_button(__('View Chapters'), function() {}, __('View'));
                            chapters.forEach(chapter => {
                                frm.add_custom_button(chapter, function() {
                                    frappe.set_route('Form', 'Chapter', chapter);
                                }, __('View'), chapter_dropdown);
                            });
                        }
                    }
                });
                
                frm.add_custom_button(__('Change Chapter'), function() {
                    if (window.ChapterUtils) {
                        ChapterUtils.suggest_chapter_for_member(frm);
                    }
                }, __('Actions'));
                
                // Add chapter suggestion UI when no chapter is assigned
                add_chapter_suggestion_UI(frm);
                
                // Chapter indicator is handled in main member form JS
                
                // Add debug button for postal code matching (development only)
                if (frappe.boot.developer_mode && window.UIUtils) {
                    frm.add_custom_button(__('Debug Postal Code'), function() {
                        UIUtils.show_debug_postal_code_info(frm);
                    }, __('Debug'));
                }
            }
        },
        error: function(r) {
            // If API call fails, still add basic chapter button if chapter exists
            console.log('Error checking chapter management, adding basic chapter button');
            get_member_current_chapters(frm.doc.name).then((chapters) => {
                if (chapters.length > 0) {
                    frm.add_custom_button(__('View Chapter'), function() {
                        frappe.set_route('Form', 'Chapter', chapters[0]);
                    }, __('View'));
                }
            });
        }
    });
}

function add_view_buttons(frm) {
    if (frm.doc.customer) {
        frm.add_custom_button(__('Customer'), function() {
            frappe.set_route('Form', 'Customer', frm.doc.customer);
        }, __('View'));
        
        frm.add_custom_button(__('Refresh Financial History'), function() {
            if (window.PaymentUtils) {
                PaymentUtils.refresh_financial_history(frm);
            }
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
    // Add create volunteer button (always available)
    if (!frm.custom_buttons[__('Create Volunteer')]) {
        frm.add_custom_button(__('Create Volunteer'), function() {
            if (window.VolunteerUtils) {
                VolunteerUtils.create_volunteer_from_member(frm);
            }
        }, __('Actions'));
    }
    
    // Add button to view existing volunteer record if any (original implementation)
    if (!frm.custom_buttons[__('View Volunteer')]) {
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
    }
}

function add_user_buttons(frm) {
    // Add button to create user (original implementation)
    if (!frm.doc.user && frm.doc.email && !frm.custom_buttons[__('Create User')]) {
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
    
    // Add button to view linked user
    if (frm.doc.user && !frm.custom_buttons[__('User')]) {
        frm.add_custom_button(__('User'), function() {
            frappe.set_route('Form', 'User', frm.doc.user);
        }, __('View'));
    }
}

function add_termination_buttons(frm) {
    // Check termination status and add appropriate buttons
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
                        if (window.TerminationUtils) {
                            TerminationUtils.show_termination_dialog(frm.doc.name, frm.doc.full_name);
                        }
                    }, __('Actions'));
                    
                    if (btn && btn.addClass) {
                        btn.addClass(button_class + ' termination-button');
                    }
                }
                
                
                // Add view termination history button
                frm.add_custom_button(__('Termination History'), function() {
                    if (window.TerminationUtils) {
                        TerminationUtils.show_termination_history(frm.doc.name);
                    }
                }, __('View'));
            }
        },
        error: function(r) {
            // If API call fails, still add basic termination button
            console.log('Error checking termination status, adding basic termination button');
            let btn = frm.add_custom_button(__('Terminate Membership'), function() {
                if (window.TerminationUtils) {
                    TerminationUtils.show_termination_dialog(frm.doc.name, frm.doc.full_name);
                }
            }, __('Actions'));
            
            if (btn && btn.addClass) {
                btn.addClass('btn-danger termination-button');
            }
        }
    });
}

function add_chapter_suggestion_UI(frm) {
    if (!frm.doc.__islocal && !$('.chapter-suggestion-container').length) {
        // Check if member has any chapters assigned
        get_member_current_chapters(frm.doc.name).then((chapters) => {
            if (chapters.length === 0) {
                var $container = $('<div class="chapter-suggestion-container alert alert-info mt-2"></div>');
                $container.html(`
                    <p>${__("This member doesn't have a chapter assigned yet.")}</p>
                    <button class="btn btn-sm btn-primary suggest-chapter-btn">
                        ${__("Find a Chapter")}
                    </button>
                `);
                
                // Append to the current chapter display field wrapper
                $(frm.fields_dict.current_chapter_display.wrapper).append($container);
                
                $('.suggest-chapter-btn').on('click', function() {
                    if (window.ChapterUtils) {
                        ChapterUtils.suggest_chapter_for_member(frm);
                    }
                });
            }
        });
    }
}

// ==================== FORM SETUP FUNCTIONS ====================

function setup_form_behavior(frm) {
    // Set up member ID field behavior
    if (frm.doc.member_id) {
        frm.set_df_property('member_id', 'read_only', 1);
    }
    
    // Set up payment method dependent fields
    if (window.UIUtils) {
        UIUtils.handle_payment_method_change(frm);
    }
    
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
                        if (window.UIUtils) {
                            UIUtils.create_organization_user(frm);
                        }
                    }, __('Actions'));
                }
            }
        }
    });
}


// Member form utilities namespace
frappe.provide("verenigingen.member_form");

verenigingen.member_form = {
    initialize_member_form: function(frm) {
        console.log('Initializing member form for:', frm.doc.name);
        
        // Initialize UI and custom CSS
        if (window.UIUtils) {
            UIUtils.add_custom_css();
            UIUtils.setup_payment_history_grid(frm);
            UIUtils.setup_member_id_display(frm);
        }
        
        // Update chapter display if member exists
        if (frm.doc.name && !frm.doc.__islocal) {
            console.log('Calling refresh_chapter_display for member:', frm.doc.name);
            this.refresh_chapter_display(frm);
        } else {
            console.log('Not calling refresh_chapter_display - doc name:', frm.doc.name, 'islocal:', frm.doc.__islocal);
        }
        
        // Application review is now handled in the main member.js file
        
        // Set up buttons immediately without clearing (to prevent disappearing)
        this.setup_all_buttons(frm);
        
        // Check SEPA mandate status
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.iban && window.SepaUtils) {
            SepaUtils.check_sepa_mandate_status(frm);
        }
        
        // Show volunteer info if exists
        if (window.VolunteerUtils) {
            VolunteerUtils.show_volunteer_info(frm);
        }
        
        // Show board memberships if any
        if (window.UIUtils) {
            UIUtils.show_board_memberships(frm);
        }
    },
    
    setup_all_buttons: function(frm) {
        console.log('Setting up all buttons for member form');
        
        // Add action buttons for submitted documents
        if (frm.doc.docstatus === 1) {
            add_payment_buttons(frm);
        }
        
        // Add customer creation button if not exists
        add_customer_buttons(frm);
        
        // Add user creation/view buttons
        add_user_buttons(frm);
        
        // Add membership creation/view buttons
        add_membership_buttons(frm);
        
        // Add chapter management buttons
        add_chapter_buttons(frm);
        
        // Add view buttons for related records
        add_view_buttons(frm);
        
        // Add volunteer-related buttons
        add_volunteer_buttons(frm);
        
        // Add termination buttons
        add_termination_buttons(frm);
        
        // Add debug button to manually show chapter info
        if (frm.doc.name && !frm.doc.__islocal) {
            frm.add_custom_button(__('Show Chapter Info'), function() {
                verenigingen.member_form.refresh_chapter_display(frm);
            }, __('Debug'));
        }
        
        console.log('All member form buttons setup complete');
    },
    
    refresh_chapter_display: function(frm) {
        // Refresh the chapter display information
        console.log('refresh_chapter_display called for:', frm.doc.name);
        if (!frm.doc.name || frm.doc.__islocal) {
            console.log('Skipping chapter display - no name or local doc');
            return;
        }
        
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.member.member.get_member_chapter_display_html',
            args: {
                member_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    console.log('Chapter display HTML received:', r.message);
                    
                    // Try multiple insertion strategies
                    let chapter_html = `
                        <div class="member-chapter-info" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 6px; border: 1px solid #dee2e6;">
                            <h5 style="margin-bottom: 10px; color: #495057;">
                                <i class="fa fa-map-marker" style="margin-right: 8px;"></i>
                                Chapter Membership
                            </h5>
                            <div class="chapter-content">
                                ${r.message}
                            </div>
                        </div>
                    `;
                    
                    // Remove existing display first
                    $('.member-chapter-info').remove();
                    
                    // Strategy 1: Insert after chapter_assigned_date field
                    if (frm.fields_dict.chapter_assigned_date) {
                        $(frm.fields_dict.chapter_assigned_date.wrapper).after(chapter_html);
                        console.log('Inserted chapter info after chapter_assigned_date field');
                    }
                    // Strategy 2: Insert after chapter_assigned_by field  
                    else if (frm.fields_dict.chapter_assigned_by) {
                        $(frm.fields_dict.chapter_assigned_by.wrapper).after(chapter_html);
                        console.log('Inserted chapter info after chapter_assigned_by field');
                    }
                    // Strategy 3: Insert after member details section
                    else if (frm.fields_dict.member_details_section) {
                        $(frm.fields_dict.member_details_section.wrapper).after(chapter_html);
                        console.log('Inserted chapter info after member_details_section');
                    }
                    // Strategy 4: Insert at the top of the form
                    else {
                        $(frm.wrapper).find('.form-layout').first().prepend(chapter_html);
                        console.log('Inserted chapter info at top of form');
                    }
                }
            },
            error: function(r) {
                console.log('Error refreshing chapter display:', r);
            }
        });
    },
    
    
    initialize_member_form_basic: function(frm) {
        // Basic initialization without utilities
        console.log('Loading member form with basic functionality (utilities not available)');
        
        // Add action buttons for submitted documents
        if (frm.doc.docstatus === 1) {
            add_payment_buttons(frm);
        }
        
        // Add customer creation button if not exists
        add_customer_buttons(frm);
        
        // Add user creation/view buttons
        add_user_buttons(frm);
        
        // Add membership creation/view buttons
        add_membership_buttons(frm);
        
        // Add chapter management buttons
        add_chapter_buttons(frm);
        
        // Add view buttons for related records
        add_view_buttons(frm);
        
        // Add volunteer-related buttons
        add_volunteer_buttons(frm);
        
        // Add termination buttons
        add_termination_buttons(frm);
    }
};

// ==================== HELPER FUNCTIONS ====================

function get_member_current_chapters(member_name) {
    // Get list of chapters a member belongs to using safe server method
    return new Promise((resolve, reject) => {
        if (!member_name) {
            resolve([]);
            return;
        }
        
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.member.member.get_member_current_chapters',
            args: {
                member_name: member_name
            },
            callback: function(r) {
                if (r.message) {
                    // Extract chapter names from the returned chapter objects
                    const chapters = r.message.map(ch => ch.chapter || ch.parent).filter(ch => ch);
                    resolve(chapters);
                } else {
                    resolve([]);
                }
            },
            error: function(r) {
                console.error('Error getting member chapters:', r);
                resolve([]);
            }
        });
    });
}

console.log("Member form scripts and review functionality loaded");