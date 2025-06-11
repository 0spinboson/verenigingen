import frappe
from frappe import _
from frappe.utils import getdate, today, add_days, flt, formatdate

def execute(filters=None):
    """Generate Chapter Expense Report"""
    
    columns = get_columns()
    data = get_data(filters)
    
    # Add summary statistics
    summary = get_summary(data)
    
    # Add chart data
    chart = get_chart_data(data)
    
    return columns, data, None, chart, summary

def get_columns():
    """Define report columns"""
    return [
        {
            "label": _("Expense ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Volunteer Expense",
            "width": 120
        },
        {
            "label": _("Volunteer"),
            "fieldname": "volunteer_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Description"),
            "fieldname": "description",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": _("Date"),
            "fieldname": "expense_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": _("Category"),
            "fieldname": "category_name",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Organization"),
            "fieldname": "organization_name",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Type"),
            "fieldname": "organization_type",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": _("Status"),
            "fieldname": "status_indicator",
            "fieldtype": "HTML",
            "width": 100
        },
        {
            "label": _("Approval Level"),
            "fieldname": "approval_level",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Approved By"),
            "fieldname": "approved_by_name",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Approved Date"),
            "fieldname": "approved_on",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Days to Approval"),
            "fieldname": "days_to_approval",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Attachments"),
            "fieldname": "attachment_count",
            "fieldtype": "Int",
            "width": 100
        }
    ]

