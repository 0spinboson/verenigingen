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
			
			frm.add_custom_button(__('Full Migration'), function() {
				console.log('Full Migration button clicked');
				
				// Simple validation
				if (!frm.doc.company) {
					frappe.msgprint(__('Company is required'));
					return;
				}
				
				frappe.confirm(
					__('<h4>Full E-Boekhouden Migration</h4>' +
					   '<p>This will perform a comprehensive migration that includes:</p>' +
					   '<ul>' +
					   '<li>Automatically determine the date range from E-Boekhouden</li>' +
					   '<li>Create opening balance journal entry</li>' +
					   '<li>Migrate chart of accounts</li>' +
					   '<li>Migrate all transactions</li>' +
					   '<li>Create payment entries where applicable</li>' +
					   '</ul>' +
					   '<p><strong>⚠️ WARNING: This action cannot be undone and may take several minutes!</strong></p>' +
					   '<p>Are you sure you want to proceed?</p>'),
					function() {
						console.log('User confirmed full migration');
						
						// Show progress dialog
						let progress_dialog = new frappe.ui.Dialog({
							title: 'Full Migration Progress',
							fields: [{
								fieldtype: 'HTML',
								fieldname: 'progress_html',
								options: '<div id="migration-progress">' +
										'<div class="progress">' +
										'<div class="progress-bar progress-bar-striped active" role="progressbar" ' +
										'style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">' +
										'0%</div></div>' +
										'<p class="text-muted mt-2" id="progress-message">Initializing migration...</p>' +
										'</div>'
							}]
						});
						progress_dialog.show();
						progress_dialog.get_close_btn().hide();
						
						// Start full migration
						frappe.call({
							method: 'verenigingen.utils.eboekhouden_full_migration.migrate_all_eboekhouden_data',
							callback: function(r) {
								progress_dialog.hide();
								console.log('Full migration completed, response:', r);
								
								if (r.message && r.message.success) {
									console.log('Full migration successful');
									
									// Show detailed summary dialog
									let summary = r.message.summary;
									let summary_html = `
										<h5>Migration Completed Successfully!</h5>
										<hr>
										<div class="row">
											<div class="col-md-6">
												<h6>Date Range:</h6>
												<p>${summary.date_range.from} to ${summary.date_range.to}<br>
												(${summary.date_range.years} years, ${summary.date_range.days} days)</p>
											</div>
											<div class="col-md-6">
												<h6>Migration Date:</h6>
												<p>${summary.migration_date}</p>
											</div>
										</div>
										<hr>
										<h6>Results Summary:</h6>
										<table class="table table-sm">
											<tr>
												<td>Chart of Accounts</td>
												<td>${summary.totals.total_accounts} accounts</td>
											</tr>
											<tr>
												<td>Journal Entries</td>
												<td>${summary.totals.total_journal_entries} created</td>
											</tr>
											<tr>
												<td>Payment Entries</td>
												<td>${summary.totals.total_payment_entries} created</td>
											</tr>
											<tr>
												<td>Total Errors</td>
												<td class="${summary.totals.total_errors > 0 ? 'text-danger' : 'text-success'}">
													${summary.totals.total_errors}
												</td>
											</tr>
										</table>
									`;
									
									if (summary.results.opening_balance.created) {
										summary_html += `<p><strong>Opening Balance:</strong> Created as ${summary.results.opening_balance.journal_entry}</p>`;
									}
									
									let result_dialog = new frappe.ui.Dialog({
										title: 'Full Migration Summary',
										fields: [{
											fieldtype: 'HTML',
											options: summary_html
										}],
										primary_action_label: 'Close',
										primary_action: function() {
											result_dialog.hide();
											frm.reload_doc();
										}
									});
									result_dialog.show();
									
								} else {
									console.error('Full migration failed:', r.message);
									frappe.msgprint({
										title: __('Migration Failed'),
										message: __('Full migration failed: ') + (r.message ? r.message.error : 'Unknown error'),
										indicator: 'red'
									});
								}
							},
							error: function(error) {
								progress_dialog.hide();
								console.error('Full migration error:', error);
								frappe.msgprint({
									title: __('Migration Error'),
									message: __('Full migration error: ') + (error.message || error),
									indicator: 'red'
								});
							}
						});
						
						// Update progress bar
						frappe.realtime.on('progress', function(data) {
							if (data.progress) {
								let percent = data.progress;
								let message = data.title || 'Processing...';
								
								$('#migration-progress .progress-bar')
									.css('width', percent + '%')
									.attr('aria-valuenow', percent)
									.text(percent + '%');
								$('#progress-message').text(message);
							}
						});
					}
				);
			}).addClass('btn-warning');
			
			// Add Post-Migration section with account type mapping
			frm.add_custom_button(__('Map Account Types'), function() {
				// Step 1: Analyze categories
				frappe.call({
					method: 'verenigingen.utils.eboekhouden_account_type_mapping.analyze_account_categories',
					callback: function(r) {
						if (r.message && r.message.success) {
							show_account_mapping_dialog(r.message);
						} else {
							frappe.msgprint({
								title: __('Error'),
								message: __('Failed to analyze account categories'),
								indicator: 'red'
							});
						}
					}
				});
			}, __('Post-Migration'));
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
			frm.set_intro(__('<strong>How to use:</strong><br>1. First click "Test Connection" to verify API settings<br>2. Click "Preview Migration" to see what would be imported (recommended)<br>3. Click "Start Migration" to perform the actual import with specified date range<br>4. Or click "Full Migration" to automatically migrate ALL data from E-Boekhouden'), 'blue');
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

