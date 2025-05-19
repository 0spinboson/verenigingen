// Copyright (c) 2025, Your Name and contributors
// For license information, please see license.txt

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
            
            if (frm.fields_dict.payment_history && frm.fields_dict.payment_history.grid && 
                frm.fields_dict.payment_history.grid.grid_rows) {
                frm.fields_dict.payment_history.grid.grid_rows.forEach(row => {
                    format_payment_history_row(row);
                });
            }
            
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
        
        if (frm.fields_dict.payment_history) {
            // Remove 'No.' column from the payment history grid
            setTimeout(function() {
                const gridWrapper = $(frm.fields_dict.payment_history.grid.wrapper);
                
                // Find and hide the idx column
                gridWrapper.find('.grid-heading-row .grid-row-check').hide();
                gridWrapper.find('.grid-heading-row .row-index').hide();
                
                // Hide idx column in all rows
                gridWrapper.find('.grid-body .data-row .row-index').hide();
                gridWrapper.find('.grid-body .data-row .grid-row-check').hide();
                
                // Add a class to enable custom styling via CSS
                gridWrapper.addClass('no-idx-column');
            }, 500);
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
        
        // Chapter-related buttons - check if chapter management is enabled
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
            callback: function(r) {
                if (r.message) {
                    // Only show chapter buttons if enabled
                    if (frm.doc.primary_chapter) {
                        frm.add_custom_button(__('View Chapter'), function() {
                            frappe.set_route('Form', 'Chapter', frm.doc.primary_chapter);
                        }, __('View'));
                    }
                    
                    frm.add_custom_button(__('Change Chapter'), function() {
                        suggest_chapter_for_member(frm);
                    }, __('Actions'));
                    
                    // Add chapter suggestion UI when no chapter is assigned
                    if (!frm.doc.__islocal && !frm.doc.primary_chapter && !$('.chapter-suggestion-container').length) {
                        var $container = $('<div class="chapter-suggestion-container alert alert-info mt-2"></div>');
                        $container.html(`
                            <p>${__("This member doesn't have a chapter assigned yet.")}</p>
                            <button class="btn btn-sm btn-primary suggest-chapter-btn">
                                ${__("Find a Chapter")}
                            </button>
                        `);
                        
                        $(frm.fields_dict.primary_chapter.wrapper).append($container);
                        
                        // Add click handler
                        $('.suggest-chapter-btn').on('click', function() {
                            suggest_chapter_for_member(frm);
                        });
                    }
                    
                    // Add a nice visual indicator in the form header if chapter is set
                    if (frm.doc.primary_chapter && !frm.doc.__unsaved) {
                        frm.dashboard.add_indicator(__("Member of {0}", [frm.doc.primary_chapter]), "blue");
                    }
                    
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
                } else {
                    // Hide chapter field if chapter management is disabled
                    frm.toggle_display('primary_chapter', false);
                    frm.toggle_display('chapter_and_volunteer_activity_section', false);
                    
                    if (frm.fields_dict.board_memberships_html) {
                        $(frm.fields_dict.board_memberships_html.wrapper).empty();
                    }
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
            
            // If there's a current mandate, add button to view it
            let currentMandate = null;
            if (frm.doc.sepa_mandates && frm.doc.sepa_mandates.length) {
                currentMandate = frm.doc.sepa_mandates.find(m => m.is_current);
            }
            
            if (currentMandate) {
                frm.add_custom_button(__('Current SEPA Mandate'), function() {
                    frappe.set_route('Form', 'SEPA Mandate', currentMandate.sepa_mandate);
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
        
        // Check for volunteer record and display details - UPDATED FOR NEW SCHEMA
        if (!frm.doc.__islocal && frm.fields_dict.volunteer_details_html) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Volunteer',
                    filters: {
                        'member': frm.doc.name
                    },
                    fields: ['name', 'volunteer_name', 'status', 'commitment_level', 'experience_level', 'preferred_work_style']
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        const volunteer = r.message[0];
                        
                        // Get volunteer skills
                        frappe.call({
                            method: 'frappe.client.get',
                            args: {
                                doctype: 'Volunteer',
                                name: volunteer.name
                            },
                            callback: function(r) {
                                if (r.message) {
                                    const volunteerDoc = r.message;
                                    let skillsHtml = '';
                                    
                                    // Use the new skills_and_qualifications field instead of volunteer_skills
                                    if (volunteerDoc.skills_and_qualifications && volunteerDoc.skills_and_qualifications.length > 0) {
                                        skillsHtml = '<div class="volunteer-skills"><h5>Skills</h5><ul>';
                                        volunteerDoc.skills_and_qualifications.forEach(function(skill) {
                                            skillsHtml += '<li>' + skill.volunteer_skill;
                                            if (skill.proficiency_level) {
                                                skillsHtml += ' <span class="text-muted">(' + skill.proficiency_level + ')</span>';
                                            }
                                            skillsHtml += '</li>';
                                        });
                                        skillsHtml += '</ul></div>';
                                    }

                                    // Add interests if available
                                    let interestsHtml = '';
                                    if (volunteerDoc.interests && volunteerDoc.interests.length > 0) {
                                        interestsHtml = '<div class="volunteer-interests"><h5>Areas of Interest</h5><div class="flex">';
                                        volunteerDoc.interests.forEach(function(interest) {
                                            interestsHtml += '<span class="badge badge-light mr-2 mb-2">' + 
                                                interest.interest_area + '</span>';
                                        });
                                        interestsHtml += '</div></div>';
                                    }
                                    
                                    // Create volunteer info HTML - Updated with new fields
                                    let html = `
                                        <div class="volunteer-info">
                                            <h4><a href="/app/volunteer/${volunteer.name}">${volunteer.volunteer_name}</a></h4>
                                            <div class="row">
                                                <div class="col-md-6">
                                                    <p><strong>Status:</strong> ${volunteer.status || 'Not specified'}</p>
                                                    <p><strong>Commitment:</strong> ${volunteer.commitment_level || 'Not specified'}</p>
                                                </div>
                                                <div class="col-md-6">
                                                    <p><strong>Experience:</strong> ${volunteer.experience_level || 'Not specified'}</p>
                                                    <p><strong>Work Style:</strong> ${volunteer.preferred_work_style || 'Not specified'}</p>
                                                </div>
                                            </div>
                                            ${interestsHtml}
                                            ${skillsHtml}
                                        </div>
                                    `;
                                    
                                    $(frm.fields_dict.volunteer_details_html.wrapper).html(html);
                                }
                            }
                        });
                    } else {
                        // No volunteer record found
                        $(frm.fields_dict.volunteer_details_html.wrapper).html(`
                            <div class="volunteer-info text-muted">
                                <p>No volunteer record linked to this member.</p>
                                <button class="btn btn-xs btn-default create-volunteer-btn">
                                    Create Volunteer Record
                                </button>
                            </div>
                        `);
                        
                        // Add click handler for create button
                        $(frm.fields_dict.volunteer_details_html.wrapper).find('.create-volunteer-btn').on('click', function() {
                            frm.events.createVolunteerRecord(frm);
                        });
                    }
                }
            });
        }
        
        // Add CSS for chapter selection interface
        frappe.dom.set_style(`
            .chapter-suggestion-container {
                margin-top: 10px;
                padding: 10px;
            }
            .suggested-chapter {
                font-weight: bold;
                color: var(--primary);
            }
        `);
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
            
            // Get form settings based on system configuration
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.get_member_form_settings',
                callback: function(r) {
                    if (r.message) {
                        // Toggle chapter field visibility based on settings
                        frm.toggle_display('primary_chapter', r.message.show_chapter_field);
                        frm.toggle_display('chapter_and_volunteer_activity_section', r.message.show_chapter_field);
                        
                        // Update chapter field label if needed
                        if (r.message.chapter_field_label) {
                            frm.set_df_property('primary_chapter', 'label', r.message.chapter_field_label);
                        }
                    }
                }
            });
        }
    },
    
    primary_address: function(frm) {
        // If address is set and chapter is not, suggest chapter
        if (frm.doc.primary_address && !frm.doc.primary_chapter) {
            // First check if chapter management is enabled
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
                callback: function(r) {
                    if (r.message) {
                        suggest_chapter_from_address(frm);
                    }
                }
            });
        }
    },
    
    createVolunteerRecord: function(frm) {
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
                    'personal_email': frm.doc.email || '',  // Personal email from member
                    'status': 'Active',  // Default to Active
                    'start_date': frappe.datetime.get_today()  // Set start date
                };
            
                // Create new volunteer doc
                frappe.new_doc('Volunteer');
            }
        });
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
        const show_bank_details = ['Direct Debit', 'Bank Transfer'].includes(frm.doc.payment_method);
        
        frm.toggle_display(['bank_details_section'], show_bank_details);
        frm.toggle_reqd(['iban', 'bank_account_name'], is_direct_debit);
    },
    
    iban: function(frm) {
        // When IBAN changes, only format it correctly - don't check for mandate yet
        if (frm.doc.payment_method === 'Direct Debit' && frm.doc.iban) {
            // Format the IBAN
            const formattedIban = formatIBAN(frm.doc.iban);
            if (formattedIban !== frm.doc.iban) {
                frm.set_value('iban', formattedIban);
                // Don't do anything else here - we'll check for mandates after save
            }
        }
    },
    
    after_save: function(frm) {
        // After saving, if payment method is Direct Debit and we have IBAN
        // and bank account name, check for mandate
        if (frm.doc.payment_method === 'Direct Debit' && 
            frm.doc.iban && frm.doc.bank_account_name) {
            checkForExistingMandate(frm);
        }
    },
    
    bank_account_name: function(frm) {
        // Don't do anything when bank account name changes
        // We'll check for mandates after save
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
    
    is_current: function(frm, cdt, cdn) {
        // When setting a mandate as current, unset others
        const row = locals[cdt][cdn];
        
        if (row.is_current) {
            // Unset current on other mandates
            frm.doc.sepa_mandates.forEach(function(mandate) {
                if (mandate.name !== cdn && mandate.is_current) {
                    frappe.model.set_value(mandate.doctype, mandate.name, 'is_current', 0);
                }
            });
        }
    }
});

