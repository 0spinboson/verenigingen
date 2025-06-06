// SEPA mandate utility functions for Member doctype

function generateMandateReference(memberDoc) {
    // Format: M-[MemberID]-[YYYYMMDD]-[Random3Digits]
    const today = new Date();
    const dateStr = today.getFullYear().toString() + 
                   (today.getMonth() + 1).toString().padStart(2, '0') + 
                   today.getDate().toString().padStart(2, '0');
    
    const randomSuffix = Math.floor(Math.random() * 900) + 100; // 3-digit random number
    
    let memberId = memberDoc.member_id || memberDoc.name.replace('Assoc-Member-', '').replace(/-/g, '');
    
    return `M-${memberId}-${dateStr}-${randomSuffix}`;
}

function create_sepa_mandate_with_dialog(frm, message = null) {
    const suggestedReference = generateMandateReference(frm.doc);
    
    const confirmMessage = message || __('Would you like to create a new SEPA mandate for this bank account?');
    
    frappe.confirm(
        confirmMessage,
        function() {
            const d = new frappe.ui.Dialog({
                title: __('Create SEPA Mandate'),
                size: 'large',
                fields: [
                    {
                        fieldname: 'mandate_id',
                        fieldtype: 'Data',
                        label: __('Mandate Reference'),
                        reqd: 1,
                        default: suggestedReference,
                        description: __('Unique identifier for this mandate')
                    },
                    {
                        fieldname: 'iban',
                        fieldtype: 'Data',
                        label: __('IBAN'),
                        reqd: 1,
                        default: frm.doc.iban || '',
                        description: __('International Bank Account Number')
                    },
                    {
                        fieldname: 'bic',
                        fieldtype: 'Data',
                        label: __('BIC/SWIFT Code'),
                        default: frm.doc.bic || '',
                        description: __('Bank Identifier Code (auto-derived from IBAN if empty)')
                    },
                    {
                        fieldname: 'account_holder_name',
                        fieldtype: 'Data',
                        label: __('Account Holder Name'),
                        reqd: 1,
                        default: frm.doc.full_name || '',
                        description: __('Name of the bank account holder')
                    },
                    {
                        fieldtype: 'Column Break'
                    },
                    {
                        fieldname: 'mandate_type',
                        fieldtype: 'Select',
                        label: __('Mandate Type'),
                        options: 'One-off\nRecurring',
                        default: 'Recurring',
                        reqd: 1
                    },
                    {
                        fieldname: 'sign_date',
                        fieldtype: 'Date',
                        label: __('Signature Date'),
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        fieldname: 'used_for_memberships',
                        fieldtype: 'Check',
                        label: __('Use for Membership Payments'),
                        default: 1
                    },
                    {
                        fieldname: 'used_for_donations',
                        fieldtype: 'Check',
                        label: __('Use for Donation Payments'),
                        default: 0
                    },
                    {
                        fieldtype: 'Section Break',
                        label: __('Additional Options')
                    },
                    {
                        fieldname: 'update_payment_method',
                        fieldtype: 'Check',
                        label: __('Update Member Payment Method to Direct Debit'),
                        default: frm.doc.payment_method !== 'Direct Debit' ? 1 : 0
                    },
                    {
                        fieldname: 'notes',
                        fieldtype: 'Text',
                        label: __('Notes'),
                        description: __('Optional notes about this mandate')
                    }
                ],
                primary_action_label: __('Create Mandate'),
                primary_action: function(values) {
                    create_mandate_with_values(frm, values, d);
                }
            });
            
            d.show();
            
            // Auto-derive BIC when IBAN changes
            d.fields_dict.iban.df.onchange = function() {
                const iban = d.get_value('iban');
                if (iban && !d.get_value('bic')) {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.member.member.derive_bic_from_iban',
                        args: { iban: iban },
                        callback: function(r) {
                            if (r.message && r.message.bic) {
                                d.set_value('bic', r.message.bic);
                            }
                        }
                    });
                }
            };
        },
        function() {
            console.log('User declined mandate creation');
            frappe.show_alert(__('No new SEPA mandate created. The existing mandate will remain active.'), 5);
        }
    );
}

