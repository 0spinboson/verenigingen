import frappe
from frappe import _
from frappe.utils import getdate, today, add_days

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
        
        # Require secondary approver for pending approval status
        if not doc.secondary_approver and doc.status == "Pending Approval":
            frappe.throw(_("Secondary approver is required for disciplinary terminations"))
        
        # Validate approver permissions
        if doc.secondary_approver:
            validate_approver_permissions(doc.secondary_approver)
    
    # Validate dates
    if doc.termination_date and getdate(doc.termination_date) < getdate(doc.request_date):
        frappe.throw(_("Termination date cannot be before request date"))
    
    if doc.grace_period_end and doc.termination_date:
        if getdate(doc.grace_period_end) < getdate(doc.termination_date):
            frappe.throw(_("Grace period end cannot be before termination date"))

def validate_approver_permissions(approver_user):
    """Validate that the approver has the required permissions"""
    approver_roles = frappe.get_roles(approver_user)
    
    if not any(role in ["System Manager", "Association Manager"] for role in approver_roles):
        # Check if national board member
        settings = frappe.get_single("Verenigingen Settings")
        if settings and settings.national_board_chapter:
            is_national_board = frappe.db.sql("""
                SELECT COUNT(*) 
                FROM `tabMember` m
                JOIN `tabVolunteer` v ON m.name = v.member
                JOIN `tabChapter Board Member` cbm ON v.name = cbm.volunteer
                WHERE m.user = %s AND cbm.parent = %s AND cbm.is_active = 1
            """, (approver_user, settings.national_board_chapter))
            
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
        deadline = add_days(termination.execution_date, 30)
        if getdate(doc.appeal_date) > getdate(deadline):
            frappe.throw(_("Appeal deadline has passed. Appeals must be filed within 30 days of termination."))
    
    # Validate appellant authority
    if doc.appellant_relationship == "Self":
        # Verify appellant is the member or their user
        member_user = frappe.db.get_value("Member", doc.member, "user")
        member_email = frappe.db.get_value("Member", doc.member, "email")
        
        if not (doc.appellant_email == member_email or 
               (member_user and frappe.db.get_value("User", member_user, "email") == doc.appellant_email)):
            frappe.throw(_("Appellant email must match member's email for self-filed appeals"))
