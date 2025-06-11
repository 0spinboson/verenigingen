// Copyright (c) 2025, Your Organization and contributors
// For license information, please see license.txt

frappe.ui.form.on('Expense Approval Dashboard', {
	refresh: function(frm) {
		// Load the dashboard on refresh
		load_expense_dashboard(frm);
		
		// Set up button handlers
		setup_button_handlers(frm);
	},
	
	organization_type: function(frm) {
		// Clear organization when type changes
		frm.set_value('organization', '');
		refresh_dashboard_data(frm);
	},
	
	organization: function(frm) {
		refresh_dashboard_data(frm);
	},
	
	amount_range: function(frm) {
		refresh_dashboard_data(frm);
	},
	
	approval_level_filter: function(frm) {
		refresh_dashboard_data(frm);
	},
	
	date_range: function(frm) {
		refresh_dashboard_data(frm);
	},
	
	volunteer_filter: function(frm) {
		refresh_dashboard_data(frm);
	}
});

function setup_button_handlers(frm) {
	// Refresh Dashboard button
	frm.fields_dict.refresh_dashboard.$input.click(function() {
		refresh_dashboard_data(frm);
	});
	
	// Bulk Approve button
	frm.fields_dict.bulk_approve.$input.click(function() {
		bulk_approve_selected_expenses(frm);
	});
	
	// Export Data button
	frm.fields_dict.export_data.$input.click(function() {
		export_expense_data(frm);
	});
	
	// Generate Report button
	frm.fields_dict.generate_report.$input.click(function() {
		generate_expense_report(frm);
	});
}

function load_expense_dashboard(frm) {
	// Load initial dashboard statistics
	frappe.call({
		method: 'verenigingen.verenigingen.doctype.expense_approval_dashboard.expense_approval_dashboard.get_approval_statistics',
		callback: function(r) {
			if (r.message) {
				render_dashboard_statistics(r.message);
			}
		}
	});
	
	// Load pending expenses
	refresh_dashboard_data(frm);
}

function refresh_dashboard_data(frm) {
	// Get current filter values
	const filters = {
		organization_type: frm.doc.organization_type,
		organization: frm.doc.organization,
		amount_range: frm.doc.amount_range,
		approval_level_filter: frm.doc.approval_level_filter,
		date_range: frm.doc.date_range,
		volunteer_filter: frm.doc.volunteer_filter
	};
	
	// Load filtered expenses
	frappe.call({
		method: 'verenigingen.verenigingen.doctype.expense_approval_dashboard.expense_approval_dashboard.get_pending_expenses_for_dashboard',
		args: { filters: filters },
		callback: function(r) {
			if (r.message) {
				render_expense_table(r.message);
			}
		}
	});
}

function render_dashboard_statistics(stats) {
	const html = `
		<div class="expense-dashboard-stats">
			<div class="row">
				<div class="col-md-3">
					<div class="dashboard-stat-card">
						<h4>${stats.total_pending}</h4>
						<p>Pending Approvals</p>
					</div>
				</div>
				<div class="col-md-3">
					<div class="dashboard-stat-card">
						<h4>€${stats.total_amount.toLocaleString()}</h4>
						<p>Total Amount</p>
					</div>
				</div>
				<div class="col-md-3">
					<div class="dashboard-stat-card text-warning">
						<h4>${stats.overdue_7_days}</h4>
						<p>Overdue > 7 Days</p>
					</div>
				</div>
				<div class="col-md-3">
					<div class="dashboard-stat-card text-danger">
						<h4>${stats.overdue_30_days}</h4>
						<p>Overdue > 30 Days</p>
					</div>
				</div>
			</div>
			<div class="row mt-3">
				<div class="col-md-4">
					<div class="approval-level-stat">
						<span class="badge badge-success">${stats.by_level.basic}</span> Basic Level
					</div>
				</div>
				<div class="col-md-4">
					<div class="approval-level-stat">
						<span class="badge badge-warning">${stats.by_level.financial}</span> Financial Level
					</div>
				</div>
				<div class="col-md-4">
					<div class="approval-level-stat">
						<span class="badge badge-danger">${stats.by_level.admin}</span> Admin Level
					</div>
				</div>
			</div>
		</div>
	`;
	
	// Add stats at the top of the dashboard
	$('#expense-approval-dashboard').prepend(html);
}

