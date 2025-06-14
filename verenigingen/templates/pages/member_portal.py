"""
Member Portal Landing Page
Provides an overview and easy access to all member portal pages
"""

import frappe
from frappe import _
from frappe.utils import getdate, today, format_datetime

def get_context(context):
    """Get context for member portal landing page"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access the member portal"), frappe.PermissionError)
    
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("Member Portal")
    
    # Get member record
    member = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member:
        frappe.throw(_("No member record found for your account"), frappe.DoesNotExistError)
    
    context.member = frappe.get_doc("Member", member)
    
    # Get active membership
    membership = frappe.db.get_value(
        "Membership",
        {
            "member": member,
            "status": "Active",
            "docstatus": 1
        },
        ["name", "membership_type", "start_date", "renewal_date", "status", "auto_renew"],
        as_dict=True
    )
    context.membership = membership
    
    # Get volunteer record if exists
    volunteer = frappe.db.get_value("Volunteer", {"member": member})
    if volunteer:
        context.volunteer = frappe.get_doc("Volunteer", volunteer)
        
        # Calculate volunteer hours this year
        try:
            year_start = getdate(today()).replace(month=1, day=1)
            volunteer_hours = frappe.db.sql("""
                SELECT SUM(actual_hours) as total_hours
                FROM `tabVolunteer Assignment`
                WHERE parent = %s
                AND start_date >= %s
                AND status = 'Completed'
                AND actual_hours IS NOT NULL
            """, (volunteer, year_start), as_dict=True)
            
            context.volunteer_hours = volunteer_hours[0].total_hours if volunteer_hours and volunteer_hours[0].total_hours else 0
        except Exception as e:
            frappe.log_error(f"Error calculating volunteer hours: {str(e)}")
            context.volunteer_hours = 0
    else:
        context.volunteer = None
        context.volunteer_hours = 0
    
    # Get recent activity
    context.recent_activity = get_member_activity(member)
    
    # Get quick actions based on member status
    context.quick_actions = get_quick_actions(context.member, membership, context.volunteer)
    
    return context

def has_website_permission(doc, ptype, user, verbose=False):
    """Check website permission for member portal page"""
    # Only logged-in users can access
    if user == "Guest":
        return False
    
    # Check if user has a member record
    member = frappe.db.get_value("Member", {"email": user})
    return bool(member)

def get_member_activity(member_name):
    """Get recent activity for member"""
    activities = []
    
    # Get recent payments
    payments = frappe.get_all(
        "Payment Entry",
        filters={
            "party_type": "Customer",
            "party": frappe.db.get_value("Member", member_name, "customer"),
            "docstatus": 1
        },
        fields=["name", "posting_date", "paid_amount"],
        order_by="posting_date desc",
        limit=3
    )
    
    for payment in payments:
        activities.append({
            "icon": "fa-credit-card",
            "description": _("Payment of {0} received").format(
                frappe.format_value(payment.paid_amount, {"fieldtype": "Currency"})
            ),
            "date": payment.posting_date
        })
    
    # Get recent volunteer assignments if applicable
    volunteer = frappe.db.get_value("Volunteer", {"member": member_name})
    if volunteer:
        assignments = frappe.get_all(
            "Volunteer Assignment",
            filters={"parent": volunteer},
            fields=["assignment_type", "start_date", "role"],
            order_by="start_date desc",
            limit=2
        )
        
        for assignment in assignments:
            activities.append({
                "icon": "fa-heart",
                "description": _("Volunteer assignment: {0}").format(assignment.role or assignment.assignment_type),
                "date": assignment.start_date
            })
    
    # Get recent membership changes
    member_doc = frappe.get_doc("Member", member_name)
    if member_doc.modified:
        activities.append({
            "icon": "fa-user",
            "description": _("Profile updated"),
            "date": getdate(member_doc.modified)
        })
    
    # Get recent SEPA mandate changes
    recent_mandate = frappe.get_all(
        "SEPA Mandate",
        filters={"member": member_name},
        fields=["creation", "status", "mandate_id"],
        order_by="creation desc",
        limit=1
    )
    
    if recent_mandate:
        mandate = recent_mandate[0]
        activities.append({
            "icon": "fa-bank",
            "description": _("SEPA mandate {0} {1}").format(
                mandate.mandate_id, 
                _("activated") if mandate.status == "Active" else _("updated")
            ),
            "date": getdate(mandate.creation)
        })
    
    # Sort by date and limit to 5 most recent
    activities.sort(key=lambda x: x["date"], reverse=True)
    return activities[:5]

def get_quick_actions(member, membership, volunteer):
    """Get quick actions based on member status"""
    actions = []
    
    # Payment-related actions
    if not membership:
        actions.append({
            "title": _("Update Payment Details"),
            "route": "/bank_details",
            "class": "btn-primary",
            "icon": "fa-id-card"
        })
    elif membership.status != "Active":
        actions.append({
            "title": _("Update Payment Details"),
            "route": "/bank_details",
            "class": "btn-primary",
            "icon": "fa-refresh"
        })
    
    # Bank details setup
    if not member.iban:
        actions.append({
            "title": _("Set Up Bank Details"),
            "route": "/bank_details",
            "class": "btn-primary",
            "icon": "fa-credit-card"
        })
    elif member.payment_method != "Direct Debit":
        actions.append({
            "title": _("Enable Auto-Pay"),
            "route": "/bank_details",
            "class": "btn-secondary",
            "icon": "fa-magic"
        })
    
    # Address updates
    address_incomplete = False
    try:
        if not member.primary_address:
            address_incomplete = True
        else:
            # Check if the linked address has required fields
            address_doc = frappe.get_doc("Address", member.primary_address)
            if not address_doc.address_line1 or not address_doc.city:
                address_incomplete = True
    except:
        address_incomplete = True
    
    if address_incomplete:
        actions.append({
            "title": _("Complete Address"),
            "route": "/address_change",
            "class": "btn-secondary",
            "icon": "fa-map-marker"
        })
    
    # Volunteer-specific actions
    if volunteer:
        try:
            # Check for pending expense claims
            pending_expenses = frappe.db.count(
                "Volunteer Expense",
                filters={
                    "volunteer": volunteer.name,
                    "status": "Draft"  # Now all pending expenses are in Draft status
                }
            )
            
            if pending_expenses:
                actions.append({
                    "title": _("Review Expense Claims ({0})").format(pending_expenses),
                    "route": "/volunteer/expenses",
                    "class": "btn-secondary",
                    "icon": "fa-receipt"
                })
            else:
                actions.append({
                    "title": _("Submit Expenses"),
                    "route": "/volunteer/expenses",
                    "class": "btn-secondary",
                    "icon": "fa-plus"
                })
        except Exception as e:
            frappe.log_error(f"Error checking volunteer expenses: {str(e)}")
            # Add a generic volunteer expenses link if error occurs
            actions.append({
                "title": _("Volunteer Expenses"),
                "route": "/volunteer/expenses",
                "class": "btn-secondary",
                "icon": "fa-receipt"
            })
    
    # Fee adjustment if needed
    try:
        if getattr(member, 'membership_fee_override', None):
            actions.append({
                "title": _("Review Fee Adjustment"),
                "route": "/membership_fee_adjustment",
                "class": "btn-secondary",
                "icon": "fa-euro"
            })
    except:
        pass  # Ignore if field doesn't exist
    
    # Contact request action - always available
    actions.append({
        "title": _("Contact Support"),
        "route": "/contact_request",
        "class": "btn-secondary",
        "icon": "fa-envelope"
    })
    
    return actions