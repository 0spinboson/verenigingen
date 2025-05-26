frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Add application review buttons if member is pending
        if (frm.doc.application_status === 'Pending' && frm.doc.status === 'Pending') {
            // Check if user has appropriate permissions
            if (frappe.user.has_role(['Association Manager', 'Membership Manager']) || 
                is_chapter_board_member_with_permissions(frm)) {
                
                // Add review section
                add_review_section(frm);
                
                // Add approve button
                frm.add_custom_button(__('Approve Application'), function() {
                    show_approval_dialog(frm);
                }, __('Review'));
                
                // Add reject button
                frm.add_custom_button(__('Reject Application'), function() {
                    show_rejection_dialog(frm);
                }, __('Review'));
                
                // Add request more info button
                frm.add_custom_button(__('Request More Info'), function() {
                    request_more_info(frm);
                }, __('Review'));
            }
        }
        
        // Show review status if already reviewed
        if (frm.doc.application_status && frm.doc.application_status !== 'Pending') {
            show_review_status(frm);
        }
        
        // Add suggested chapter info
        if (frm.doc.suggested_chapter && !frm.doc.primary_chapter) {
            frm.dashboard.add_comment(
                __('Suggested Chapter: {0} (based on postal code)', [frm.doc.suggested_chapter]),
                'blue'
            );
        }
    },
    
    // Auto-suggest chapter when postal code is entered
    postal_code: function(frm) {
        if (frm.doc.postal_code) {
            suggest_chapter_for_member(frm);
        }
    }
});

function add_review_section(frm) {
    // Add HTML field to show application details prominently
    var review_html = `
        <div class="review-section alert alert-warning">
            <h4>${__('Membership Application Review')}</h4>
            <div class="row">
                <div class="col-md-6">
                    <p><strong>${__('Application Date')}:</strong> ${frappe.datetime.str_to_user(frm.doc.application_date)}</p>
                    <p><strong>${__('Suggested Chapter')}:</strong> ${frm.doc.suggested_chapter || __('None')}</p>
                </div>
                <div class="col-md-6">
                    <p><strong>${__('Age')}:</strong> ${frm.doc.age || __('Not calculated')}</p>
                    <p><strong>${__('Payment Method')}:</strong> ${frm.doc.payment_method || __('Not specified')}</p>
                </div>
            </div>
            ${frm.doc.notes ? `<p><strong>${__('Motivation')}:</strong><br>${frm.doc.notes}</p>` : ''}
        </div>
    `;
    
    // Add to dashboard
    frm.dashboard.add_comment(review_html, 'yellow', true);
}

function show_approval_dialog(frm) {
    // Get membership types
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Membership Type',
            filters: { is_active: 1 },
            fields: ['name', 'membership_fee']
        },
        callback: function(r) {
            var membership_types = r.message || [];
            
            var d = new frappe.ui.Dialog({
                title: __('Approve Membership Application'),
                fields: [
                    {
                        fieldname: 'membership_type',
                        fieldtype: 'Select',
                        label: __('Membership Type'),
                        options: membership_types.map(t => t.name).join('\n'),
                        reqd: 1
                    },
                    {
                        fieldname: 'create_invoice',
                        fieldtype: 'Check',
                        label: __('Create Invoice'),
                        default: 1,
                        description: __('Generate an invoice for the first membership fee')
                    },
                    {
                        fieldname: 'assign_chapter',
                        fieldtype: 'Link',
                        label: __('Assign to Chapter'),
                        options: 'Chapter',
                        default: frm.doc.suggested_chapter
                    },
                    {
                        fieldname: 'welcome_message',
                        fieldtype: 'Small Text',
                        label: __('Additional Welcome Message'),
                        description: __('Optional personalized message to include in welcome email')
                    }
                ],
                primary_action_label: __('Approve'),
                primary_action: function(values) {
                    // Update chapter if changed
                    if (values.assign_chapter && values.assign_chapter !== frm.doc.primary_chapter) {
                        frappe.model.set_value(frm.doctype, frm.docname, 'primary_chapter', values.assign_chapter);
                    }
                    
                    // Call approval method
                    frappe.call({
                        method: 'verenigingen.verenigingen.web_form.membership_application.approve_membership_application',
                        args: {
                            member_name: frm.doc.name,
                            create_invoice: values.create_invoice,
                            membership_type: values.membership_type
                        },
                        freeze: true,
                        freeze_message: __('Approving application...'),
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Application approved successfully!'),
                                    indicator: 'green'
                                }, 5);
                                d.hide();
                                frm.reload_doc();
                            }
                        }
                    });
                }
            });
            
            d.show();
        }
    });
}

