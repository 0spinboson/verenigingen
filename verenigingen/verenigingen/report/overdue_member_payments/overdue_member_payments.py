import frappe
from frappe import _
from frappe.utils import getdate, today, add_days, flt

def execute(filters=None):
    """Generate Overdue Member Payments Report"""
    
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
            "label": _("Member ID"),
            "fieldname": "member_name",
            "fieldtype": "Link",
            "options": "Member",
            "width": 120
        },
        {
            "label": _("Member Name"),
            "fieldname": "member_full_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Email"),
            "fieldname": "member_email",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Chapter"),
            "fieldname": "chapter",
            "fieldtype": "Link",
            "options": "Chapter",
            "width": 120
        },
        {
            "label": _("Overdue Invoices"),
            "fieldname": "overdue_count",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Total Overdue Amount"),
            "fieldname": "total_overdue",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": _("Oldest Invoice Date"),
            "fieldname": "oldest_invoice_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Days Overdue"),
            "fieldname": "days_overdue",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Membership Type"),
            "fieldname": "membership_type",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Status"),
            "fieldname": "status_indicator",
            "fieldtype": "HTML",
            "width": 100
        },
        {
            "label": _("Last Payment"),
            "fieldname": "last_payment_date",
            "fieldtype": "Date",
            "width": 120
        }
    ]

def get_data(filters):
    """Get report data"""
    
    # Apply role-based chapter filtering
    user_chapter_condition = get_user_chapter_filter()
    chapter_join = ""
    chapter_condition = ""
    
    if user_chapter_condition:
        chapter_join = "LEFT JOIN `tabMember` m ON si.customer = m.customer"
        chapter_condition = f"AND {user_chapter_condition}"
    
    # Base conditions for overdue invoices
    conditions = [
        "si.status IN ('Overdue', 'Unpaid')",
        "si.due_date < CURDATE()",
        "si.docstatus = 1"
    ]
    
    # Apply filters
    filter_conditions = []
    if filters:
        if filters.get("chapter"):
            filter_conditions.append("m.primary_chapter = %(chapter)s")
        
        if filters.get("from_date"):
            filter_conditions.append("si.posting_date >= %(from_date)s")
        
        if filters.get("to_date"):
            filter_conditions.append("si.posting_date <= %(to_date)s")
        
        if filters.get("membership_type"):
            filter_conditions.append("ms.membership_type = %(membership_type)s")
        
        if filters.get("days_overdue"):
            cutoff_date = add_days(today(), -int(filters.get("days_overdue")))
            filter_conditions.append(f"si.due_date < '{cutoff_date}'")
        
        if filters.get("critical_only"):
            # Critical = more than 60 days overdue
            critical_date = add_days(today(), -60)
            filter_conditions.append(f"si.due_date < '{critical_date}'")
        
        if filters.get("urgent_only"):
            # Urgent = more than 30 days overdue
            urgent_date = add_days(today(), -30)
            filter_conditions.append(f"si.due_date < '{urgent_date}'")
    
    # Combine all conditions
    all_conditions = conditions + filter_conditions
    if chapter_condition:
        all_conditions.append(chapter_condition.replace("AND ", ""))
    
    where_clause = " AND ".join(all_conditions)
    
    # Query to get overdue invoices with member information
    data = frappe.db.sql(f"""
        SELECT 
            m.name as member_name,
            m.full_name as member_full_name,
            m.email as member_email,
            m.primary_chapter as chapter,
            COUNT(si.name) as overdue_count,
            SUM(si.outstanding_amount) as total_overdue,
            MIN(si.posting_date) as oldest_invoice_date,
            DATEDIFF(CURDATE(), MIN(si.due_date)) as days_overdue,
            ms.membership_type,
            MAX(pe.posting_date) as last_payment_date
        FROM `tabSales Invoice` si
        LEFT JOIN `tabMember` m ON si.customer = m.customer
        LEFT JOIN `tabMembership` ms ON ms.member = m.name AND ms.status = 'Active'
        LEFT JOIN `tabPayment Entry Reference` per ON per.reference_name = si.name
        LEFT JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
        WHERE {where_clause}
            AND si.subscription IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM `tabSubscription` sub 
                WHERE sub.name = si.subscription 
                AND sub.reference_doctype = 'Membership Type'
            )
        GROUP BY m.name, m.full_name, m.email, m.primary_chapter, ms.membership_type
        HAVING overdue_count > 0
        ORDER BY days_overdue DESC, total_overdue DESC
    """, filters or {}, as_dict=True)
    
    # Process data and add status indicators
    for row in data:
        # Add status indicator with color coding
        days_overdue = row.get("days_overdue") or 0
        if days_overdue > 60:
            row["status_indicator"] = '<span class="indicator red">Critical</span>'
        elif days_overdue > 30:
            row["status_indicator"] = '<span class="indicator orange">Urgent</span>'
        elif days_overdue > 14:
            row["status_indicator"] = '<span class="indicator yellow">Overdue</span>'
        else:
            row["status_indicator"] = '<span class="indicator blue">Due</span>'
        
        # Format amounts
        row["total_overdue"] = flt(row.get("total_overdue"), 2)
    
    return data

