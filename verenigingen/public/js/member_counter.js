// Member doctype form customizations
frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Only show counter management for system managers
        if (frappe.user.has_role('System Manager')) {
            setup_member_counter_section(frm);
            load_counter_statistics(frm);
        }
        
        // Show member ID preview for new members
        if (frm.doc.__islocal && !frm.doc.member_id) {
            show_member_id_preview(frm);
        }
    },
    
    reset_counter_button: function(frm) {
        handle_counter_reset(frm);
    },
    
    birth_date: function(frm) {
        // Auto-calculate age when birth date changes
        if (frm.doc.birth_date) {
            const age = calculate_age(frm.doc.birth_date);
            frm.set_value('age', age);
            
            // Show warning for unusual ages
            if (age < 12) {
                frappe.show_alert({
                    message: __('Applicant is under 12 years old - may require special handling'),
                    indicator: 'orange'
                }, 8);
            } else if (age > 100) {
                frappe.show_alert({
                    message: __('Please verify birth date - applicant would be over 100 years old'),
                    indicator: 'yellow'
                }, 8);
            }
        }
    }
});

function setup_member_counter_section(frm) {
    // Add custom buttons for counter management
    frm.add_custom_button(__('Counter Statistics'), function() {
        show_counter_statistics_dialog();
    }, __('Member ID Management'));
    
    frm.add_custom_button(__('Reset Counter'), function() {
        show_counter_reset_dialog(frm);
    }, __('Member ID Management'));
    
    frm.add_custom_button(__('Migration Tools'), function() {
        show_migration_tools_dialog();
    }, __('Member ID Management'));
}

function load_counter_statistics(frm) {
    // Load and display current counter statistics
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member_id_manager.get_member_id_statistics',
        callback: function(r) {
            if (r.message) {
                update_counter_display(frm, r.message);
            }
        }
    });
}

function update_counter_display(frm, stats) {
    // Update the next_member_id field display
    if (frm.doc.name === 'MEMBER-COUNTER-SYSTEM' || frappe.user.has_role('System Manager')) {
        frm.set_df_property('next_member_id', 'description', 
            `Next ID: ${stats.next_id} | Highest Assigned: ${stats.highest_assigned} | Gaps: ${stats.gap_count}`);
    }
}

function show_member_id_preview(frm) {
    // Show preview of next member ID for new members
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member_id_manager.get_next_member_id_preview',
        callback: function(r) {
            if (r.message) {
                frm.set_df_property('member_id', 'description', 
                    `Will be assigned: ${r.message.next_id}`);
            }
        }
    });
}

function handle_counter_reset(frm) {
    // Handle the reset counter button click
    if (!frm.doc.reset_counter_to) {
        frappe.msgprint(__('Please enter a value to reset the counter to'));
        return;
    }
    
    frappe.confirm(
        __('Are you sure you want to reset the member ID counter to {0}? This action cannot be undone.', [frm.doc.reset_counter_to]),
        function() {
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member_id_manager.reset_member_id_counter',
                args: {
                    counter_value: frm.doc.reset_counter_to
                },
                freeze: true,
                freeze_message: __('Resetting counter...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 5);
                        
                        // Clear the input field
                        frm.set_value('reset_counter_to', '');
                        
                        // Reload statistics
                        load_counter_statistics(frm);
                    }
                }
            });
        }
    );
}

function show_counter_statistics_dialog() {
    // Show detailed counter statistics
    frappe.call({
        method: 'verenigingen.verenigingen.doctype.member.member_id_manager.get_member_id_statistics',
        callback: function(r) {
            if (r.message) {
                const stats = r.message;
                
                let dialog_content = `
                    <div class="counter-stats">
                        <h4>Member ID Counter Statistics</h4>
                        <table class="table table-bordered">
                            <tr><td><strong>Next ID to Assign</strong></td><td>${stats.next_id}</td></tr>
                            <tr><td><strong>Current Counter Value</strong></td><td>${stats.current_counter}</td></tr>
                            <tr><td><strong>Highest Assigned ID</strong></td><td>${stats.highest_assigned}</td></tr>
                            <tr><td><strong>Total Members with Numeric IDs</strong></td><td>${stats.total_with_numeric_ids}</td></tr>
                            <tr><td><strong>ID Gaps Found</strong></td><td>${stats.gap_count}</td></tr>
                        </table>
                `;
                
                if (stats.gaps && stats.gaps.length > 0) {
                    dialog_content += `
                        <h5>Available ID Gaps (first 10):</h5>
                        <p class="text-muted">${stats.gaps.join(', ')}</p>
                    `;
                }
                
                dialog_content += '</div>';
                
                frappe.msgprint({
                    title: __('Member ID Statistics'),
                    message: dialog_content,
                    wide: true
                });
            }
        }
    });
}

function show_counter_reset_dialog(frm) {
    // Show dialog for counter reset with validation
    let d = new frappe.ui.Dialog({
        title: __('Reset Member ID Counter'),
        fields: [
            {
                fieldname: 'new_counter_value',
                fieldtype: 'Int',
                label: __('New Counter Value'),
                reqd: 1,
                description: __('Enter the new counter value. Must be greater than current highest assigned ID.')
            },
            {
                fieldname: 'confirm_reset',
                fieldtype: 'Check',
                label: __('I understand this action cannot be undone'),
                reqd: 1
            }
        ],
        primary_action_label: __('Reset Counter'),
        primary_action: function(values) {
            if (!values.confirm_reset) {
                frappe.msgprint(__('Please confirm you understand this action cannot be undone'));
                return;
            }
            
            frappe.call({
                method: 'verenigingen.verenigingen.doctype.member.member_id_manager.reset_member_id_counter',
                args: {
                    counter_value: values.new_counter_value
                },
                freeze: true,
                freeze_message: __('Resetting counter...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 5);
                        
                        d.hide();
                        load_counter_statistics(frm);
                    }
                }
            });
        }
    });
    
    d.show();
}

function show_migration_tools_dialog() {
    // Show migration tools for counter system
    let d = new frappe.ui.Dialog({
        title: __('Member ID Migration Tools'),
        fields: [
            {
                fieldname: 'migration_info',
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        <h5>Migration Tools</h5>
                        <p>These tools help migrate from the old counter system in Verenigingen Settings to the new Member-based counter system.</p>
                        <p><strong>Warning:</strong> Only run migration once during system upgrade.</p>
                    </div>
                `
            }
        ],
        primary_action_label: __('Run Migration'),
        primary_action: function() {
            frappe.confirm(
                __('Run member ID counter migration? This should only be done once during system upgrade.'),
                function() {
                    frappe.call({
                        method: 'verenigingen.verenigingen.doctype.member.member.migrate_member_id_counter',
                        freeze: true,
                        freeze_message: __('Running migration...'),
                        callback: function(r) {
                            if (r.message) {
                                if (r.message.success) {
                                    frappe.show_alert({
                                        message: r.message.message,
                                        indicator: 'green'
                                    }, 8);
                                } else {
                                    frappe.msgprint(__('Migration failed: {0}', [r.message.error]));
                                }
                            }
                            d.hide();
                        }
                    });
                }
            );
        }
    });
    
    d.show();
}

function calculate_age(birth_date) {
    // Calculate age from birth date
    if (!birth_date) return null;
    
    const birth = new Date(birth_date);
    const today = new Date();
    
    if (isNaN(birth.getTime())) return null;
    
    let age = today.getFullYear() - birth.getFullYear();
    
    // Adjust if birthday hasn't occurred this year
    if (today.getMonth() < birth.getMonth() || 
        (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
        age--;
    }
    
    return age;
}
