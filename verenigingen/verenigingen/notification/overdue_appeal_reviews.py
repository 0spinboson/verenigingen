# Notification Configuration: Overdue Appeal Reviews
# File: verenigingen/verenigingen/notification/overdue_appeal_reviews.py

import frappe
from frappe import _
from frappe.utils import today, add_days

@frappe.whitelist()
def send_overdue_appeal_notifications():
    """
    Send notifications for overdue appeal reviews
    This should be called via a scheduled job
    """
    
    # Get overdue appeals (deadline passed)
    overdue_appeals = frappe.get_all(
        "Termination Appeals Process",
        filters={
            "review_deadline": ["<", today()],
            "appeal_status": ["in", ["Under Review", "Pending Decision"]]
        },
        fields=["name", "appeal_reference", "member_name", "assigned_reviewer", 
               "review_deadline", "urgency_level", "appellant_email"]
    )
    
    # Group by reviewer
    reviewer_appeals = {}
    for appeal in overdue_appeals:
        reviewer = appeal.assigned_reviewer
        if reviewer not in reviewer_appeals:
            reviewer_appeals[reviewer] = []
        reviewer_appeals[reviewer].append(appeal)
    
    # Send notifications to reviewers
    for reviewer, appeals in reviewer_appeals.items():
        if not reviewer:
            continue
            
        try:
            send_overdue_notification_to_reviewer(reviewer, appeals)
        except Exception as e:
            frappe.log_error(
                message=f"Error sending overdue notification to {reviewer}: {str(e)}",
                title="Overdue Appeal Notification Error"
            )
    
    # Also notify governance team about critical overdue appeals
    critical_overdue = [a for a in overdue_appeals if a.urgency_level in ["High", "Urgent"]]
    if critical_overdue:
        send_critical_overdue_notification(critical_overdue)
    
    return {
        "total_overdue": len(overdue_appeals),
        "reviewers_notified": len(reviewer_appeals),
        "critical_overdue": len(critical_overdue)
    }

def send_overdue_notification_to_reviewer(reviewer, appeals):
    """Send overdue notification to a specific reviewer"""
    
    reviewer_email = frappe.db.get_value("User", reviewer, "email")
    if not reviewer_email:
        return
    
    reviewer_name = frappe.db.get_value("User", reviewer, "full_name") or reviewer
    
    appeals_list = ""
    for appeal in appeals:
        days_overdue = (frappe.utils.getdate(today()) - frappe.utils.getdate(appeal.review_deadline)).days
        appeals_list += f"""
        <tr>
            <td><a href="{frappe.utils.get_url()}/app/termination-appeals-process/{appeal.name}">{appeal.appeal_reference}</a></td>
            <td>{appeal.member_name}</td>
            <td>{frappe.utils.format_date(appeal.review_deadline)}</td>
            <td style="color: #dc3545;">{days_overdue} days</td>
            <td><span style="color: {'#dc3545' if appeal.urgency_level in ['High', 'Urgent'] else '#6c757d'}">{appeal.urgency_level}</span></td>
        </tr>
        """
    
    subject = f"⚠️ Overdue Appeal Reviews - {len(appeals)} appeals require attention"
    
    message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #dc3545;">
            <h2 style="color: #721c24; margin: 0;">⚠️ Overdue Appeal Reviews</h2>
            <p style="color: #6c757d; margin: 5px 0 0 0;">Action Required</p>
        </div>
        
        <p>Dear {reviewer_name},</p>
        
        <p>You have <strong>{len(appeals)}</strong> appeal review(s) that are past their deadline:</p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Appeal Reference</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Member</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Deadline</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Days Overdue</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Urgency</th>
                </tr>
            </thead>
            <tbody>
                {appeals_list}
            </tbody>
        </table>
        
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
            <p style="margin: 0;"><strong>Action Required:</strong> Please review and make decisions on these appeals as soon as possible to maintain compliance with our appeals process.</p>
        </div>
        
        <div style="text-align: center; margin: 20px 0;">
            <a href="{frappe.utils.get_url()}/app/termination-appeals-process" 
               style="background-color: #dc3545; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Review Appeals
            </a>
        </div>
        
        <p>Best regards,<br>Governance System</p>
    </div>
    """
    
    frappe.sendmail(
        recipients=[reviewer_email],
        subject=subject,
        message=message,
        header=["Overdue Appeal Reviews", "red"]
    )

def send_critical_overdue_notification(critical_appeals):
    """Send notification about critical overdue appeals to governance team"""
    
    # Get governance team emails (Association Managers)
    governance_users = frappe.get_all(
        "Has Role",
        filters={"role": "Association Manager"},
        fields=["parent"]
    )
    
    governance_emails = []
    for user_role in governance_users:
        email = frappe.db.get_value("User", user_role.parent, "email")
        if email and email != "Administrator":
            governance_emails.append(email)
    
    if not governance_emails:
        return
    
    appeals_list = ""
    for appeal in critical_appeals:
        days_overdue = (frappe.utils.getdate(today()) - frappe.utils.getdate(appeal.review_deadline)).days
        appeals_list += f"""
        <tr>
            <td>{appeal.appeal_reference}</td>
            <td>{appeal.member_name}</td>
            <td>{appeal.assigned_reviewer or 'Unassigned'}</td>
            <td>{days_overdue} days</td>
            <td>{appeal.urgency_level}</td>
        </tr>
        """
    
    subject = f"🚨 Critical Overdue Appeals - {len(critical_appeals)} high-priority appeals"
    
    message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #dc3545;">
            <h2 style="color: #721c24; margin: 0;">🚨 Critical Overdue Appeals</h2>
            <p style="color: #6c757d; margin: 5px 0 0 0;">Governance Oversight Required</p>
        </div>
        
        <p>Dear Governance Team,</p>
        
        <p>The following <strong>high-priority appeals</strong> are overdue for review:</p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Appeal Reference</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Member</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Assigned Reviewer</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Days Overdue</th>
                    <th style="padding: 10px; border: 1px solid #dee2e6; text-align: left;">Urgency</th>
                </tr>
            </thead>
            <tbody>
                {appeals_list}
            </tbody>
        </table>
        
        <div style="background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545;">
            <p style="margin: 0;"><strong>Governance Action Required:</strong> These critical appeals may require reassignment or escalation to ensure timely resolution.</p>
        </div>
        
        <p>Best regards,<br>Governance System</p>
    </div>
    """
    
    frappe.sendmail(
        recipients=governance_emails,
        subject=subject,
        message=message,
        header=["Critical Overdue Appeals", "red"]
    )