def get_user_chapter_filter():
    """Get chapter filter based on user's role and permissions (same as applications)"""
    user = frappe.session.user
    
    # System managers and Association/Membership managers see all
    admin_roles = ["System Manager", "Association Manager", "Membership Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return None  # No filter - see all
    
    # Get user's member record
    user_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not user_member:
        return "1=0"  # No access if not a member
    
    # Get chapters where user has board access with membership or finance permissions
    user_chapters = []
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
            # Check if the role has membership or finance permissions
            try:
                role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                if role_doc.permissions_level in ["Admin", "Membership", "Finance"]:
                    if position.parent not in user_chapters:
                        user_chapters.append(position.parent)
            except Exception:
                continue
    
    # Add national chapter if configured and user has access
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if hasattr(settings, 'national_chapter') and settings.national_chapter:
            # Check if user has board access to national chapter
            national_board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "parent": settings.national_chapter,
                    "volunteer": ["in", [v.name for v in volunteer_records]],
                    "is_active": 1
                },
                fields=["chapter_role"]
            )
            
            for position in national_board_positions:
                try:
                    role_doc = frappe.get_doc("Chapter Role", position.chapter_role)
                    if role_doc.permissions_level in ["Admin", "Membership", "Finance"]:
                        if settings.national_chapter not in user_chapters:
                            user_chapters.append(settings.national_chapter)
                        break
                except Exception:
                    continue
    except Exception:
        pass
    
    if not user_chapters:
        return "1=0"  # No access if not on any board with relevant permissions
    
    # Return filter for user's chapters, including null/empty chapters for national access
    if len(user_chapters) == 1 and user_chapters[0] == getattr(frappe.get_single("Verenigingen Settings"), 'national_chapter', None):
        # National chapter access - can see all including unassigned
        return None
    else:
        # Chapter-specific access
        chapter_conditions = [f"m.primary_chapter = '{chapter}'" for chapter in user_chapters]
        # Also include members without a chapter assigned if user has national access
        try:
            settings = frappe.get_single("Verenigingen Settings")
            if hasattr(settings, 'national_chapter') and settings.national_chapter in user_chapters:
                chapter_conditions.append("(m.primary_chapter IS NULL OR m.primary_chapter = '')")
        except Exception:
            pass
        
        return f"({' OR '.join(chapter_conditions)})"

def get_summary(data):
    """Get summary statistics"""
    if not data:
        return []
    
    total_members = len(data)
    total_amount = sum(flt(d.get("total_overdue", 0)) for d in data)
    total_invoices = sum(int(d.get("overdue_count", 0)) for d in data)
    
    critical_count = len([d for d in data if (d.get("days_overdue") or 0) > 60])
    urgent_count = len([d for d in data if (d.get("days_overdue") or 0) > 30])
    
    avg_days_overdue = sum((d.get("days_overdue") or 0) for d in data) / len(data) if data else 0
    
    return [
        {
            "value": total_members,
            "label": _("Members with Overdue Payments"),
            "datatype": "Int"
        },
        {
            "value": total_invoices,
            "label": _("Total Overdue Invoices"),
            "datatype": "Int"
        },
        {
            "value": total_amount,
            "label": _("Total Overdue Amount"),
            "datatype": "Currency",
            "color": "red" if total_amount > 1000 else "orange" if total_amount > 500 else "green"
        },
        {
            "value": critical_count,
            "label": _("Critical (>60 days)"),
            "datatype": "Int",
            "color": "red" if critical_count > 0 else "green"
        },
        {
            "value": urgent_count,
            "label": _("Urgent (>30 days)"),
            "datatype": "Int",
            "color": "orange" if urgent_count > 0 else "green"
        },
        {
            "value": round(avg_days_overdue, 1),
            "label": _("Average Days Overdue"),
            "datatype": "Float"
        }
    ]

def get_chart_data(data):
    """Get chart data for visualization"""
    if not data:
        return None
    
    # Group by chapter
    chapter_amounts = {}
    for row in data:
        chapter = row.get("chapter") or "Unassigned"
        if chapter not in chapter_amounts:
            chapter_amounts[chapter] = 0
        chapter_amounts[chapter] += flt(row.get("total_overdue", 0))
    
    return {
        "data": {
            "labels": list(chapter_amounts.keys()),
            "datasets": [{
                "name": _("Overdue Amount"),
                "values": list(chapter_amounts.values())
            }]
        },
        "type": "bar",
        "colors": ["#ff6b6b"]
    }