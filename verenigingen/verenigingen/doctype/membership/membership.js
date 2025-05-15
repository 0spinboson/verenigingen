frappe.ui.form.on('Membership', {
    refresh: function(frm) {
        // Hide irrelevant fields in different states
        frm.trigger('toggle_fields');

        // Override the standard button handler for subscription creation
        if (frm.fields_dict.create_subscription && frm.fields_dict.create_subscription.input) {
            frm.fields_dict.create_subscription.input.onclick = function() {
                createSubscriptionWithOptions(frm);
                return false; // Prevent default behavior
            };
        }
        if (frm.is_new()) {
            frm.add_custom_button(__('Allow Multiple Memberships'), function() {
                frm.set_value('allow_multiple_memberships', 1);
                frm.save();
            }, __('Actions')).addClass('btn-warning');
        }
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
        if (frm.doc.docstatus === 1 && frm.doc.start_date) {
            const startDate = frappe.datetime.str_to_obj(frm.doc.start_date);
            const today = frappe.datetime.get_today();
            const todayObj = frappe.datetime.str_to_obj(today);
            
            // Calculate months difference
            const monthDiff = (todayObj.getFullYear() - startDate.getFullYear()) * 12 + 
                             todayObj.getMonth() - startDate.getMonth();
            
            if (monthDiff < 12) {
                // Calculate remaining months
                const remainingMonths = 12 - monthDiff;
                
                // Add warning message
                frm.set_intro(
                    `<div class="alert alert-warning">
                        <strong>Note:</strong> This membership is in its first year. 
                        ${remainingMonths} month${remainingMonths !== 1 ? 's' : ''} remaining until the minimum period ends.
                    </div>`,
                    'yellow'
                );
            }
        }
            // Add button to cancel membership
            if (frm.doc.status === "Active" || frm.doc.status === "Pending" || frm.doc.status === "Inactive") {
                // Calculate 1 year after start date to validate cancellation
                const startDate = frappe.datetime.str_to_obj(frm.doc.start_date);
                const minCancellationDate = frappe.datetime.add_months(startDate, 12);
                const today = frappe.datetime.get_today();
                
                // Only allow cancellation if 1 year has passed
                if (frappe.datetime.str_to_obj(today) >= minCancellationDate) {
                    frm.add_custom_button(__('Cancel Membership'), function() {
                        show_cancellation_dialog(frm);
                    }, __('Actions')).addClass('btn-danger');
                } else {
                    // Show disabled button with tooltip
                    frm.add_custom_button(__('Cancel Membership'), function() {
                        frappe.msgprint(__('Membership cannot be cancelled before 1 year from start date'));
                    }, __('Actions')).addClass('btn-default');
                }
            }
            
            // Add custom button to create subscription if not already linked
            if (!frm.doc.subscription && (frm.doc.status === "Active" || frm.doc.status === "Pending")) {
                frm.add_custom_button(__('Create Subscription'), function() {
                    createSubscriptionWithOptions(frm);
                }, __('Actions'));
            }
            
            // Add button to sync payment details if subscription exists
            if (frm.doc.subscription) {
                frm.add_custom_button(__('Sync Payment Details'), function() {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.membership.sync_membership_payments',
                        args: {
                            'membership_name': frm.doc.name
                        },
                        callback: function(r) {
                            frm.refresh();
                            frappe.msgprint(__('Payment details synchronized with subscription.'));
                        }
                    });
                }, __('Actions'));
            }
            
            // Set up the view payments button
            if (frm.doc.subscription && frm.fields_dict.view_payments) {
                frm.fields_dict.view_payments.input.onclick = function() {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.membership.show_payment_history',
                        args: {
                            'membership_name': frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message && r.message.length) {
                                show_payment_history_dialog(r.message);
                            } else {
                                frappe.msgprint(__('No payment history found for this membership.'));
                            }
                        }
                    });
                    return false;
                };
            }
            frm.add_custom_button(__('View All Invoices'), function() {
                frappe.call({
                    method: 'verenigingen.verenigingen.doctype.membership.membership.show_all_invoices',
                    args: {
                        'membership_name': frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.length) {
                            show_invoices_dialog(r.message);
                        } else {
                            frappe.msgprint(__('No invoices found for this membership.'));
                        }
                    }
                });
            }, __('Actions'));
            // Add button to add to direct debit batch if payment method is Direct Debit
            if (frm.doc.payment_method === 'Direct Debit' && frm.doc.unpaid_amount > 0) {
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
        if (frm.doc.subscription && frm.fields_dict.view_subscription) {
            frm.fields_dict.view_subscription.input.onclick = function() {
                frappe.set_route('Form', 'Subscription', frm.doc.subscription);
                return false;
            };
        }
        
        // Make renewal_date read-only - it's calculated based on start_date and membership_type
        frm.set_df_property('renewal_date', 'read_only', 1);
        
        // Display next billing date information
        if (frm.doc.next_billing_date) {
            frm.set_intro(__('Next billing date: {0}', [frappe.datetime.str_to_user(frm.doc.next_billing_date)]), 'blue');
        }
    },
    
    toggle_fields: function(frm) {
        // Hide/show fields based on status
        const is_cancelled = frm.doc.status === 'Cancelled';
        const has_paid = frm.doc.last_payment_date;
        
        frm.toggle_display(['cancellation_date', 'cancellation_reason', 'cancellation_type'], is_cancelled);
        frm.toggle_display(['last_payment_date'], has_paid);
        
        // Show next billing date when subscription exists
        frm.toggle_display(['next_billing_date'], frm.doc.subscription);
    },
    
    membership_type: function(frm) {
        // Recalculate renewal date when membership type changes
        frm.trigger('calculate_renewal_date');
    },
    
    start_date: function(frm) {
        // Recalculate renewal date when start date changes
        frm.trigger('calculate_renewal_date');
    },
    
    calculate_renewal_date: function(frm) {
        // Calculate renewal date based on membership type and start date
        if (frm.doc.membership_type && frm.doc.start_date) {
            frappe.db.get_doc('Membership Type', frm.doc.membership_type)
                .then(membership_type => {
                    if (membership_type.subscription_period === 'Lifetime') {
                        // For lifetime memberships, still set a minimum 1-year initial period
                        let renewal_date = frappe.datetime.add_months(frm.doc.start_date, 12);
                        frm.set_value('renewal_date', renewal_date);
                        frappe.msgprint(__('Note: Although this is a lifetime membership, a 1-year minimum commitment period still applies.'));
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
                        
                        // Ensure minimum 1-year membership period
                        if (months > 0 && months < 12) {
                            frappe.msgprint(__('Note: Membership type has a period less than 1 year. Due to the mandatory minimum period, the renewal date is set to 1 year from start date.'));
                            months = 12;
                        }
                        
                        if (months > 0) {
                            let renewal_date = frappe.datetime.add_months(frm.doc.start_date, months);
                            // Subtract 1 day to make it inclusive
                            renewal_date = frappe.datetime.add_days(renewal_date);
                            frm.set_value('renewal_date', renewal_date);
                        }
                    }
                    
                    // Set subscription plan if linked
                    if (membership_type.subscription_plan) {
                        frm.set_value('subscription_plan', membership_type.subscription_plan);
                    }
                    
                    // Set auto_renew based on membership type settings
                    if (membership_type.allow_auto_renewal) {
                        frm.set_value('auto_renew', membership_type.allow_auto_renewal);
                    }
                });
        }
    },
    
    payment_method: function(frm) {
        // Show/hide mandate fields based on payment method
        const is_direct_debit = frm.doc.payment_method === 'Direct Debit';
        frm.toggle_reqd(['sepa_mandate'], is_direct_debit);
    },
    
    // Hook for create_subscription button
    create_subscription: function(frm) {
        createSubscriptionWithOptions(frm);
    }
});

