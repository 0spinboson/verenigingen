// Copyright (c) 2025, R.S.P. and contributors
// For license information, please see license.txt

frappe.ui.form.on('E-Boekhouden Migration', {
	refresh: function(frm) {
		console.log('E-Boekhouden Migration refresh called', frm.doc);
		console.log('Doc status:', frm.doc.docstatus, 'Migration status:', frm.doc.migration_status);
		
		// Add custom buttons based on status
		if (frm.doc.docstatus === 0 && frm.doc.migration_status === 'Draft') {
			console.log('Adding buttons for Draft status');
			
			frm.add_custom_button(__('Test Connection'), function() {
				console.log('Test Connection clicked');
				frappe.call({
					method: 'verenigingen.utils.eboekhouden_api.test_api_connection',
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __('✅ Connection successful! API is working.'),
								indicator: 'green'
							});
						} else {
							frappe.show_alert({
								message: __('❌ Connection failed: ') + (r.message ? r.message.error : 'Unknown error'),
								indicator: 'red'
							});
						}
					}
				});
			}).addClass('btn-info');
			
			frm.add_custom_button(__('Preview Migration'), function() {
				console.log('Preview Migration button clicked');
				
				// Simple validation
				if (!frm.doc.migration_name) {
					frappe.msgprint(__('Migration Name is required'));
					return;
				}
				if (!frm.doc.company) {
					frappe.msgprint(__('Company is required'));
					return;
				}
				
				console.log('Validation passed, showing confirm dialog');
				frappe.confirm(
					__('This will preview what data would be migrated without actually importing anything. Continue?'),
					function() {
						console.log('User confirmed preview migration');
						
						// Use direct API call instead of form submission
						console.log('Starting preview migration via API...');
						
						frappe.call({
							method: 'verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration.start_migration_api',
							args: {
								migration_name: frm.doc.name,
								dry_run: 1
							},
							callback: function(r) {
								console.log('API call completed, response:', r);
								
								if (r.message && r.message.success) {
									console.log('Preview migration started successfully');
									frappe.show_alert({
										message: __('✅ Preview migration started successfully!'),
										indicator: 'green'
									});
									
									// Reload the form to show updated status
									setTimeout(() => {
										frm.reload_doc();
									}, 1000);
								} else {
									console.error('Preview migration failed:', r.message);
									frappe.show_alert({
										message: __('❌ Preview migration failed: ') + (r.message ? r.message.error : 'Unknown error'),
										indicator: 'red'
									});
								}
							},
							error: function(error) {
								console.error('API call error:', error);
								frappe.show_alert({
									message: __('❌ API call failed: ') + (error.message || error),
									indicator: 'red'
								});
							}
						});
					},
					function() {
						console.log('User cancelled preview migration');
					}
				);
			}).addClass('btn-secondary');
			
			frm.add_custom_button(__('Start Migration'), function() {
				console.log('Start Migration button clicked');
				
				// Simple validation
				if (!frm.doc.migration_name) {
					frappe.msgprint(__('Migration Name is required'));
					return;
				}
				if (!frm.doc.company) {
					frappe.msgprint(__('Company is required'));
					return;
				}
				
				frappe.confirm(
					__('Are you sure you want to start the migration? This will import data from e-Boekhouden into ERPNext.<br><br><strong>This action cannot be undone!</strong>'),
					function() {
						console.log('User confirmed start migration');
						
						// Use direct API call instead of form submission
						console.log('Starting actual migration via API...');
						
						frappe.call({
							method: 'verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration.start_migration_api',
							args: {
								migration_name: frm.doc.name,
								dry_run: 0
							},
							callback: function(r) {
								console.log('API call completed, response:', r);
								
								if (r.message && r.message.success) {
									console.log('Migration started successfully');
									frappe.show_alert({
										message: __('✅ Migration started successfully!'),
										indicator: 'green'
									});
									
									// Reload the form to show updated status
									setTimeout(() => {
										frm.reload_doc();
									}, 1000);
								} else {
									console.error('Migration failed:', r.message);
									frappe.show_alert({
										message: __('❌ Migration failed: ') + (r.message ? r.message.error : 'Unknown error'),
										indicator: 'red'
									});
								}
							},
							error: function(error) {
								console.error('API call error:', error);
								frappe.show_alert({
									message: __('❌ API call failed: ') + (error.message || error),
									indicator: 'red'
								});
							}
						});
					}
				);
			}).addClass('btn-primary');
		} else if (frm.doc.migration_status === 'Failed') {
			console.log('Adding reset button for Failed status');
			frm.add_custom_button(__('Reset to Draft'), function() {
				frappe.confirm(
					__('This will reset the migration status to Draft so you can try again. Continue?'),
					function() {
						frappe.call({
							method: 'frappe.client.set_value',
							args: {
								doctype: 'E-Boekhouden Migration',
								name: frm.doc.name,
								fieldname: {
									'migration_status': 'Draft',
									'error_log': '',
									'current_operation': '',
									'progress_percentage': 0
								}
							},
							callback: function(r) {
								if (r.message) {
									frappe.show_alert({
										message: __('Migration reset to Draft status'),
										indicator: 'green'
									});
									frm.reload_doc();
								}
							}
						});
					}
				);
			}).addClass('btn-secondary');
		} else {
			console.log('Not adding buttons - docstatus:', frm.doc.docstatus, 'status:', frm.doc.migration_status);
		}
		
		// Add progress refresh button if in progress
		if (frm.doc.migration_status === 'In Progress') {
			frm.add_custom_button(__('Refresh Progress'), function() {
				frm.reload_doc();
			});
			
			// Auto-refresh every 5 seconds
			if (!frm.auto_refresh_interval) {
				frm.auto_refresh_interval = setInterval(() => {
					frm.reload_doc();
				}, 5000);
			}
		} else if (frm.auto_refresh_interval) {
			clearInterval(frm.auto_refresh_interval);
			frm.auto_refresh_interval = null;
		}
		
		// Add view results button if completed
		if (frm.doc.migration_status === 'Completed') {
			frm.add_custom_button(__('View Migration Summary'), function() {
				let dialog = new frappe.ui.Dialog({
					title: 'Migration Summary',
					fields: [{
						fieldtype: 'HTML',
						options: `<div class="migration-summary">
							<h5>Migration Results:</h5>
							<div class="row">
								<div class="col-md-4">
									<div class="card text-center">
										<div class="card-body">
											<h3 class="text-success">${frm.doc.imported_records || 0}</h3>
											<p>Imported Records</p>
										</div>
									</div>
								</div>
								<div class="col-md-4">
									<div class="card text-center">
										<div class="card-body">
											<h3 class="text-danger">${frm.doc.failed_records || 0}</h3>
											<p>Failed Records</p>
										</div>
									</div>
								</div>
								<div class="col-md-4">
									<div class="card text-center">
										<div class="card-body">
											<h3 class="text-info">${frm.doc.total_records || 0}</h3>
											<p>Total Records</p>
										</div>
									</div>
								</div>
							</div>
							<hr>
							<h6>Detailed Summary:</h6>
							<pre style="max-height: 300px; overflow-y: auto; background: #f8f9fa; padding: 10px; border-radius: 3px;">${frm.doc.migration_summary || 'No summary available'}</pre>
						</div>`
					}],
					primary_action_label: 'Close',
					primary_action: function() { dialog.hide(); }
				});
				dialog.show();
			});
		}
		
		// Show progress bar if migration is running
		if (frm.doc.migration_status === 'In Progress') {
			frm.dashboard.add_progress('Migration Progress', 
				frm.doc.progress_percentage || 0, 
				frm.doc.current_operation || 'Processing...'
			);
		}
		
		// Set help text based on status
		if (frm.doc.migration_status === 'Draft') {
			frm.set_intro(__('<strong>How to use:</strong><br>1. First click "Test Connection" to verify API settings<br>2. Click "Preview Migration" to see what would be imported (recommended)<br>3. Click "Start Migration" to perform the actual import'), 'blue');
		} else if (frm.doc.migration_status === 'In Progress') {
			frm.set_intro(__('Migration is currently running. Progress will be updated automatically.'));
		} else if (frm.doc.migration_status === 'Completed') {
			frm.set_intro(__('Migration completed successfully. Check the summary for details.'));
		} else if (frm.doc.migration_status === 'Failed') {
			frm.set_intro(__('Migration failed. Check the error log for details.'), 'red');
		}
	},
	
	onload: function(frm) {
		// Set default company from E-Boekhouden settings
		if (!frm.doc.company) {
			frappe.db.get_single_value('E-Boekhouden Settings', 'default_company')
				.then(company => {
					if (company) {
						frm.set_value('company', company);
					}
				});
		}
		
		// Set default date range (last month)
		if (!frm.doc.date_from && !frm.doc.date_to) {
			let today = new Date();
			let lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
			let lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
			
			frm.set_value('date_from', frappe.datetime.obj_to_str(lastMonth));
			frm.set_value('date_to', frappe.datetime.obj_to_str(lastMonthEnd));
		}
	},
	
	migrate_transactions: function(frm) {
		// Show/hide date fields based on transaction migration
		frm.toggle_reqd(['date_from', 'date_to'], frm.doc.migrate_transactions);
	}
});

// Clean up intervals when form is destroyed
frappe.ui.form.on('E-Boekhouden Migration', 'before_unload', function(frm) {
	if (frm.auto_refresh_interval) {
		clearInterval(frm.auto_refresh_interval);
	}
});