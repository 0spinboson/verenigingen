frappe.ui.form.on('Termination Appeals Process', {
    refresh: function(frm) {
        // Set status indicator
        set_status_indicator(frm);
        
        // Add action buttons based on status
        add_action_buttons(frm);
        
        // Make timeline and communications read-only
        frm.set_df_property('appeal_timeline', 'read_only', 1);
        frm.set_df_property('appeal_communications', 'read_only', 1);
        
        // Toggle field visibility based on status
        toggle_status_fields(frm);
        
        // Add view buttons
        add_view_buttons(frm);
    },
    
    onload: function(frm) {
        // Set default values for new documents
        if (frm.is_new()) {
            frm.set_value('appeal_date', frappe.datetime.get_today());
            frm.set_value('appeal_status', 'Draft');
        }
        
        // Set filters for linked documents
        set_document_filters(frm);
    },
    
    appeal_status: function(frm) {
        toggle_status_fields(frm);
    },
    
    appeal_type: function(frm) {
        // Set automatic deadlines based on appeal type
        if (!frm.doc.review_deadline && frm.doc.appeal_date) {
            const deadline_days = {
                "Procedural Appeal": 30,
                "Substantive Appeal": 60,
                "New Evidence Appeal": 45,
                "Full Review Appeal": 90
            };
            
            const days = deadline_days[frm.doc.appeal_type] || 60;
            const deadline = frappe.datetime.add_days(frm.doc.appeal_date, days);
            frm.set_value('review_deadline', deadline);
        }
    },
    
    termination_request: function(frm) {
        // Auto-populate member details from termination request
        if (frm.doc.termination_request) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Membership Termination Request',
                    name: frm.doc.termination_request
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('member', r.message.member);
                        frm.set_value('member_name', r.message.member_name);
                        
                        // Check if there's an expulsion entry
                        find_expulsion_entry(frm, r.message);
                    }
                }
            });
        }
    },
    
    legal_representative: function(frm) {
        // Toggle legal representative fields
        frm.toggle_display(['legal_rep_name', 'legal_rep_contact'], frm.doc.legal_representative);
        frm.toggle_reqd(['legal_rep_name', 'legal_rep_contact'], frm.doc.legal_representative);
    },
    
    before_save: function(frm) {
        // Validate required fields based on status
        validate_required_fields(frm);
    }
});

function set_status_indicator(frm) {
    const indicator_map = {
        'Draft': 'blue',
        'Submitted': 'orange',
        'Under Review': 'yellow',
        'Pending Decision': 'purple',
        'Decided - Upheld': 'green',
        'Decided - Rejected': 'red',
        'Decided - Partially Upheld': 'orange',
        'Withdrawn': 'gray',
        'Dismissed': 'darkgray'
    };
    
    if (frm.doc.appeal_status && indicator_map[frm.doc.appeal_status]) {
        frm.page.set_indicator(frm.doc.appeal_status, indicator_map[frm.doc.appeal_status]);
    }
}

function add_action_buttons(frm) {
    // Clear existing custom buttons
    frm.clear_custom_buttons();
    
    if (frm.doc.appeal_status === 'Draft') {
        // Submit appeal button
        frm.add_custom_button(__('Submit Appeal'), function() {
            submit_appeal(frm);
        }, __('Actions')).addClass('btn-primary');
        
    } else if (frm.doc.appeal_status === 'Submitted' || frm.doc.appeal_status === 'Under Review') {
        // Reviewer actions
        if (can_review_appeal(frm)) {
            frm.add_custom_button(__('Update Review Status'), function() {
                update_review_status_dialog(frm);
            }, __('Actions'));
            
            frm.add_custom_button(__('Record Decision'), function() {
                record_decision_dialog(frm);
            }, __('Actions')).addClass('btn-warning');
        }
        
    } else if (frm.doc.appeal_status === 'Pending Decision') {
        // Decision actions
        if (can_review_appeal(frm)) {
            frm.add_custom_button(__('Record Decision'), function() {
                record_decision_dialog(frm);
            }, __('Actions')).addClass('btn-warning');
        }
        
    } else if (frm.doc.implementation_status === 'Pending') {
        // Implementation actions
        if (can_implement_decision(frm)) {
            frm.add_custom_button(__('Implement Decision'), function() {
                implement_decision(frm);
            }, __('Actions')).addClass('btn-success');
        }
    }
    
    // Communication buttons
    if (!frm.doc.__islocal) {
        frm.add_custom_button(__('Send Email'), function() {
            send_email_dialog(frm);
        }, __('Communication'));
        
        frm.add_custom_button(__('Add Note'), function() {
            add_note_dialog(frm);
        }, __('Communication'));
    }
}

