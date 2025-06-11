import frappe
from frappe import _
from frappe.utils import today, flt, formatdate, get_url

def get_context(context):
    """Get context for volunteer expense portal page"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access the volunteer expense portal"), frappe.PermissionError)
    
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("Volunteer Expenses")
    
    # Get current user's volunteer record
    volunteer = get_user_volunteer_record()
    if not volunteer:
        context.error_message = _("No volunteer record found for your account. Please contact your chapter administrator.")
        return context
    
    context.volunteer = volunteer
    
    # Get volunteer's organizations (chapters and teams)
    context.organizations = get_volunteer_organizations(volunteer.name)
    
    # Get expense categories
    context.expense_categories = get_expense_categories()
    
    # Get volunteer's recent expenses
    context.recent_expenses = get_volunteer_expenses(volunteer.name, limit=10)
    
    # Get expense statistics
    context.expense_stats = get_expense_statistics(volunteer.name)
    
    # Get maximum amounts for each approval level (for UI guidance)
    context.approval_thresholds = get_approval_thresholds()
    
    return context

def get_user_volunteer_record():
    """Get volunteer record for current user"""
    user_email = frappe.session.user
    
    # First try to find by linked member
    member = frappe.db.get_value("Member", {"email": user_email}, "name")
    if member:
        volunteer = frappe.db.get_value("Volunteer", {"member": member}, ["name", "volunteer_name"], as_dict=True)
        if volunteer:
            return volunteer
    
    # Try to find volunteer directly by email (if volunteer has direct email)
    volunteer = frappe.db.get_value("Volunteer", {"email": user_email}, ["name", "volunteer_name"], as_dict=True)
    if volunteer:
        return volunteer
    
    return None

def get_volunteer_organizations(volunteer_name):
    """Get chapters and teams the volunteer belongs to"""
    organizations = {"chapters": [], "teams": []}
    
    # Check if volunteer exists
    if not frappe.db.exists("Volunteer", volunteer_name):
        return organizations
    
    # Get chapters through member relationship
    volunteer_doc = frappe.get_doc("Volunteer", volunteer_name)
    if hasattr(volunteer_doc, 'member') and volunteer_doc.member:
        # Get chapters where this member is active
        chapter_members = frappe.get_all("Chapter Member",
            filters={"member": volunteer_doc.member, "enabled": 1},
            fields=["parent as chapter_name"]
        )
        
        for cm in chapter_members:
            chapter_info = frappe.db.get_value("Chapter", cm.chapter_name, 
                ["name", "chapter_name"], as_dict=True)
            if chapter_info:
                organizations["chapters"].append(chapter_info)
    
    # Get teams where volunteer is active
    team_members = frappe.get_all("Team Member",
        filters={"volunteer": volunteer_name, "status": "Active"},
        fields=["parent as team_name"]
    )
    
    for tm in team_members:
        team_info = frappe.db.get_value("Team", tm.team_name,
            ["name", "team_name"], as_dict=True)
        if team_info:
            organizations["teams"].append(team_info)
    
    return organizations

def get_expense_categories():
    """Get available expense categories"""
    return frappe.get_all("Expense Category",
        filters={"is_active": 1},
        fields=["name", "category_name", "description"],
        order_by="category_name"
    )

def get_volunteer_expenses(volunteer_name, limit=None):
    """Get volunteer's recent expenses"""
    filters = {"volunteer": volunteer_name}
    
    expenses = frappe.get_all("Volunteer Expense",
        filters=filters,
        fields=[
            "name", "description", "amount", "currency", "expense_date",
            "status", "organization_type", "chapter", "team", "category",
            "creation", "approved_on"
        ],
        order_by="creation desc",
        limit=limit
    )
    
    # Enhance with additional info
    for expense in expenses:
        # Get category name
        if expense.category:
            expense.category_name = frappe.db.get_value("Expense Category", expense.category, "category_name")
        else:
            expense.category_name = "Uncategorized"
        
        # Get organization name
        expense.organization_name = expense.chapter or expense.team
        
        # Format dates
        expense.formatted_date = formatdate(expense.expense_date)
        expense.formatted_creation = formatdate(expense.creation)
        if expense.approved_on:
            expense.formatted_approved_on = formatdate(expense.approved_on)
        
        # Add status styling
        expense.status_class = get_status_class(expense.status)
    
    return expenses

