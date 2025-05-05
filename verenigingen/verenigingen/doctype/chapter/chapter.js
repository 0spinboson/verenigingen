// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Chapter', {
    refresh: function(frm) {
        // Existing code

        // Add button to view chapter members
        frm.add_custom_button(__('View Members'), function() {
            frappe.set_route('List', 'Member', {'primary_chapter': frm.doc.name});
        }, __('Actions'));
        
        // Add button to send email to board members
        frm.add_custom_button(__('Email Board Members'), function() {
            send_email_to_board_members(frm);
        }, __('Actions'));
        
        // Add button to send email to all chapter members
        frm.add_custom_button(__('Email All Members'), function() {
            send_email_to_chapter_members(frm);
        }, __('Actions'));
    }
});

// Function to send email to board members
function send_email_to_board_members(frm) {
    if (!frm.doc.board_members || !frm.doc.board_members.length) {
        frappe.msgprint(__('No board members to email'));
        return;
    }
    
    var board_members = frm.doc.board_members.filter(function(member) {
        return member.is_active && member.email;
    }).map(function(member) {
        return member.email;
    });
    
    if (!board_members.length) {
        frappe.msgprint(__('No active board members with email addresses'));
        return;
    }
    
    var d = new frappe.ui.Dialog({
        title: __('Email Board Members'),
        fields: [
            {
                label: __('Subject'),
                fieldname: 'subject',
                fieldtype: 'Data',
                reqd: 1,
                default: __('Message from Chapter ') + frm.doc.name
            },
            {
                label: __('Message'),
                fieldname: 'message',
                fieldtype: 'Text Editor',
                reqd: 1
            }
        ],
        primary_action_label: __('Send'),
        primary_action: function() {
            var values = d.get_values();
            
            frappe.call({
                method: 'frappe.core.doctype.communication.email.make',
                args: {
                    recipients: board_members.join(','),
                    subject: values.subject,
                    content: values.message,
                    doctype: frm.doctype,
                    name: frm.docname,
                    send_email: 1
                },
                callback: function(r) {
                    if(!r.exc) {
                        frappe.msgprint(__('Email sent to board members'));
                        d.hide();
                    }
                }
            });
        }
    });
    
    d.show();
}

// Function to send email to all chapter members
function send_email_to_chapter_members(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Member',
            filters: {
                'primary_chapter': frm.doc.name
            },
            fields: ['name', 'full_name', 'email']
        },
        callback: function(r) {
            if (!r.message || !r.message.length) {
                frappe.msgprint(__('No members found for this chapter'));
                return;
            }
            
            var members = r.message.filter(function(member) {
                return member.email;
            });
            
            if (!members.length) {
                frappe.msgprint(__('No members with email addresses found'));
                return;
            }
            
            var d = new frappe.ui.Dialog({
                title: __('Email Chapter Members'),
                fields: [
                    {
                        label: __('Subject'),
                        fieldname: 'subject',
                        fieldtype: 'Data',
                        reqd: 1,
                        default: __('Message from Chapter ') + frm.doc.name
                    },
                    {
                        label: __('Message'),
                        fieldname: 'message',
                        fieldtype: 'Text Editor',
                        reqd: 1
                    }
                ],
                primary_action_label: __('Send'),
                primary_action: function() {
                    var values = d.get_values();
                    
                    frappe.call({
                        method: 'frappe.core.doctype.communication.email.make',
                        args: {
                            recipients: members.map(function(m) { return m.email; }).join(','),
                            subject: values.subject,
                            content: values.message,
                            doctype: frm.doctype,
                            name: frm.docname,
                            send_email: 1
                        },
                        callback: function(r) {
                            if(!r.exc) {
                                frappe.msgprint(__('Email sent to chapter members'));
                                d.hide();
                            }
                        }
                    });
                }
            });
            
            d.show();
        }
    });
}
