frappe.ui.form.on('Membership', {
    refresh: function(frm) {
        // Hide irrelevant fields in different states
        frm.trigger('toggle_fields');
        
        // Add buttons for action
        if (frm.doc.docstatus === 1) {
            // Add button to renew membership
            if (frm.doc.status === "Active" || frm.doc.status === "Expired") {
                frm.add_custom_button(__('Renew Membership'), function() {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.membership.renew_membership',
                        args: {
                            'membership_name': frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.set_route('Form', 'Membership', r.message);
                            }
                        }
                    });
                }, __('Actions'));
            }
            
            // Add button to cancel membership
            if (frm.doc.status === "Active") {
                frm.add_custom_button(__('Cancel Membership'), function() {
                    frappe.confirm(
                        __('Are you sure you want to cancel this membership?'),
                        function() {
                            frm.set_value('status', 'Cancelled');
                            frm.set_value('cancellation_date', frappe.datetime.get_today());
                            
                            // Prompt for cancellation reason
                            frappe.prompt({
                                fieldtype: 'Small Text',
                                label: __('Cancellation Reason'),
                                fieldname: 'reason'
                            }, 
                            function(values) {
                                frm.set_value('cancelation_reason', values.reason);
                                frm.save_or_update();
                            }, 
                            __('Cancellation Reason'));
                        }
                    );
                }).addClass('btn-danger');
            }
            
            // Add button to create subscription if not already linked
            if (!frm.doc.subscription && frm.doc.status === "Active") {
                frm.add_custom_button(__('Create Subscription'), function() {
                    if (!frm.doc.subscription_plan) {
                        frappe.prompt({
                            fieldtype: 'Link',
                            label: __('Subscription Plan'),
                            fieldname: 'subscription_plan',
                            options: 'Subscription Plan',
                            reqd: 1
                        }, 
                        function(values) {
                            frm.set_value('subscription_plan', values.subscription_plan);
                            frm.save().then(() => {
                                frappe.call({
                                    method: 'verenigingen.verenigingen.doctype.membership.membership.create_subscription',
                                    args: {
                                        'membership_name': frm.doc.name
                                    },
                                    callback: function(r) {
                                        if (r.message) {
                                            frm.refresh();
                                        }
                                    }
                                });
                            });
                        }, 
                        __('Select Subscription Plan'));
                    } else {
                        frappe.call({
                            method: 'verenigingen.verenigingen.doctype.membership.membership.create_subscription',
                            args: {
                                'membership_name': frm.doc.name
                            },
                            callback: function(r) {
                                if (r.message) {
                                    frm.refresh();
                                }
                            }
                        });
                    }
                }, __('Actions'));
            }
        }
        
        // View related documents
        if (frm.doc.member) {
            frm.add_custom_button(__('Member'), function() {
                frappe.set_route('Form', 'Member', frm.doc.member);
            }, __('View'));
        }
        
        if (frm.doc.subscription) {
            frm.add_custom_button(__('Subscription'), function() {
                frappe.set_route('Form', 'Subscription', frm.doc.subscription);
            }, __('View'));
        }
        
        // Set button to view subscription
        if (frm.doc.subscription) {
            frm.set_df_property('view_subscription', 'hidden', 0);
            frm.fields_dict['view_subscription'].input.onclick = function() {
                frappe.set_route('Form', 'Subscription', frm.doc.subscription);
            };
        } else {
            frm.set_df_property('view_subscription', 'hidden', 1);
        }
    },
    
    toggle_fields: function(frm) {
        // Hide/show fields based on status
        const is_cancelled = frm.doc.status === 'Cancelled';
        const is_paid = frm.doc.payment_status === 'Paid' || frm.doc.payment_status === 'Refunded';
        
        frm.toggle_display(['cancellation_date', 'cancelation_reason'], is_cancelled);
        frm.toggle_display(['payment_date', 'paid_amount'], is_paid);
    },
    
    membership_type: function(frm) {
        // Load fee details from membership type
        if (frm.doc.membership_type) {
            frappe.db.get_doc('Membership Type', frm.doc.membership_type)
                .then(membership_type => {
                    frm.set_value('fee_amount', membership_type.amount);
                    frm.set_value('currency', membership_type.currency);
                    
                    // Set subscription plan if linked
                    if (membership_type.subscription_plan) {
                        frm.set_value('subscription_plan', membership_type.subscription_plan);
                    }
                    
                    // Set auto_renew based on membership type settings
                    if (membership_type.allow_auto_renewal) {
                        frm.set_value('auto_renew', membership_type.allow_auto_renewal);
                    }
                    
                    // Calculate end date if not set
                    if (!frm.doc.end_date && frm.doc.start_date) {
                        if (membership_type.subscription_period === 'Lifetime') {
                            frm.set_value('end_date', null);
                        } else {
                            let months = 0;
                            
                            // Calculate months based on period
                            switch(membership_type.subscription_period) {
                                case 'Monthly':
                                    months = 1;
                                    break;
                                case 'Quarterly':
                                    months = 3;
                                    break;
                                case 'Biannual':
                                    months = 6;
                                    break;
                                case 'Annual':
                                    months = 12;
                                    break;
                                case 'Custom':
                                    months = membership_type.subscription_period_in_months || 0;
                                    break;
                            }
                            
                            if (months > 0) {
                                let end_date = frappe.datetime.add_months(frm.doc.start_date, months);
                                // Subtract 1 day to make it inclusive
                                end_date = frappe.datetime.add_days(end_date, -1);
                                frm.set_value('end_date', end_date);
                            }
                        }
                    }
                });
        }
    },
    
    start_date: function(frm) {
        // Recalculate end date when start date changes
        if (frm.doc.membership_type && frm.doc.start_date) {
            frm.trigger('membership_type');
        }
    },
    
    payment_status: function(frm) {
        frm.trigger('toggle_fields');
        
        // Set payment date to today when marked as paid
        if (frm.doc.payment_status === 'Paid' && !frm.doc.payment_date) {
            frm.set_value('payment_date', frappe.datetime.get_today());
        }
    },
    
    create_subscription: function(frm) {
        // Validate required fields
        if (!frm.doc.subscription_plan) {
            frappe.throw(__('Please select a Subscription Plan first'));
            return;
        }
        
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.membership.membership.create_subscription',
            args: {
                'membership_name': frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    frm.refresh();
                }
            }
        });
    }
});