// Function to suggest chapters based on address
function suggest_chapter_from_address(frm) {
    // First check if chapter management is enabled
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
        callback: function(r) {
            if (!r.message) {
                return;
            }
            
            // Get the address details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Address',
                    name: frm.doc.primary_address
                },
                callback: function(r) {
                    if (r.message) {
                        const address = r.message;
                        
                        // Call the suggestion function with address details
                        suggest_chapter_for_member(frm, {
                            postal_code: address.pincode,
                            state: address.state,
                            city: address.city
                        });
                    }
                }
            });
        }
    });
}

// Main function to suggest chapters for a member
function suggest_chapter_for_member(frm, location_data) {
    // First check if chapter management is enabled
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.is_chapter_management_enabled',
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint(__('Chapter management is disabled in system settings.'));
                return;
            }
            
            let postal_code, state, city;
            
            if (location_data) {
                postal_code = location_data.postal_code;
                state = location_data.state;
                city = location_data.city;
            }
            
            // If we have a primary address but no location data, fetch it
            if (!location_data && frm.doc.primary_address) {
                return suggest_chapter_from_address(frm);
            }
            
            // Call server method to find matching chapters
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member',
                args: {
                    member_name: frm.doc.name,
                    postal_code: postal_code || null,
                    state: state || null,
                    city: city || null
                },
                callback: function(r) {
                    if (!r.message) {
                        // If no suggestions, show the simple chapter selector
                        show_chapter_selector(frm);
                        return;
                    }
                    
                    const results = r.message;
                    
                    if (results.disabled) {
                        frappe.msgprint(__('Chapter management is disabled in system settings.'));
                        return;
                    }
                    
                    // Prioritize matches in this order: postal > region > city
                    let best_matches = results.matches_by_postal?.length ? results.matches_by_postal :
                                      results.matches_by_region?.length ? results.matches_by_region :
                                      results.matches_by_city?.length ? results.matches_by_city :
                                      [];
                                      
                    if (best_matches.length === 1) {
                        // Single best match - suggest directly
                        suggest_single_chapter(frm, best_matches[0], location_data);
                    } else if (best_matches.length > 1) {
                        // Multiple matches - show selection with matches highlighted
                        show_chapter_selector(frm, best_matches);
                    } else {
                        // No matches - show standard selector
                        show_chapter_selector(frm);
                    }
                }
            });
        }
    });
}

