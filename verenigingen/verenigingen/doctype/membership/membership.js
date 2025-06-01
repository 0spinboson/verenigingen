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
            // Add custom amount management buttons
            if (frm.doc.status === 'Active') {
                // Add "Adjust Amount" button
                frm.add_custom_button(__('Adjust Amount'), function() {
                    show_amount_adjustment_dialog(frm);
                }, __('Actions'));
                
                // Add "Revert to Standard" button if using custom amount
                if (frm.doc.uses_custom_amount) {
                    frm.add_custom_button(__('Revert to Standard Amount'), function() {
                        revert_to_standard_amount(frm);
                    }, __('Actions'));
                }
                
                // Add "Check Subscription" button for debugging
                if (frm.doc.subscription) {
                    frm.add_custom_button(__('Check Subscription Amount'), function() {
                        check_subscription_amount(frm);
                    }, __('Debug'));
                }
            }
            
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
        
        // Update amount display
        update_amount_display(frm);
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
        
        // When membership type changes, update custom amount options and display
        if (frm.doc.membership_type) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Membership Type',
                    filters: {name: frm.doc.membership_type},
                    fieldname: ['allow_custom_amount', 'minimum_amount', 'amount', 'currency']
                },
                callback: function(r) {
                    if (r.message) {
                        const mt = r.message;
                        
                        // Show/hide custom amount section
                        frm.toggle_display('custom_amount_section', mt.allow_custom_amount);
                        
                        if (mt.allow_custom_amount) {
                            // Set minimum amount for custom amount field
                            const min_amount = mt.minimum_amount || mt.amount;
                            frm.set_df_property('custom_amount', 'description', 
                                `Minimum amount: ${mt.currency} ${min_amount}`);
                        }
                        
                        // Calculate effective amount
                        frm.trigger('calculate_effective_amount');
                    }
                }
            });
        }
    },
    
    start_date: function(frm) {
        // Recalculate renewal date when start date changes
        frm.trigger('calculate_renewal_date');
    },
    
    uses_custom_amount: function(frm) {
        frm.trigger('calculate_effective_amount');
        update_amount_display(frm);
    },
    
    custom_amount: function(frm) {
        frm.trigger('calculate_effective_amount');
        frm.trigger('validate_custom_amount');
    },
    
    calculate_effective_amount: function(frm) {
        if (frm.doc.uses_custom_amount && frm.doc.custom_amount) {
            frm.set_value('effective_amount', frm.doc.custom_amount);
        } else if (frm.doc.membership_type) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Membership Type',
                    filters: {name: frm.doc.membership_type},
                    fieldname: 'amount'
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('effective_amount', r.message.amount);
                    }
                }
            });
        }
    },
    
    validate_custom_amount: function(frm) {
        if (!frm.doc.uses_custom_amount || !frm.doc.custom_amount || !frm.doc.membership_type) {
            return;
        }
        
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Membership Type',
                filters: {name: frm.doc.membership_type},
                fieldname: ['minimum_amount', 'amount', 'allow_custom_amount']
            },
            callback: function(r) {
                if (r.message) {
                    const mt = r.message;
                    const minimum = mt.minimum_amount || mt.amount;
                    
                    if (!mt.allow_custom_amount) {
                        frappe.msgprint(__('Custom amounts are not allowed for this membership type'));
                        frm.set_value('uses_custom_amount', 0);
                        return;
                    }
                    
                    if (frm.doc.custom_amount < minimum) {
                        frappe.msgprint(__('Amount cannot be less than minimum: {0}', [minimum]));
                        frm.set_value('custom_amount', minimum);
                    }
                }
            }
        });
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

function update_amount_display(frm) {
    // Add visual indicators for custom amounts
    if (frm.doc.uses_custom_amount) {
        frm.dashboard.add_indicator(__('Using Custom Amount: {0}', [format_currency(frm.doc.custom_amount)]), 'blue');
        
        if (frm.doc.amount_difference !== 0) {
            const diff_text = frm.doc.amount_difference > 0 ? 
                __('Above Standard: +{0}', [format_currency(frm.doc.amount_difference)]) :
                __('Below Standard: {0}', [format_currency(frm.doc.amount_difference)]);
            frm.dashboard.add_indicator(diff_text, frm.doc.amount_difference > 0 ? 'green' : 'orange');
        }
    }
}

