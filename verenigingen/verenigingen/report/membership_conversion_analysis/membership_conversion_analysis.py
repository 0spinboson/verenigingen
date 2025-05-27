# verenigingen/verenigingen/report/membership_conversion_analysis/membership_conversion_analysis.py

import frappe
from frappe import _
from frappe.utils import getdate, add_days, flt

def execute(filters=None):
    """Generate Membership Conversion Analysis Report"""
    
    columns = get_columns()
    data = get_data(filters)
    
    # Add summary with conversion metrics
    summary = get_conversion_metrics(data, filters)
    
    # Add conversion funnel chart
    chart = get_conversion_funnel_chart(filters)
    
    return columns, data, None, chart, summary

def get_columns():
    """Define report columns"""
    return [
        {
            "label": _("Period"),
            "fieldname": "period",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Total Applications"),
            "fieldname": "total_applications",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": _("Approved"),
            "fieldname": "approved",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Rejected"),
            "fieldname": "rejected",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Pending"),
            "fieldname": "pending",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Paid"),
            "fieldname": "paid",
            "fieldtype": "Int",
            "width": 100
        },
        {
            "label": _("Conversion Rate"),
            "fieldname": "conversion_rate",
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "label": _("Avg Processing Days"),
            "fieldname": "avg_processing_days",
            "fieldtype": "Float",
            "width": 140
        },
        {
            "label": _("Revenue"),
            "fieldname": "revenue",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("By Chapter"),
            "fieldname": "chapter_breakdown",
            "fieldtype": "HTML",
            "width": 200
        },
        {
            "label": _("By Source"),
            "fieldname": "source_breakdown",
            "fieldtype": "HTML",
            "width": 200
        }
    ]

