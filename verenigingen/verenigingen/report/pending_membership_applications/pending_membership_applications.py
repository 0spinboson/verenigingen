import frappe
from frappe import _
from frappe.utils import getdate, today, add_days

def execute(filters=None):
    """Generate Pending Membership Applications Report"""
    
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
            "label": _("Application ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Member",
            "width": 120
        },
        {
            "label": _("Applicant Name"),
            "fieldname": "full_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Email"),
            "fieldname": "email",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Application Date"),
            "fieldname": "application_date",
            "fieldtype": "Datetime",
            "width": 140
        },
        {
            "label": _("Days Pending"),
            "fieldname": "days_pending",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Chapter"),
            "fieldname": "chapter",
            "fieldtype": "Link",
            "options": "Chapter",
            "width": 120
        },
        {
            "label": _("Membership Type"),
            "fieldname": "selected_membership_type",
            "fieldtype": "Link",
            "options": "Membership Type",
            "width": 130
        },
        {
            "label": _("Age"),
            "fieldname": "age",
            "fieldtype": "Int",
            "width": 60
        },
        {
            "label": _("Volunteer Interest"),
            "fieldname": "volunteer_interest",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Source"),
            "fieldname": "application_source",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Status"),
            "fieldname": "status_indicator",
            "fieldtype": "HTML",
            "width": 100
        }
    ]

def get_data(filters):
    """Get report data"""
    
    # Base conditions
    conditions = ["m.application_status = 'Pending'"]
    
    # Apply filters
    if filters:
        if filters.get("chapter"):
            conditions.append(f"(m.primary_chapter = %(chapter)s OR m.suggested_chapter = %(chapter)s)")
        
        if filters.get("from_date"):
            conditions.append("DATE(m.application_date) >= %(from_date)s")
        
        if filters.get("to_date"):
            conditions.append("DATE(m.application_date) <= %(to_date)s")
        
        if filters.get("membership_type"):
            conditions.append("m.selected_membership_type = %(membership_type)s")
        
        if filters.get("overdue_only"):
            overdue_date = add_days(today(), -14)
            conditions.append(f"DATE(m.application_date) < '{overdue_date}'")
    
    where_clause = " AND ".join(conditions)
    
    data = frappe.db.sql(f"""
        SELECT 
            m.name,
            m.full_name,
            m.email,
            m.application_date,
            DATEDIFF(CURDATE(), DATE(m.application_date)) as days_pending,
            COALESCE(m.primary_chapter, m.suggested_chapter) as chapter,
            m.selected_membership_type,
            m.age,
            m.interested_in_volunteering,
            m.application_source,
            m.application_status
        FROM `tabMember` m
        WHERE {where_clause}
        ORDER BY m.application_date ASC
    """, filters, as_dict=True)
    
    # Process data
    for row in data:
        # Add volunteer interest indicator
        row["volunteer_interest"] = "Yes" if row.get("interested_in_volunteering") else "No"
        
        # Add status indicator with color coding
        if row["days_pending"] > 14:
            row["status_indicator"] = '<span class="indicator red">Overdue</span>'
        elif row["days_pending"] > 7:
            row["status_indicator"] = '<span class="indicator orange">Aging</span>'
        else:
            row["status_indicator"] = '<span class="indicator blue">Recent</span>'
    
    return data

def get_summary(data):
    """Get summary statistics"""
    if not data:
        return []
    
    total_pending = len(data)
    overdue_count = len([d for d in data if d["days_pending"] > 14])
    volunteer_interested = len([d for d in data if d.get("interested_in_volunteering")])
    
    avg_days_pending = sum(d["days_pending"] for d in data) / len(data) if data else 0
    
    return [
        {
            "value": total_pending,
            "label": _("Total Pending"),
            "datatype": "Int"
        },
        {
            "value": overdue_count,
            "label": _("Overdue (>14 days)"),
            "datatype": "Int",
            "color": "red" if overdue_count > 0 else "green"
        },
        {
            "value": round(avg_days_pending, 1),
            "label": _("Average Days Pending"),
            "datatype": "Float"
        },
        {
            "value": f"{(volunteer_interested/total_pending*100):.1f}%" if total_pending > 0 else "0%",
            "label": _("Volunteer Interest Rate"),
            "datatype": "Data"
        }
    ]

def get_chart_data(data):
    """Get chart data for visualization"""
    if not data:
        return None
    
    # Group by chapter
    chapter_counts = {}
    for row in data:
        chapter = row.get("chapter") or "Unassigned"
        chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1
    
    return {
        "data": {
            "labels": list(chapter_counts.keys()),
            "datasets": [{
                "name": _("Pending Applications"),
                "values": list(chapter_counts.values())
            }]
        },
        "type": "bar",
        "colors": ["#7cd6fd"]
    }
