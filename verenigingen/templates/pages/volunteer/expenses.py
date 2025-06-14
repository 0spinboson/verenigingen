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
    
    # Get national chapter info from settings
    context.national_chapter = get_national_chapter()
    
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

@frappe.whitelist()
def debug_volunteer_access():
    """Debug function to help administrators troubleshoot volunteer access issues"""
    if not frappe.has_permission("Volunteer", "read"):
        frappe.throw(_("Insufficient permissions to debug volunteer access"))
    
    user_email = frappe.session.user
    result = {
        "user_email": user_email,
        "timestamp": frappe.utils.now()
    }
    
    # Check Member record
    member = frappe.db.get_value("Member", {"email": user_email}, ["name", "first_name", "last_name"], as_dict=True)
    result["member"] = member
    
    if member:
        # Check for linked Volunteer
        volunteer = frappe.db.get_value("Volunteer", {"member": member.name}, ["name", "volunteer_name", "status"], as_dict=True)
        result["volunteer_via_member"] = volunteer
    
    # Check direct Volunteer record
    volunteer_direct = frappe.db.get_value("Volunteer", {"email": user_email}, ["name", "volunteer_name", "member", "status"], as_dict=True)
    result["volunteer_direct"] = volunteer_direct
    
    return result

@frappe.whitelist()
def check_workspace_status():
    """Check workspace status in database vs file"""
    if not frappe.has_permission("Workspace", "read"):
        frappe.throw(_("Insufficient permissions to check workspace status"))
    
    result = {}
    
    # Check if workspace exists in database
    db_workspace = frappe.db.sql("""
        SELECT name, public, is_hidden, modified, modified_by, for_user 
        FROM `tabWorkspace` 
        WHERE name = 'Verenigingen'
    """, as_dict=True)
    
    result["db_workspace"] = db_workspace[0] if db_workspace else None
    
    # Get workspace links from database
    db_links = frappe.db.sql("""
        SELECT link_to, label, hidden, link_type, type
        FROM `tabWorkspace Link`
        WHERE parent = 'Verenigingen'
        ORDER BY idx
    """, as_dict=True)
    
    result["db_links_count"] = len(db_links)
    result["db_links"] = db_links
    
    return result

