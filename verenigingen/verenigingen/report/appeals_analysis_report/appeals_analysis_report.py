import frappe
from frappe import _
from frappe.utils import add_days, today, getdate, date_diff

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)
    return columns, data, None, None, summary

def get_columns():
    return [
        {
            "fieldname": "appeal_reference",
            "label": _("Appeal Reference"),
            "fieldtype": "Link",
            "options": "Termination Appeals Process",
            "width": 150
        },
        {
            "fieldname": "member_name",
            "label": _("Member"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "termination_type",
            "label": _("Termination Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "appeal_grounds",
            "label": _("Grounds"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "appeal_date",
            "label": _("Appeal Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "appeal_status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "days_to_decision",
            "label": _("Days to Decision"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "appeal_decision",
            "label": _("Decision"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "success_rate",
            "label": _("Success"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "assigned_reviewer",
            "label": _("Reviewer"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "urgency_level",
            "label": _("Urgency"),
            "fieldtype": "Data",
            "width": 80
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("from_date"):
        conditions.append("tap.appeal_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
        
    if filters.get("to_date"):
        conditions.append("tap.appeal_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
        
    if filters.get("appeal_status"):
        conditions.append("tap.appeal_status = %(appeal_status)s")
        values["appeal_status"] = filters["appeal_status"]
        
    if filters.get("termination_type"):
        conditions.append("mtr.termination_type = %(termination_type)s")
        values["termination_type"] = filters["termination_type"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT 
            tap.name as appeal_reference,
            tap.member_name,
            tap.appeal_grounds,
            tap.appeal_date,
            tap.appeal_status,
            tap.appeal_decision,
            tap.decision_date,
            tap.assigned_reviewer,
            tap.urgency_level,
            mtr.termination_type
        FROM `tabTermination Appeals Process` tap
        LEFT JOIN `tabMembership Termination Request` mtr ON tap.termination_request = mtr.name
        {where_clause}
        ORDER BY tap.appeal_date DESC
    """
    
    results = frappe.db.sql(query, values, as_dict=True)
    
    data = []
    for row in results:
        days_to_decision = ""
        success_rate = ""
        
        # Calculate processing time
        if row.decision_date and row.appeal_date:
            days_to_decision = date_diff(row.decision_date, row.appeal_date)
        elif row.appeal_date:
            # For pending appeals, show days since filing
            days_pending = date_diff(today(), row.appeal_date)
            if row.appeal_status in ["Under Review", "Pending Decision"]:
                days_to_decision = f"{days_pending} (pending)"
        
        # Determine success
        if row.appeal_decision:
            if row.appeal_decision in ["Upheld", "Partially Upheld"]:
                success_rate = "✓"
            else:
                success_rate = "✗"
        
        data.append({
            "appeal_reference": row.appeal_reference,
            "member_name": row.member_name,
            "termination_type": row.termination_type or "Unknown",
            "appeal_grounds": row.appeal_grounds,
            "appeal_date": row.appeal_date,
            "appeal_status": row.appeal_status,
            "days_to_decision": days_to_decision,
            "appeal_decision": row.appeal_decision or "",
            "success_rate": success_rate,
            "assigned_reviewer": row.assigned_reviewer or "",
            "urgency_level": row.urgency_level or "Medium"
        })
    
    return data

def get_summary(data):
    total_appeals = len(data)
    decided_appeals = len([d for d in data if d["appeal_decision"]])
    successful_appeals = len([d for d in data if d["success_rate"] == "✓"])
    
    success_rate = (successful_appeals / decided_appeals * 100) if decided_appeals > 0 else 0
    
    # Calculate average processing time
    processing_times = []
    for d in data:
        if d["days_to_decision"] and isinstance(d["days_to_decision"], int):
            processing_times.append(d["days_to_decision"])
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    return [
        {
            "label": _("Total Appeals"),
            "value": total_appeals,
            "indicator": "blue"
        },
        {
            "label": _("Success Rate"),
            "value": f"{success_rate:.1f}%",
            "indicator": "green" if success_rate > 30 else "red"
        },
        {
            "label": _("Avg. Processing Time"),
            "value": f"{avg_processing_time:.1f} days",
            "indicator": "green" if avg_processing_time <= 30 else "orange"
        },
        {
            "label": _("Pending Appeals"),
            "value": total_appeals - decided_appeals,
            "indicator": "orange" if (total_appeals - decided_appeals) > 5 else "blue"
        }
    ]
