// Membership form controller with improved maintainability and custom amount handling
frappe.ui.form.on('Membership', {
    // Cache for membership type data to avoid repeated API calls
    _membership_type_cache: {},
    
    // Constants
    MINIMUM_MEMBERSHIP_MONTHS: 12,
    DEFAULT_SUBSCRIPTION_OPTIONS: {
        'follow_calendar_months': 1,
        'generate_invoice_at_period_start': 1,
        'generate_new_invoices_past_due_date': 1,
        'submit_invoice': 1,
        'days_until_due': 18
    },
    
    get_status_indicator: function(status) {
        const status_map = {
            'Paid': 'green',
            'Unpaid': 'orange',
            'Overdue': 'red',
            'Cancelled': 'gray'
        };
        const color = status_map[status] || 'gray';
        return `<span class="indicator ${color}">${status}</span>`;
    }
});
    
    refresh: function(frm) {
        this.setup_form_ui(frm);
        this.setup_buttons(frm);
        this.update_indicators(frm);
        this.setup_subscription_button_override(frm);
    },
    
    setup_form_ui: function(frm) {
        this.toggle_fields(frm);
        this.setup_custom_amount_visibility(frm);
    },
    
    setup_subscription_button_override: function(frm) {
        // Override subscription creation button
        if (frm.fields_dict.create_subscription && frm.fields_dict.create_subscription.input) {
            frm.fields_dict.create_subscription.input.onclick = () => {
                this.handle_create_subscription(frm);
                return false;
            };
        }
    },
    
    setup_custom_amount_visibility: async function(frm) {
        if (frm.doc.membership_type) {
            const mt = await this.get_membership_type_data(frm.doc.membership_type);
            frm.toggle_display('custom_amount_section', mt.allow_custom_amount);
        }
    },
    
    setup_buttons: function(frm) {
        const buttons = this.get_action_buttons(frm);
        
        buttons.forEach(btn => {
            if (btn.condition) {
                frm.add_custom_button(__(btn.label), btn.action, __(btn.group || 'Actions'))
                    .addClass(btn.className || '');
            }
        });
        
        // View buttons
        this.setup_view_buttons(frm);
    },
    
    setup_view_buttons: function(frm) {
        if (frm.doc.member) {
            frm.add_custom_button(__('Member'), () => {
                frappe.set_route('Form', 'Member', frm.doc.member);
            }, __('View'));
        }
        
        if (frm.doc.subscription) {
            frm.add_custom_button(__('Subscription'), () => {
                frappe.set_route('Form', 'Subscription', frm.doc.subscription);
            }, __('View'));
        }
    },
    
    get_action_buttons: function(frm) {
        const is_submitted = frm.doc.docstatus === 1;
        const is_active = frm.doc.status === 'Active';
        const can_cancel = this.can_cancel_membership(frm);
        
        return [
            // Multiple memberships
            {
                label: 'Allow Multiple Memberships',
                condition: frm.is_new(),
                action: () => {
                    frm.set_value('allow_multiple_memberships', 1);
                    frm.save();
                },
                className: 'btn-warning'
            },
            
            // Amount management - Enhanced with new functionality
            {
                label: 'Adjust Amount',
                condition: is_submitted && is_active,
                action: () => this.show_enhanced_amount_dialog(frm)
            },
            {
                label: 'Revert to Standard Amount',
                condition: is_submitted && is_active && frm.doc.uses_custom_amount,
                action: () => this.revert_to_standard_amount(frm)
            },
            {
                label: 'Check Subscription Amount',
                condition: is_submitted && frm.doc.subscription,
                action: () => this.check_subscription_amount(frm),
                group: 'Debug'
            },
            
            // Membership actions
            {
                label: 'Renew Membership',
                condition: is_submitted && ['Active', 'Expired'].includes(frm.doc.status),
                action: () => this.renew_membership(frm)
            },
            {
                label: 'Cancel Membership',
                condition: is_submitted && ['Active', 'Pending', 'Inactive'].includes(frm.doc.status),
                action: () => can_cancel ? this.show_cancellation_dialog(frm) : 
                    frappe.msgprint(__('Membership cannot be cancelled before 1 year from start date')),
                className: can_cancel ? 'btn-danger' : 'btn-default'
            },
            {
                label: 'Create Subscription',
                condition: is_submitted && !frm.doc.subscription && ['Active', 'Pending'].includes(frm.doc.status),
                action: () => this.handle_create_subscription(frm)
            },
            {
                label: 'Sync Payment Details',
                condition: is_submitted && frm.doc.subscription,
                action: () => this.sync_payment_details(frm)
            },
            {
                label: 'View All Invoices',
                condition: is_submitted,
                action: () => this.view_all_invoices(frm)
            }
        ];
    },
    
    update_indicators: function(frm) {
        // Minimum period warning
        if (frm.doc.docstatus === 1 && frm.doc.start_date) {
            const monthsElapsed = this.get_months_elapsed(frm.doc.start_date);
            if (monthsElapsed < this.MINIMUM_MEMBERSHIP_MONTHS) {
                const remaining = this.MINIMUM_MEMBERSHIP_MONTHS - monthsElapsed;
                frm.set_intro(
                    `<div class="alert alert-warning">
                        <strong>Note:</strong> This membership is in its first year. 
                        ${remaining} month${remaining !== 1 ? 's' : ''} remaining until the minimum period ends.
                    </div>`,
                    'yellow'
                );
            }
        }
        
        // Next billing date
        if (frm.doc.next_billing_date) {
            frm.set_intro(__('Next billing date: {0}', [frappe.datetime.str_to_user(frm.doc.next_billing_date)]), 'blue');
        }
        
        // Custom amount indicators - Enhanced
        this.update_custom_amount_indicators(frm);
    },
    
    update_custom_amount_indicators: function(frm) {
        if (frm.doc.uses_custom_amount && frm.doc.custom_amount) {
            frm.dashboard.add_indicator(
                __('Using Custom Amount: {0}', [frappe.format(frm.doc.custom_amount, {fieldtype: 'Currency'})]), 
                'blue'
            );
            
            if (frm.doc.amount_difference !== 0) {
                const diff_text = frm.doc.amount_difference > 0 ? 
                    __('Above Standard: +{0}', [frappe.format(Math.abs(frm.doc.amount_difference), {fieldtype: 'Currency'})]) :
                    __('Below Standard: {0}', [frappe.format(Math.abs(frm.doc.amount_difference), {fieldtype: 'Currency'})]);
                frm.dashboard.add_indicator(diff_text, frm.doc.amount_difference > 0 ? 'green' : 'orange');
            }
        }
    },
    
    toggle_fields: function(frm) {
        const is_cancelled = frm.doc.status === 'Cancelled';
        frm.toggle_display(['cancellation_date', 'cancellation_reason', 'cancellation_type'], is_cancelled);
        frm.toggle_display(['last_payment_date'], !!frm.doc.last_payment_date);
        frm.toggle_display(['next_billing_date'], !!frm.doc.subscription);
        frm.set_df_property('renewal_date', 'read_only', 1);
    },
    
    // Field triggers - Enhanced with better custom amount handling
    membership_type: async function(frm) {
        await this.handle_membership_type_change(frm);
    },
    
    handle_membership_type_change: async function(frm) {
        frm.trigger('calculate_renewal_date');
        
        if (frm.doc.membership_type) {
            const mt = await this.get_membership_type_data(frm.doc.membership_type);
            
            // Update custom amount section visibility and validation
            frm.toggle_display('custom_amount_section', mt.allow_custom_amount);
            
            if (mt.allow_custom_amount) {
                this.setup_custom_amount_field(frm, mt);
            } else {
                // Reset custom amount if not allowed
                if (frm.doc.uses_custom_amount) {
                    frm.set_value('uses_custom_amount', 0);
                    frm.set_value('custom_amount', null);
                    frm.set_value('amount_reason', '');
                }
            }
            
            await this.calculate_effective_amount(frm);
        }
    },
    
    setup_custom_amount_field: function(frm, membership_type_data) {
        const min_amount = membership_type_data.minimum_amount || membership_type_data.amount;
        frm.set_df_property('custom_amount', 'description', 
            __('Minimum amount: {0}', [frappe.format(min_amount, {
                fieldtype: 'Currency', 
                currency: membership_type_data.currency
            })]));
    },
    
    start_date: function(frm) {
        frm.trigger('calculate_renewal_date');
    },
    
    uses_custom_amount: function(frm) {
        this.calculate_effective_amount(frm);
        this.update_custom_amount_indicators(frm);
        
        // Clear custom amount fields if unchecked
        if (!frm.doc.uses_custom_amount) {
            frm.set_value('custom_amount', null);
            frm.set_value('amount_reason', '');
        }
    },
    
    custom_amount: function(frm) {
        this.calculate_effective_amount(frm);
        this.validate_custom_amount(frm);
    },
    
    payment_method: function(frm) {
        const is_direct_debit = frm.doc.payment_method === 'Direct Debit';
        frm.toggle_reqd(['sepa_mandate'], is_direct_debit);
    },
    
    // Enhanced calculations and validation
    calculate_effective_amount: async function(frm) {
        let effective_amount = 0;
        
        if (frm.doc.uses_custom_amount && frm.doc.custom_amount) {
            effective_amount = frm.doc.custom_amount;
        } else if (frm.doc.membership_type) {
            const mt = await this.get_membership_type_data(frm.doc.membership_type);
            effective_amount = mt.amount;
        }
        
        frm.set_value('effective_amount', effective_amount);
        
        // Calculate difference from standard
        if (frm.doc.membership_type) {
            const mt = await this.get_membership_type_data(frm.doc.membership_type);
            const difference = effective_amount - mt.amount;
            frm.set_value('amount_difference', difference);
        }
    },
    
    validate_custom_amount: async function(frm) {
        if (!frm.doc.uses_custom_amount || !frm.doc.custom_amount || !frm.doc.membership_type) {
            return;
        }
        
        const mt = await this.get_membership_type_data(frm.doc.membership_type);
        
        if (!mt.allow_custom_amount) {
            frappe.msgprint(__('Custom amounts are not allowed for this membership type'));
            frm.set_value('uses_custom_amount', 0);
            return;
        }
        
        const minimum = mt.minimum_amount || mt.amount;
        if (frm.doc.custom_amount < minimum) {
            frappe.msgprint(__('Amount cannot be less than minimum: {0}', 
                [frappe.format(minimum, {fieldtype: 'Currency', currency: mt.currency})]));
            frm.set_value('custom_amount', minimum);
        }
    },
    
    calculate_renewal_date: async function(frm) {
        if (!frm.doc.membership_type || !frm.doc.start_date) return;
        
        const membership_type = await frappe.db.get_doc('Membership Type', frm.doc.membership_type);
        let months = 0;
        
        if (membership_type.subscription_period === 'Lifetime') {
            months = this.MINIMUM_MEMBERSHIP_MONTHS;
            frappe.msgprint(__('Note: Although this is a lifetime membership, a 1-year minimum commitment period still applies.'));
        } else {
            months = this.get_period_months(membership_type);
            
            if (months > 0 && months < this.MINIMUM_MEMBERSHIP_MONTHS) {
                frappe.msgprint(__('Note: Membership type has a period less than 1 year. Due to the mandatory minimum period, the renewal date is set to 1 year from start date.'));
                months = this.MINIMUM_MEMBERSHIP_MONTHS;
            }
        }
        
        if (months > 0) {
            const renewal_date = frappe.datetime.add_months(frm.doc.start_date, months);
            frm.set_value('renewal_date', renewal_date);
        }
        
        // Set related fields
        if (membership_type.subscription_plan) {
            frm.set_value('subscription_plan', membership_type.subscription_plan);
        }
        
        if (membership_type.allow_auto_renewal) {
            frm.set_value('auto_renew', membership_type.allow_auto_renewal);
        }
    },
    
    // Utility functions
    get_membership_type_data: async function(membership_type) {
        if (!this._membership_type_cache[membership_type]) {
            const response = await frappe.db.get_value(
                'Membership Type',
                membership_type,
                ['allow_custom_amount', 'minimum_amount', 'amount', 'currency', 'subscription_plan', 'allow_auto_renewal']
            );
            this._membership_type_cache[membership_type] = response.message;
        }
        return this._membership_type_cache[membership_type];
    },
    
    get_period_months: function(membership_type) {
        const period_map = {
            'Monthly': 1,
            'Quarterly': 3,
            'Biannual': 6,
            'Annual': 12,
            'Custom': membership_type.subscription_period_in_months || 0
        };
        return period_map[membership_type.subscription_period] || 0;
    },
    
    get_months_elapsed: function(start_date) {
        const startDate = frappe.datetime.str_to_obj(start_date);
        const today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
        return (today.getFullYear() - startDate.getFullYear()) * 12 + 
               today.getMonth() - startDate.getMonth();
    },
    
    can_cancel_membership: function(frm) {
        if (!frm.doc.start_date) return false;
        const startDate = frappe.datetime.str_to_obj(frm.doc.start_date);
        const minCancellationDate = frappe.datetime.add_months(startDate, this.MINIMUM_MEMBERSHIP_MONTHS);
        return frappe.datetime.str_to_obj(frappe.datetime.get_today()) >= minCancellationDate;
    },
    
    // Enhanced actions with better custom amount support
    handle_create_subscription: function(frm) {
        if (!frm.doc.subscription_plan) {
            frappe.msgprint(__('Please select a Subscription Plan first'));
            return;
        }
        
        frappe.msgprint(__('Creating subscription with enhanced options... Please wait.'));
        
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.membership.membership.create_subscription',
            args: {
                'membership_name': frm.doc.name,
                'options': this.DEFAULT_SUBSCRIPTION_OPTIONS
            },
            callback: (r) => {
                if (r.message) {
                    frm.reload_doc();
                    frappe.msgprint(__('Subscription created successfully.'));
                }
            },
            error: (r) => {
                frappe.msgprint({
                    title: __('Error'),
                    indicator: 'red',
                    message: r.message || __('An error occurred while creating the subscription.')
                });
            }
        });
    },
    
    // Enhanced amount adjustment dialog - Refactored for better UX
    show_enhanced_amount_dialog: async function(frm) {
        const mt = await this.get_membership_type_data(frm.doc.membership_type);
        
        if (!mt.allow_custom_amount) {
            frappe.msgprint(__('Custom amounts are not allowed for this membership type'));
            return;
        }
        
        const minimum_amount = mt.minimum_amount || mt.amount;
        const current_amount = frm.doc.uses_custom_amount ? frm.doc.custom_amount : mt.amount;
        
        const dialog = new frappe.ui.Dialog({
            title: __('Adjust Membership Amount'),
            size: 'small',
            fields: [
                {
                    fieldtype: 'HTML',
                    options: this.build_amount_info_html(current_amount, mt.amount, minimum_amount, mt.currency)
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    fieldtype: 'Currency',
                    fieldname: 'new_amount',
                    label: __('New Amount'),
                    reqd: 1,
                    default: current_amount,
                    description: __('Enter the new membership amount')
                },
                {
                    fieldtype: 'Small Text',
                    fieldname: 'reason',
                    label: __('Reason for Change'),
                    description: __('Optional: Explain why the amount is being adjusted')
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    fieldtype: 'Check',
                    fieldname: 'update_subscription',
                    label: __('Update Linked Subscription'),
                    default: !!frm.doc.subscription,
                    read_only: !frm.doc.subscription,
                    description: frm.doc.subscription ? 
                        __('Automatically update subscription amount and regenerate pending invoices') :
                        __('No subscription linked')
                }
            ],
            primary_action_label: __('Update Amount'),
            primary_action: (values) => this.process_amount_update(frm, values, minimum_amount, mt, dialog)
        });
        
        dialog.show();
    },
    
    build_amount_info_html: function(current, standard, minimum, currency) {
        const format_amount = (amount) => frappe.format(amount, {fieldtype: 'Currency', currency: currency});
        
        return `
            <div class="alert alert-info" style="margin-bottom: 15px;">
                <h5 style="margin-top: 0;">Amount Information</h5>
                <div class="row">
                    <div class="col-sm-4">
                        <strong>Current:</strong><br>
                        <span class="text-primary h6">${format_amount(current)}</span>
                    </div>
                    <div class="col-sm-4">
                        <strong>Standard:</strong><br>
                        <span class="text-muted">${format_amount(standard)}</span>
                    </div>
                    <div class="col-sm-4">
                        <strong>Minimum:</strong><br>
                        <span class="text-warning">${format_amount(minimum)}</span>
                    </div>
                </div>
            </div>
        `;
    },
    
    process_amount_update: function(frm, values, minimum_amount, membership_type_data, dialog) {
        if (values.new_amount < minimum_amount) {
            frappe.msgprint(__('Amount cannot be less than minimum: {0}', 
                [frappe.format(minimum_amount, {fieldtype: 'Currency', currency: membership_type_data.currency})]));
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
            freeze_message: __('Updating membership amount...'),
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.show_update_success_message(r.message, frm);
                    frm.reload_doc();
                    dialog.hide();
                }
            }
        });
    },
    
    show_update_success_message: function(response, frm) {
        let message = response.message;
        
        if (response.subscription_updated) {
            message += '<br>' + __('Subscription amount has been updated automatically.');
        }
        
        frappe.show_alert({
            message: message,
            indicator: 'green'
        }, 7);
    },
    
    renew_membership: function(frm) {
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.membership.membership.renew_membership',
            args: {'membership_name': frm.doc.name},
            callback: (r) => {
                if (r.message) {
                    frappe.set_route('Form', 'Membership', r.message);
                }
            }
        });
    },
    
    sync_payment_details: function(frm) {
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.membership.membership.sync_membership_payments',
            args: {'membership_name': frm.doc.name},
            callback: () => {
                frm.refresh();
                frappe.msgprint(__('Payment details synchronized with subscription.'));
            }
        });
    },
    
    view_all_invoices: function(frm) {
        frappe.call({
            method: 'verenigingen.verenigingen.doctype.membership.membership.show_all_invoices',
            args: {'membership_name': frm.doc.name},
            callback: (r) => {
                if (r.message && r.message.length) {
                    this.show_invoices_dialog(r.message);
                } else {
                    frappe.msgprint(__('No invoices found for this membership.'));
                }
            }
        });
    },
    
    revert_to_standard_amount: function(frm) {
        frappe.confirm(
            __('Are you sure you want to revert to the standard membership amount? This will affect future billing.'),
            () => {
                frappe.prompt({
                    fieldname: 'reason',
                    fieldtype: 'Small Text',
                    label: __('Reason (optional)')
                }, (values) => {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.membership.membership.revert_to_standard_amount',
                        args: {
                            membership_name: frm.doc.name,
                            reason: values.reason
                        },
                        freeze: true,
                        freeze_message: __('Reverting to standard amount...'),
                        callback: (r) => {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                }, 5);
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('Revert to Standard Amount'));
            }
        );
    },
    
    check_subscription_amount: function(frm) {
        if (!frm.doc.subscription) {
            frappe.msgprint(__('No subscription linked to this membership'));
            return;
        }
        
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Subscription Plan Detail',
                filters: {parent: frm.doc.subscription},
                fields: ['plan', 'cost'],
                parent: 'Subscription'
            },
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    const plan = r.message[0];
                    const expected_amount = frm.doc.uses_custom_amount ? frm.doc.custom_amount : frm.doc.effective_amount;
                    const matches = Math.abs(plan.cost - expected_amount) < 0.01;
                    
                    frappe.msgprint({
                        title: __('Subscription Amount Check'),
                        message: `
                            <strong>${__('Membership Amount')}:</strong> ${frappe.format(expected_amount, {fieldtype: 'Currency'})}<br>
                            <strong>${__('Subscription Amount')}:</strong> ${frappe.format(plan.cost, {fieldtype: 'Currency'})}<br>
                            <strong>${__('Status')}:</strong> ${matches ? 
                                '<span class="text-success">✓ Amounts match</span>' : 
                                '<span class="text-warning">⚠ Amounts do not match</span>'
                            }
                        `,
                        indicator: matches ? 'green' : 'orange'
                    });
                }
            }
        });
    },
    
    show_cancellation_dialog: function(frm) {
        const today = frappe.datetime.get_today();
        const startDate = frappe.datetime.str_to_obj(frm.doc.start_date);
        const minCancellationDate = frappe.datetime.add_months(startDate, this.MINIMUM_MEMBERSHIP_MONTHS);
        
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
            primary_action: (values) => {
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
                    callback: (r) => {
                        if (r.message) {
                            dialog.hide();
                            frm.reload_doc();
                        }
                    }
                });
            }
        });
        
        dialog.show();
    },
    
    show_invoices_dialog: function(invoices_data) {
        const table_html = this.create_invoice_table(invoices_data);
        
        const dialog = new frappe.ui.Dialog({
            title: __('All Invoices for Membership'),
            fields: [{
                fieldtype: 'HTML',
                options: table_html
            }],
            size: 'large'
        });
        
        dialog.show();
    },
    
    create_invoice_table: function(invoices) {
        const rows = invoices.map(invoice => `
            <tr>
                <td><a href="/app/sales-invoice/${invoice.invoice}">${invoice.invoice}</a></td>
                <td>${frappe.datetime.str_to_user(invoice.date)}</td>
                <td>${invoice.due_date ? frappe.datetime.str_to_user(invoice.due_date) : '-'}</td>
                <td>${frappe.format(invoice.amount, {fieldtype: 'Currency'})}</td>
                <td>${frappe.format(invoice.outstanding, {fieldtype: 'Currency'})}</td>
                <td>${this.get_status_indicator(invoice.status)}</td>
                <td>${invoice.source || '-'}</td>
            </tr>
        `).join('');
        
        const totals = invoices.reduce((acc, inv) => ({
            amount: acc.amount + flt(inv.amount),
            outstanding: acc.outstanding + flt(inv.outstanding)
        }), {amount: 0, outstanding: 0});
        
        return `
            <div class="invoices-list">
                <table class="table table-bordered table-condensed">
                    <thead>
                        <tr>
                            <th>${__("Invoice")}</th>
                            <th>${__("Date")}</th>
                            <th>${__("Due Date")}</th>
                            <th>${__("Amount")}</th>
                            <th>${__("Outstanding")}</th>
                            <th>${__("Status")}</th>
                            <th>${__("Source")}</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
                <div class="row mt-3">
                    <div class="col-sm-6">
                        <p><strong>${__("Total Invoices")}:</strong> ${invoices.length}</p>
                    </div>
                    <div class="col-sm-6 text-right">
                        <p><strong>${__("Total Amount")}:</strong> ${frappe.format(totals.amount, {fieldtype: 'Currency'})}</p>
                        <p><strong>${__("Total Outstanding")}:</strong> ${frappe.format(totals.outstanding, {fieldtype: 'Currency'})}</p>
                    </div>
                </div>
            </div>
        `;
    },
