frappe.ui.form.on('Member', {
    refresh: function(frm) {
        // Add buttons to create customer and user
        if (!frm.doc.customer) {
            frm.add_custom_button(__('Create Customer'), function() {
                frm.call({
                    doc: frm.doc,
                    method: 'create_customer',
                    callback: function(r) {
                        if (r.message) {
                            frm.refresh();
                        }
                    }
                });
            }, __('Actions'));
        }
        
        if (!frm.doc.user && frm.doc.email) {
            frm.add_custom_button(__('Create User'), function() {
                frm.call({
                    doc: frm.doc,
                    method: 'create_user',
                    callback: function(r) {
                        if (r.message) {
                            frm.refresh();
                        }
                    }
                });
            }, __('Actions'));
        }
        
        // Add button to create a new membership
        frm.add_custom_button(__('Create Membership'), function() {
            frappe.new_doc('Membership', {
                'member': frm.doc.name,
                'member_name': frm.doc.full_name,
                'email': frm.doc.email,
                'mobile_no': frm.doc.mobile_no,
                'start_date': frappe.datetime.get_today()
            });
        }, __('Actions'));
        
        // Add button to view memberships
        frm.add_custom_button(__('View Memberships'), function() {
            frappe.set_route('List', 'Membership', {'member': frm.doc.name});
        }, __('View'));
        
        // Add button to view linked customer
        if (frm.doc.customer) {
            frm.add_custom_button(__('Customer'), function() {
                frappe.set_route('Form', 'Customer', frm.doc.customer);
            }, __('View'));
        }
        
        // Add button to view linked user
        if (frm.doc.user) {
            frm.add_custom_button(__('User'), function() {
                frappe.set_route('Form', 'User', frm.doc.user);
            }, __('View'));
        }
        
        // Add button to view current membership
        if (frm.doc.current_membership_details) {
            frm.add_custom_button(__('Current Membership'), function() {
                frappe.set_route('Form', 'Membership', frm.doc.current_membership_details);
            }, __('View'));
        }
        
        // Setup Address buttons and display
        frm.add_custom_button(__('New Address'), function() {
            frappe.new_doc('Address', {
                address_title: frm.doc.full_name,
                address_type: 'Personal',
                links: [{
                    link_doctype: 'Member',
                    link_name: frm.doc.name
                }]
            });
        }, __('Actions'));
        
        if (frm.doc.address) {
            frm.add_custom_button(__('Address'), function() {
                frappe.set_route('Form', 'Address', frm.doc.address);
            }, __('View'));
        }
        
        // Refresh Address HTML
        if (frm.doc.__onload && frm.doc.__onload.addr_list) {
            let addr_html = frappe.render_template('address_list', {
                addr_list: frm.doc.__onload.addr_list
            });
            $(frm.fields_dict['address_html'].wrapper).html(addr_html);
        }
    },
    
    first_name: function(frm) {
        // Automatically update full name
        frm.trigger('update_full_name');
    },
    
    middle_name: function(frm) {
        // Automatically update full name
        frm.trigger('update_full_name');
    },
    
    last_name: function(frm) {
        // Automatically update full name
        frm.trigger('update_full_name');
    },
    
    update_full_name: function(frm) {
        // Build full name from components
        let full_name = [
            frm.doc.first_name,
            frm.doc.middle_name,
            frm.doc.last_name
        ].filter(Boolean).join(' ');
        
        frm.set_value('full_name', full_name);
    },
    
    address: function(frm) {
        // Fetch address details when address is selected
        if (frm.doc.address) {
            frappe.call({
                method: 'frappe.contacts.doctype.address.address.get_address_display',
                args: {
                    "address_dict": frm.doc.address
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('address_display', r.message);
                    }
                }
            });
        }
    }
});
