// Copyright (c) 2025, R.S.P. and contributors
// For license information, please see license.txt

frappe.ui.form.on('E-Boekhouden Settings', {
	refresh: function(frm) {
		// Add custom buttons for testing
		frm.add_custom_button(__('Test Connection'), function() {
			frm.call('test_connection').then(r => {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __('Connection test successful!'),
						indicator: 'green'
					});
				} else {
					frappe.show_alert({
						message: __('Connection test failed. Check your credentials.'),
						indicator: 'red'
					});
				}
				frm.reload_doc();
			});
		}).addClass('btn-primary');
		
		// Add test API call button
		if (frm.doc.connection_status && frm.doc.connection_status.includes('✅')) {
			frm.add_custom_button(__('Test Chart of Accounts'), function() {
				frappe.call({
					method: 'verenigingen.verenigingen.doctype.e_boekhouden_settings.e_boekhouden_settings.get_grootboekrekeningen',
					callback: function(r) {
						if (r.message && r.message.success) {
							let dialog = new frappe.ui.Dialog({
								title: 'Chart of Accounts Preview',
								fields: [{
									fieldtype: 'HTML',
									options: `<div class="text-muted">
										<h5>API Response Preview:</h5>
										<pre style="max-height: 400px; overflow-y: auto; background: #f8f9fa; padding: 10px; border-radius: 3px;">${r.message.data_preview}</pre>
									</div>`
								}],
								primary_action_label: 'Close',
								primary_action: function() { dialog.hide(); }
							});
							dialog.show();
						} else {
							frappe.msgprint({
								title: 'API Test Failed',
								message: r.message.error || 'Unknown error occurred',
								indicator: 'red'
							});
						}
					}
				});
			});
		}
	},
	
	test_connection: function(frm) {
		// Handle test connection button click
		frm.call('test_connection').then(r => {
			frm.reload_doc();
		});
	},
	
	default_company: function(frm) {
		// Auto-set cost center when company changes
		if (frm.doc.default_company) {
			frappe.db.get_value('Cost Center', 
				{'company': frm.doc.default_company, 'is_group': 0}, 
				'name'
			).then(r => {
				if (r.message && r.message.name) {
					frm.set_value('default_cost_center', r.message.name);
				}
			});
		}
	}
});

// Add help text
frappe.ui.form.on('E-Boekhouden Settings', 'onload', function(frm) {
	frm.set_intro(__('Configure your e-Boekhouden API credentials to enable data migration to ERPNext. You can find your API credentials in your e-Boekhouden account settings.'));
});