function add_view_buttons(frm) {
    // View related documents
    if (frm.doc.termination_request) {
        frm.add_custom_button(__('View Termination Request'), function() {
            frappe.set_route('Form', 'Membership Termination Request', frm.doc.termination_request);
        }, __('View'));
    }
    
    if (frm.doc.member) {
        frm.add_custom_button(__('View Member'), function() {
            frappe.set_route('Form', 'Member', frm.doc.member);
        }, __('View'));
    }
    
    if (frm.doc.expulsion_entry) {
        frm.add_custom_button(__('View Expulsion Entry'), function() {
            frappe.set_route('Form', 'Expulsion Report Entry', frm.doc.expulsion_entry);
        }, __('View'));
    }
}

function toggle_status_fields(frm) {
    // Show/hide fields based on appeal status
    const is_decided = frm.doc.appeal_status && frm.doc.appeal_status.includes('Decided');
    const is_under_review = frm.doc.appeal_status === 'Under Review';
    
    // Decision fields
    frm.toggle_display(['decision_date', 'decision_outcome', 'decision_rationale', 'decided_by'], is_decided);
    
    // Review fields
    frm.toggle_display(['review_status'], is_under_review);
    
    // Implementation fields
    const needs_implementation = is_decided && ['Upheld', 'Partially Upheld'].includes(frm.doc.decision_outcome);
    frm.toggle_display(['implementation_section'], needs_implementation);
}

function set_document_filters(frm) {
    // Filter termination requests to executed ones only
    frm.set_query('termination_request', function() {
        return {
            filters: {
                'status': 'Executed'
            }
        };
    });
    
    // Filter assigned reviewer to eligible users
    frm.set_query('assigned_reviewer', function() {
        return {
            query: 'verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_eligible_approvers'
        };
    });
}

function find_expulsion_entry(frm, termination_data) {
    // Find related expulsion entry if termination was disciplinary
    const disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion'];
    
    if (disciplinary_types.includes(termination_data.termination_type)) {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Expulsion Report Entry',
                filters: {
                    member_id: termination_data.member,
                    expulsion_date: termination_data.execution_date
                },
                limit: 1
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    frm.set_value('expulsion_entry', r.message[0].name);
                }
            }
        });
    }
}

function can_review_appeal(frm) {
    // Check if current user can review this appeal
    const user_roles = frappe.user_roles;
    
    // System managers can always review
    if (user_roles.includes('System Manager')) {
        return true;
    }
    
    // Association managers can review
    if (user_roles.includes('Association Manager')) {
        return true;
    }
    
    // Check if user is the assigned reviewer
    return frm.doc.assigned_reviewer === frappe.session.user;
}

function can_implement_decision(frm) {
    // Check if user can implement decisions
    const user_roles = frappe.user_roles;
    return (
        user_roles.includes('System Manager') ||
        user_roles.includes('Association Manager')
    );
}

function validate_required_fields(frm) {
    if (frm.doc.appeal_status === 'Submitted') {
        const required_fields = ['appellant_name', 'appellant_email', 'appeal_grounds', 'remedy_sought'];
        
        for (let field of required_fields) {
            if (!frm.doc[field]) {
                frappe.throw(__('Field {0} is required for appeal submission', [frappe.meta.get_label(frm.doctype, field)]));
            }
        }
    }
}

