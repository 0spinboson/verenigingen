# File: verenigingen/verenigingen/report/governance_compliance_report/governance_compliance_report.py

import frappe
from frappe import _
from frappe.utils import getdate, today, add_days, add_months, date_diff
import json
from datetime import datetime

def execute(filters=None):
    """Execute the governance compliance report"""
    
    # Calculate date range based on period selection
    end_date = getdate(today())
    
    if filters.get("report_period") == "Last Month":
        start_date = add_months(end_date, -1)
    elif filters.get("report_period") == "Last Quarter":
        start_date = add_months(end_date, -3)
    elif filters.get("report_period") == "Last 6 Months":
        start_date = add_months(end_date, -6)
    elif filters.get("report_period") == "Last Year":
        start_date = add_months(end_date, -12)
    elif filters.get("report_period") == "Custom":
        start_date = getdate(filters.get("from_date")) if filters.get("from_date") else add_months(end_date, -3)
        end_date = getdate(filters.get("to_date")) if filters.get("to_date") else end_date
    else:
        start_date = add_months(end_date, -3)  # Default to last quarter
    
    # Generate comprehensive compliance report
    report_data = generate_governance_compliance_report(
        start_date, 
        end_date, 
        filters.get("include_appeals", True),
        filters.get("include_expulsions", True)
    )
    
    # Return empty columns as this is primarily a summary report
    columns = []
    data = []
    
    # Format as chart data and summary
    chart = create_compliance_chart(report_data)
    summary = create_compliance_summary(report_data)
    
    return columns, data, None, chart, summary

def generate_governance_compliance_report(start_date, end_date, include_appeals=True, include_expulsions=True):
    """Generate comprehensive governance compliance report"""
    
    report = {
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "days": date_diff(end_date, start_date)
        },
        "terminations": get_termination_compliance_data(start_date, end_date),
        "appeals": get_appeals_compliance_data(start_date, end_date) if include_appeals else None,
        "expulsions": get_expulsion_compliance_data(start_date, end_date) if include_expulsions else None,
        "compliance_score": 0,
        "risk_level": "LOW",
        "issues": [],
        "recommendations": []
    }
    
    # Calculate overall compliance score
    report["compliance_score"] = calculate_compliance_score(report)
    report["risk_level"] = determine_risk_level(report["compliance_score"], report)
    report["issues"] = identify_compliance_issues(report)
    report["recommendations"] = generate_compliance_recommendations(report)
    
    return report

def get_termination_compliance_data(start_date, end_date):
    """Get termination compliance data"""
    
    terminations = frappe.db.sql("""
        SELECT 
            name, member, member_name, termination_type, status, request_date,
            execution_date, requires_secondary_approval, approved_by, approval_date,
            disciplinary_documentation, secondary_approver
        FROM `tabMembership Termination Request`
        WHERE request_date BETWEEN %s AND %s
        ORDER BY request_date DESC
    """, (start_date, end_date), as_dict=True)
    
    compliance_data = {
        "total": len(terminations),
        "by_status": {},
        "by_type": {},
        "disciplinary": 0,
        "pending_overdue": 0,
        "missing_documentation": 0,
        "missing_approval": 0,
        "processing_times": [],
        "compliance_issues": []
    }
    
    disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
    
    for termination in terminations:
        # Status breakdown
        status = termination.status
        compliance_data["by_status"][status] = compliance_data["by_status"].get(status, 0) + 1
        
        # Type breakdown
        t_type = termination.termination_type
        compliance_data["by_type"][t_type] = compliance_data["by_type"].get(t_type, 0) + 1
        
        # Disciplinary analysis
        if t_type in disciplinary_types:
            compliance_data["disciplinary"] += 1
            
            # Check for missing documentation
            if not termination.disciplinary_documentation:
                compliance_data["missing_documentation"] += 1
                compliance_data["compliance_issues"].append({
                    "type": "Missing Documentation",
                    "request": termination.name,
                    "severity": "High"
                })
            
            # Check for missing secondary approval
            if termination.requires_secondary_approval and not termination.approved_by:
                compliance_data["missing_approval"] += 1
                compliance_data["compliance_issues"].append({
                    "type": "Missing Secondary Approval",
                    "request": termination.name,
                    "severity": "Critical"
                })
        
        # Check for overdue pending requests
        if status in ['Pending Approval', 'Approved'] and termination.request_date:
            days_pending = date_diff(today(), termination.request_date)
            if days_pending > 7:  # Overdue after 7 days
                compliance_data["pending_overdue"] += 1
                compliance_data["compliance_issues"].append({
                    "type": "Overdue Processing",
                    "request": termination.name,
                    "days": days_pending,
                    "severity": "Medium"
                })
        
        # Calculate processing times for executed requests
        if status == 'Executed' and termination.execution_date and termination.request_date:
            processing_days = date_diff(termination.execution_date, termination.request_date)
            compliance_data["processing_times"].append(processing_days)
    
    # Calculate average processing time
    if compliance_data["processing_times"]:
        compliance_data["avg_processing_time"] = sum(compliance_data["processing_times"]) / len(compliance_data["processing_times"])
    else:
        compliance_data["avg_processing_time"] = 0
    
    return compliance_data

