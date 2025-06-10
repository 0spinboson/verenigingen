/**
 * Client-side functionality for reviewing member applications
 */

frappe.provide("verenigingen.member_review");

// Add to Member form
frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Only show for pending applications
        if (frm.doc.application_status === 'Pending' && frm.doc.status === 'Pending') {
            verenigingen.member_review.setup_review_section(frm);
        }
        
        // Show payment status for approved applications
        if (frm.doc.application_status === 'Active') {
            verenigingen.member_review.show_membership_details(frm);
        }
        
        // Show refund options for rejected with payment
        if (frm.doc.application_status === 'Rejected' && frm.doc.application_payment) {
            verenigingen.member_review.show_refund_options(frm);
        }
    },
    
    // Auto-calculate age when birth date changes
    birth_date: function(frm) {
        if (frm.doc.birth_date) {
            let today = frappe.datetime.get_today();
            let birth = frappe.datetime.str_to_obj(frm.doc.birth_date);
            let age = moment(today).diff(moment(birth), 'years');
            
            frm.set_value('age', age);
            
            if (age <= 12) {
                frappe.show_alert({
                    message: __('Note: Applicant is {0} years old. Parental consent may be required.', [age]),
                    indicator: 'orange'
                }, 10);
            }
        }
    }
});

verenigingen.member_review = {
    setup_review_section: function(frm) {
        // Check user permissions
        if (!frappe.user.has_role(['Verenigingen Manager', 'Membership Manager']) && 
            !this.is_chapter_reviewer(frm)) {
            return;
        }
        
        // Add custom HTML section for review
        let review_html = `
            <div class="review-section frappe-card">
                <div class="card-header">
                    <h4>${__('Application Review')}</h4>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <strong>${__('Application Date')}:</strong> 
                            ${frappe.datetime.str_to_user(frm.doc.application_date)}
                        </div>
                        <div class="col-md-6">
                            <strong>${__('Days Pending')}:</strong> 
                            ${this.calculate_days_pending(frm.doc.application_date)}
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <strong>${__('Current Membership Type')}:</strong> 
                            ${frm.doc.current_membership_type || 'Not selected'}
                        </div>
                        <div class="col-md-6">
                            <strong>${__('Payment Amount')}:</strong> 
                            ${this.get_membership_amount(frm)}
                        </div>
                    </div>
                    
                    ${this.get_chapter_info_html(frm)}
                    ${this.get_volunteer_info_html(frm)}
                    
                    <div class="review-actions mt-4">
                        <button class="btn btn-success btn-sm mr-2" id="approve-btn">
                            <i class="fa fa-check"></i> ${__('Approve Application')}
                        </button>
                        <button class="btn btn-danger btn-sm" id="reject-btn">
                            <i class="fa fa-times"></i> ${__('Reject Application')}
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Add to form - find the application section or add to dashboard
        if (frm.fields_dict.application_section && frm.fields_dict.application_section.wrapper) {
            $(frm.fields_dict.application_section.wrapper).html(review_html);
        } else {
            // If application_section wrapper is not available, add to dashboard
            frm.dashboard.add_comment(review_html, 'orange', true);
        }
        
        // Bind events
        $('#approve-btn').click(() => this.approve_application(frm));
        $('#reject-btn').click(() => this.reject_application(frm));
    },
    
    calculate_days_pending: function(application_date) {
        if (!application_date) return 0;
        
        let app_date = frappe.datetime.str_to_obj(application_date);
        let today = frappe.datetime.get_today();
        let days = moment(today).diff(moment(app_date), 'days');
        
        if (days > 14) {
            return `<span class="text-danger">${days} days (overdue)</span>`;
        }
        return `${days} days`;
    },
    
    get_membership_amount: function(frm) {
        if (!frm.doc.current_membership_type) return 'N/A';
        
        // This would fetch from server, simplified here
        return new Promise((resolve) => {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Membership Type',
                    filters: { name: frm.doc.current_membership_type },
                    fieldname: ['amount', 'currency']
                },
                callback: function(r) {
                    if (r.message) {
                        let amount = format_currency(r.message.amount, r.message.currency);
                        $('#payment-amount').text(amount);
                    }
                }
            });
        });
    },
    
    get_chapter_info_html: function(frm) {
        let chapter = frm.doc.primary_chapter;
        if (!chapter) return '';
        
        return `
            <div class="row mb-3">
                <div class="col-md-12">
                    <strong>${__('Chapter')}:</strong> ${chapter}
                </div>
            </div>
        `;
    },
    
    get_volunteer_info_html: function(frm) {
        if (!frm.doc.interested_in_volunteering) return '';
        
        let interests = frm.doc.volunteer_interests || [];
        let skills = frm.doc.volunteer_skills || [];
        
        return `
            <div class="volunteer-info alert alert-info">
                <h6>${__('Interested in Volunteering')}</h6>
                <div class="row">
                    <div class="col-md-6">
                        <strong>${__('Availability')}:</strong> ${frm.doc.volunteer_availability || 'Not specified'}
                    </div>
                    <div class="col-md-6">
                        <strong>${__('Experience')}:</strong> ${frm.doc.volunteer_experience_level || 'Not specified'}
                    </div>
                </div>
                ${interests.length > 0 ? `
                    <div class="mt-2">
                        <strong>${__('Interest Areas')}:</strong>
                        <ul class="list-unstyled mb-0">
                            ${interests.map(i => `<li>• ${i.interest_area}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${skills.length > 0 ? `
                    <div class="mt-2">
                        <strong>${__('Skills')}:</strong>
                        <ul class="list-unstyled mb-0">
                            ${skills.map(s => `<li>• ${s.skill_name} (${s.proficiency_level || 'N/A'})</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
    },
    
    is_chapter_reviewer: function(frm) {
        // Check if current user is a board member of the applicant's chapter
        let chapter = frm.doc.primary_chapter;
        if (!chapter) return false;
        
        // This would be an async call in reality
        // Simplified for illustration
        return frappe.user.has_role('Chapter Board Member');
    },
    
    approve_application: function(frm) {
        // Validate membership type is selected
        if (!frm.doc.current_membership_type) {
            frappe.msgprint(__('Please select a membership type before approving'));
            return;
        }
        
        let d = new frappe.ui.Dialog({
            title: __('Approve Membership Application'),
            fields: [
                {
                    fieldname: 'membership_type',
                    fieldtype: 'Link',
                    label: __('Membership Type'),
                    options: 'Membership Type',
                    default: frm.doc.current_membership_type,
                    reqd: 1
                },
                {
                    fieldname: 'assign_chapter',
                    fieldtype: 'Link',
                    label: __('Assign to Chapter'),
                    options: 'Chapter',
                    default: frm.doc.primary_chapter
                },
                {
                    fieldname: 'notes',
                    fieldtype: 'Small Text',
                    label: __('Approval Notes'),
                    description: __('Optional notes about the approval')
                }
            ],
            primary_action_label: __('Approve & Send Invoice'),
            primary_action: function(values) {
                frappe.call({
                    method: 'verenigingen.api.membership_application.approve_membership_application',
                    args: {
                        member_name: frm.doc.name,
                        membership_type: values.membership_type,
                        chapter: values.assign_chapter,
                        notes: values.notes
                    },
                    freeze: true,
                    freeze_message: __('Processing approval...'),
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Application approved! Invoice sent to applicant.'),
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
    },
    
    reject_application: function(frm) {
        let d = new frappe.ui.Dialog({
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
                    fieldname: 'process_refund',
                    fieldtype: 'Check',
                    label: __('Process Refund'),
                    default: 1,
                    depends_on: "eval:frm.doc.application_payment",
                    description: __('Automatically process refund if payment was made')
                }
            ],
            primary_action_label: __('Reject Application'),
            primary_action: function(values) {
                frappe.confirm(
                    __('Are you sure you want to reject this application?'),
                    () => {
                        frappe.call({
                            method: 'verenigingen.api.membership_application.reject_membership_application',
                            args: {
                                member_name: frm.doc.name,
                                reason: values.reason,
                                process_refund: values.process_refund && frm.doc.application_payment ? 1 : 0
                            },
                            freeze: true,
                            freeze_message: __('Processing rejection...'),
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    frappe.show_alert({
                                        message: __('Application rejected. Notification sent to applicant.'),
                                        indicator: 'red'
                                    }, 5);
                                    d.hide();
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }
        });
        
        d.show();
    },
    
    show_membership_details: function(frm) {
        // Show active membership details
        if (!frm.doc.__onload || !frm.doc.__onload.membership) return;
        
        let membership = frm.doc.__onload.membership;
        let html = `
            <div class="membership-details alert alert-success">
                <h5>${__('Active Membership')}</h5>
                <div class="row">
                    <div class="col-md-6">
                        <strong>${__('Membership ID')}:</strong> ${membership.name}<br>
                        <strong>${__('Type')}:</strong> ${membership.membership_type}<br>
                        <strong>${__('Status')}:</strong> <span class="badge badge-success">${membership.status}</span>
                    </div>
                    <div class="col-md-6">
                        <strong>${__('Start Date')}:</strong> ${frappe.datetime.str_to_user(membership.start_date)}<br>
                        <strong>${__('Renewal Date')}:</strong> ${frappe.datetime.str_to_user(membership.renewal_date)}<br>
                        <strong>${__('Auto Renew')}:</strong> ${membership.auto_renew ? 'Yes' : 'No'}
                    </div>
                </div>
            </div>
        `;
        
        // Add to dashboard since membership_details field may not exist
        frm.dashboard.add_comment(html, 'green', true);
    },
    
    show_refund_options: function(frm) {
        if (frm.doc.refund_status === 'Processed') return;
        
        frm.add_custom_button(__('Process Refund'), function() {
            frappe.confirm(
                __('Process refund for this rejected application?'),
                () => {
                    frappe.call({
                        method: 'verenigingen.api.payment_processing.process_application_refund',
                        args: {
                            member_name: frm.doc.name,
                            reason: 'Application Rejected'
                        },
                        freeze: true,
                        freeze_message: __('Processing refund...'),
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Refund processed successfully'),
                                    indicator: 'green'
                                }, 5);
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __('Actions'));
    }
};
