# Query Report: Termination Compliance Report
# File: verenigingen/verenigingen/report/termination_compliance_report/termination_compliance_report.py

import frappe
from frappe import _
from frappe.utils import add_days, today, getdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "request_id",
            "label": _("Request ID"),
            "fieldtype": "Link",
            "options": "Membership Termination Request",
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
            "label": _("Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "request_date",
            "label": _("Request Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "days_pending",
            "label": _("Days Pending"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "compliance_issue",
            "label": _("Compliance Issue"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "priority",
            "label": _("Priority"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "requested_by",
            "label": _("Requested By"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "secondary_approver",
            "label": _("Approver"),
            "fieldtype": "Data",
            "width": 150
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("from_date"):
        conditions.append("mtr.request_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
        
    if filters.get("to_date"):
        conditions.append("mtr.request_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
        
    if filters.get("termination_type"):
        conditions.append("mtr.termination_type = %(termination_type)s")
        values["termination_type"] = filters["termination_type"]
        
    if filters.get("chapter"):
        conditions.append("m.primary_chapter = %(chapter)s")
        values["chapter"] = filters["chapter"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT 
            mtr.name as request_id,
            mtr.member_name,
            mtr.termination_type,
            mtr.request_date,
            mtr.status,
            mtr.requested_by,
            mtr.secondary_approver,
            mtr.disciplinary_documentation,
            mtr.approved_by,
            mtr.approval_date,
            m.primary_chapter
        FROM `tabMembership Termination Request` mtr
        LEFT JOIN `tabMember` m ON mtr.member = m.name
        {where_clause}
        ORDER BY mtr.request_date DESC
    """
    
    results = frappe.db.sql(query, values, as_dict=True)
    
    data = []
    for row in results:
        days_pending = 0
        compliance_issue = ""
        priority = "Normal"
        
        # Calculate days pending
        if row.status in ["Pending Approval", "Approved"]:
            if row.status == "Pending Approval":
                days_pending = (getdate(today()) - getdate(row.request_date)).days
            elif row.status == "Approved" and row.approval_date:
                days_pending = (getdate(today()) - getdate(row.approval_date)).days
        
        # Identify compliance issues
        disciplinary_types = ["Policy Violation", "Disciplinary Action", "Expulsion"]
        
        if row.termination_type in disciplinary_types:
            if not row.disciplinary_documentation:
                compliance_issue = "Missing Documentation"
                priority = "High"
            elif row.status == "Pending Approval" and days_pending > 7:
                compliance_issue = "Overdue Approval"
                priority = "High"
            elif not row.approved_by and row.status == "Executed":
                compliance_issue = "Missing Secondary Approval"
                priority = "Critical"
        
        if row.status == "Approved" and days_pending > 3:
            if compliance_issue:
                compliance_issue += ", Delayed Execution"
            else:
                compliance_issue = "Delayed Execution"
            priority = "Medium"
        
        if not compliance_issue:
            compliance_issue = "Compliant"
            priority = "Normal"
        
        data.append({
            "request_id": row.request_id,
            "member_name": row.member_name,
            "termination_type": row.termination_type,
            "request_date": row.request_date,
            "status": row.status,
            "days_pending": days_pending if days_pending > 0 else "",
            "compliance_issue": compliance_issue,
            "priority": priority,
            "requested_by": row.requested_by,
            "secondary_approver": row.secondary_approver or ""
        })
    
    return data


# Query Report: Appeals Analysis Report
# File: verenigingen/verenigingen/report/appeals_analysis_report/appeals_analysis_report.py

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


# Query Report: Board Position Termination Impact
# File: verenigingen/verenigingen/report/board_position_termination_impact/board_position_termination_impact.py

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "termination_request",
            "label": _("Termination Request"),
            "fieldtype": "Link",
            "options": "Membership Termination Request",
            "width": 180
        },
        {
            "fieldname": "member_name",
            "label": _("Member"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "chapter",
            "label": _("Chapter"),
            "fieldtype": "Link",
            "options": "Chapter",
            "width": 150
        },
        {
            "fieldname": "board_role",
            "label": _("Board Role"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "role_start_date",
            "label": _("Role Start"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "role_end_date",
            "label": _("Role End"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "termination_date",
            "label": _("Termination Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "termination_type",
            "label": _("Termination Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "auto_ended",
            "label": _("Auto Ended"),
            "fieldtype": "Check",
            "width": 100
        },
        {
            "fieldname": "volunteer_history_updated",
            "label": _("History Updated"),
            "fieldtype": "Check",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("from_date"):
        conditions.append("mtr.execution_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
        
    if filters.get("to_date"):
        conditions.append("mtr.execution_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
        
    if filters.get("chapter"):
        conditions.append("cbm.parent = %(chapter)s")
        values["chapter"] = filters["chapter"]
        
    if filters.get("termination_type"):
        conditions.append("mtr.termination_type = %(termination_type)s")
        values["termination_type"] = filters["termination_type"]

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Query to find board positions that were ended due to member termination
    query = f"""
        SELECT 
            mtr.name as termination_request,
            mtr.member_name,
            mtr.execution_date as termination_date,
            mtr.termination_type,
            cbm.parent as chapter,
            cbm.chapter_role as board_role,
            cbm.from_date as role_start_date,
            cbm.to_date as role_end_date,
            cbm.is_active,
            v.name as volunteer_id
        FROM `tabMembership Termination Request` mtr
        JOIN `tabMember` m ON mtr.member = m.name
        JOIN `tabVolunteer` v ON m.name = v.member
        JOIN `tabChapter Board Member` cbm ON v.name = cbm.volunteer
        {where_clause}
        AND mtr.status = 'Executed'
        AND mtr.end_board_positions = 1
        ORDER BY mtr.execution_date DESC, cbm.parent, cbm.chapter_role
    """
    
    results = frappe.db.sql(query, values, as_dict=True)
    
    data = []
    for row in results:
        # Check if the board position was automatically ended (role_end_date matches termination_date)
        auto_ended = (row.role_end_date == row.termination_date and not row.is_active)
        
        # Check if volunteer history was updated
        volunteer_history_updated = False
        if row.volunteer_id:
            # Check for completed assignment in volunteer history
            history_check = frappe.db.sql("""
                SELECT COUNT(*) as count
                FROM `tabVolunteer Assignment History` vah
                WHERE vah.parent = %s
                AND vah.reference_doctype = 'Chapter'
                AND vah.reference_name = %s
                AND vah.role = %s
                AND vah.status = 'Completed'
                AND vah.end_date = %s
            """, (row.volunteer_id, row.chapter, row.board_role, row.termination_date))
            
            volunteer_history_updated = history_check[0][0] > 0 if history_check else False
        
        data.append({
            "termination_request": row.termination_request,
            "member_name": row.member_name,
            "chapter": row.chapter,
            "board_role": row.board_role,
            "role_start_date": row.role_start_date,
            "role_end_date": row.role_end_date,
            "termination_date": row.termination_date,
            "termination_type": row.termination_type,
            "auto_ended": 1 if auto_ended else 0,
            "volunteer_history_updated": 1 if volunteer_history_updated else 0
        })
    
    return data


# Query Report Filters for Termination Compliance Report
# File: verenigingen/verenigingen/report/termination_compliance_report/termination_compliance_report.json

TERMINATION_COMPLIANCE_FILTERS = [
    {
        "fieldname": "from_date",
        "label": "From Date",
        "fieldtype": "Date",
        "default": "Last Month"
    },
    {
        "fieldname": "to_date", 
        "label": "To Date",
        "fieldtype": "Date",
        "default": "Today"
    },
    {
        "fieldname": "termination_type",
        "label": "Termination Type",
        "fieldtype": "Select",
        "options": "\nVoluntary\nNon-payment\nDeceased\nPolicy Violation\nDisciplinary Action\nExpulsion"
    },
    {
        "fieldname": "chapter",
        "label": "Chapter",
        "fieldtype": "Link",
        "options": "Chapter"
    },
    {
        "fieldname": "compliance_issues_only",
        "label": "Compliance Issues Only",
        "fieldtype": "Check",
        "default": 0
    }
]