function submit_appeal(frm) {
    // Validate and submit the appeal
    frappe.confirm(
        __('Are you sure you want to submit this appeal? Once submitted, it cannot be edited.'),
        function() {
            frappe.call({
                method: 'submit_appeal',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message) {
                        frm.refresh();
                        frappe.show_alert({
                            message: __('Appeal submitted successfully'),
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    );
}

function update_review_status_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Update Review Status'),
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'review_status',
                label: __('Review Status'),
                options: 'Document Review\nEvidence Gathering\nHearing Scheduled\nHearing Completed\nDeliberations\nDecision Pending',
                default: frm.doc.review_status,
                reqd: 1
            },
            {
                fieldtype: 'Small Text',
                fieldname: 'notes',
                label: __('Notes')
            }
        ],
        primary_action_label: __('Update'),
        primary_action: function(values) {
            frappe.call({
                method: 'update_review_status',
                doc: frm.doc,
                args: {
                    new_status: values.review_status,
                    notes: values.notes || ''
                },
                callback: function(r) {
                    if (r.message) {
                        frm.refresh();
                        dialog.hide();
                        frappe.show_alert({
                            message: __('Review status updated'),
                            indicator: 'blue'
                        }, 3);
                    }
                }
            });
        }
    });
    
    dialog.show();
}

function record_decision_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Record Appeal Decision'),
        size: 'large',
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'decision_outcome',
                label: __('Decision Outcome'),
                options: 'Upheld\nRejected\nPartially Upheld\nRemanded for Rehearing',
                reqd: 1,
                onchange: function() {
                    const outcome = this.value;
                    const needs_implementation = ['Upheld', 'Partially Upheld'].includes(outcome);
                    dialog.fields_dict.implementation_required.df.hidden = !needs_implementation;
                    dialog.refresh();
                }
            },
            {
                fieldtype: 'Text Editor',
                fieldname: 'decision_rationale',
                label: __('Decision Rationale'),
                reqd: 1,
                description: __('Detailed explanation of the decision and reasoning')
            },
            {
                fieldtype: 'Check',
                fieldname: 'implementation_required',
                label: __('Implementation Required'),
                default: 1,
                hidden: 1
            }
        ],
        primary_action_label: __('Record Decision'),
        primary_action: function(values) {
            frappe.confirm(
                __('Are you sure you want to record this decision? This action cannot be undone.'),
                function() {
                    frappe.call({
                        method: 'make_decision',
                        doc: frm.doc,
                        args: {
                            outcome: values.decision_outcome,
                            rationale: values.decision_rationale,
                            implementation_required: values.implementation_required || false
                        },
                        callback: function(r) {
                            if (r.message) {
                                frm.refresh();
                                dialog.hide();
                                frappe.show_alert({
                                    message: __('Decision recorded successfully'),
                                    indicator: 'green'
                                }, 5);
                            }
                        }
                    });
                }
            );
        }
    });
    
    dialog.show();
}

function implement_decision(frm) {
    frappe.confirm(
        __('Are you sure you want to implement this appeal decision? This will execute the required corrective actions.'),
        function() {
            frappe.call({
                method: 'implement_decision',
                doc: frm.doc,
                freeze: true,
                freeze_message: __('Implementing decision...'),
                callback: function(r) {
                    if (r.message) {
                        frm.refresh();
                        frappe.show_alert({
                            message: __('Decision implemented successfully'),
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    );
}

function send_email_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Send Email'),
        fields: [
            {
                fieldtype: 'Data',
                fieldname: 'recipient',
                label: __('Recipient'),
                default: frm.doc.appellant_email,
                reqd: 1
            },
            {
                fieldtype: 'Data',
                fieldname: 'subject',
                label: __('Subject'),
                default: `Re: Appeal ${frm.doc.name}`,
                reqd: 1
            },
            {
                fieldtype: 'Text Editor',
                fieldname: 'message',
                label: __('Message'),
                reqd: 1
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function(values) {
            frappe.call({
                method: 'frappe.core.doctype.communication.email.make',
                args: {
                    recipients: values.recipient,
                    subject: values.subject,
                    content: values.message,
                    reference_doctype: frm.doctype,
                    reference_name: frm.docname,
                    send_email: 1
                },
                callback: function(r) {
                    if (r.message) {
                        // Add to communications log
                        frm.add_child('appeal_communications', {
                            communication_date: frappe.datetime.now_datetime(),
                            communication_type: 'Email',
                            direction: 'Outgoing',
                            from_party: frappe.session.user,
                            to_party: values.recipient,
                            subject: values.subject,
                            content_summary: values.message.substring(0, 200) + (values.message.length > 200 ? '...' : '')
                        });
                        
                        frm.save();
                        dialog.hide();
                        frappe.show_alert({
                            message: __('Email sent successfully'),
                            indicator: 'green'
                        }, 3);
                    }
                }
            });
        }
    });
    
    dialog.show();
}

function add_note_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Add Note'),
        fields: [
            {
                fieldtype: 'Select',
                fieldname: 'event_type',
                label: __('Event Type'),
                options: 'General Note\nReview Update\nCommunication Note\nDecision Note\nImplementation Note',
                default: 'General Note',
                reqd: 1
            },
            {
                fieldtype: 'Small Text',
                fieldname: 'note',
                label: __('Note'),
                reqd: 1
            }
        ],
        primary_action_label: __('Add Note'),
        primary_action: function(values) {
            frm.add_child('appeal_timeline', {
                event_date: frappe.datetime.get_today(),
                event_type: values.event_type,
                event_description: values.note,
                responsible_party: frappe.session.user,
                completion_status: 'Completed'
            });
            
            frm.refresh_field('appeal_timeline');
            frm.save();
            dialog.hide();
            
            frappe.show_alert({
                message: __('Note added successfully'),
                indicator: 'blue'
            }, 3);
        }
    });
    
    dialog.show();
}

// Enhanced appeal creation function that can be called from Member form
window.show_appeal_creation_dialog = function(termination_request_id) {
    // First get the termination request details
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'Membership Termination Request',
            name: termination_request_id
        },
        callback: function(r) {
            if (r.message) {
                show_appeal_dialog(r.message);
            }
        }
    });
};

