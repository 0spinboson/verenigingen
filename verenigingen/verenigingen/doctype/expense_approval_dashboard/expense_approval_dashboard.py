# Copyright (c) 2025, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today, getdate, add_days, flt

class ExpenseApprovalDashboard(Document):
	def validate(self):
		"""This is a single doctype for dashboard display"""
		pass

@frappe.whitelist()
def get_pending_expenses_for_dashboard(filters=None):
	"""Get pending expenses for the approval dashboard"""
	from verenigingen.utils.expense_permissions import ExpensePermissionManager
	
	if not filters:
		filters = {}
	
	manager = ExpensePermissionManager()
	
	# Build base filters
	base_filters = {
		"status": "Submitted",
		"docstatus": 1
	}
	
	# Apply organization type filter
	if filters.get("organization_type"):
		base_filters["organization_type"] = filters.get("organization_type")
		
		if filters.get("organization"):
			if filters.get("organization_type") == "Chapter":
				base_filters["chapter"] = filters.get("organization")
			else:
				base_filters["team"] = filters.get("organization")
	
	# Apply date range filter
	if filters.get("date_range"):
		date_filter = get_date_filter(filters.get("date_range"))
		if date_filter:
			base_filters["expense_date"] = date_filter
	
	# Apply volunteer filter
	if filters.get("volunteer_filter"):
		base_filters["volunteer"] = filters.get("volunteer_filter")
	
	# Get expenses
	expenses = frappe.get_all("Volunteer Expense",
		filters=base_filters,
		fields=[
			"name", "volunteer", "description", "amount", "currency", 
			"expense_date", "category", "organization_type", "chapter", 
			"team", "creation", "owner"
		],
		order_by="expense_date desc, creation desc"
	)
	
	# Filter expenses user can approve and apply additional filters
	filtered_expenses = []
	for expense in expenses:
		# Check if user can approve this expense
		expense_doc = frappe.get_doc("Volunteer Expense", expense.name)
		if not manager.can_approve_expense(expense_doc):
			continue
		
		# Apply amount range filter
		if filters.get("amount_range"):
			if not matches_amount_range(expense.amount, filters.get("amount_range")):
				continue
		
		# Apply approval level filter
		if filters.get("approval_level_filter"):
			required_level = manager.get_required_permission_level(expense.amount)
			if required_level.lower() != filters.get("approval_level_filter").lower():
				continue
		
		# Add additional info
		expense["required_approval_level"] = manager.get_required_permission_level(expense.amount)
		expense["organization_name"] = expense.chapter or expense.team
		expense["volunteer_name"] = frappe.db.get_value("Volunteer", expense.volunteer, "volunteer_name")
		expense["days_pending"] = (getdate(today()) - getdate(expense.expense_date)).days
		
		filtered_expenses.append(expense)
	
	return filtered_expenses

@frappe.whitelist() 
def bulk_approve_expenses(expense_names):
	"""Bulk approve multiple expenses"""
	from verenigingen.utils.expense_permissions import ExpensePermissionManager
	
	if isinstance(expense_names, str):
		import json
		expense_names = json.loads(expense_names)
	
	manager = ExpensePermissionManager()
	results = {
		"approved": [],
		"failed": [],
		"total": len(expense_names)
	}
	
	for expense_name in expense_names:
		try:
			expense = frappe.get_doc("Volunteer Expense", expense_name)
			
			# Check permission
			if not manager.can_approve_expense(expense):
				results["failed"].append({
					"name": expense_name,
					"error": "Insufficient permission to approve this expense"
				})
				continue
			
			# Approve expense
			expense.status = "Approved"
			expense.approved_by = frappe.session.user
			expense.approved_on = frappe.utils.now()
			expense.save()
			
			results["approved"].append(expense_name)
			
		except Exception as e:
			results["failed"].append({
				"name": expense_name,
				"error": str(e)
			})
	
	frappe.db.commit()
	
	# Send notification summary
	if results["approved"]:
		frappe.msgprint(_(f"Successfully approved {len(results['approved'])} expenses"))
	
	if results["failed"]:
		frappe.msgprint(_(f"Failed to approve {len(results['failed'])} expenses"))
	
	return results

@frappe.whitelist()
def get_approval_statistics():
	"""Get approval statistics for dashboard"""
	from verenigingen.utils.expense_permissions import ExpensePermissionManager
	
	manager = ExpensePermissionManager()
	
	# Get total pending expenses user can approve
	all_pending = frappe.get_all("Volunteer Expense",
		filters={"status": "Submitted", "docstatus": 1},
		fields=["name", "amount", "expense_date"]
	)
	
	user_pending = []
	for expense in all_pending:
		expense_doc = frappe.get_doc("Volunteer Expense", expense.name)
		if manager.can_approve_expense(expense_doc):
			user_pending.append(expense)
	
	# Calculate statistics
	total_pending = len(user_pending)
	total_amount = sum(flt(exp.amount) for exp in user_pending)
	
	# Age statistics
	overdue_7_days = len([exp for exp in user_pending 
		if (getdate(today()) - getdate(exp.expense_date)).days > 7])
	overdue_30_days = len([exp for exp in user_pending 
		if (getdate(today()) - getdate(exp.expense_date)).days > 30])
	
	# Amount breakdown
	basic_count = len([exp for exp in user_pending 
		if manager.get_required_permission_level(exp.amount) == "basic"])
	financial_count = len([exp for exp in user_pending 
		if manager.get_required_permission_level(exp.amount) == "financial"])
	admin_count = len([exp for exp in user_pending 
		if manager.get_required_permission_level(exp.amount) == "admin"])
	
	return {
		"total_pending": total_pending,
		"total_amount": total_amount,
		"overdue_7_days": overdue_7_days,
		"overdue_30_days": overdue_30_days,
		"by_level": {
			"basic": basic_count,
			"financial": financial_count, 
			"admin": admin_count
		}
	}

def get_date_filter(date_range):
	"""Convert date range string to date filter"""
	if date_range == "Last 7 days":
		return [">=", add_days(today(), -7)]
	elif date_range == "Last 30 days":
		return [">=", add_days(today(), -30)]
	elif date_range == "Last 90 days":
		return [">=", add_days(today(), -90)]
	return None

def matches_amount_range(amount, amount_range):
	"""Check if amount matches the specified range"""
	amount = flt(amount)
	
	if amount_range == "Under €100":
		return amount < 100
	elif amount_range == "€100 - €500":
		return 100 <= amount <= 500
	elif amount_range == "Over €500":
		return amount > 500
	
	return True