// Function to suggest a single chapter
function suggest_single_chapter(frm, chapter, location_data) {
    let location_text = "";
    if (location_data) {
        if (location_data.postal_code) {
            location_text = __("postal code {0}", [location_data.postal_code]);
        } else if (location_data.city) {
            location_text = location_data.city;
        } else if (location_data.state) {
            location_text = location_data.state;
        }
    }
    
    frappe.confirm(
        __('Based on your location in {0}, we suggest joining the {1} chapter. Would you like to join this chapter?', 
        [location_text || 'your area', chapter.name]),
        function() {
            // Yes - set primary chapter
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: 'Member',
                    name: frm.doc.name,
                    fieldname: 'primary_chapter',
                    value: chapter.name
                },
                callback: function(r) {
                    if(!r.exc) {
                        frappe.msgprint(__('You have joined the {0} chapter', [chapter.name]));
                        frm.reload_doc();
                    }
                }
            });
        },
        function() {
            // No - show the standard chapter selection dialog
            show_chapter_selector(frm);
        }
    );
}

// Function to show chapter selector dialog
function show_chapter_selector(frm, suggested_chapters) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Chapter',
            filters: {
                'published': 1
            },
            fields: ['name', 'region', 'introduction']
        },
        callback: function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint(__('No active chapters found'));
                return;
            }
            
            const chapters = r.message;
            
            // Format options for the select field
            let options = chapters.map(function(chapter) {
                return {
                    value: chapter.name,
                    label: __("{0} ({1})", [chapter.name, chapter.region])
                };
            });
            
            // Determine the most suitable default
            let default_chapter = frm.doc.primary_chapter;
            
            // If we have suggested chapters, use the first one as default
            if (suggested_chapters && suggested_chapters.length) {
                default_chapter = suggested_chapters[0].name;
            }
            
            const d = new frappe.ui.Dialog({
                title: __('Select Chapter'),
                fields: [
                    {
                        label: __('Chapter'),
                        fieldname: 'chapter',
                        fieldtype: 'Select',
                        options: options,
                        reqd: 1,
                        default: default_chapter
                    },
                    {
                        label: __('Note'),
                        fieldname: 'note',
                        fieldtype: 'Small Text',
                        depends_on: 'eval:!doc.chapter'
                    }
                ],
                primary_action_label: __('Join Chapter'),
                primary_action: function() {
                    const values = d.get_values();
                    
                    if (!values.chapter) {
                        frappe.msgprint(__('Please select a chapter'));
                        return;
                    }
                    
                    if (values.chapter === frm.doc.primary_chapter) {
                        frappe.msgprint(__('No change in chapter'));
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
                                // Log the change if a note was provided
                                if (values.note) {
                                    frappe.call({
                                        method: 'frappe.client.insert',
                                        args: {
                                            doc: {
                                                doctype: 'Comment',
                                                comment_type: 'Info',
                                                reference_doctype: 'Member',
                                                reference_name: frm.doc.name,
                                                content: __('Changed chapter to {0}. Note: {1}', 
                                                    [values.chapter, values.note])
                                            }
                                        }
                                    });
                                }
                                
                                frappe.msgprint(__('Successfully joined the {0} chapter', [values.chapter]));
                                frm.reload_doc();
                                d.hide();
                            }
                        }
                    });
                }
            });
            
            d.show();
            
            // If we have suggested chapters, highlight them in the dialog
            if (suggested_chapters && suggested_chapters.length) {
                setTimeout(function() {
                    // Add a note about the suggestions
                    const suggested_names = suggested_chapters.map(c => c.name).join(', ');
                    const suggestion_note = $(`<div class="alert alert-info mt-3">
                        <span>${__('Suggested chapters based on your location:')} <strong>${suggested_names}</strong></span>
                    </div>`);
                    
                    $(d.body).find('.form-layout').prepend(suggestion_note);
                }, 500);
            }
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

