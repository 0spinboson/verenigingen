"""
Bank Details Confirmation Page
Shows confirmation of bank details changes before processing
"""

import frappe
from frappe import _
from frappe.utils import today, now

def get_context(context):
    """Get context for bank details confirmation page"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access this page"), frappe.PermissionError)
    
    # Check if we have pending update data
    update_data = frappe.session.get('bank_details_update')
    if not update_data:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/bank_details"
        return
    
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("Confirm Bank Details Update")
    
    # Pass all update data to template
    for key, value in update_data.items():
        context[key] = value
    
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
    
    # Get member
    member_name = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member_name:
        frappe.throw(_("No member record found"), frappe.DoesNotExistError)
    
    # Get pending update data
    update_data = frappe.session.get('bank_details_update')
    if not update_data:
        frappe.throw(_("No pending update found"), frappe.ValidationError)
    
    try:
        # Get member document
        member = frappe.get_doc("Member", member_name)
        
        # Extract update data
        new_iban = update_data['new_iban']
        new_bic = update_data['new_bic']
        new_account_holder = update_data['new_account_holder']
        enable_dd = update_data['enable_dd']
        action_needed = update_data['action_needed']
        current_mandate = update_data['current_mandate']
        
        # Update bank details on member record
        member.iban = new_iban
        member.bic = new_bic
        member.bank_account_name = new_account_holder
        
        # Update payment method based on direct debit choice
        if enable_dd:
            member.payment_method = "Direct Debit"
        else:
            # Only change if currently Direct Debit, preserve other methods
            if member.payment_method == "Direct Debit":
                member.payment_method = "Manual"
        
        # Save member changes
        member.save(ignore_permissions=True)
        
        # Handle SEPA mandate changes
        mandate_result = handle_sepa_mandate_changes(
            member_name, 
            action_needed, 
            current_mandate, 
            new_iban, 
            new_bic, 
            new_account_holder
        )
        
        # Clear session data
        if 'bank_details_update' in frappe.session:
            del frappe.session['bank_details_update']
        
        # Create success message
        if enable_dd:
            if action_needed == "create_mandate":
                message = _("Bank details updated successfully. SEPA mandate will be created by our scheduled task within 24 hours.")
            elif action_needed == "replace_mandate":
                message = _("Bank details updated successfully. Your SEPA mandate will be updated within 24 hours.")
            else:
                message = _("Bank details updated successfully. Your SEPA Direct Debit remains active.")
        else:
            if action_needed == "cancel_mandate":
                message = _("Bank details updated successfully. SEPA Direct Debit has been disabled.")
            else:
                message = _("Bank details updated successfully.")
        
        frappe.msgprint(message, title=_("Update Successful"), indicator="green")
        
        # Redirect to member dashboard
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/member_dashboard?success=bank_details_updated"
        
    except Exception as e:
        frappe.log_error(f"Bank details update failed: {str(e)}")
        frappe.throw(_("Failed to update bank details. Please try again or contact support."))

def handle_sepa_mandate_changes(member_name, action_needed, current_mandate, new_iban, new_bic, new_account_holder):
    """Handle SEPA mandate changes based on action needed"""
    
    result = {"action": action_needed, "success": True}
    
    try:
        if action_needed == "create_mandate":
            # Create mandate pending record for scheduled task
            create_mandate_pending_record(member_name, new_iban, new_bic, new_account_holder)
            result["message"] = "Mandate creation scheduled"
            
        elif action_needed == "replace_mandate":
            # Cancel existing mandate and create new one
            if current_mandate:
                cancel_existing_mandate(current_mandate['name'])
            create_mandate_pending_record(member_name, new_iban, new_bic, new_account_holder)
            result["message"] = "Mandate replacement scheduled"
            
        elif action_needed == "cancel_mandate":
            # Cancel existing mandate
            if current_mandate:
                cancel_existing_mandate(current_mandate['name'])
            result["message"] = "Mandate cancelled"
            
        elif action_needed == "keep_mandate":
            # Update existing mandate with new details (if bank details changed)
            if current_mandate:
                update_existing_mandate(current_mandate['name'], new_iban, new_bic, new_account_holder)
            result["message"] = "Mandate updated"
            
        # Log the action for audit trail
        frappe.log_error(
            f"SEPA mandate action '{action_needed}' processed for member {member_name}",
            "Bank Details Update"
        )
        
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        frappe.log_error(f"SEPA mandate handling failed: {str(e)}")
    
    return result

def create_mandate_pending_record(member_name, iban, bic, account_holder):
    """Create a pending mandate record for scheduled task processing"""
    
    # Create a record that the scheduled task can pick up
    try:
        # For now, we'll create a simple log entry that the scheduled task can process
        # In a full implementation, you might create a dedicated "SEPA Mandate Request" doctype
        
        frappe.log_error(
            f"SEPA_MANDATE_REQUEST|{member_name}|{iban}|{bic or ''}|{account_holder}|{now()}",
            "SEPA Mandate Pending"
        )
        
        # You could also create a more structured approach:
        # frappe.get_doc({
        #     "doctype": "SEPA Mandate Request",
        #     "member": member_name,
        #     "iban": iban,
        #     "bic": bic,
        #     "account_holder_name": account_holder,
        #     "status": "Pending",
        #     "request_date": now()
        # }).insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Failed to create mandate pending record: {str(e)}")

def cancel_existing_mandate(mandate_name):
    """Cancel an existing SEPA mandate"""
    
    try:
        mandate = frappe.get_doc("SEPA Mandate", mandate_name)
        mandate.status = "Cancelled"
        mandate.is_active = 0
        mandate.cancellation_date = today()
        mandate.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Failed to cancel mandate {mandate_name}: {str(e)}")

def update_existing_mandate(mandate_name, new_iban, new_bic, new_account_holder):
    """Update existing mandate with new bank details"""
    
    try:
        mandate = frappe.get_doc("SEPA Mandate", mandate_name)
        mandate.iban = new_iban
        mandate.bic = new_bic
        mandate.account_holder_name = new_account_holder
        mandate.save(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Failed to update mandate {mandate_name}: {str(e)}")