def get_appeals_compliance_data(start_date, end_date):
    """Get appeals compliance data"""
    
    appeals = frappe.db.sql("""
        SELECT 
            name, member_name, appeal_status, appeal_date, review_deadline,
            assigned_reviewer, decision_date, decision_outcome, implementation_status
        FROM `tabTermination Appeals Process`
        WHERE appeal_date BETWEEN %s AND %s
        ORDER BY appeal_date DESC
    """, (start_date, end_date), as_dict=True)
    
    compliance_data = {
        "total": len(appeals),
        "by_status": {},
        "overdue_reviews": 0,
        "avg_processing_time": 0,
        "success_rate": 0,
        "implementation_pending": 0,
        "compliance_issues": []
    }
    
    processing_times = []
    successful_appeals = 0
    decided_appeals = 0
    
    for appeal in appeals:
        # Status breakdown
        status = appeal.appeal_status
        compliance_data["by_status"][status] = compliance_data["by_status"].get(status, 0) + 1
        
        # Check for overdue reviews
        if status in ['Under Review', 'Pending Decision'] and appeal.review_deadline:
            if getdate(appeal.review_deadline) < getdate(today()):
                compliance_data["overdue_reviews"] += 1
                compliance_data["compliance_issues"].append({
                    "type": "Overdue Appeal Review",
                    "appeal": appeal.name,
                    "overdue_days": date_diff(today(), appeal.review_deadline),
                    "severity": "High"
                })
        
        # Calculate processing times and success rates
        if appeal.decision_date and appeal.appeal_date:
            processing_days = date_diff(appeal.decision_date, appeal.appeal_date)
            processing_times.append(processing_days)
            decided_appeals += 1
            
            if appeal.decision_outcome in ['Upheld', 'Partially Upheld']:
                successful_appeals += 1
        
        # Check for pending implementations
        if appeal.implementation_status == 'Pending':
            compliance_data["implementation_pending"] += 1
    
    # Calculate averages
    if processing_times:
        compliance_data["avg_processing_time"] = sum(processing_times) / len(processing_times)
    
    if decided_appeals > 0:
        compliance_data["success_rate"] = (successful_appeals / decided_appeals) * 100
    
    return compliance_data

def get_expulsion_compliance_data(start_date, end_date):
    """Get expulsion compliance data"""
    
    expulsions = frappe.db.sql("""
        SELECT 
            name, member_name, expulsion_type, expulsion_date, status,
            under_appeal, initiated_by, approved_by, documentation
        FROM `tabExpulsion Report Entry`
        WHERE expulsion_date BETWEEN %s AND %s
        ORDER BY expulsion_date DESC
    """, (start_date, end_date), as_dict=True)
    
    compliance_data = {
        "total": len(expulsions),
        "by_type": {},
        "by_status": {},
        "under_appeal": 0,
        "missing_documentation": 0,
        "compliance_issues": []
    }
    
    for expulsion in expulsions:
        # Type breakdown
        e_type = expulsion.expulsion_type
        compliance_data["by_type"][e_type] = compliance_data["by_type"].get(e_type, 0) + 1
        
        # Status breakdown
        status = expulsion.status
        compliance_data["by_status"][status] = compliance_data["by_status"].get(status, 0) + 1
        
        # Appeals tracking
        if expulsion.under_appeal:
            compliance_data["under_appeal"] += 1
        
        # Documentation check
        if not expulsion.documentation:
            compliance_data["missing_documentation"] += 1
            compliance_data["compliance_issues"].append({
                "type": "Missing Expulsion Documentation",
                "expulsion": expulsion.name,
                "severity": "High"
            })
    
    return compliance_data

def calculate_compliance_score(report):
    """Calculate overall compliance score (0-100)"""
    
    score = 100
    terminations = report["terminations"]
    appeals = report["appeals"]
    
    # Deduct points for compliance issues
    if terminations["total"] > 0:
        # Missing documentation (major issue)
        if terminations["missing_documentation"] > 0:
            score -= min(30, (terminations["missing_documentation"] / terminations["total"]) * 50)
        
        # Missing approvals (critical issue)
        if terminations["missing_approval"] > 0:
            score -= min(40, (terminations["missing_approval"] / terminations["total"]) * 60)
        
        # Overdue processing (medium issue)
        if terminations["pending_overdue"] > 0:
            score -= min(20, (terminations["pending_overdue"] / terminations["total"]) * 30)
    
    # Appeals compliance
    if appeals and appeals["total"] > 0:
        # Overdue reviews (major issue)
        if appeals["overdue_reviews"] > 0:
            score -= min(25, (appeals["overdue_reviews"] / appeals["total"]) * 40)
        
        # Long processing times (medium issue)
        if appeals["avg_processing_time"] > 45:  # More than 45 days
            score -= 15
    
    return max(0, round(score))

