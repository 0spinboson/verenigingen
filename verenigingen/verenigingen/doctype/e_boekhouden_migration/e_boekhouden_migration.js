// Copyright (c) 2025, R.S.P. and contributors
// For license information, please see license.txt

frappe.ui.form.on('E-Boekhouden Migration', {
	refresh: function(frm) {
		// Add custom buttons based on status
		if (frm.doc.docstatus === 0 && frm.doc.migration_status === 'Draft') {
			frm.add_custom_button(__('Preview Migration'), function() {
				// Set dry run and submit for preview
				frm.set_value('dry_run', 1);
				frm.save().then(() => {
					frm.submit();
				});
			}).addClass('btn-secondary');
			
			frm.add_custom_button(__('Start Migration'), function() {
				frappe.confirm(
					__('Are you sure you want to start the migration? This will import data from e-Boekhouden into ERPNext.'),
					function() {
						frm.set_value('dry_run', 0);
						frm.save().then(() => {
							frm.submit();
						});
					}
				);
			}).addClass('btn-primary');
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
			frm.set_intro(__('Configure your migration settings and click "Start Migration" to begin importing data from e-Boekhouden.'));
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