function show_rejection_dialog(frm) {
    var d = new frappe.ui.Dialog({
        title: __('Reject Membership Application'),
        fields: [
            {
                fieldname: 'reason',
                fieldtype: 'Small Text',
                label: __('Reason for Rejection'),
                reqd: 1,
                description: __('This will be sent to the applicant')
            },
            {
                fieldname: 'internal_notes',
                fieldtype: 'Small Text',
                label: __('Internal Notes'),
                description: __('For internal use only, not sent to applicant')
            }
        ],
        primary_action_label: __('Reject'),
        primary_action: function(values) {
            frappe.call({
                method: 'verenigingen.verenigingen.web_form.membership_application.reject_membership_application',
                args: {
                    member_name: frm.doc.name,
                    reason: values.reason
                },
                freeze: true,
                freeze_message: __('Rejecting application...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        // Add internal notes if provided
                        if (values.internal_notes) {
                            frappe.model.set_value(frm.doctype, frm.docname, 
                                'review_notes', 
                                (frm.doc.review_notes || '') + '\n\nInternal: ' + values.internal_notes
                            );
                        }
                        
                        frappe.show_alert({
                            message: __('Application rejected'),
                            indicator: 'red'
                        }, 5);
                        d.hide();
                        frm.reload_doc();
                    }
                }
            });
        }
    });
    
    d.show();
}

function request_more_info(frm) {
    var d = new frappe.ui.Dialog({
        title: __('Request More Information'),
        fields: [
            {
                fieldname: 'info_needed',
                fieldtype: 'Small Text',
                label: __('Information Needed'),
                reqd: 1,
                description: __('Describe what additional information you need from the applicant')
            }
        ],
        primary_action_label: __('Send Request'),
        primary_action: function(values) {
            // Update status to "Under Review"
            frappe.model.set_value(frm.doctype, frm.docname, 'application_status', 'Under Review');
            
            // Send email to applicant
            frappe.call({
                method: 'frappe.core.doctype.communication.email.make',
                args: {
                    recipients: frm.doc.email,
                    subject: __('Additional Information Required for Your Membership Application'),
                    content: `
                        <p>Dear ${frm.doc.first_name},</p>
                        <p>Thank you for your membership application. We need some additional information to process your application:</p>
                        <p><strong>${values.info_needed}</strong></p>
                        <p>Please reply to this email with the requested information.</p>
                        <p>Best regards,<br>The Membership Team</p>
                    `,
                    doctype: frm.doctype,
                    name: frm.docname,
                    send_email: 1
                },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({
                            message: __('Request sent to applicant'),
                            indicator: 'blue'
                        }, 5);
                        d.hide();
                        frm.save();
                    }
                }
            });
        }
    });
    
    d.show();
}

function show_review_status(frm) {
    var status_color = {
        'Approved': 'green',
        'Rejected': 'red',
        'Under Review': 'orange'
    };
    
    var status_html = `
        <div class="review-status alert alert-${status_color[frm.doc.application_status] || 'info'}">
            <h5>${__('Application Status')}: ${__(frm.doc.application_status)}</h5>
            ${frm.doc.reviewed_by ? `<p>${__('Reviewed by')}: ${frm.doc.reviewed_by}</p>` : ''}
            ${frm.doc.review_date ? `<p>${__('Review date')}: ${frappe.datetime.str_to_user(frm.doc.review_date)}</p>` : ''}
            ${frm.doc.review_notes ? `<p>${__('Notes')}: ${frm.doc.review_notes}</p>` : ''}
        </div>
    `;
    
    frm.set_df_property('board_memberships_html', 'options', status_html);
}

function is_chapter_board_member_with_permissions(frm) {
    // Check if current user is a board member of the suggested chapter with appropriate permissions
    if (!frm.doc.suggested_chapter) return false;
    
    // This would need a server call to check properly
    // For now, returning false - you'd implement the actual check
    return false;
}

function suggest_chapter_for_member(frm) {
    if (!frm.doc.postal_code) return;
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.chapter.chapter.suggest_chapter_for_member',
        args: {
            member_name: frm.doc.name,
            postal_code: frm.doc.postal_code,
            state: frm.doc.state,
            city: frm.doc.city
        },
        callback: function(r) {
            if (r.message) {
                var suggestions = r.message;
                
                if (suggestions.matches_by_postal && suggestions.matches_by_postal.length > 0) {
                    // Auto-suggest the first postal match
                    var suggested = suggestions.matches_by_postal[0];
                    frappe.model.set_value(frm.doctype, frm.docname, 'suggested_chapter', suggested.name);
                    
                    frappe.show_alert({
                        message: __('Chapter suggested based on postal code: {0}', [suggested.name]),
                        indicator: 'blue'
                    }, 5);
                }
            }
        }
    });
}