def determine_risk_level(compliance_score, report):
    """Determine risk level based on compliance score and issues"""
    
    critical_issues = len([i for issues in [
        report["terminations"]["compliance_issues"],
        report["appeals"]["compliance_issues"] if report["appeals"] else [],
        report["expulsions"]["compliance_issues"] if report["expulsions"] else []
    ] for i in issues if i.get("severity") == "Critical"])
    
    if critical_issues > 0 or compliance_score < 60:
        return "HIGH"
    elif compliance_score < 80:
        return "MEDIUM"
    else:
        return "LOW"

def identify_compliance_issues(report):
    """Identify and consolidate compliance issues"""
    
    all_issues = []
    
    # Collect issues from all sections
    if report["terminations"]["compliance_issues"]:
        all_issues.extend(report["terminations"]["compliance_issues"])
    
    if report["appeals"] and report["appeals"]["compliance_issues"]:
        all_issues.extend(report["appeals"]["compliance_issues"])
    
    if report["expulsions"] and report["expulsions"]["compliance_issues"]:
        all_issues.extend(report["expulsions"]["compliance_issues"])
    
    # Sort by severity
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "Low"), 3))
    
    return all_issues

def generate_compliance_recommendations(report):
    """Generate actionable recommendations"""
    
    recommendations = []
    terminations = report["terminations"]
    appeals = report["appeals"]
    
    # Termination recommendations
    if terminations["missing_documentation"] > 0:
        recommendations.append({
            "priority": "High",
            "category": "Documentation",
            "recommendation": f"Complete documentation for {terminations['missing_documentation']} disciplinary termination(s)",
            "action": "Review and update all disciplinary termination records with proper documentation"
        })
    
    if terminations["missing_approval"] > 0:
        recommendations.append({
            "priority": "Critical", 
            "category": "Approval Process",
            "recommendation": f"Obtain secondary approval for {terminations['missing_approval']} disciplinary termination(s)",
            "action": "Ensure all disciplinary terminations have proper secondary approval"
        })
    
    if terminations["pending_overdue"] > 0:
        recommendations.append({
            "priority": "Medium",
            "category": "Processing Efficiency",
            "recommendation": f"Process {terminations['pending_overdue']} overdue termination request(s)",
            "action": "Review and expedite processing of pending termination requests"
        })
    
    # Appeals recommendations
    if appeals and appeals["overdue_reviews"] > 0:
        recommendations.append({
            "priority": "High",
            "category": "Appeals Processing",
            "recommendation": f"Complete {appeals['overdue_reviews']} overdue appeal review(s)",
            "action": "Prioritize overdue appeal reviews to meet statutory deadlines"
        })
    
    if appeals and appeals["avg_processing_time"] > 45:
        recommendations.append({
            "priority": "Medium",
            "category": "Appeals Efficiency", 
            "recommendation": f"Reduce average appeal processing time from {appeals['avg_processing_time']:.1f} days",
            "action": "Streamline appeal review process and assign dedicated reviewers"
        })
    
    return recommendations

def create_compliance_chart(report_data):
    """Create chart for compliance dashboard"""
    
    return {
        "data": {
            "labels": ["Compliant", "Issues"],
            "datasets": [
                {
                    "name": "Compliance Score",
                    "values": [report_data["compliance_score"], 100 - report_data["compliance_score"]]
                }
            ]
        },
        "type": "donut",
        "colors": ["#28a745", "#dc3545"]
    }

def create_compliance_summary(report_data):
    """Create summary cards for the report"""
    
    summary = [
        {
            "label": _("Compliance Score"),
            "value": f"{report_data['compliance_score']}/100",
            "indicator": "green" if report_data["compliance_score"] >= 80 else "orange" if report_data["compliance_score"] >= 60 else "red"
        },
        {
            "label": _("Risk Level"),
            "value": report_data["risk_level"],
            "indicator": "red" if report_data["risk_level"] == "HIGH" else "orange" if report_data["risk_level"] == "MEDIUM" else "green"
        },
        {
            "label": _("Total Terminations"),
            "value": report_data["terminations"]["total"],
            "indicator": "blue"
        },
        {
            "label": _("Compliance Issues"),
            "value": len(report_data["issues"]),
            "indicator": "red" if len(report_data["issues"]) > 0 else "green"
        }
    ]
    
    if report_data["appeals"]:
        summary.append({
            "label": _("Appeals Filed"),
            "value": report_data["appeals"]["total"],
            "indicator": "blue"
        })
        
        summary.append({
            "label": _("Appeal Success Rate"),
            "value": f"{report_data['appeals']['success_rate']:.1f}%",
            "indicator": "green" if report_data["appeals"]["success_rate"] > 30 else "orange"
        })
    
    return summary

@frappe.whitelist()
def generate_governance_compliance_report_api(filters=None):
    """API endpoint for generating governance compliance report"""
    
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    # Use current date as default end date
    end_date = getdate(today())
    start_date = add_months(end_date, -3)  # Default to last quarter
    
    if filters:
        if filters.get("from_date"):
            start_date = getdate(filters["from_date"])
        if filters.get("to_date"):
            end_date = getdate(filters["to_date"])
    
    return generate_governance_compliance_report(
        start_date,
        end_date,
        filters.get("include_appeals", True) if filters else True,
        filters.get("include_expulsions", True) if filters else True
    )