// Helper function for creating subscription with our required options
function createSubscriptionWithOptions(frm) {
    // Validate required fields
    if (!frm.doc.subscription_plan) {
        frappe.msgprint(__('Please select a Subscription Plan first'));
        return;
    }
    
    // Enhanced options
    const options = {
        'follow_calendar_months': 1,
        'generate_invoice_at_period_start': 1,
        'generate_new_invoices_past_due_date': 1,
        'submit_invoice': 1,
        'days_until_due': 18
    };
    
    // Show a loading indicator
    frappe.msgprint(__('Creating subscription with enhanced options... Please wait.'));
    
    // Call the server API
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.membership.membership.create_subscription',
        args: {
            'membership_name': frm.doc.name,
            'options': options
        },
        callback: function(r) {
            if (r.message) {
                frm.reload_doc();
                frappe.msgprint(__('Subscription created successfully.'));
            }
        },
        error: function(r) {
            // Display detailed error message
            let error_msg = r.message || __('An error occurred while creating the subscription.');
            frappe.msgprint({
                title: __('Error'),
                indicator: 'red',
                message: error_msg
            });
        }
    });
}

// Function to display cancellation dialog
function show_cancellation_dialog(frm) {
    const today = frappe.datetime.get_today();
    
    // Calculate 1 year after start date
    const startDate = frappe.datetime.str_to_obj(frm.doc.start_date);
    const minCancellationDate = frappe.datetime.add_months(startDate, 12);
    
    // Enforce 1 year minimum
    if (frappe.datetime.str_to_obj(today) < minCancellationDate) {
        const minDateStr = frappe.datetime.obj_to_str(minCancellationDate);
        frappe.msgprint(__('Membership cannot be cancelled before {0}', [minDateStr]));
        return;
    }
    
    const dialog = new frappe.ui.Dialog({
        title: __('Cancel Membership'),
        fields: [
            {
                fieldname: 'cancellation_date',
                fieldtype: 'Date',
                label: __('Cancellation Date'),
                default: today,
                reqd: 1
            },
            {
                fieldname: 'cancellation_type',
                fieldtype: 'Select',
                label: __('Cancellation Type'),
                options: 'Immediate\nEnd of Period',
                default: 'Immediate',
                reqd: 1,
                description: __('Immediate: Cancel right away. End of Period: Continue until renewal date.')
            },
            {
                fieldname: 'cancellation_reason',
                fieldtype: 'Small Text',
                label: __('Cancellation Reason'),
                reqd: 1
            }
        ],
        primary_action_label: __('Cancel Membership'),
        primary_action: function(values) {
            // Validate the cancellation date is after 1 year minimum
            if (frappe.datetime.str_to_obj(values.cancellation_date) < minCancellationDate) {
                frappe.msgprint(__('Cancellation date must be at least 1 year after the start date.'));
                return;
            }
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.membership.membership.cancel_membership',
                args: {
                    'membership_name': frm.doc.name,
                    'cancellation_date': values.cancellation_date,
                    'cancellation_reason': values.cancellation_reason,
                    'cancellation_type': values.cancellation_type
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
    html += '<th>' + __("Outstanding") + '</th>';
    html += '<th>' + __("Status") + '</th>';
    html += '</tr></thead>';
    html += '<tbody>';
    
    payment_history.forEach(function(ph) {
        html += '<tr>';
        html += '<td><a href="/app/sales-invoice/' + ph.invoice + '">' + ph.invoice + '</a></td>';
        html += '<td>' + frappe.datetime.str_to_user(ph.date) + '</td>';
        html += '<td>' + format_currency(ph.amount) + '</td>';
        html += '<td>' + format_currency(ph.outstanding) + '</td>';
        html += '<td>' + get_status_indicator(ph.status) + '</td>';
        html += '</tr>';
        
        // Add payment entries if any
        if (ph.payments && ph.payments.length) {
            ph.payments.forEach(function(payment) {
                html += '<tr class="payment-entry">';
                html += '<td colspan="2" class="text-right">' + __("Payment Entry") + ': ';
                html += '<a href="/app/payment-entry/' + payment.payment_entry + '">' + payment.payment_entry + '</a></td>';
                html += '<td>' + format_currency(payment.amount) + '</td>';
                html += '<td></td>'; // No outstanding for payments
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

function show_invoices_dialog(invoices_data) {
    // Format the invoices data for display
    let html = '<div class="invoices-list">';
    
    // Add table for invoices
    html += '<table class="table table-bordered table-condensed">';
    html += '<thead><tr>';
    html += '<th>' + __("Invoice") + '</th>';
    html += '<th>' + __("Date") + '</th>';
    html += '<th>' + __("Due Date") + '</th>';
    html += '<th>' + __("Amount") + '</th>';
    html += '<th>' + __("Outstanding") + '</th>';
    html += '<th>' + __("Status") + '</th>';
    html += '<th>' + __("Source") + '</th>';
    html += '</tr></thead>';
    html += '<tbody>';
    
    invoices_data.forEach(function(invoice) {
        html += '<tr>';
        html += '<td><a href="/app/sales-invoice/' + invoice.invoice + '">' + invoice.invoice + '</a></td>';
        html += '<td>' + frappe.datetime.str_to_user(invoice.date) + '</td>';
        html += '<td>' + (invoice.due_date ? frappe.datetime.str_to_user(invoice.due_date) : '-') + '</td>';
        html += '<td>' + format_currency(invoice.amount) + '</td>';
        html += '<td>' + format_currency(invoice.outstanding) + '</td>';
        html += '<td>' + get_status_indicator(invoice.status) + '</td>';
        html += '<td>' + (invoice.source || '-') + '</td>';
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    
    // Add summary section
    let total_amount = 0;
    let total_outstanding = 0;
    
    invoices_data.forEach(function(invoice) {
        total_amount += flt(invoice.amount);
        total_outstanding += flt(invoice.outstanding);
    });
    
    html += '<div class="row mt-3">';
    html += '<div class="col-sm-6">';
    html += '<p><strong>' + __("Total Invoices") + ':</strong> ' + invoices_data.length + '</p>';
    html += '</div>';
    html += '<div class="col-sm-6 text-right">';
    html += '<p><strong>' + __("Total Amount") + ':</strong> ' + format_currency(total_amount) + '</p>';
    html += '<p><strong>' + __("Total Outstanding") + ':</strong> ' + format_currency(total_outstanding) + '</p>';
    html += '</div>';
    html += '</div>';
    
    html += '</div>';
    
    // Show dialog with invoices list
    let d = new frappe.ui.Dialog({
        title: __('All Invoices for Membership'),
        fields: [{
            fieldtype: 'HTML',
            options: html
        }],
        size: 'large'
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
