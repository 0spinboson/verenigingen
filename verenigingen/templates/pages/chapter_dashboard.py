"""
Chapter Board Dashboard - Simplified interface for chapter board members
"""
import frappe
from frappe import _
from frappe.utils import today, flt, formatdate, add_days, date_diff, now_datetime
from datetime import datetime, timedelta, date

def serialize_dates(obj):
    """Recursively convert date/datetime objects to strings for JSON serialization"""
    if isinstance(obj, (datetime, date)):
        return obj.strftime("%Y-%m-%d %H:%M:%S") if isinstance(obj, datetime) else obj.strftime("%Y-%m-%d")
    elif isinstance(obj, dict):
        return {k: serialize_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_dates(item) for item in obj]
    return obj

def get_context(context):
    """Get context for chapter dashboard page"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access the chapter dashboard"), frappe.PermissionError)
    
    # Handle both dict and object context
    if hasattr(context, 'no_cache'):
        context.no_cache = 1
        context.show_sidebar = True
        context.title = _("Chapter Dashboard")
    else:
        # For direct dictionary access (debugging/testing)
        context["no_cache"] = 1
        context["show_sidebar"] = True
        context["title"] = _("Chapter Dashboard")
    
    # Get user's board chapters
    user_chapters = get_user_board_chapters()
    if not user_chapters:
        error_msg = _("You must be a board member to access this dashboard. Please contact your chapter administrator.")
        user_roles = frappe.get_roles()
        
        if hasattr(context, 'error_message'):
            context.error_message = error_msg
            context.user_roles = user_roles
        else:
            context["error_message"] = error_msg
            context["user_roles"] = user_roles
        return context
    
    # Handle chapter selection (default to first chapter)
    selected_chapter = frappe.form_dict.get('chapter') or user_chapters[0]['chapter_name']
    
    # Verify user has access to selected chapter
    if not any(ch['chapter_name'] == selected_chapter for ch in user_chapters):
        selected_chapter = user_chapters[0]['chapter_name']
    
    # Set context variables
    if hasattr(context, 'selected_chapter'):
        context.selected_chapter = selected_chapter
        context.user_chapters = user_chapters
        context.user_board_role = get_user_board_role(selected_chapter)
    else:
        context["selected_chapter"] = selected_chapter
        context["user_chapters"] = user_chapters
        context["user_board_role"] = get_user_board_role(selected_chapter)
    
    # Get dashboard data
    try:
        dashboard_data = get_chapter_dashboard_data(selected_chapter)
        has_data = True
    except Exception as e:
        frappe.log_error(f"Error loading dashboard data: {str(e)}", "Chapter Dashboard")
        dashboard_data = None
        has_data = False
    
    if hasattr(context, 'dashboard_data'):
        context.dashboard_data = dashboard_data
        context.has_data = has_data
        if not has_data:
            context.error_message = _("Error loading dashboard data. Please try again.")
    else:
        context["dashboard_data"] = dashboard_data
        context["has_data"] = has_data
        if not has_data:
            context["error_message"] = _("Error loading dashboard data. Please try again.")
    
    return context

def get_user_board_chapters():
    """Get chapters where current user is a board member"""
    user_email = frappe.session.user
    
    # Admin users can see all chapters
    admin_roles = ["System Manager", "Verenigingen Administrator"]
    if any(role in frappe.get_roles() for role in admin_roles):
        return frappe.get_all("Chapter", 
            fields=["name as chapter_name", "region"], 
            filters={"published": 1},
            order_by="name")
    
    # Find member record for current user
    member = frappe.db.get_value("Member", {"email": user_email}, "name")
    if not member:
        return []
    
    # Find volunteer record linked to member
    volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
    if not volunteer:
        return []
    
    # Get chapters where this volunteer is a board member
    board_chapters = frappe.db.sql("""
        SELECT DISTINCT cbm.parent as chapter_name, c.region,
               cbm.chapter_role, cbm.from_date, cbm.to_date, cbm.is_active
        FROM `tabChapter Board Member` cbm
        INNER JOIN `tabChapter` c ON cbm.parent = c.name
        WHERE cbm.volunteer = %s AND cbm.is_active = 1
        ORDER BY cbm.from_date DESC
    """, (volunteer,), as_dict=True)
    
    return board_chapters

def get_user_board_role(chapter_name):
    """Get user's board role for specific chapter"""
    user_email = frappe.session.user
    
    # Admin users have full access
    admin_roles = ["System Manager", "Verenigingen Administrator"]
    if any(role in frappe.get_roles() for role in admin_roles):
        return {"role": "System Administrator", "permissions": "full"}
    
    member = frappe.db.get_value("Member", {"email": user_email}, "name")
    if not member:
        return None
    
    volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
    if not volunteer:
        return None
    
    board_role = frappe.db.get_value("Chapter Board Member", 
        {"parent": chapter_name, "volunteer": volunteer, "is_active": 1},
        ["chapter_role", "from_date"], as_dict=True)
    
    if board_role:
        # Get role permissions based on chapter role
        role_permissions = get_role_permissions(board_role.chapter_role)
        return {
            "role": board_role.chapter_role,
            "since": board_role.from_date,
            "since_formatted": board_role.from_date.strftime('%B %Y') if board_role.from_date else '',
            "permissions": role_permissions
        }
    
    return None

