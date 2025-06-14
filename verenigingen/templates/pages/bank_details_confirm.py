"""
Bank Details Confirmation Page
Handles the confirmation and processing of bank details updates
"""

import frappe
from frappe import _
from frappe.utils import today, now
import json

def get_context(context):
    """Get context for bank details confirmation page"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access this page"), frappe.PermissionError)
    
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("Confirm Bank Details Update")
    
    # Get stored update data from session
    update_data = frappe.session.get('bank_details_update')
    if not update_data:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/bank_details"
        return
    
    context.update_data = update_data
    
    # Get organization details for SEPA info
    settings = frappe.get_single("Verenigingen Settings")
    context.organization_name = settings.organization_name if settings else None
    context.creditor_id = settings.sepa_creditor_id if settings else None
    
    return context

def has_website_permission(doc, ptype, user, verbose=False):
    """Check website permission for bank details confirmation page"""
    # Only logged-in users can access
    if user == "Guest":
        return False
    
    # Check if user has a member record
    member = frappe.db.get_value("Member", {"email": user})
    return bool(member)

@frappe.whitelist(allow_guest=False, methods=["POST"])
def process_bank_details_update():
    """Process the confirmed bank details update"""
    
    # Get stored update data
    update_data = frappe.session.get('bank_details_update')
    if not update_data:
        frappe.throw(_("Session expired. Please start over."))
    
    # Verify action is confirm
    if frappe.local.form_dict.get('action') != 'confirm':
        frappe.throw(_("Invalid action"))
    
    try:
        # Get member
        member = frappe.get_doc("Member", update_data['member']['name'])
        
        # Update bank details
        member.iban = update_data['new_iban']
        member.bic = update_data['new_bic']
        member.bank_account_name = update_data['new_account_holder']
        
        # Update payment method if needed
        if update_data['enable_dd']:
            member.payment_method = "Direct Debit"
        elif update_data['current_payment_method'] == "Direct Debit" and not update_data['enable_dd']:
            # If disabling DD, set to a default alternative
            member.payment_method = "Bank Transfer"
        
        # Save member changes
        member.save(ignore_permissions=True)
        
        # Handle SEPA mandate changes
        mandate_result = handle_sepa_mandate_changes(member, update_data)
        
        # Clear session data
        if 'bank_details_update' in frappe.session:
            del frappe.session['bank_details_update']
        
        # Prepare success message
        success_message = prepare_success_message(update_data, mandate_result)
        
        # Store success message in session for redirect
        frappe.session['bank_details_success'] = success_message
        
        # Redirect to success page
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/bank_details_success"
        
    except Exception as e:
        frappe.log_error(f"Bank details update failed: {str(e)}")
        frappe.throw(_("Failed to update bank details. Please try again or contact support."))

def handle_sepa_mandate_changes(member, update_data):
    """Handle SEPA mandate creation, replacement, or cancellation using existing methods"""
    
    action = update_data['action_needed']
    result = {"action": action, "success": False}
    
    try:
        if action == "create_mandate":
            # Use existing create_and_link_mandate_enhanced method
            mandate_result = create_sepa_mandate_via_existing_method(member, update_data)
            result["mandate_name"] = mandate_result.get("mandate_name")
            result["success"] = True
            
        elif action == "replace_mandate":
            # Cancel current mandate and create new one
            if update_data['current_mandate']:
                cancel_sepa_mandate_via_existing_method(update_data['current_mandate']['name'])
            
            mandate_result = create_sepa_mandate_via_existing_method(member, update_data)
            result["old_mandate"] = update_data['current_mandate']['name']
            result["mandate_name"] = mandate_result.get("mandate_name")
            result["success"] = True
            
        elif action == "cancel_mandate":
            # Cancel existing mandate
            if update_data['current_mandate']:
                cancel_sepa_mandate_via_existing_method(update_data['current_mandate']['name'])
                result["cancelled_mandate"] = update_data['current_mandate']['name']
                result["success"] = True
            
        elif action in ["keep_mandate", "no_mandate", "no_action"]:
            # No mandate changes needed
            result["success"] = True
            
    except Exception as e:
        frappe.log_error(f"SEPA mandate handling failed: {str(e)}")
        result["error"] = str(e)
    
    return result

def create_sepa_mandate_via_existing_method(member, update_data):
    """Create a new SEPA mandate using existing member controller method"""
    
    # Generate mandate reference
    mandate_id = generate_mandate_reference(member)
    
    # Use the existing whitelist method from member controller
    from verenigingen.verenigingen.doctype.member.member import create_and_link_mandate_enhanced
    
    return create_and_link_mandate_enhanced(
        member=member.name,
        mandate_id=mandate_id,
        iban=update_data['new_iban'],
        bic=update_data['new_bic'] or "",
        account_holder_name=update_data['new_account_holder'],
        mandate_type="Recurring",
        sign_date=today(),
        used_for_memberships=1,
        used_for_donations=0,
        notes=f"Created via member portal on {today()}"
    )

def cancel_sepa_mandate_via_existing_method(mandate_name):
    """Cancel an existing SEPA mandate using existing method"""
    
    mandate = frappe.get_doc("SEPA Mandate", mandate_name)
    
    # Use the existing cancel_mandate method
    mandate.cancel_mandate(
        reason="Cancelled via member portal - bank details changed",
        cancellation_date=today()
    )
    
    mandate.save(ignore_permissions=True)

def generate_mandate_reference(member):
    """Generate a unique mandate reference"""
    
    member_id = member.member_id or member.name.replace('Assoc-Member-', '').replace('-', '')
    date_str = today().replace('-', '')
    
    # Find next sequence number for today
    existing_count = frappe.db.count(
        "SEPA Mandate",
        filters={
            "mandate_id": ["like", f"M-{member_id}-{date_str}-%"],
            "creation": [">=", today() + " 00:00:00"]
        }
    )
    
    sequence = str(existing_count + 1).zfill(3)
    return f"M-{member_id}-{date_str}-{sequence}"

def prepare_success_message(update_data, mandate_result):
    """Prepare success message based on actions taken"""
    
    messages = []
    
    # Bank details update
    if update_data['bank_details_changed']:
        messages.append(_("Your bank details have been updated successfully."))
    
    # SEPA mandate actions
    if mandate_result['success']:
        action = mandate_result['action']
        
        if action == "create_mandate":
            messages.append(_("A new SEPA Direct Debit mandate has been created and activated."))
            
        elif action == "replace_mandate":
            messages.append(_("Your SEPA mandate has been updated with the new bank details."))
            
        elif action == "cancel_mandate":
            messages.append(_("Your SEPA Direct Debit mandate has been cancelled."))
            messages.append(_("Future membership fees will be collected via alternative payment methods."))
            
        elif action == "keep_mandate":
            messages.append(_("Your existing SEPA Direct Debit mandate remains active."))
    
    else:
        if 'error' in mandate_result:
            messages.append(_("Bank details updated, but there was an issue with the SEPA mandate: {0}").format(mandate_result['error']))
    
    # Payment method change
    if update_data['enable_dd'] and update_data['current_payment_method'] != "Direct Debit":
        messages.append(_("Your payment method has been changed to Direct Debit."))
    elif not update_data['enable_dd'] and update_data['current_payment_method'] == "Direct Debit":
        messages.append(_("Your payment method has been changed to Bank Transfer."))
    
    return messages