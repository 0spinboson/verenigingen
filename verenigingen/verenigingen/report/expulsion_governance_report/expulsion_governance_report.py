import frappe
from frappe import _
from frappe.utils import getdate, today, add_days, add_months, date_diff, flt
import json
from collections import defaultdict

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data, filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart, summary

def get_columns():
    return [
        {
            "fieldname": "expulsion_id",
            "label": _("Expulsion ID"),
            "fieldtype": "Link",
            "options": "Expulsion Report Entry",
            "width": 150
        },
        {
            "fieldname": "member_name",
            "label": _("Member"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "member_id",
            "label": _("Member ID"),
            "fieldtype": "Link",
            "options": "Member",
            "width": 120
        },
        {
            "fieldname": "expulsion_date",
            "label": _("Expulsion Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "expulsion_type",
            "label": _("Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "chapter_involved",
            "label": _("Chapter"),
            "fieldtype": "Link",
            "options": "Chapter",
            "width": 150
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "under_appeal",
            "label": _("Under Appeal"),
            "fieldtype": "Check",
            "width": 100
        },
        {
            "fieldname": "appeal_status",
            "label": _("Appeal Status"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "appeal_decision",
            "label": _("Appeal Decision"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "initiated_by",
            "label": _("Initiated By"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "approved_by",
            "label": _("Approved By"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "compliance_checked",
            "label": _("Compliance Verified"),
            "fieldtype": "Check",
            "width": 120
        },
        {
            "fieldname": "board_review_date",
            "label": _("Board Review Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "case_priority",
            "label": _("Priority"),
            "fieldtype": "Data",
            "width": 80
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    # Date filters
    if filters.get("from_date"):
        conditions.append("ere.expulsion_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]
    
    if filters.get("to_date"):
        conditions.append("ere.expulsion_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]
    
    # Other filters
    if filters.get("chapter"):
        conditions.append("ere.chapter_involved = %(chapter)s")
        values["chapter"] = filters["chapter"]
    
    if filters.get("expulsion_type"):
        conditions.append("ere.expulsion_type = %(expulsion_type)s")
        values["expulsion_type"] = filters["expulsion_type"]
    
    if filters.get("status"):
        conditions.append("ere.status = %(status)s")
        values["status"] = filters["status"]
    
    if filters.get("under_appeal_only"):
        conditions.append("ere.under_appeal = 1")
    
    if filters.get("pending_compliance_only"):
        conditions.append("ere.compliance_checked = 0")
    
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    
    # Main query joining expulsion entries with appeals
    query = f"""
        SELECT 
            ere.name as expulsion_id,
            ere.member_name,
            ere.member_id,
            ere.expulsion_date,
            ere.expulsion_type,
            ere.chapter_involved,
            ere.status,
            ere.under_appeal,
            ere.appeal_date,
            ere.initiated_by,
            ere.approved_by,
            ere.compliance_checked,
            ere.board_review_date,
            ere.case_priority,
            ere.reversal_date,
            ere.reversal_reason,
            tap.name as appeal_id,
            tap.appeal_status,
            tap.decision_outcome as appeal_decision,
            tap.decision_date,
            tap.assigned_reviewer,
            mtr.name as termination_request,
            mtr.disciplinary_documentation
        FROM `tabExpulsion Report Entry` ere
        LEFT JOIN `tabTermination Appeals Process` tap ON ere.name = tap.expulsion_entry
        LEFT JOIN `tabMembership Termination Request` mtr ON ere.member_id = mtr.member 
            AND mtr.termination_type = ere.expulsion_type
            AND mtr.status = 'Executed'
        {where_clause}
        ORDER BY ere.expulsion_date DESC
    """
    
    results = frappe.db.sql(query, values, as_dict=True)
    
    # Process data
    data = []
    processed_expulsions = set()
    
    for row in results:
        # Avoid duplicate entries if multiple appeals exist
        if row.expulsion_id in processed_expulsions and not row.appeal_id:
            continue
        
        processed_expulsions.add(row.expulsion_id)
        
        # Format appeal information
        appeal_status = ""
        appeal_decision = ""
        
        if row.appeal_id:
            appeal_status = row.appeal_status or "No Appeal"
            appeal_decision = row.appeal_decision or "-"
        elif row.under_appeal:
            appeal_status = "Appeal Filed"
            appeal_decision = "Pending"
        else:
            appeal_status = "No Appeal"
            appeal_decision = "-"
        
        data.append({
            "expulsion_id": row.expulsion_id,
            "member_name": row.member_name,
            "member_id": row.member_id,
            "expulsion_date": row.expulsion_date,
            "expulsion_type": row.expulsion_type,
            "chapter_involved": row.chapter_involved or "-",
            "status": row.status,
            "under_appeal": row.under_appeal,
            "appeal_status": appeal_status,
            "appeal_decision": appeal_decision,
            "initiated_by": row.initiated_by,
            "approved_by": row.approved_by,
            "compliance_checked": row.compliance_checked,
            "board_review_date": row.board_review_date,
            "case_priority": row.case_priority or "Medium",
            "has_documentation": bool(row.disciplinary_documentation),
            "reversal_date": row.reversal_date,
            "reversal_reason": row.reversal_reason
        })
    
    return data

def get_summary(data, filters):
    """Generate summary statistics for governance oversight"""
    
    total_expulsions = len(data)
    
    if total_expulsions == 0:
        return []
    
    # Status breakdown
    active_expulsions = len([r for r in data if r["status"] == "Active"])
    reversed_expulsions = len([r for r in data if r["status"] == "Reversed"])
    under_appeal = len([r for r in data if r["under_appeal"]])
    
    # Compliance tracking
    compliance_verified = len([r for r in data if r["compliance_checked"]])
    pending_compliance = total_expulsions - compliance_verified
    
    # Appeals analysis
    appeals_filed = len([r for r in data if r["appeal_status"] != "No Appeal"])
    appeals_upheld = len([r for r in data if r["appeal_decision"] in ["Upheld", "Partially Upheld"]])
    appeals_rejected = len([r for r in data if r["appeal_decision"] == "Rejected"])
    
    appeal_success_rate = (appeals_upheld / appeals_filed * 100) if appeals_filed > 0 else 0
    
    # Chapter analysis
    chapter_counts = defaultdict(int)
    for row in data:
        if row["chapter_involved"] and row["chapter_involved"] != "-":
            chapter_counts[row["chapter_involved"]] += 1
    
    most_active_chapter = max(chapter_counts.items(), key=lambda x: x[1])[0] if chapter_counts else "N/A"
    
    # Type analysis
    type_counts = defaultdict(int)
    for row in data:
        type_counts[row["expulsion_type"]] += 1
    
    # Priority analysis
    high_priority = len([r for r in data if r["case_priority"] in ["High", "Urgent"]])
    
    summary = [
        {
            "label": _("Total Expulsions"),
            "value": total_expulsions,
            "indicator": "blue"
        },
        {
            "label": _("Active Expulsions"),
            "value": active_expulsions,
            "indicator": "red"
        },
        {
            "label": _("Under Appeal"),
            "value": under_appeal,
            "indicator": "orange"
        },
        {
            "label": _("Appeal Success Rate"),
            "value": f"{appeal_success_rate:.1f}%",
            "indicator": "green" if appeal_success_rate > 30 else "red"
        },
        {
            "label": _("Compliance Rate"),
            "value": f"{(compliance_verified/total_expulsions*100):.1f}%",
            "indicator": "green" if compliance_verified/total_expulsions > 0.8 else "orange"
        },
        {
            "label": _("Pending Compliance"),
            "value": pending_compliance,
            "indicator": "red" if pending_compliance > 5 else "yellow"
        },
        {
            "label": _("Most Active Chapter"),
            "value": most_active_chapter,
            "indicator": "blue"
        },
        {
            "label": _("High Priority Cases"),
            "value": high_priority,
            "indicator": "red" if high_priority > 0 else "green"
        }
    ]
    
    return summary

def get_chart_data(data):
    """Generate chart data for governance dashboard"""
    
    # Prepare multiple charts
    charts = []
    
    # Chart 1: Expulsion Types Distribution
    type_counts = defaultdict(int)
    for row in data:
        type_counts[row["expulsion_type"]] += 1
    
    if type_counts:
        charts.append({
            "title": "Expulsions by Type",
            "data": {
                "labels": list(type_counts.keys()),
                "datasets": [{
                    "name": "Count",
                    "values": list(type_counts.values())
                }]
            },
            "type": "pie",
            "colors": ["#ff6384", "#ff9f40", "#ffcd56"]
        })
    
    # Chart 2: Monthly Trend
    monthly_counts = defaultdict(int)
    for row in data:
        if row["expulsion_date"]:
            month_key = row["expulsion_date"].strftime("%Y-%m")
            monthly_counts[month_key] += 1
    
    if monthly_counts:
        sorted_months = sorted(monthly_counts.keys())
        charts.append({
            "title": "Monthly Expulsion Trend",
            "data": {
                "labels": sorted_months,
                "datasets": [{
                    "name": "Expulsions",
                    "values": [monthly_counts[m] for m in sorted_months]
                }]
            },
            "type": "line",
            "colors": ["#4bc0c0"]
        })
    
    # Chart 3: Appeal Outcomes
    appeal_outcomes = {
        "Upheld": 0,
        "Rejected": 0,
        "Partially Upheld": 0,
        "Pending": 0,
        "No Appeal": 0
    }
    
    for row in data:
        if row["appeal_decision"] == "-" and row["appeal_status"] == "No Appeal":
            appeal_outcomes["No Appeal"] += 1
        elif row["appeal_decision"] == "Pending":
            appeal_outcomes["Pending"] += 1
        elif row["appeal_decision"] in appeal_outcomes:
            appeal_outcomes[row["appeal_decision"]] += 1
    
    # Return the main chart (type distribution)
    return charts[0] if charts else None

@frappe.whitelist()
def get_governance_compliance_details(filters=None):
    """Get detailed governance compliance information"""
    
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    _, data, _, _, _ = execute(filters)
    
    compliance_issues = []
    
    # Check for various compliance issues
    for row in data:
        issues = []
        
        # Missing documentation
        if not row.get("has_documentation"):
            issues.append({
                "type": "Missing Documentation",
                "severity": "High",
                "member": row["member_name"],
                "expulsion_date": row["expulsion_date"]
            })
        
        # Long-standing unverified cases
        if not row["compliance_checked"] and row["expulsion_date"]:
            days_since = date_diff(today(), row["expulsion_date"])
            if days_since > 30:
                issues.append({
                    "type": "Overdue Compliance Check",
                    "severity": "Medium",
                    "member": row["member_name"],
                    "days_overdue": days_since - 30
                })
        
        # High priority cases without board review
        if row["case_priority"] in ["High", "Urgent"] and not row["board_review_date"]:
            issues.append({
                "type": "High Priority Without Review",
                "severity": "High",
                "member": row["member_name"],
                "priority": row["case_priority"]
            })
        
        compliance_issues.extend(issues)
    
    # Group issues by type
    issues_by_type = defaultdict(list)
    for issue in compliance_issues:
        issues_by_type[issue["type"]].append(issue)
    
    return {
        "total_issues": len(compliance_issues),
        "issues_by_type": dict(issues_by_type),
        "high_severity_count": len([i for i in compliance_issues if i["severity"] == "High"]),
        "recommendations": generate_recommendations(data, compliance_issues)
    }

def generate_recommendations(data, compliance_issues):
    """Generate actionable recommendations based on governance data"""
    
    recommendations = []
    
    # Check documentation completeness
    missing_docs = len([i for i in compliance_issues if i["type"] == "Missing Documentation"])
    if missing_docs > 0:
        recommendations.append({
            "priority": "High",
            "category": "Documentation",
            "recommendation": f"Complete documentation for {missing_docs} expulsion case(s)",
            "action": "Review and upload all required disciplinary documentation"
        })
    
    # Check compliance verification backlog
    pending_compliance = len([r for r in data if not r["compliance_checked"]])
    if pending_compliance > 10:
        recommendations.append({
            "priority": "Medium",
            "category": "Compliance",
            "recommendation": f"Clear compliance verification backlog ({pending_compliance} cases)",
            "action": "Schedule board review sessions for pending cases"
        })

    # Check appeal success rate
    appeals_filed = len([r for r in data if r["appeal_status"] != "No Appeal"])
    appeals_upheld = len([r for r in data if r["appeal_decision"] in ["Upheld", "Partially Upheld"]])
    
    if appeals_filed > 0:
        success_rate = (appeals_upheld / appeals_filed) * 100
        if success_rate > 40:
            recommendations.append({
                "priority": "High",
                "category": "Process Review",
                "recommendation": f"Review expulsion procedures (Appeal success rate: {success_rate:.1f}%)",
                "action": "Analyze upheld appeals to identify process improvements"
            })
    
    # Check for chapter concentration
    chapter_counts = defaultdict(int)
    for row in data:
        if row["chapter_involved"] and row["chapter_involved"] != "-":
            chapter_counts[row["chapter_involved"]] += 1
    
    if chapter_counts:
        max_chapter_count = max(chapter_counts.values())
        total_expulsions = len(data)
        
        if total_expulsions > 5 and max_chapter_count / total_expulsions > 0.5:
            chapter_name = [k for k, v in chapter_counts.items() if v == max_chapter_count][0]
            recommendations.append({
                "priority": "Medium",
                "category": "Chapter Review",
                "recommendation": f"Investigate high expulsion rate in {chapter_name}",
                "action": "Conduct chapter-specific review and provide additional training"
            })
    
    # Check for reviewer workload
    reviewer_counts = defaultdict(int)
    for row in data:
        if row.get("assigned_reviewer"):
            reviewer_counts[row["assigned_reviewer"]] += 1
    
    if reviewer_counts and max(reviewer_counts.values()) > 10:
        recommendations.append({
            "priority": "Low",
            "category": "Workload",
            "recommendation": "Consider expanding reviewer pool",
            "action": "Train additional staff for appeal reviews"
        })
    
    return recommendations

@frappe.whitelist()
def export_governance_report(filters=None):
    """Export comprehensive governance report"""
    
    columns, data, _, _, summary = execute(filters)
    
    # Prepare export with additional governance metrics
    export_data = []
    
    # Add header section
    export_data.append({
        "expulsion_id": "GOVERNANCE REPORT",
        "member_name": f"Generated: {today()}",
        "expulsion_date": f"Period: {filters.get('from_date', 'All')} to {filters.get('to_date', 'Current')}"
    })
    
    export_data.append({})  # Empty row
    
    # Add summary section
    export_data.append({"expulsion_id": "SUMMARY METRICS"})
    for metric in summary:
        export_data.append({
            "expulsion_id": metric["label"],
            "member_name": metric["value"]
        })
    
    export_data.append({})  # Empty row
    
    # Add compliance analysis
    compliance_details = get_governance_compliance_details(filters)
    export_data.append({"expulsion_id": "COMPLIANCE ANALYSIS"})
    export_data.append({
        "expulsion_id": "Total Issues",
        "member_name": compliance_details["total_issues"]
    })
    export_data.append({
        "expulsion_id": "High Severity",
        "member_name": compliance_details["high_severity_count"]
    })
    
    export_data.append({})  # Empty row
    
    # Add recommendations
    export_data.append({"expulsion_id": "RECOMMENDATIONS"})
    for rec in compliance_details["recommendations"]:
        export_data.append({
            "expulsion_id": f"[{rec['priority']}] {rec['category']}",
            "member_name": rec["recommendation"],
            "expulsion_type": rec["action"]
        })
    
    export_data.append({})  # Empty row
    export_data.append({"expulsion_id": "DETAILED RECORDS"})
    
    # Add the actual data
    export_data.extend(data)
    
    return {
        "columns": columns,
        "data": export_data,
        "file_name": f"expulsion_governance_report_{today()}.xlsx"
    }

@frappe.whitelist()
def get_chapter_expulsion_analysis(chapter=None):
    """Get detailed expulsion analysis for a specific chapter"""
    
    filters = {"chapter": chapter} if chapter else {}
    _, data, _, _, _ = execute(filters)
    
    if not data:
        return {
            "error": "No data found for the specified chapter"
        }
    
    # Analyze patterns
    analysis = {
        "chapter": chapter or "All Chapters",
        "total_expulsions": len(data),
        "time_period_analyzed": "All available data",
        "patterns": []
    }
    
    # Type distribution
    type_counts = defaultdict(int)
    for row in data:
        type_counts[row["expulsion_type"]] += 1
    
    analysis["type_distribution"] = dict(type_counts)
    
    # Initiator analysis
    initiator_counts = defaultdict(int)
    for row in data:
        initiator_counts[row["initiated_by"]] += 1
    
    # Find if there's concentration
    if initiator_counts:
        max_initiator_count = max(initiator_counts.values())
        total = len(data)
        
        if total > 5 and max_initiator_count / total > 0.4:
            analysis["patterns"].append({
                "pattern": "Initiator Concentration",
                "description": f"Single initiator responsible for {(max_initiator_count/total*100):.1f}% of expulsions",
                "severity": "Medium"
            })
    
    # Time-based patterns
    monthly_counts = defaultdict(int)
    for row in data:
        if row["expulsion_date"]:
            month = row["expulsion_date"].month
            monthly_counts[month] += 1
    
    if monthly_counts:
        avg_monthly = sum(monthly_counts.values()) / 12
        for month, count in monthly_counts.items():
            if count > avg_monthly * 2:
                month_name = ["", "January", "February", "March", "April", "May", "June", 
                             "July", "August", "September", "October", "November", "December"][month]
                analysis["patterns"].append({
                    "pattern": "Seasonal Spike",
                    "description": f"High expulsion rate in {month_name} ({count} vs avg {avg_monthly:.1f})",
                    "severity": "Low"
                })
    
    # Appeal analysis
    appeals_filed = len([r for r in data if r["appeal_status"] != "No Appeal"])
    if len(data) > 0:
        appeal_rate = (appeals_filed / len(data)) * 100
        if appeal_rate > 50:
            analysis["patterns"].append({
                "pattern": "High Appeal Rate",
                "description": f"{appeal_rate:.1f}% of expulsions are appealed",
                "severity": "High"
            })
    
    analysis["initiator_distribution"] = dict(initiator_counts)
    analysis["monthly_distribution"] = dict(monthly_counts)
    
    return analysis

@frappe.whitelist()
def check_governance_compliance(expulsion_id):
    """Check compliance status for a specific expulsion"""
    
    expulsion = frappe.get_doc("Expulsion Report Entry", expulsion_id)
    
    compliance_checklist = {
        "documentation_complete": False,
        "proper_approval": False,
        "timeline_compliance": False,
        "appeal_handled": False,
        "board_review": False
    }
    
    issues = []
    
    # Check documentation
    termination_request = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": expulsion.member_id,
            "termination_type": expulsion.expulsion_type,
            "status": "Executed"
        },
        fields=["disciplinary_documentation"],
        limit=1
    )
    
    if termination_request and termination_request[0].disciplinary_documentation:
        compliance_checklist["documentation_complete"] = True
    else:
        issues.append("Missing disciplinary documentation")
    
    # Check approval
    if expulsion.approved_by and expulsion.initiated_by != expulsion.approved_by:
        compliance_checklist["proper_approval"] = True
    else:
        issues.append("Missing secondary approval or self-approval detected")
    
    # Check timeline (expulsion should be processed within reasonable time)
    # This is a placeholder - actual timeline requirements should be configured
    compliance_checklist["timeline_compliance"] = True
    
    # Check appeal handling
    if expulsion.under_appeal:
        # Check if appeal is being processed
        appeal = frappe.get_all(
            "Termination Appeals Process",
            filters={"expulsion_entry": expulsion_id},
            fields=["appeal_status"],
            limit=1
        )
        
        if appeal and appeal[0].appeal_status not in ["Draft", "Submitted"]:
            compliance_checklist["appeal_handled"] = True
        else:
            issues.append("Appeal not being processed")
    else:
        compliance_checklist["appeal_handled"] = True
    
    # Check board review
    if expulsion.board_review_date or expulsion.compliance_checked:
        compliance_checklist["board_review"] = True
    else:
        issues.append("Pending board review")
    
    # Calculate compliance score
    score = sum(1 for v in compliance_checklist.values() if v)
    total = len(compliance_checklist)
    compliance_rate = (score / total) * 100
    
    return {
        "compliance_rate": compliance_rate,
        "checklist": compliance_checklist,
        "issues": issues,
        "status": "Compliant" if compliance_rate >= 80 else "Non-Compliant"
    }
