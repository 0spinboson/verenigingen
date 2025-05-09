frappe.ui.form.on('Membership', {
    refresh: function(frm) {
        // Hide irrelevant fields in different states
        frm.trigger('toggle_fields');
        
        // Add custom buttons after document is submitted
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
            
            // Add button to view payment history if subscription exists
            if (frm.doc.subscription) {
                frm.add_custom_button(__('View Payment History'), function() {
                    // Call method to get payment history
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.enhanced_subscription.get_membership_payment_history',
                        args: {
                            'membership_doc': frm.doc
                        },
                        callback: function(r) {
                            if (r.message && r.message.length) {
                                // Display payment history in a dialog
                                show_payment_history_dialog(r.message);
                            } else {
                                frappe.msgprint(__('No payment history found for this membership.'));
                            }
                        }
                    });
                }, __('View'));
                
                // Add button to sync with subscription
                frm.add_custom_button(__('Sync Payment Status'), function() {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.enhanced_subscription.sync_membership_with_subscription',
                        args: {
                            'membership_doc': frm.doc
                        },
                        callback: function(r) {
                            frm.refresh();
                            frappe.msgprint(__('Payment status synchronized with subscription.'));
                        }
                    });
                }, __('Actions'));
            }
            
            // Add button to add to direct debit batch if payment method is Direct Debit
            if (frm.doc.payment_method === 'Direct Debit' && frm.doc.payment_status === 'Unpaid') {
                frm.add_custom_button(__('Add to Direct Debit Batch'), function() {
                    // Call method to add to direct debit batch
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.enhanced_subscription.add_to_direct_debit_batch',
                        args: {
                            'membership_name': frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.set_route('Form', 'Direct Debit Batch', r.message);
                            }
                        }
                    });
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
                'membership_name': frm.doc.name,
                'options': {
                    'follow_calendar_months': 1,
                    'generate_invoice_at_period_start': 1,
                    'generate_new_invoices_past_due_date': 1,
                    'submit_invoice': 1,
                    'days_until_due': 30
                }
            },
            callback: function(r) {
                if (r.message) {
                    frm.refresh();
                }
            }
        });
    }
});

// Function to display payment history in a dialog
function show_payment_history_dialog(payment_history) {
    // Format the payment history data for display
    let html = '<div class="payment-history">';
    
    // Add table for invoices
    html += '<table class="table table-bordered table-condensed">';
    html += '<thead><tr>';
    html += '<th>' + __("Invoice") + '</th>';
    html += '<th>' + __("Date") + '</th>';
    html += '<th>' + __("Amount") + '</th>';
    html += '<th>' + __("Status") + '</th>';
    html += '</tr></thead>';
    html += '<tbody>';
    
    payment_history.forEach(function(ph) {
        html += '<tr>';
        html += '<td><a href="/app/sales-invoice/' + ph.invoice + '">' + ph.invoice + '</a></td>';
        html += '<td>' + frappe.datetime.str_to_user(ph.date) + '</td>';
        html += '<td>' + format_currency(ph.amount) + '</td>';
        html += '<td>' + get_status_indicator(ph.status) + '</td>';
        html += '</tr>';
        
        // Add payment entries if any
        if (ph.payments && ph.payments.length) {
            ph.payments.forEach(function(payment) {
                html += '<tr class="payment-entry">';
                html += '<td colspan="2" class="text-right">' + __("Payment Entry") + ': ';
                html += '<a href="/app/payment-entry/' + payment.payment_entry + '">' + payment.payment_entry + '</a></td>';
                html += '<td>' + format_currency(payment.amount) + '</td>';
                html += '<td>' + payment.mode + '</td>';
                html += '</tr>';
            });
        }
    });
    
    html += '</tbody></table>';
    html += '</div>';
    
    // Show dialog with payment history
    let d = new frappe.ui.Dialog({
        title: __('Payment History'),
        fields: [{
            fieldtype: 'HTML',
            options: html
        }]
    });
    
    d.show();
}

// Helper function to format currency
function format_currency(value) {
    return frappe.format(value, {fieldtype: 'Currency'});
}

// Helper function to get status indicator
function get_status_indicator(status) {
    let color = 'gray';
    if (status === 'Paid') color = 'green';
    else if (status === 'Unpaid') color = 'orange';
    else if (status === 'Overdue') color = 'red';
    
    return '<span class="indicator ' + color + '">' + status + '</span>';
}