@frappe.whitelist()  
def update_workspace_links():
    """Update workspace with comprehensive links"""
    if not frappe.has_permission("Workspace", "write"):
        frappe.throw(_("Insufficient permissions to update workspace"))
    
    try:
        # Always create a fresh workspace
        # Delete if exists
        if frappe.db.exists("Workspace", "Verenigingen"):
            frappe.db.delete("Workspace", "Verenigingen")
            frappe.db.delete("Workspace Link", {"parent": "Verenigingen"})
        
        # Create new workspace with proper content structure
        workspace = frappe.get_doc({
            "doctype": "Workspace",
            "name": "Verenigingen",
            "title": "Verenigingen", 
            "label": "Verenigingen",
            "icon": "non-profit",
            "module": "Verenigingen",
            "public": 1,
            "is_hidden": 0,
            "content": """[
                {"id":"NFcjh9I8BH","type":"header","data":{"text":"<span class=\\"h4\\"><b>Members/Memberships</b></span>","col":12}},
                {"id":"oIk2CrSoAH","type":"card","data":{"card_name":"Memberships","col":4}},
                {"id":"sxzInK1PHL","type":"shortcut","data":{"shortcut_name":"Member","col":3}},
                {"id":"q6OM4R0OUa","type":"shortcut","data":{"shortcut_name":"Membership","col":3}},
                {"id":"zGoLYG0xRM","type":"spacer","data":{"col":12}},
                {"id":"jMy1CTqEJS","type":"header","data":{"text":"<span class=\\"h4\\"><b>Volunteering</b></span>","col":12}},
                {"id":"2vHgUjgQcL","type":"card","data":{"card_name":"Volunteers","col":4}},
                {"id":"zGoLYG0xRM2","type":"spacer","data":{"col":12}},
                {"id":"jMy1CTqEJS2","type":"header","data":{"text":"<span class=\\"h4\\"><b>Chapters/Teams</b></span>","col":12}},
                {"id":"S8Mi0T41U7","type":"card","data":{"card_name":"Chapters","col":4}},
                {"id":"XXEhdaTHF_","type":"card","data":{"card_name":"Teams and Commissions","col":4}},
                {"id":"zGoLYG0xRM3","type":"spacer","data":{"col":12}},
                {"id":"jMy1CTqEJS3","type":"header","data":{"text":"<span class=\\"h4\\"><b>Financial</b></span>","col":12}},
                {"id":"ZvroSYo9F3","type":"card","data":{"card_name":"Donations","col":4}},
                {"id":"PaymentCard","type":"card","data":{"card_name":"Payment Processing","col":4}},
                {"id":"zGoLYG0xRM4","type":"spacer","data":{"col":12}},
                {"id":"jMy1CTqEJS4","type":"header","data":{"text":"<span class=\\"h4\\"><b>Reports</b></span>","col":12}},
                {"id":"ReportsCard","type":"card","data":{"card_name":"Reports","col":8}},
                {"id":"zGoLYG0xRM5","type":"spacer","data":{"col":12}},
                {"id":"SettingsHeader","type":"header","data":{"text":"<span class=\\"h4\\"><b>Settings</b></span>","col":12}},
                {"id":"RKkllDSemd","type":"card","data":{"card_name":"Module Settings","col":4}}
            ]""",
            "links": [],
            "shortcuts": [
                {"label": "Member", "link_to": "Member", "type": "DocType", "color": "Grey"},
                {"label": "Membership", "link_to": "Membership", "type": "DocType", "color": "Grey"},
                {"label": "Chapter", "link_to": "Chapter", "type": "DocType", "color": "Grey"},
                {"label": "Users by Team", "link_to": "Users by Team", "type": "Report", "color": "Grey", "report_ref_doctype": "Team"}
            ]
        })
        
        # Add comprehensive links - Card Break entries must come BEFORE their respective links
        links_data = [
            # Memberships section - Card Break first, then links
            {"label": "Memberships", "link_count": 5, "link_type": "DocType", "type": "Card Break"},
            {"label": "Member", "link_to": "Member", "link_type": "DocType", "type": "Link", "onboard": 1},
            {"label": "Membership", "link_to": "Membership", "link_type": "DocType", "type": "Link", "onboard": 1},
            {"label": "Membership Type", "link_to": "Membership Type", "link_type": "DocType", "type": "Link"},
            {"label": "Contribution Amendment Request", "link_to": "Contribution Amendment Request", "link_type": "DocType", "type": "Link"},
            {"label": "Membership Termination Request", "link_to": "Membership Termination Request", "link_type": "DocType", "type": "Link"},
            
            # Volunteers section - Card Break first, then links
            {"label": "Volunteers", "link_count": 5, "link_type": "DocType", "type": "Card Break"},
            {"label": "Volunteer", "link_to": "Volunteer", "link_type": "DocType", "type": "Link", "onboard": 1},
            {"label": "Volunteer Expense", "link_to": "Volunteer Expense", "link_type": "DocType", "type": "Link"},
            {"label": "Volunteer Activity", "link_to": "Volunteer Activity", "link_type": "DocType", "type": "Link"},
            {"label": "Expense Category", "link_to": "Expense Category", "link_type": "DocType", "type": "Link"},
            {"label": "Expense Approval Dashboard", "link_to": "Expense Approval Dashboard", "link_type": "DocType", "type": "Link"},
            
            # Chapters section - Card Break first, then links
            {"label": "Chapters", "link_count": 2, "link_type": "DocType", "type": "Card Break"},
            {"label": "Chapter", "link_to": "Chapter", "link_type": "DocType", "type": "Link", "onboard": 1},
            {"label": "Chapter Role", "link_to": "Chapter Role", "link_type": "DocType", "type": "Link"},
            
            # Teams section - Card Break first, then links
            {"label": "Teams and Commissions", "link_count": 1, "link_type": "DocType", "type": "Card Break"},
            {"label": "Team", "link_to": "Team", "link_type": "DocType", "type": "Link"},
            
            # Donations section - Card Break first, then links
            {"label": "Donations", "link_count": 3, "link_type": "DocType", "type": "Card Break"},
            {"label": "Donor", "link_to": "Donor", "link_type": "DocType", "type": "Link"},
            {"label": "Donation", "link_to": "Donation", "link_type": "DocType", "type": "Link"},
            {"label": "Donation Type", "link_to": "Donation Type", "link_type": "DocType", "type": "Link"},
            
            # Payment Processing section - Card Break first, then links
            {"label": "Payment Processing", "link_count": 2, "link_type": "DocType", "type": "Card Break"},
            {"label": "SEPA Mandate", "link_to": "SEPA Mandate", "link_type": "DocType", "type": "Link"},
            {"label": "Direct Debit Batch", "link_to": "Direct Debit Batch", "link_type": "DocType", "type": "Link"},
            
            # Reports section - Card Break first, then links
            {"label": "Reports", "link_count": 9, "link_type": "Report", "type": "Card Break"},
            {"label": "Expiring Memberships", "link_to": "Expiring Memberships", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "New Members", "link_to": "New Members", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Members Without Chapter", "link_to": "Members Without Chapter", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Overdue Member Payments", "link_to": "Overdue Member Payments", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Orphaned Subscriptions Report", "link_to": "Orphaned Subscriptions Report", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Chapter Expense Report", "link_to": "Chapter Expense Report", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Governance Compliance Report", "link_to": "Governance Compliance Report", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Termination Compliance Report", "link_to": "Termination Compliance Report", "link_type": "Report", "type": "Link", "is_query_report": 1},
            {"label": "Users by Team", "link_to": "Users by Team", "link_type": "Report", "type": "Link", "is_query_report": 1},
            
            # Settings section - Card Break first, then links
            {"label": "Module Settings", "link_count": 1, "link_type": "DocType", "type": "Card Break"},
            {"label": "Verenigingen Settings", "link_to": "Verenigingen Settings", "link_type": "DocType", "type": "Link"}
        ]
        
        # Add links to workspace
        for link_data in links_data:
            workspace.append("links", link_data)
        
        # Save workspace
        workspace.insert()
        
        return {
            "success": True,
            "message": f"Workspace updated successfully. Now has {len(workspace.links)} links.",
            "links_count": len(workspace.links)
        }
        
    except Exception as e:
        frappe.db.rollback()
        import traceback
        return {
            "success": False, 
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist()
def create_volunteer_for_member(member_name):
    """Create a volunteer record for an existing member (admin function)"""
    if not frappe.has_permission("Volunteer", "create"):
        frappe.throw(_("Insufficient permissions to create volunteer records"))
    
    # Get member details
    member = frappe.get_doc("Member", member_name)
    
    # Check if volunteer already exists
    existing_volunteer = frappe.db.get_value("Volunteer", {"member": member_name}, "name")
    if existing_volunteer:
        frappe.throw(_("Volunteer record already exists for member {0}: {1}").format(member_name, existing_volunteer))
    
    # Create volunteer record
    volunteer = frappe.get_doc({
        "doctype": "Volunteer",
        "volunteer_name": f"{member.first_name} {member.last_name}",
        "email": member.email,
        "member": member.name,
        "status": "Active",
        "start_date": frappe.utils.today()
    })
    
    volunteer.insert()
    
    return {
        "success": True,
        "volunteer_name": volunteer.name,
        "message": _("Volunteer record created successfully for {0}").format(member.full_name)
    }

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
            fields=["parent"]
        )
        
        for cm in chapter_members:
            chapter_info = frappe.db.get_value("Chapter", cm.parent, 
                ["name"], as_dict=True)
            if chapter_info:
                # Add chapter_name field with same value as name for consistency
                chapter_info["chapter_name"] = chapter_info["name"] 
                organizations["chapters"].append(chapter_info)
    
    # Get teams where volunteer is active
    team_members = frappe.get_all("Team Member",
        filters={"volunteer": volunteer_name, "status": "Active"},
        fields=["parent"]
    )
    
    for tm in team_members:
        team_info = frappe.db.get_value("Team", tm.parent,
            ["name"], as_dict=True)
        if team_info:
            # Add team_name field with same value as name for consistency
            team_info["team_name"] = team_info["name"]
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