// Function to show account mapping dialog
function show_account_mapping_dialog(analysis_data) {
	let mapping_fields = [];
	
	// Add intro
	mapping_fields.push({
		fieldtype: 'HTML',
		options: `<div class="alert alert-info">
			<h5>Account Type Mapping</h5>
			<p>Map E-Boekhouden categories to ERPNext account types. This is a two-step process:</p>
			<ol>
				<li>Review and adjust the mappings below</li>
				<li>Preview changes before applying</li>
			</ol>
			<p><strong>Note:</strong> Receivable/Payable accounts require party information in journal entries.</p>
		</div>`
	});
	
	// Add mapping fields for each proposal (group or category)
	analysis_data.mapping_proposals.forEach(function(proposal) {
		let suggested = proposal.suggested_mapping || {};
		let proposal_type = proposal.type || 'category';
		let display_name = proposal.name || proposal.identifier || proposal.category;
		let identifier = proposal.identifier || proposal.category;
		
		let field_html = `
			<div class="form-group">
				<label>${display_name} (${proposal.account_count} accounts)</label>
				<div class="text-muted small mb-2">`;
		
		// Show type badge
		if (proposal_type === 'group') {
			field_html += `<span class="badge badge-info">Group ${identifier}</span> `;
		} else {
			field_html += `<span class="badge badge-secondary">Category</span> `;
		}
		
		// Show sample accounts
		if (proposal.sample_accounts && proposal.sample_accounts.length > 0) {
			field_html += '<strong>Examples:</strong> ';
			field_html += proposal.sample_accounts.slice(0, 3).map(acc => 
				`${acc.code} - ${acc.description}`
			).join(', ');
			if (proposal.account_count > 3) {
				field_html += ` ... and ${proposal.account_count - 3} more`;
			}
		}
		
		// Show suggestion if available
		if (suggested.reason) {
			field_html += `<br><strong>Suggestion:</strong> ${suggested.reason}`;
			if (suggested.action) {
				field_html += ` (${suggested.action})`;
			}
		}
		
		// Show current types
		if (proposal.current_erpnext_types) {
			field_html += `<br><strong>Current ERPNext types:</strong> ${proposal.current_erpnext_types.join(', ')}`;
		}
		
		field_html += '</div></div>';
		
		mapping_fields.push({
			fieldtype: 'HTML',
			fieldname: `${identifier}_label`,
			options: field_html
		});
		
		mapping_fields.push({
			fieldtype: 'Select',
			fieldname: `mapping_${identifier}`,
			label: '',
			options: [
				'',
				'Skip',
				'Receivable',
				'Payable',
				'Bank',
				'Cash',
				'Current Asset',
				'Fixed Asset',
				'Stock',
				'Current Liability',
				'Expense',
				'Income'
			],
			default: suggested.type === 'Various' ? 'Skip' : (suggested.type || 'Skip')
		});
		
		mapping_fields.push({
			fieldtype: 'Column Break'
		});
	});
	
	// Create dialog
	let mapping_dialog = new frappe.ui.Dialog({
		title: 'Map E-Boekhouden Account Types',
		fields: mapping_fields,
		size: 'large',
		primary_action_label: 'Preview Changes',
		primary_action: function(values) {
			// Extract mappings
			let mappings = {};
			for (let key in values) {
				if (key.startsWith('mapping_')) {
					let category = key.replace('mapping_', '');
					if (values[key] && values[key] !== 'Skip') {
						mappings[category] = values[key];
					}
				}
			}
			
			// Preview changes
			frappe.call({
				method: 'verenigingen.utils.eboekhouden_account_type_mapping.get_mapping_preview',
				args: { mappings: mappings },
				callback: function(r) {
					if (r.message && r.message.success) {
						show_mapping_preview(mappings, r.message.preview);
					}
				}
			});
		},
		secondary_action_label: 'Cancel'
	});
	
	mapping_dialog.show();
}