// Helper function to prompt for SEPA mandate creation
function promptCreateMandate(frm) {
    if (!frm.doc.iban || !frm.doc.bank_account_name) {
        frappe.msgprint(__('Please enter both IBAN and Account Holder Name before creating a SEPA mandate'));
        return;
    }
    
    frappe.confirm(
        __('Would you like to create a new SEPA mandate for this bank account?'),
        function() {
            // Yes - show dialog for mandate type
            selectMandateType(frm);
        },
        function() {
            // No - do nothing
            frappe.show_alert(__('No SEPA mandate created. Payment by direct debit requires a mandate.'), 5);
        }
    );
}

// Function to select mandate type (one-off or continuous)
function selectMandateType(frm) {
    const d = new frappe.ui.Dialog({
        title: __('Create SEPA Mandate'),
        fields: [
            {
                label: __('Mandate Type'),
                fieldname: 'mandate_type',
                fieldtype: 'Select',
                options: [
                    {label: __('One-off payment'), value: 'OOFF'},
                    {label: __('Recurring payments'), value: 'RCUR'}
                ],
                default: 'RCUR',
                reqd: 1
            },
            {
                label: __('Sign Date'),
                fieldname: 'sign_date',
                fieldtype: 'Date',
                default: frappe.datetime.get_today(),
                reqd: 1
            },
            {
                label: __('Used for'),
                fieldname: 'usage_section',
                fieldtype: 'Section Break'
            },
            {
                label: __('Memberships'),
                fieldname: 'used_for_memberships',
                fieldtype: 'Check',
                default: 1
            },
            {
                label: __('Donations'),
                fieldname: 'used_for_donations',
                fieldtype: 'Check',
                default: 0
            }
        ],
        primary_action_label: __('Create'),
        primary_action(values) {
            createSEPAMandate(frm, values);
            d.hide();
        }
    });
    
    d.show();
}