def get_data(filters):
    """Get conversion data grouped by period"""
    
    # Determine grouping period
    group_by = filters.get("group_by", "Month")
    from_date = filters.get("from_date", add_days(getdate(), -90))
    to_date = filters.get("to_date", getdate())
    
    # Get all applications in period
    applications = frappe.db.sql("""
        SELECT 
            m.name,
            m.application_date,
            m.application_status,
            m.review_date,
            m.payment_date,
            m.payment_amount,
            m.primary_chapter,
            m.application_source,
            CASE 
                WHEN %(group_by)s = 'Week' THEN CONCAT(YEAR(m.application_date), '-W', WEEK(m.application_date))
                WHEN %(group_by)s = 'Month' THEN DATE_FORMAT(m.application_date, '%%Y-%%m')
                WHEN %(group_by)s = 'Quarter' THEN CONCAT(YEAR(m.application_date), '-Q', QUARTER(m.application_date))
                ELSE DATE(m.application_date)
            END as period
        FROM `tabMember` m
        WHERE m.application_date BETWEEN %(from_date)s AND %(to_date)s
        AND m.application_status IS NOT NULL
        ORDER BY m.application_date
    """, {
        "group_by": group_by,
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)
    
    # Group data by period
    period_data = {}
    
    for app in applications:
        period = app.period
        if period not in period_data:
            period_data[period] = {
                "period": period,
                "total_applications": 0,
                "approved": 0,
                "rejected": 0,
                "pending": 0,
                "paid": 0,
                "revenue": 0,
                "processing_days": [],
                "chapters": {},
                "sources": {}
            }
        
        pd = period_data[period]
        pd["total_applications"] += 1
        
        # Count by status
        if app.application_status == "Active":
            pd["approved"] += 1
            if app.payment_date:
                pd["paid"] += 1
                pd["revenue"] += flt(app.payment_amount)
        elif app.application_status == "Rejected":
            pd["rejected"] += 1
        elif app.application_status == "Pending":
            pd["pending"] += 1
        
        # Calculate processing time
        if app.review_date and app.application_date:
            days = (getdate(app.review_date) - getdate(app.application_date)).days
            pd["processing_days"].append(days)
        
        # Track by chapter
        chapter = app.primary_chapter or "Unassigned"
        pd["chapters"][chapter] = pd["chapters"].get(chapter, 0) + 1
        
        # Track by source
        source = app.application_source or "Unknown"
        pd["sources"][source] = pd["sources"].get(source, 0) + 1
    
    # Convert to list and calculate metrics
    data = []
    for period, pd in sorted(period_data.items()):
        row = {
            "period": format_period(period, group_by),
            "total_applications": pd["total_applications"],
            "approved": pd["approved"],
            "rejected": pd["rejected"],
            "pending": pd["pending"],
            "paid": pd["paid"],
            "revenue": pd["revenue"],
            "conversion_rate": (pd["paid"] / pd["total_applications"] * 100) if pd["total_applications"] > 0 else 0,
            "avg_processing_days": sum(pd["processing_days"]) / len(pd["processing_days"]) if pd["processing_days"] else 0
        }
        
        # Add chapter breakdown
        chapter_html = "<small>"
        for chapter, count in sorted(pd["chapters"].items(), key=lambda x: x[1], reverse=True)[:3]:
            chapter_html += f"{chapter}: {count}<br>"
        row["chapter_breakdown"] = chapter_html + "</small>"
        
        # Add source breakdown  
        source_html = "<small>"
        for source, count in sorted(pd["sources"].items(), key=lambda x: x[1], reverse=True)[:3]:
            source_html += f"{source}: {count}<br>"
        row["source_breakdown"] = source_html + "</small>"
        
        data.append(row)
    
    return data

def format_period(period, group_by):
    """Format period for display"""
    if group_by == "Week":
        year, week = period.split("-W")
        return f"Week {week}, {year}"
    elif group_by == "Month":
        year, month = period.split("-")
        return f"{frappe.utils.get_month_name(int(month))} {year}"
    elif group_by == "Quarter":
        return period
    else:
        return frappe.format_date(period)

def get_conversion_metrics(data, filters):
    """Calculate overall conversion metrics"""
    if not data:
        return []
    
    total_apps = sum(row["total_applications"] for row in data)
    total_approved = sum(row["approved"] for row in data)
    total_paid = sum(row["paid"] for row in data)
    total_revenue = sum(row["revenue"] for row in data)
    
    return [
        {
            "value": total_apps,
            "label": _("Total Applications"),
            "datatype": "Int"
        },
        {
            "value": f"{(total_approved/total_apps*100):.1f}%" if total_apps > 0 else "0%",
            "label": _("Approval Rate"),
            "datatype": "Data"
        },
        {
            "value": f"{(total_paid/total_apps*100):.1f}%" if total_apps > 0 else "0%",
            "label": _("Conversion Rate"),
            "datatype": "Data",
            "color": "green" if total_apps > 0 and (total_paid/total_apps) > 0.7 else "orange"
        },
        {
            "value": total_revenue,
            "label": _("Total Revenue"),
            "datatype": "Currency"
        },
        {
            "value": total_revenue / total_paid if total_paid > 0 else 0,
            "label": _("Avg Transaction Value"),
            "datatype": "Currency"
        }
    ]

def get_conversion_funnel_chart(filters):
    """Get conversion funnel visualization"""
    
    from_date = filters.get("from_date", add_days(getdate(), -90))
    to_date = filters.get("to_date", getdate())
    
    # Get funnel data
    funnel_data = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_applications,
            SUM(CASE WHEN application_status != 'Rejected' THEN 1 ELSE 0 END) as not_rejected,
            SUM(CASE WHEN application_status = 'Active' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN payment_date IS NOT NULL THEN 1 ELSE 0 END) as paid,
            SUM(CASE WHEN interested_in_volunteering = 1 AND application_status = 'Active' THEN 1 ELSE 0 END) as volunteers
        FROM `tabMember`
        WHERE application_date BETWEEN %(from_date)s AND %(to_date)s
        AND application_status IS NOT NULL
    """, {
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)[0]
    
    return {
        "data": {
            "labels": [
                _("Applied"),
                _("Not Rejected"), 
                _("Approved"),
                _("Paid"),
                _("Volunteered")
            ],
            "datasets": [{
                "name": _("Conversion Funnel"),
                "values": [
                    funnel_data.total_applications,
                    funnel_data.not_rejected,
                    funnel_data.approved,
                    funnel_data.paid,
                    funnel_data.volunteers
                ]
            }]
        },
        "type": "bar",
        "colors": ["#5e64ff"],
        "barOptions": {
            "height": 20
        }
    }