def get_data(filters):
    """Get report data"""
    from verenigingen.utils.expense_permissions import ExpensePermissionManager
    
    manager = ExpensePermissionManager()
    
    # Build base filters
    base_filters = {"docstatus": 1}
    
    # Apply date filters
    if filters:
        if filters.get("from_date"):
            base_filters["expense_date"] = [">=", filters.get("from_date")]
        if filters.get("to_date"):
            if "expense_date" in base_filters:
                base_filters["expense_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
            else:
                base_filters["expense_date"] = ["<=", filters.get("to_date")]
        
        # Apply status filter
        if filters.get("status"):
            base_filters["status"] = filters.get("status")
        
        # Apply organization type filter
        if filters.get("organization_type"):
            base_filters["organization_type"] = filters.get("organization_type")
            
            # Apply specific organization filter
            if filters.get("organization"):
                if filters.get("organization_type") == "Chapter":
                    base_filters["chapter"] = filters.get("organization")
                else:
                    base_filters["team"] = filters.get("organization")
        
        # Apply volunteer filter
        if filters.get("volunteer"):
            base_filters["volunteer"] = filters.get("volunteer")
        
        # Apply amount range filter
        if filters.get("amount_min"):
            base_filters["amount"] = [">=", flt(filters.get("amount_min"))]
        if filters.get("amount_max"):
            if "amount" in base_filters:
                base_filters["amount"] = ["between", [flt(filters.get("amount_min", 0)), flt(filters.get("amount_max"))]]
            else:
                base_filters["amount"] = ["<=", flt(filters.get("amount_max"))]
        
        # Apply category filter
        if filters.get("category"):
            base_filters["category"] = filters.get("category")
    
    # Get expenses
    expenses = frappe.get_all("Volunteer Expense",
        filters=base_filters,
        fields=[
            "name", "volunteer", "description", "amount", "currency", 
            "expense_date", "category", "organization_type", "chapter", 
            "team", "status", "approved_by", "approved_on", "creation",
            "owner"
        ],
        order_by="expense_date desc, creation desc"
    )
    
    # Get user accessible chapters for permission filtering
    user_chapters = get_user_accessible_chapters()
    
    # Process and filter expenses
    data = []
    for expense in expenses:
        # Apply chapter access filtering
        if user_chapters is not None:  # None means see all
            if expense.organization_type == "Chapter" and expense.chapter:
                if expense.chapter not in user_chapters:
                    continue
            elif expense.organization_type == "Team" and expense.team:
                # Check if team's chapter is accessible
                team_chapter = frappe.db.get_value("Team", expense.team, "chapter")
                if team_chapter and team_chapter not in user_chapters:
                    continue
        
        # Apply approval level filter if specified
        if filters and filters.get("approval_level"):
            required_level = manager.get_required_permission_level(expense.amount)
            if required_level.lower() != filters.get("approval_level").lower():
                continue
        
        # Get additional data
        volunteer_name = frappe.db.get_value("Volunteer", expense.volunteer, "volunteer_name")
        category_name = frappe.db.get_value("Expense Category", expense.category, "category_name") if expense.category else "Uncategorized"
        organization_name = expense.chapter or expense.team
        
        # Get approval level
        approval_level = manager.get_required_permission_level(expense.amount)
        
        # Get approver name
        approved_by_name = None
        if expense.approved_by:
            approved_by_name = frappe.db.get_value("User", expense.approved_by, "full_name")
        
        # Calculate days to approval
        days_to_approval = None
        if expense.approved_on and expense.expense_date:
            days_to_approval = (getdate(expense.approved_on) - getdate(expense.expense_date)).days
        elif expense.status == "Submitted":
            days_to_approval = (getdate(today()) - getdate(expense.expense_date)).days
        
        # Get attachment count
        attachment_count = frappe.db.count("File", {"attached_to_name": expense.name, "attached_to_doctype": "Volunteer Expense"})
        
        # Build row data
        row = {
            "name": expense.name,
            "volunteer_name": volunteer_name,
            "description": expense.description,
            "amount": flt(expense.amount, 2),
            "currency": expense.currency,
            "expense_date": expense.expense_date,
            "category_name": category_name,
            "organization_name": organization_name,
            "organization_type": expense.organization_type,
            "status": expense.status,
            "approval_level": approval_level.title(),
            "approved_by_name": approved_by_name,
            "approved_on": expense.approved_on,
            "days_to_approval": days_to_approval,
            "attachment_count": attachment_count
        }
        
        # Add status indicator with color coding
        if expense.status == "Approved":
            row["status_indicator"] = '<span class="indicator green">Approved</span>'
        elif expense.status == "Rejected":
            row["status_indicator"] = '<span class="indicator red">Rejected</span>'
        elif expense.status == "Submitted":
            if days_to_approval and days_to_approval > 7:
                row["status_indicator"] = '<span class="indicator orange">Pending (Overdue)</span>'
            else:
                row["status_indicator"] = '<span class="indicator blue">Pending</span>'
        else:
            row["status_indicator"] = f'<span class="indicator grey">{expense.status}</span>'
        
        data.append(row)
    
    return data

def get_user_accessible_chapters():
    """Get chapters accessible to current user"""
    user = frappe.session.user
    
    # System managers and Association managers see all
    admin_roles = ["System Manager", "Verenigingen Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return None  # No filter - see all
    
    # Get user's member record
    user_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not user_member:
        return []  # No access if not a member
    
    # Get chapters where user has board access
    user_chapters = []
    try:
        volunteer_records = frappe.get_all("Volunteer", filters={"member": user_member}, fields=["name"])
        
        for volunteer_record in volunteer_records:
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["parent", "chapter_role"]
            )
            
            for position in board_positions:
                if position.parent not in user_chapters:
                    user_chapters.append(position.parent)
    except Exception:
        pass
    
    return user_chapters if user_chapters else []

def get_summary(data):
    """Get summary statistics"""
    if not data:
        return []
    
    # Basic counts
    total_expenses = len(data)
    approved_count = len([d for d in data if d.get("status") == "Approved"])
    pending_count = len([d for d in data if d.get("status") == "Submitted"])
    rejected_count = len([d for d in data if d.get("status") == "Rejected"])
    
    # Amount calculations
    total_amount = sum(flt(d.get("amount", 0)) for d in data)
    approved_amount = sum(flt(d.get("amount", 0)) for d in data if d.get("status") == "Approved")
    pending_amount = sum(flt(d.get("amount", 0)) for d in data if d.get("status") == "Submitted")
    
    # Approval time statistics
    approval_times = [d.get("days_to_approval") for d in data if d.get("days_to_approval") is not None and d.get("status") == "Approved"]
    avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else 0
    
    # Amount level breakdown
    basic_count = len([d for d in data if d.get("approval_level") == "Basic"])
    financial_count = len([d for d in data if d.get("approval_level") == "Financial"])
    admin_count = len([d for d in data if d.get("approval_level") == "Admin"])
    
    return [
        {
            "value": total_expenses,
            "label": _("Total Expenses"),
            "datatype": "Int"
        },
        {
            "value": total_amount,
            "label": _("Total Amount"),
            "datatype": "Currency"
        },
        {
            "value": approved_count,
            "label": _("Approved"),
            "datatype": "Int",
            "color": "green"
        },
        {
            "value": approved_amount,
            "label": _("Approved Amount"),
            "datatype": "Currency",
            "color": "green"
        },
        {
            "value": pending_count,
            "label": _("Pending Approval"),
            "datatype": "Int",
            "color": "orange" if pending_count > 0 else "green"
        },
        {
            "value": pending_amount,
            "label": _("Pending Amount"),
            "datatype": "Currency",
            "color": "orange" if pending_amount > 0 else "green"
        },
        {
            "value": rejected_count,
            "label": _("Rejected"),
            "datatype": "Int",
            "color": "red" if rejected_count > 0 else "green"
        },
        {
            "value": round(avg_approval_time, 1),
            "label": _("Avg. Approval Time (days)"),
            "datatype": "Float"
        },
        {
            "value": basic_count,
            "label": _("Basic Level"),
            "datatype": "Int"
        },
        {
            "value": financial_count,
            "label": _("Financial Level"),
            "datatype": "Int"
        },
        {
            "value": admin_count,
            "label": _("Admin Level"),
            "datatype": "Int"
        }
    ]

def get_chart_data(data):
    """Get chart data for visualization"""
    if not data:
        return None
    
    # Group by organization for chart
    org_amounts = {}
    for row in data:
        org = row.get("organization_name") or "Unassigned"
        if org not in org_amounts:
            org_amounts[org] = {"approved": 0, "pending": 0, "rejected": 0}
        
        amount = flt(row.get("amount", 0))
        status = row.get("status", "").lower()
        
        if status == "approved":
            org_amounts[org]["approved"] += amount
        elif status == "submitted":
            org_amounts[org]["pending"] += amount
        elif status == "rejected":
            org_amounts[org]["rejected"] += amount
    
    organizations = list(org_amounts.keys())
    approved_amounts = [org_amounts[org]["approved"] for org in organizations]
    pending_amounts = [org_amounts[org]["pending"] for org in organizations]
    rejected_amounts = [org_amounts[org]["rejected"] for org in organizations]
    
    return {
        "data": {
            "labels": organizations,
            "datasets": [
                {
                    "name": _("Approved"),
                    "values": approved_amounts
                },
                {
                    "name": _("Pending"),
                    "values": pending_amounts
                },
                {
                    "name": _("Rejected"),
                    "values": rejected_amounts
                }
            ]
        },
        "type": "bar",
        "colors": ["#28a745", "#ffc107", "#dc3545"]
    }