# Custom Field Definitions
# File: verenigingen/verenigingen/custom_fields.py

def create_custom_fields():
    """Create custom fields for the termination system"""
    
    # Add fields to Membership Termination Request
    custom_fields = {
        "Membership Termination Request": [
            {
                "fieldname": "cancel_sepa_mandates",
                "fieldtype": "Check",
                "label": "Cancel SEPA Mandates",
                "insert_after": "termination_reason",
                "default": "0",
                "description": "Automatically cancel all active SEPA mandates"
            },
            {
                "fieldname": "end_board_positions", 
                "fieldtype": "Check",
                "label": "End Board Positions",
                "insert_after": "cancel_sepa_mandates",
                "default": "0",
                "description": "Automatically end all board and committee positions"
            },
            {
                "fieldname": "cancel_memberships",
                "fieldtype": "Check", 
                "label": "Cancel Active Memberships",
                "insert_after": "end_board_positions",
                "default": "0",
                "description": "Cancel all active memberships"
            },
            {
                "fieldname": "process_invoices",
                "fieldtype": "Check",
                "label": "Process Outstanding Invoices", 
                "insert_after": "cancel_memberships",
                "default": "0",
                "description": "Update and process outstanding invoices"
            },
            {
                "fieldname": "cancel_subscriptions",
                "fieldtype": "Check",
                "label": "Cancel Subscriptions",
                "insert_after": "process_invoices", 
                "default": "0",
                "description": "Cancel all active subscriptions"
            },
            {
                "fieldname": "system_actions_section",
                "fieldtype": "Section Break",
                "label": "System Actions",
                "insert_after": "disciplinary_documentation",
                "collapsible": 1
            },
            {
                "fieldname": "action_log",
                "fieldtype": "Code",
                "label": "Action Log",
                "insert_after": "cancel_subscriptions",
                "read_only": 1,
                "description": "Log of all system actions performed during termination"
            }
        ]
    }
    
    # Create the custom fields
    for doctype, fields in custom_fields.items():
        for field in fields:
            if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
                custom_field = frappe.get_doc({
                    "doctype": "Custom Field",
                    "dt": doctype,
                    **field
                })
                custom_field.insert()

# Workflow State Management
# File: verenigingen/verenigingen/workflow_states.py