function render_expense_table(expenses) {
	if (!expenses || expenses.length === 0) {
		$('#expense-approval-dashboard .expense-table-container').html('<p class="text-muted">No pending expenses found.</p>');
		return;
	}
	
	let html = `
		<div class="expense-table-container">
			<div class="mb-3">
				<button class="btn btn-sm btn-primary" onclick="select_all_expenses()">Select All</button>
				<button class="btn btn-sm btn-secondary" onclick="clear_selections()">Clear All</button>
			</div>
			<table class="table table-striped expense-approval-table">
				<thead>
					<tr>
						<th><input type="checkbox" id="select-all-checkbox"></th>
						<th>Expense ID</th>
						<th>Volunteer</th>
						<th>Description</th>
						<th>Amount</th>
						<th>Date</th>
						<th>Organization</th>
						<th>Level</th>
						<th>Days Pending</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
	`;
	
	expenses.forEach(expense => {
		const levelClass = get_level_class(expense.required_approval_level);
		const pendingClass = expense.days_pending > 7 ? 'text-warning' : '';
		
		html += `
			<tr>
				<td><input type="checkbox" class="expense-checkbox" data-expense="${expense.name}"></td>
				<td><a href="/app/volunteer-expense/${expense.name}" target="_blank">${expense.name}</a></td>
				<td>${expense.volunteer_name || expense.volunteer}</td>
				<td>${expense.description}</td>
				<td>€${expense.amount.toLocaleString()}</td>
				<td>${frappe.datetime.str_to_user(expense.expense_date)}</td>
				<td>${expense.organization_name} (${expense.organization_type})</td>
				<td><span class="badge ${levelClass}">${expense.required_approval_level}</span></td>
				<td class="${pendingClass}">${expense.days_pending}</td>
				<td>
					<button class="btn btn-sm btn-success" onclick="approve_single_expense('${expense.name}')">Approve</button>
					<button class="btn btn-sm btn-danger" onclick="reject_single_expense('${expense.name}')">Reject</button>
				</td>
			</tr>
		`;
	});
	
	html += `
				</tbody>
			</table>
		</div>
	`;
	
	// Remove existing table and add new one
	$('#expense-approval-dashboard .expense-table-container').remove();
	$('#expense-approval-dashboard').append(html);
	
	// Set up checkbox handlers
	setup_checkbox_handlers();
}

function get_level_class(level) {
	switch(level) {
		case 'basic': return 'badge-success';
		case 'financial': return 'badge-warning';
		case 'admin': return 'badge-danger';
		default: return 'badge-secondary';
	}
}

function setup_checkbox_handlers() {
	// Select all checkbox
	$('#select-all-checkbox').change(function() {
		$('.expense-checkbox').prop('checked', this.checked);
	});
	
	// Individual checkboxes
	$('.expense-checkbox').change(function() {
		// Update select all checkbox state
		const total = $('.expense-checkbox').length;
		const checked = $('.expense-checkbox:checked').length;
		$('#select-all-checkbox').prop('checked', total === checked);
	});
}

function select_all_expenses() {
	$('.expense-checkbox').prop('checked', true);
	$('#select-all-checkbox').prop('checked', true);
}

function clear_selections() {
	$('.expense-checkbox').prop('checked', false);
	$('#select-all-checkbox').prop('checked', false);
}

function bulk_approve_selected_expenses(frm) {
	const selected = $('.expense-checkbox:checked').map(function() {
		return $(this).data('expense');
	}).get();
	
	if (selected.length === 0) {
		frappe.msgprint('Please select at least one expense to approve.');
		return;
	}
	
	frappe.confirm(
		`Are you sure you want to approve ${selected.length} expense(s)?`,
		function() {
			frappe.call({
				method: 'verenigingen.verenigingen.doctype.expense_approval_dashboard.expense_approval_dashboard.bulk_approve_expenses',
				args: { expense_names: selected },
				callback: function(r) {
					if (r.message) {
						frappe.show_alert(`Approved ${r.message.approved.length} expenses`);
						refresh_dashboard_data(frm);
					}
				}
			});
		}
	);
}

function approve_single_expense(expense_name) {
	frappe.confirm(
		`Are you sure you want to approve expense ${expense_name}?`,
		function() {
			frappe.call({
				method: 'verenigingen.verenigingen.doctype.volunteer_expense.volunteer_expense.approve_expense',
				args: { expense_name: expense_name },
				callback: function(r) {
					frappe.show_alert('Expense approved successfully');
					// Refresh current form if it's the dashboard
					if (cur_frm && cur_frm.doctype === 'Expense Approval Dashboard') {
						refresh_dashboard_data(cur_frm);
					}
				}
			});
		}
	);
}

function reject_single_expense(expense_name) {
	frappe.prompt([
		{
			fieldtype: 'Small Text',
			fieldname: 'reason',
			label: 'Rejection Reason',
			reqd: 1
		}
	], function(values) {
		frappe.call({
			method: 'verenigingen.verenigingen.doctype.volunteer_expense.volunteer_expense.reject_expense',
			args: { 
				expense_name: expense_name,
				reason: values.reason
			},
			callback: function(r) {
				frappe.show_alert('Expense rejected');
				// Refresh current form if it's the dashboard
				if (cur_frm && cur_frm.doctype === 'Expense Approval Dashboard') {
					refresh_dashboard_data(cur_frm);
				}
			}
		});
	}, 'Reject Expense', 'Reject');
}

function export_expense_data(frm) {
	frappe.msgprint('Export functionality will be implemented with the reporting module.');
}

function generate_expense_report(frm) {
	frappe.set_route('query-report', 'Chapter Expense Report');
}