function create_mandate_with_values(frm, values, dialog) {
    let additionalArgs = {};
    
    // Get server-side validation data
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.validate_mandate_creation',
        args: {
            member: frm.doc.name,
            iban: values.iban,
            mandate_id: values.mandate_id
        },
        callback: function(validation_response) {
            const serverData = validation_response.message;
            
            if (serverData && serverData.existing_mandate) {
                additionalArgs.replace_existing = serverData.existing_mandate;
                frappe.show_alert({
                    message: __('Existing mandate {0} will be replaced', [serverData.existing_mandate]),
                    indicator: 'orange'
                }, 5);
            }
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member.create_and_link_mandate_enhanced',
                args: {
                    member: frm.doc.name,
                    mandate_id: values.mandate_id,
                    iban: values.iban,
                    bic: values.bic || '',
                    account_holder_name: values.account_holder_name,
                    mandate_type: values.mandate_type,
                    sign_date: values.sign_date,
                    used_for_memberships: values.used_for_memberships,
                    used_for_donations: values.used_for_donations,
                    notes: values.notes,
                    ...additionalArgs
                },
                callback: function(r) {
                    console.log('Mandate creation response:', r);
                    if (r.message) {
                        let alertMessage = __('SEPA Mandate {0} created successfully', [values.mandate_id]);
                        if (serverData && serverData.existing_mandate) {
                            alertMessage += '. ' + __('Previous mandate has been marked as replaced.');
                        }
                        
                        frappe.show_alert({
                            message: alertMessage,
                            indicator: 'green'
                        }, 7);
                        
                        // Update payment method if requested
                        if (values.update_payment_method && frm.doc.payment_method !== 'Direct Debit') {
                            frm.set_value('payment_method', 'Direct Debit');
                            frappe.show_alert({
                                message: __('Payment method updated to Direct Debit'),
                                indicator: 'blue'
                            }, 5);
                        }
                        
                        // Wait a moment then reload the form
                        setTimeout(() => {
                            frm.reload_doc();
                        }, 1500);
                    }
                },
                error: function(r) {
                    console.error('Error creating mandate:', r);
                }
            });
            dialog.hide();
        }
    });
}

function check_sepa_mandate_status(frm) {
    if (!frm.doc.iban) return;
    
    // Prevent duplicate SEPA mandate displays
    if (frm._sepa_check_done) return;
    frm._sepa_check_done = true;
    
    let currentMandate = null;
    
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member.get_active_sepa_mandate',
        args: {
            member: frm.doc.name,
            iban: frm.doc.iban
        },
        callback: function(r) {
            console.log('SEPA mandate check response:', r);
            
            if (r.message) {
                currentMandate = r.message;
                console.log('Current mandate found:', currentMandate);
                
                if (currentMandate.status === 'Active') {
                    frm.dashboard.add_indicator(__("SEPA Mandate: {0}", [currentMandate.mandate_id]), "green");
                } else if (currentMandate.status === 'Pending') {
                    frm.dashboard.add_indicator(__("SEPA Mandate: {0} (Pending)", [currentMandate.mandate_id]), "orange");
                } else {
                    frm.dashboard.add_indicator(__("SEPA Mandate: {0} ({1})", [currentMandate.mandate_id, currentMandate.status]), "red");
                }
                
                // Add view mandate button if one exists
                frm.add_custom_button(__('View SEPA Mandate'), function() {
                    frappe.set_route('Form', 'SEPA Mandate', currentMandate.name);
                }, __('View'));
                
            } else {
                console.log('No active mandate found for this IBAN');
                
                // Show mandate creation option if IBAN exists but no mandate
                if (frm.doc.iban && frm.doc.payment_method === 'Direct Debit') {
                    frm.dashboard.add_indicator(__("No SEPA Mandate"), "red");
                    
                    frm.add_custom_button(__('Create SEPA Mandate'), function() {
                        create_sepa_mandate_with_dialog(frm, __('No active SEPA mandate found for this IBAN. Would you like to create one?'));
                    }, __('Actions'));
                }
            }
        }
    });
}

// Export functions for use in member.js
window.SepaUtils = {
    generateMandateReference,
    create_sepa_mandate_with_dialog,
    check_sepa_mandate_status
};