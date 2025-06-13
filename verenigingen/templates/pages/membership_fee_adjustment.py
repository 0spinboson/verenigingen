"""
Context for membership fee adjustment page
"""

import frappe
from frappe import _
from frappe.utils import getdate, today, flt

def get_context(context):
    """Get context for membership fee adjustment page"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access this page"), frappe.PermissionError)
    
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("Adjust Membership Fee")
    
    # Get member record
    member = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member:
        # Try alternative lookup by user field
        member = frappe.db.get_value("Member", {"user": frappe.session.user})
        
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
        ["name", "membership_type", "start_date", "renewal_date"],
        as_dict=True
    )
    
    if not membership:
        frappe.throw(_("No active membership found"), frappe.DoesNotExistError)
    
    context.membership = membership
    
    # Get membership type details and minimum fee
    membership_type = frappe.get_doc("Membership Type", membership.membership_type)
    context.membership_type = membership_type
    
    # Calculate minimum fee (could be based on membership type, student status, etc.)
    minimum_fee = get_minimum_fee(context.member, membership_type)
    context.minimum_fee = minimum_fee
    
    # Get current effective fee
    current_fee = context.member.get_current_membership_fee()
    context.current_fee = current_fee
    
    # Get fee adjustment settings
    settings = get_fee_adjustment_settings()
    context.settings = settings
    
    # Get member contact email from settings
    verenigingen_settings = frappe.get_single("Verenigingen Settings")
    context.member_contact_email = getattr(verenigingen_settings, 'member_contact_email', 'ledenadministratie@veganisme.org')
    
    # Check if member can adjust their fee
    context.can_adjust_fee = can_member_adjust_fee(context.member, settings)
    
    # Get pending fee adjustment requests
    pending_requests = frappe.get_all(
        "Contribution Amendment Request",
        filters={
            "member": member,
            "amendment_type": "Fee Change",
            "status": ["in", ["Draft", "Pending Approval"]],
            "requested_by_member": 1
        },
        fields=["name", "status", "requested_amount", "reason", "creation"],
        order_by="creation desc"
    )
    context.pending_requests = pending_requests
    
    # Add member portal links
    context.portal_links = [
        {"title": _("Dashboard"), "route": "/member_dashboard"},
        {"title": _("Profile"), "route": "/my-account"}, 
        {"title": _("Personal Details"), "route": "/personal_details"},
        {"title": _("Fee Adjustment"), "route": "/membership_fee_adjustment", "active": True},
    ]
    
    return context

def get_minimum_fee(member, membership_type):
    """Calculate minimum fee for a member"""
    base_minimum = flt(membership_type.amount * 0.3)  # 30% of standard fee as absolute minimum
    
    # Student discount
    if getattr(member, 'student_status', False):
        base_minimum = max(base_minimum, flt(membership_type.amount * 0.5))  # Students minimum 50%
    
    # Income-based minimum (if available)
    if hasattr(member, 'annual_income') and member.annual_income:
        if member.annual_income in ["Under €25,000", "€25,000 - €40,000"]:
            base_minimum = max(base_minimum, flt(membership_type.amount * 0.4))  # Low income 40%
    
    # Ensure minimum is at least €5
    return max(base_minimum, 5.0)

def get_fee_adjustment_settings():
    """Get fee adjustment settings from Verenigingen Settings"""
    try:
        settings = frappe.get_single("Verenigingen Settings")
        return {
            "enable_member_fee_adjustment": getattr(settings, 'enable_member_fee_adjustment', 1),
            "max_adjustments_per_year": getattr(settings, 'max_adjustments_per_year', 2),
            "require_approval_for_increases": getattr(settings, 'require_approval_for_increases', 0),
            "require_approval_for_decreases": getattr(settings, 'require_approval_for_decreases', 1),
            "adjustment_reason_required": getattr(settings, 'adjustment_reason_required', 1)
        }
    except:
        # Default settings if Verenigingen Settings doesn't exist or lacks fields
        return {
            "enable_member_fee_adjustment": 1,
            "max_adjustments_per_year": 2,
            "require_approval_for_increases": 0,
            "require_approval_for_decreases": 1,
            "adjustment_reason_required": 1
        }

def can_member_adjust_fee(member, settings):
    """Check if member can adjust their fee"""
    if not settings.get("enable_member_fee_adjustment"):
        return False, _("Fee adjustment is not enabled")
    
    # Check how many adjustments this year
    year_start = getdate(today()).replace(month=1, day=1)
    adjustments_this_year = frappe.db.count(
        "Contribution Amendment Request",
        filters={
            "member": member.name,
            "amendment_type": "Fee Change",
            "creation": [">=", year_start],
            "requested_by_member": 1
        }
    )
    
    max_adjustments = settings.get("max_adjustments_per_year", 2)
    if adjustments_this_year >= max_adjustments:
        return False, _("You have reached the maximum number of fee adjustments for this year ({0})").format(max_adjustments)
    
    return True, ""

@frappe.whitelist()
def submit_fee_adjustment_request(new_amount, reason=""):
    """Submit a fee adjustment request from member portal"""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login"), frappe.PermissionError)
    
    # Get member
    member = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member:
        member = frappe.db.get_value("Member", {"user": frappe.session.user})
    
    if not member:
        frappe.throw(_("No member record found"))
    
    member_doc = frappe.get_doc("Member", member)
    
    # Validate amount
    new_amount = flt(new_amount)
    if new_amount <= 0:
        frappe.throw(_("Amount must be greater than 0"))
    
    # Get membership and minimum fee
    membership = frappe.db.get_value(
        "Membership",
        {"member": member, "status": "Active", "docstatus": 1},
        ["name", "membership_type"]
    )
    
    if not membership:
        frappe.throw(_("No active membership found"))
    
    membership_type = frappe.get_doc("Membership Type", membership[1])
    minimum_fee = get_minimum_fee(member_doc, membership_type)
    
    if new_amount < minimum_fee:
        frappe.throw(_("Amount cannot be less than minimum fee of {0}").format(
            frappe.format_value(minimum_fee, {"fieldtype": "Currency"})
        ))
    
    # Check if member can adjust fee
    settings = get_fee_adjustment_settings()
    can_adjust, error_msg = can_member_adjust_fee(member_doc, settings)
    
    if not can_adjust:
        frappe.throw(error_msg)
    
    # Get current fee
    current_fee = member_doc.get_current_membership_fee()
    current_amount = current_fee.get("amount", membership_type.amount)
    
    # Validate amount is different and reasonable
    if abs(new_amount - current_amount) < 0.01:
        frappe.msgprint(
            _("The requested amount ({0}) is the same as your current membership fee.").format(
                frappe.utils.fmt_money(new_amount, currency="EUR")
            ),
            title=_("No Change Needed"),
            indicator="orange"
        )
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/membership_fee_adjustment"
        return
    
    # Determine if approval is needed
    needs_approval = False
    if new_amount > current_amount and settings.get("require_approval_for_increases"):
        needs_approval = True
    elif new_amount < current_amount and settings.get("require_approval_for_decreases"):
        needs_approval = True
    
    # Validate reason if required
    if settings.get("adjustment_reason_required") and not reason.strip():
        frappe.throw(_("Please provide a reason for the fee adjustment"))
    
    # Get current active membership
    current_membership = frappe.db.get_value(
        "Membership",
        {
            "member": member,
            "status": "Active",
            "docstatus": 1
        }
    )
    
    if not current_membership:
        frappe.throw(_("No active membership found. Cannot process fee adjustment."))
    
    # Create amendment request
    amendment = frappe.get_doc({
        "doctype": "Contribution Amendment Request",
        "member": member,
        "membership": current_membership,
        "amendment_type": "Fee Change",
        "current_amount": current_amount,
        "requested_amount": new_amount,
        "reason": reason,
        "status": "Pending Approval" if needs_approval else "Auto-Approved",
        "requested_by_member": 1,
        "effective_date": today()
    })
    
    try:
        amendment.insert(ignore_permissions=True)
    except frappe.ValidationError as e:
        # Handle validation errors more gracefully
        error_msg = str(e)
        if "same as current amount" in error_msg:
            frappe.msgprint(
                _("No changes were made as the requested amount is the same as your current fee."),
                title=_("No Change Needed"),
                indicator="orange"
            )
        else:
            frappe.msgprint(
                _("Unable to process your request: {0}").format(error_msg),
                title=_("Validation Error"),
                indicator="red"
            )
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/membership_fee_adjustment"
        return
    
    # If no approval needed, apply immediately
    if not needs_approval:
        # Apply the fee change
        member_doc.membership_fee_override = new_amount
        member_doc.fee_override_reason = f"Member self-adjustment: {reason}"
        member_doc.fee_override_date = today()
        member_doc.fee_override_by = frappe.session.user
        member_doc.save(ignore_permissions=True)
        
        # Update amendment status
        amendment.status = "Applied"
        amendment.applied_date = today()
        amendment.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": _("Your fee has been updated successfully"),
            "amendment_id": amendment.name,
            "needs_approval": False
        }
    else:
        return {
            "success": True,
            "message": _("Your fee adjustment request has been submitted for approval"),
            "amendment_id": amendment.name,
            "needs_approval": True
        }
    
@frappe.whitelist()
def get_fee_calculation_info():
    """Get fee calculation information for member"""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login"), frappe.PermissionError)
    
    # Get member
    member = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member:
        member = frappe.db.get_value("Member", {"user": frappe.session.user})
    
    if not member:
        frappe.throw(_("No member record found"))
    
    member_doc = frappe.get_doc("Member", member)
    
    # Get membership type
    membership = frappe.db.get_value(
        "Membership",
        {"member": member, "status": "Active", "docstatus": 1},
        "membership_type"
    )
    
    if not membership:
        frappe.throw(_("No active membership found"))
    
    membership_type = frappe.get_doc("Membership Type", membership)
    
    # Calculate fees
    standard_fee = membership_type.amount
    minimum_fee = get_minimum_fee(member_doc, membership_type)
    current_fee = member_doc.get_current_membership_fee()
    
    return {
        "standard_fee": standard_fee,
        "minimum_fee": minimum_fee,
        "current_fee": current_fee.get("amount", standard_fee),
        "current_source": current_fee.get("source", "membership_type"),
        "membership_type": membership_type.membership_type_name
    }