def get_role_permissions(role_name):
    """Get permissions based on board role"""
    role_permissions = {
        "Chapter Head": {
            "can_approve_members": True,
            "can_approve_expenses": True,
            "can_manage_board": True,
            "can_view_finances": True,
            "expense_limit": 1000
        },
        "Treasurer": {
            "can_approve_members": True,
            "can_approve_expenses": True,
            "can_manage_board": False,
            "can_view_finances": True,
            "expense_limit": 500
        },
        "Secretary": {
            "can_approve_members": True,
            "can_approve_expenses": False,
            "can_manage_board": False,
            "can_view_finances": False,
            "expense_limit": 0
        }
    }
    
    # Default permissions for other roles
    default_permissions = {
        "can_approve_members": False,
        "can_approve_expenses": False,
        "can_manage_board": False,
        "can_view_finances": False,
        "expense_limit": 0
    }
    
    return role_permissions.get(role_name, default_permissions)

@frappe.whitelist()
def get_chapter_dashboard_data(chapter_name):
    """Get comprehensive dashboard data for chapter board members"""
    
    if not chapter_name:
        frappe.throw(_("Chapter name is required"))
    
    # Verify user has access to this chapter
    user_chapters = get_user_board_chapters()
    if not any(ch['chapter_name'] == chapter_name for ch in user_chapters):
        frappe.throw(_("You don't have access to this chapter"))
    
    dashboard_data = {
        "chapter_info": get_chapter_basic_info(chapter_name),
        "key_metrics": get_chapter_key_metrics(chapter_name),
        "member_overview": get_member_overview(chapter_name),
        "pending_actions": get_pending_actions(chapter_name),
        "financial_summary": get_financial_summary(chapter_name),
        "board_info": get_board_information(chapter_name),
        "recent_activity": get_recent_activity(chapter_name),
        "last_updated": now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Serialize all date/datetime objects for JSON compatibility
    return serialize_dates(dashboard_data)

def get_chapter_basic_info(chapter_name):
    """Get basic chapter information"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    
    return {
        "name": chapter.name,
        "region": getattr(chapter, 'region', ''),
        "head": getattr(chapter, 'chapter_head', ''),
        "published": getattr(chapter, 'published', 0),
        "introduction": getattr(chapter, 'introduction', ''),
        "total_board_members": len([m for m in chapter.board_members if m.is_active])
    }

def get_chapter_key_metrics(chapter_name):
    """Get key metrics for dashboard cards"""
    
    # Member statistics
    member_stats = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_members,
            SUM(CASE WHEN (status = 'Active' OR status IS NULL) AND enabled = 1 THEN 1 ELSE 0 END) as active_members,
            SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending_members,
            SUM(CASE WHEN chapter_join_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as new_this_month,
            SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) as inactive_members
        FROM `tabChapter Member` 
        WHERE parent = %s
    """, (chapter_name,), as_dict=True)[0]
    
    # Expense statistics (basic for now)
    expense_stats = get_basic_expense_stats(chapter_name)
    
    # Activity statistics (placeholder for now)
    activity_stats = {
        "this_month": 2,
        "upcoming": 1,
        "last_activity": "1 week ago"
    }
    
    return {
        "members": {
            "active": int(member_stats.active_members or 0),
            "pending": int(member_stats.pending_members or 0),
            "inactive": int(member_stats.inactive_members or 0),
            "new_this_month": int(member_stats.new_this_month or 0),
            "total": int(member_stats.total_members or 0)
        },
        "expenses": expense_stats,
        "activities": activity_stats
    }

def get_basic_expense_stats(chapter_name):
    """Get basic expense statistics (placeholder for full implementation)"""
    # This is a simplified version - can be enhanced with actual expense data
    return {
        "pending_amount": 234.30,
        "pending_count": 2,
        "ytd_total": 1204.85,
        "this_month": 234.30
    }