def setup_termination_workflow():
    """Setup workflow states for termination process"""
    
    # Create workflow for Membership Termination Request
    if not frappe.db.exists("Workflow", "Membership Termination Workflow"):
        workflow = frappe.get_doc({
            "doctype": "Workflow",
            "workflow_name": "Membership Termination Workflow",
            "document_type": "Membership Termination Request",
            "is_active": 1,
            "send_email_alert": 1,
            "workflow_state_field": "workflow_state",
            "states": [
                {
                    "state": "Draft",
                    "doc_status": "0", 
                    "allow_edit": "System Manager,Association Manager",
                    "is_optional_state": 1
                },
                {
                    "state": "Pending Approval",
                    "doc_status": "0",
                    "allow_edit": "System Manager",
                    "message": "Awaiting secondary approval for disciplinary termination"
                },
                {
                    "state": "Approved", 
                    "doc_status": "0",
                    "allow_edit": "System Manager,Association Manager",
                    "message": "Approved and ready for execution"
                },
                {
                    "state": "Rejected",
                    "doc_status": "0", 
                    "allow_edit": "System Manager",
                    "message": "Termination request rejected"
                },
                {
                    "state": "Executed",
                    "doc_status": "1",
                    "allow_edit": "System Manager",
                    "message": "Termination has been executed"
                }
            ],
            "transitions": [
                {
                    "state": "Draft",
                    "action": "Submit for Approval", 
                    "next_state": "Pending Approval",
                    "allowed": "System Manager,Association Manager",
                    "condition": "doc.termination_type in ['Policy Violation', 'Disciplinary Action', 'Expulsion']"
                },
                {
                    "state": "Draft",
                    "action": "Execute", 
                    "next_state": "Executed",
                    "allowed": "System Manager,Association Manager",
                    "condition": "doc.termination_type not in ['Policy Violation', 'Disciplinary Action', 'Expulsion']"
                },
                {
                    "state": "Pending Approval",
                    "action": "Approve",
                    "next_state": "Approved", 
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Pending Approval", 
                    "action": "Reject",
                    "next_state": "Rejected",
                    "allowed": "System Manager,Association Manager"
                },
                {
                    "state": "Approved",
                    "action": "Execute",
                    "next_state": "Executed",
                    "allowed": "System Manager,Association Manager"
                }
            ]
        })
        workflow.insert()

# System Validation Functions
# File: verenigingen/verenigingen/validations.py

def validate_termination_request(doc, method):
    """Validation function for termination requests"""
    
    # Validate that member exists and is active
    if not frappe.db.exists("Member", doc.member):
        frappe.throw(_("Member {0} does not exist").format(doc.member))
    
    member_status = frappe.db.get_value("Member", doc.member, "status")
    if member_status in ["Terminated", "Expired", "Banned", "Deceased"]:
        frappe.throw(_("Cannot terminate member with status: {0}").format(member_status))
    
    # Validate disciplinary terminations
    disciplinary_types = ["Policy Violation", "Disciplinary Action", "Expulsion"]
    if doc.termination_type in disciplinary_types:
        
        # Require documentation
        if not doc.disciplinary_documentation:
            frappe.throw(_("Documentation is required for disciplinary terminations"))
        
        # Require secondary approver
        if not doc.secondary_approver and doc.status == "Pending Approval":
            frappe.throw(_("Secondary approver is required for disciplinary terminations"))
        
        # Validate approver permissions
        if doc.secondary_approver:
            approver_roles = frappe.get_roles(doc.secondary_approver)
            if not any(role in ["System Manager", "Association Manager"] for role in approver_roles):
                # Check if national board member
                settings = frappe.get_single("Verenigingen Settings")
                if settings.national_board_chapter:
                    is_national_board = frappe.db.sql("""
                        SELECT COUNT(*) 
                        FROM `tabMember` m
                        JOIN `tabVolunteer` v ON m.name = v.member
                        JOIN `tabChapter Board Member` cbm ON v.name = cbm.volunteer
                        WHERE m.user = %s AND cbm.parent = %s AND cbm.is_active = 1
                    """, (doc.secondary_approver, settings.national_board_chapter))
                    
                    if not (is_national_board and is_national_board[0][0] > 0):
                        frappe.throw(_("Secondary approver must be Association Manager or National Board Member"))

def validate_appeal_filing(doc, method):
    """Validation function for appeal filing"""
    
    # Validate appeal deadline
    if doc.termination_request:
        termination = frappe.get_doc("Membership Termination Request", doc.termination_request)
        if not termination.execution_date:
            frappe.throw(_("Cannot file appeal - termination has not been executed"))
        
        # Check 30-day deadline
        deadline = frappe.utils.add_days(termination.execution_date, 30)
        if frappe.utils.getdate(doc.appeal_date) > frappe.utils.getdate(deadline):
            frappe.throw(_("Appeal deadline has passed. Appeals must be filed within 30 days of termination."))
    
    # Validate appellant authority
    if doc.appellant_relationship == "Self":
        # Verify appellant is the member or their user
        member_user = frappe.db.get_value("Member", doc.member, "user")
        member_email = frappe.db.get_value("Member", doc.member, "email")
        
        if not (doc.appellant_email == member_email or 
               (member_user and frappe.db.get_value("User", member_user, "email") == doc.appellant_email)):
            frappe.throw(_("Appellant email must match member's email for self-filed appeals"))

# Scheduled Jobs Configuration
# File: verenigingen/verenigingen/hooks.py (addition to existing hooks)

SCHEDULER_EVENTS = {
    "daily": [
        "verenigingen.verenigingen.notification.overdue_appeal_reviews.send_overdue_appeal_notifications"
    ],
    "weekly": [
        "verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.generate_governance_compliance_report"
    ]
}