def get_national_chapter():
    """Get national chapter info from settings"""
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if settings.national_board_chapter:
            chapter_info = frappe.db.get_value("Chapter", settings.national_board_chapter, 
                ["name", "chapter_name"], as_dict=True)
            if chapter_info:
                return {
                    "name": chapter_info.name,
                    "chapter_name": chapter_info.chapter_name or chapter_info.name
                }
    except Exception as e:
        frappe.log_error(f"Error getting national chapter: {str(e)}")
    
    return None

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
        # Parse JSON string if needed
        if isinstance(expense_data, str):
            import json
            expense_data = json.loads(expense_data)
        # Get current user's volunteer record
        volunteer = get_user_volunteer_record()
        if not volunteer:
            # Provide more helpful error message with debugging info
            user_email = frappe.session.user
            member = frappe.db.get_value("Member", {"email": user_email}, "name")
            
            if member:
                error_msg = _("No volunteer record found for your account. You have a member record ({0}) but no linked volunteer record. Please contact your chapter administrator to create a volunteer profile.").format(member)
            else:
                error_msg = _("No volunteer record found for your account. Your email ({0}) is not associated with any member or volunteer record. Please contact your chapter administrator.").format(user_email)
            
            frappe.throw(error_msg)
        
        # Validate required fields
        required_fields = ["description", "amount", "expense_date", "organization_type", "category"]
        for field in required_fields:
            if not expense_data.get(field):
                frappe.throw(_(f"Field {field} is required"))
        
        # Validate organization selection
        if expense_data.get("organization_type") == "Chapter" and not expense_data.get("chapter"):
            frappe.throw(_("Please select a chapter"))
        elif expense_data.get("organization_type") == "Team" and not expense_data.get("team"):
            frappe.throw(_("Please select a team"))
        # National expenses don't require specific organization selection
        
        # Determine chapter/team based on organization type
        chapter = None
        team = None
        
        if expense_data.get("organization_type") == "Chapter":
            chapter = expense_data.get("chapter")
        elif expense_data.get("organization_type") == "Team":
            team = expense_data.get("team")
        elif expense_data.get("organization_type") == "National":
            # Set to national chapter from settings
            settings = frappe.get_single("Verenigingen Settings")
            if settings.national_board_chapter:
                chapter = settings.national_board_chapter
            else:
                frappe.throw(_("National chapter not configured in settings"))
        
        # Get default company
        default_company = frappe.defaults.get_global_default("company")
        if not default_company:
            # Fallback to first company if no default is set
            companies = frappe.get_all("Company", limit=1, fields=["name"])
            default_company = companies[0].name if companies else None
        
        if not default_company:
            frappe.throw(_("No company configured in the system. Please contact the administrator."))
        
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
            "chapter": chapter,
            "team": team,
            "notes": expense_data.get("notes"),
            "company": default_company
        })
        
        # Insert the expense (no submit since doctype is not submittable)
        expense_doc.insert()
        
        # Set status to submitted since we can't use document submission
        expense_doc.db_set("status", "Submitted")
        
        return {
            "success": True,
            "message": _("Expense submitted successfully"),
            "expense_name": expense_doc.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error submitting expense: {str(e)}", "Volunteer Expense Submission Error")
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