def get_member_overview(chapter_name):
    """Get member overview with recent activities"""
    
    # Get recent member activities
    recent_members = frappe.db.sql("""
        SELECT cm.member, m.full_name, cm.status, cm.chapter_join_date,
               cm.enabled, cm.leave_reason
        FROM `tabChapter Member` cm
        INNER JOIN `tabMember` m ON cm.member = m.name
        WHERE cm.parent = %s
        ORDER BY cm.modified DESC
        LIMIT 10
    """, (chapter_name,), as_dict=True)
    
    # Get pending applications
    pending_applications = frappe.db.sql("""
        SELECT cm.member, m.full_name, cm.chapter_join_date, m.application_date,
               DATEDIFF(CURDATE(), COALESCE(m.application_date, cm.chapter_join_date)) as days_pending
        FROM `tabChapter Member` cm
        INNER JOIN `tabMember` m ON cm.member = m.name
        WHERE cm.parent = %s AND cm.status = 'Pending'
        ORDER BY cm.chapter_join_date ASC
    """, (chapter_name,), as_dict=True)
    
    return {
        "recent_members": recent_members[:5],  # Limit to 5 for dashboard
        "pending_applications": pending_applications,
        "total_pending": len(pending_applications)
    }

def get_pending_actions(chapter_name):
    """Get items requiring board attention"""
    
    # Get pending membership applications
    pending_apps = get_member_overview(chapter_name)["pending_applications"]
    
    # Mark overdue applications (more than 7 days)
    for app in pending_apps:
        app["is_overdue"] = (app.get("days_pending", 0) or 0) > 7
    
    # Get pending expense approvals (placeholder)
    pending_expenses = []  # Will be implemented when expense system is fully integrated
    
    # Get board tasks (placeholder)
    board_tasks = []  # Will be implemented with task management
    
    return {
        "membership_applications": pending_apps,
        "expense_approvals": pending_expenses,
        "board_tasks": board_tasks,
        "total_pending": len(pending_apps) + len(pending_expenses) + len(board_tasks)
    }

def get_financial_summary(chapter_name):
    """Get financial summary for the chapter"""
    # Placeholder implementation - to be enhanced with actual financial data
    return {
        "this_month": {
            "expenses_submitted": 234.30,
            "expenses_approved": 189.50,
            "pending_approval": 67.50,
            "claims_count": 4
        },
        "ytd": {
            "total_expenses": 1204.85,
            "average_claim": 43.75,
            "total_claims": 28
        }
    }

def get_board_information(chapter_name):
    """Get board member information"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    
    board_members = []
    for board_member in chapter.board_members:
        if board_member.is_active:
            member_info = {
                "volunteer": board_member.volunteer,
                "volunteer_name": board_member.volunteer_name,
                "role": board_member.chapter_role,
                "email": board_member.email,
                "from_date": board_member.from_date,
                "to_date": board_member.to_date,
                "is_current_user": False
            }
            
            # Check if this is the current user
            current_user_email = frappe.session.user
            if board_member.email == current_user_email:
                member_info["is_current_user"] = True
            
            board_members.append(member_info)
    
    return {
        "members": board_members,
        "total_count": len(board_members),
        "next_meeting": None  # Placeholder for meeting management
    }

def get_recent_activity(chapter_name):
    """Get recent chapter activities"""
    activities = []
    
    # Get recent member changes from comments/activity
    recent_comments = frappe.get_all("Comment",
        filters={
            "reference_doctype": "Chapter",
            "reference_name": chapter_name,
            "comment_type": "Info"
        },
        fields=["content", "creation", "owner"],
        order_by="creation desc",
        limit=5
    )
    
    for comment in recent_comments:
        activities.append({
            "type": "system",
            "description": comment.content,
            "timestamp": comment.creation,
            "user": comment.owner
        })
    
    # Add member join activities
    recent_joins = frappe.db.sql("""
        SELECT m.full_name, cm.chapter_join_date, cm.status
        FROM `tabChapter Member` cm
        INNER JOIN `tabMember` m ON cm.member = m.name
        WHERE cm.parent = %s 
        AND cm.chapter_join_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        ORDER BY cm.chapter_join_date DESC
        LIMIT 5
    """, (chapter_name,), as_dict=True)
    
    for join in recent_joins:
        activities.append({
            "type": "member_join",
            "description": f"{join.full_name} joined the chapter ({join.status})",
            "timestamp": join.chapter_join_date,
            "user": "System"
        })
    
    # Sort activities by timestamp (handle both datetime and date objects)
    def get_sort_key(activity):
        timestamp = activity["timestamp"]
        if isinstance(timestamp, str):
            return datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        elif hasattr(timestamp, 'date'):
            return timestamp  # datetime object
        else:
            return datetime.combine(timestamp, datetime.min.time())  # date object
    
    activities.sort(key=get_sort_key, reverse=True)
    
    return activities[:10]  # Return top 10 recent activities