function show_appeal_dialog(termination_data) {
    const dialog = new frappe.ui.Dialog({
        title: __('File Appeal for {0}', [termination_data.member_name]),
        size: 'large',
        fields: [
            {
                fieldtype: 'Section Break',
                label: __('Termination Details')
            },
            {
                fieldtype: 'HTML',
                options: `<div class="alert alert-info">
                    <strong>Termination Type:</strong> ${termination_data.termination_type}<br>
                    <strong>Execution Date:</strong> ${frappe.datetime.str_to_user(termination_data.execution_date)}<br>
                    <strong>Reason:</strong> ${termination_data.termination_reason}
                </div>`
            },
            {
                fieldtype: 'Section Break',
                label: __('Appellant Information')
            },
            {
                fieldname: 'appellant_name',
                fieldtype: 'Data',
                label: __('Appellant Name'),
                reqd: 1
            },
            {
                fieldname: 'appellant_email',
                fieldtype: 'Data',
                label: __('Appellant Email'),
                reqd: 1
            },
            {
                fieldname: 'appellant_relationship',
                fieldtype: 'Select',
                label: __('Relationship to Member'),
                options: 'Self\nLegal Representative\nFamily Member\nAuthorized Representative',
                reqd: 1
            },
            {
                fieldtype: 'Section Break',
                label: __('Appeal Details')
            },
            {
                fieldname: 'appeal_type',
                fieldtype: 'Select',
                label: __('Appeal Type'),
                options: 'Procedural Appeal\nSubstantive Appeal\nNew Evidence Appeal\nFull Review Appeal',
                reqd: 1
            },
            {
                fieldname: 'appeal_grounds',
                fieldtype: 'Text Editor',
                label: __('Grounds for Appeal'),
                reqd: 1,
                description: __('Detailed explanation of why the termination should be overturned')
            },
            {
                fieldname: 'remedy_sought',
                fieldtype: 'Select',
                label: __('Remedy Sought'),
                options: 'Full Reinstatement\nReduction of Penalty\nNew Hearing\nProcedural Correction\nOther',
                reqd: 1
            }
        ],
        primary_action_label: __('File Appeal'),
        primary_action: function(values) {
            // Create the appeal
            frappe.call({
                method: 'frappe.client.insert',
                args: {
                    doc: {
                        doctype: 'Termination Appeals Process',
                        termination_request: termination_data.name,
                        member: termination_data.member,
                        member_name: termination_data.member_name,
                        appeal_date: frappe.datetime.get_today(),
                        appeal_status: 'Draft',
                        ...values
                    }
                },
                callback: function(r) {
                    if (r.message) {
                        dialog.hide();
                        frappe.set_route('Form', 'Termination Appeals Process', r.message.name);
                        frappe.show_alert({
                            message: __('Appeal created successfully'),
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    });
    
    dialog.show();
}