function createSEPAMandate(frm, values) {
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.create_sepa_mandate_from_bank_details',
        args: {
            member: frm.doc.name,
            iban: frm.doc.iban,
            bic: frm.doc.bic || '',
            account_holder_name: frm.doc.bank_account_name,
            mandate_type: values.mandate_type,
            sign_date: values.sign_date,
            used_for_memberships: values.used_for_memberships,
            used_for_donations: values.used_for_donations
        },
        callback: function(r) {
            if (r.message) {
                // MODIFICATION: Reload the doc instead of directly modifying it
                frm.reload_doc();
                
                frappe.show_alert({
                    message: __('SEPA Mandate created successfully'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

// Function to format IBAN
function formatIBAN(iban) {
    if (!iban) return '';
    
    // Remove spaces and convert to uppercase
    iban = iban.replace(/\s+/g, '').toUpperCase();
    
    // Format with spaces every 4 characters
    return iban.replace(/(.{4})/g, '$1 ').trim();
}

// Function to get IBAN from a mandate
function get_doc_mandate_iban(mandate_name) {
    // This is an async operation but we just want a simple check,
    // so we'll use the result when it comes back
    return frappe.db.get_value('SEPA Mandate', mandate_name, 'iban')
        .then(r => {
            if (r && r.message) {
                return r.message.iban;
            }
            return '';
        });
}

function checkForExistingMandate(frm) {
    if (frm.doc.payment_method !== 'Direct Debit' || !frm.doc.iban || !frm.doc.bank_account_name) {
        return;
    }
    
    // Use a dedicated server method to check and handle mandates
    frappe.call({
        method: 'vereiningen.verenigingen.doctype.member.member.check_and_handle_sepa_mandate',
        args: {
            member: frm.doc.name,
            iban: frm.doc.iban
        },
        callback: function(r) {
            if (r.message) {
                if (r.message.action === 'create_new') {
                    // Need to create a new mandate - show dialog after a delay
                    setTimeout(() => promptCreateMandate(frm), 1000);
                } else if (r.message.action === 'use_existing') {
                    // Server handled setting an existing mandate as current
                    frappe.show_alert({
                        message: __('Using existing SEPA mandate for this IBAN'),
                        indicator: 'green'
                    }, 5);
                    frm.reload_doc();
                }
                // If 'none_needed', do nothing
            }
        }
    });
}