// Function to show mapping preview
function show_mapping_preview(mappings, preview) {
	let preview_html = '<h5>Preview of Changes</h5><hr>';
	let total_updates = 0;
	
	for (let category in preview) {
		let cat_data = preview[category];
		let update_count = cat_data.accounts_to_update.length;
		total_updates += update_count;
		
		preview_html += `<h6>${category} → ${cat_data.target_type}</h6>`;
		
		if (update_count > 0) {
			preview_html += `<p class="text-success">${update_count} accounts will be updated:</p>`;
			preview_html += '<ul class="small">';
			cat_data.accounts_to_update.slice(0, 5).forEach(acc => {
				preview_html += `<li>${acc.code} - ${acc.description} (${acc.current_type} → ${acc.new_type})</li>`;
			});
			if (update_count > 5) {
				preview_html += `<li>... and ${update_count - 5} more</li>`;
			}
			preview_html += '</ul>';
		}
		
		if (cat_data.accounts_already_correct.length > 0) {
			preview_html += `<p class="text-muted small">${cat_data.accounts_already_correct.length} accounts already correct</p>`;
		}
		
		if (cat_data.accounts_not_found.length > 0) {
			preview_html += `<p class="text-warning small">${cat_data.accounts_not_found.length} accounts not found in ERPNext</p>`;
		}
	}
	
	preview_html += `<hr><p><strong>Total accounts to update: ${total_updates}</strong></p>`;
	
	let preview_dialog = new frappe.ui.Dialog({
		title: 'Confirm Account Type Updates',
		fields: [{
			fieldtype: 'HTML',
			options: preview_html
		}],
		size: 'large',
		primary_action_label: 'Apply Changes',
		primary_action: function() {
			preview_dialog.hide();
			
			// Apply mappings
			frappe.call({
				method: 'verenigingen.utils.eboekhouden_account_type_mapping.apply_account_type_mappings',
				args: { mappings: mappings },
				callback: function(r) {
					if (r.message && r.message.success) {
						let summary = r.message.summary;
						frappe.msgprint({
							title: __('Account Types Updated'),
							message: __(`Successfully updated ${summary.total_updated} accounts. 
								${summary.total_skipped} skipped, ${summary.total_errors} errors.`),
							indicator: 'green'
						});
					} else {
						frappe.msgprint({
							title: __('Error'),
							message: __('Failed to update account types'),
							indicator: 'red'
						});
					}
				}
			});
		},
		secondary_action_label: 'Back',
		secondary_action: function() {
			preview_dialog.hide();
		}
	});
	
	preview_dialog.show();
}