def get_expense_statistics(volunteer_name):
    """Get expense statistics for the volunteer"""
    from frappe.utils import add_months
    
    # Get expenses from last 12 months
    from_date = add_months(today(), -12)
    
    expenses = frappe.get_all("Volunteer Expense",
        filters={
            "volunteer": volunteer_name,
            "expense_date": [">=", from_date],
            "docstatus": ["!=", 2]  # Not cancelled
        },
        fields=["amount", "status", "expense_date"]
    )
    
    total_submitted = sum(flt(exp.amount) for exp in expenses if exp.status in ["Submitted", "Approved"])
    total_approved = sum(flt(exp.amount) for exp in expenses if exp.status == "Approved")
    pending_count = len([exp for exp in expenses if exp.status == "Submitted"])
    approved_count = len([exp for exp in expenses if exp.status == "Approved"])
    
    return {
        "total_submitted": total_submitted,
        "total_approved": total_approved,
        "pending_amount": total_submitted - total_approved,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "total_count": len(expenses)
    }

def get_approval_thresholds():
    """Get approval thresholds for UI guidance"""
    return {
        "basic_limit": 100.0,
        "financial_limit": 500.0,
        "admin_limit": float('inf')
    }

def get_status_class(status):
    """Get CSS class for expense status"""
    status_classes = {
        "Draft": "badge-secondary",
        "Submitted": "badge-warning",
        "Approved": "badge-success",
        "Rejected": "badge-danger",
        "Reimbursed": "badge-primary"
    }
    return status_classes.get(status, "badge-secondary")

@frappe.whitelist()
def submit_expense(expense_data):
    """Submit a new expense from the portal"""
    try:
        # Get current user's volunteer record
        volunteer = get_user_volunteer_record()
        if not volunteer:
            frappe.throw(_("No volunteer record found for your account"))
        
        # Validate required fields
        required_fields = ["description", "amount", "expense_date", "organization_type"]
        for field in required_fields:
            if not expense_data.get(field):
                frappe.throw(_(f"Field {field} is required"))
        
        # Validate organization selection
        if expense_data.get("organization_type") == "Chapter" and not expense_data.get("chapter"):
            frappe.throw(_("Please select a chapter"))
        elif expense_data.get("organization_type") == "Team" and not expense_data.get("team"):
            frappe.throw(_("Please select a team"))
        
        # Create expense document
        expense_doc = frappe.get_doc({
            "doctype": "Volunteer Expense",
            "volunteer": volunteer.name,
            "description": expense_data.get("description"),
            "amount": flt(expense_data.get("amount")),
            "currency": expense_data.get("currency", "EUR"),
            "expense_date": expense_data.get("expense_date"),
            "category": expense_data.get("category"),
            "organization_type": expense_data.get("organization_type"),
            "chapter": expense_data.get("chapter") if expense_data.get("organization_type") == "Chapter" else None,
            "team": expense_data.get("team") if expense_data.get("organization_type") == "Team" else None,
            "notes": expense_data.get("notes")
        })
        
        # Insert and submit
        expense_doc.insert()
        expense_doc.submit()
        
        return {
            "success": True,
            "message": _("Expense submitted successfully"),
            "expense_name": expense_doc.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error submitting expense: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def get_organization_options(organization_type, volunteer_name=None):
    """Get organization options for the current volunteer"""
    if not volunteer_name:
        volunteer = get_user_volunteer_record()
        if not volunteer:
            return []
        volunteer_name = volunteer.name
    
    organizations = get_volunteer_organizations(volunteer_name)
    
    if organization_type == "Chapter":
        return [{"value": ch["name"], "label": ch["chapter_name"]} for ch in organizations["chapters"]]
    elif organization_type == "Team":
        return [{"value": t["name"], "label": t["team_name"]} for t in organizations["teams"]]
    
    return []

@frappe.whitelist()
def get_expense_details(expense_name):
    """Get details for a specific expense"""
    volunteer = get_user_volunteer_record()
    if not volunteer:
        frappe.throw(_("Access denied"))
    
    # Verify the expense belongs to this volunteer
    expense = frappe.get_doc("Volunteer Expense", expense_name)
    if expense.volunteer != volunteer.name:
        frappe.throw(_("Access denied"))
    
    # Get enhanced expense details
    expense_dict = expense.as_dict()
    
    # Add category name
    if expense.category:
        expense_dict["category_name"] = frappe.db.get_value("Expense Category", expense.category, "category_name")
    
    # Add organization name
    expense_dict["organization_name"] = expense.chapter or expense.team
    
    # Add attachment count
    expense_dict["attachment_count"] = frappe.db.count("File", {
        "attached_to_name": expense.name,
        "attached_to_doctype": "Volunteer Expense"
    })
    
    return expense_dict