function show_amount_adjustment_dialog(frm) {
    // Get current membership type info
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Membership Type',
            filters: {name: frm.doc.membership_type},
            fieldname: ['allow_custom_amount', 'minimum_amount', 'amount', 'currency']
        },
        callback: function(r) {
            if (r.message) {
                const mt = r.message;
                
                if (!mt.allow_custom_amount) {
                    frappe.msgprint(__('Custom amounts are not allowed for this membership type'));
                    return;
                }
                
                const minimum_amount = mt.minimum_amount || mt.amount;
                const current_amount = frm.doc.uses_custom_amount ? frm.doc.custom_amount : mt.amount;
                
                let dialog = new frappe.ui.Dialog({
                    title: __('Adjust Membership Amount'),
                    fields: [
                        {
                            fieldtype: 'HTML',
                            options: `
                                <div class="alert alert-info">
                                    <strong>Current Amount:</strong> ${mt.currency} ${current_amount}<br>
                                    <strong>Standard Amount:</strong> ${mt.currency} ${mt.amount}<br>
                                    <strong>Minimum Allowed:</strong> ${mt.currency} ${minimum_amount}
                                </div>
                            `
                        },
                        {
                            fieldtype: 'Currency',
                            fieldname: 'new_amount',
                            label: __('New Amount'),
                            reqd: 1,
                            default: current_amount,
                            description: __('Minimum: {0} {1}', [mt.currency, minimum_amount])
                        },
                        {
                            fieldtype: 'Small Text',
                            fieldname: 'reason',
                            label: __('Reason for Change'),
                            description: __('Optional reason for the amount adjustment')
                        }
                    ],
                    primary_action_label: __('Update Amount'),
                    primary_action: function(values) {
                        if (values.new_amount < minimum_amount) {
                            frappe.msgprint(__('Amount cannot be less than minimum: {0}', [minimum_amount]));
                            return;
                        }
                        
                        frappe.call({
                            method: 'verenigingen.verenigingen.doctype.membership.membership.set_custom_amount',
                            args: {
                                membership_name: frm.doc.name,
                                custom_amount: values.new_amount,
                                reason: values.reason
                            },
                            freeze: true,
                            freeze_message: __('Updating amount...'),
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    frappe.show_alert({
                                        message: r.message.message,
                                        indicator: 'green'
                                    }, 5);
                                    frm.reload_doc();
                                    dialog.hide();
                                }
                            }
                        });
                    }
                });
                
                dialog.show();
            }
        }
    });
}

function revert_to_standard_amount(frm) {
    frappe.confirm(
        __('Are you sure you want to revert to the standard membership amount? This will affect future billing.'),
        function() {
            const reason = prompt(__('Reason for reverting to standard amount (optional):'));
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.membership.membership.revert_to_standard_amount',
                args: {
                    membership_name: frm.doc.name,
                    reason: reason
                },
                freeze: true,
                freeze_message: __('Reverting to standard amount...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 5);
                        frm.reload_doc();
                    }
                }
            });
        }
    );
}

function check_subscription_amount(frm) {
    if (!frm.doc.subscription) {
        frappe.msgprint(__('No subscription linked to this membership'));
        return;
    }
    
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Subscription',
            filters: {name: frm.doc.subscription},
            fieldname: ['status']
        },
        callback: function(r) {
            if (r.message) {
                // Get subscription plans
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Subscription Plan Detail',
                        filters: {parent: frm.doc.subscription},
                        fields: ['plan', 'cost'],
                        parent: 'Subscription'
                    },
                    callback: function(r2) {
                        if (r2.message && r2.message.length > 0) {
                            const plan = r2.message[0];
                            const expected_amount = frm.doc.uses_custom_amount ? frm.doc.custom_amount : 
                                                  (frm.doc.effective_amount || 0);
                            
                            const matches = Math.abs(plan.cost - expected_amount) < 0.01;
                            
                            frappe.msgprint({
                                title: __('Subscription Amount Check'),
                                message: `
                                    <strong>Membership Amount:</strong> ${format_currency(expected_amount)}<br>
                                    <strong>Subscription Amount:</strong> ${format_currency(plan.cost)}<br>
                                    <strong>Status:</strong> ${matches ? 
                                        '<span class="text-success">✓ Amounts match</span>' : 
                                        '<span class="text-warning">⚠ Amounts do not match</span>'
                                    }<br>
                                    <strong>Subscription Status:</strong> ${r.message.status}
                                `,
                                indicator: matches ? 'green' : 'orange'
                            });
                        }
                    }
                });
            }
        }
    });
}

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
function format_currency(value, currency = 'EUR') {
    if (typeof value === 'undefined' || value === null) return '';
    return currency + ' ' + parseFloat(value).toFixed(2);
}

// Helper function to get status indicator
function get_status_indicator(status) {
    let color = 'gray';
    if (status === 'Paid') color = 'green';
    else if (status === 'Unpaid') color = 'orange';
    else if (status === 'Overdue') color = 'red';
    
    return '<span class="indicator ' + color + '">' + status + '</span>';
}
