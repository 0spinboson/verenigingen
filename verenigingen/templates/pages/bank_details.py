"""
Bank Details Form for Members
Allows members to view and update their bank details and manage SEPA Direct Debit
"""

import frappe
from frappe import _
from frappe.utils import today, now
from frappe.utils.password import get_decrypted_password
import re

def get_context(context):
    """Get context for bank details form"""
    
    # Require login
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access this page"), frappe.PermissionError)
    
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("Bank Details")
    
    # Get member record
    member = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member:
        frappe.throw(_("No member record found for your account"), frappe.DoesNotExistError)
    
    context.member = frappe.get_doc("Member", member)
    
    # Get current bank details
    current_details = {
        'iban': context.member.iban,
        'bic': context.member.bic,
        'bank_account_name': context.member.bank_account_name
    }
    context.current_details = current_details
    
    # Check for active SEPA mandate
    context.current_mandate = get_active_sepa_mandate(member)
    
    return context

def has_website_permission(doc, ptype, user, verbose=False):
    """Check website permission for bank details page"""
    # Only logged-in users can access
    if user == "Guest":
        return False
    
    # Check if user has a member record
    member = frappe.db.get_value("Member", {"email": user})
    return bool(member)

@frappe.whitelist(allow_guest=False, methods=["POST"])
def update_bank_details():
    """Handle bank details form submission"""
    
    # Get member
    member_name = frappe.db.get_value("Member", {"email": frappe.session.user})
    if not member_name:
        frappe.throw(_("No member record found"), frappe.DoesNotExistError)
    
    member = frappe.get_doc("Member", member_name)
    
    # Get form data
    form_data = frappe.local.form_dict
    new_iban = form_data.get('iban', '').replace(' ', '').upper()
    new_bic = form_data.get('bic', '').strip().upper()
    new_account_holder = form_data.get('account_holder_name', '').strip()
    enable_dd = form_data.get('enable_direct_debit') == 'on'
    
    # Validate required fields
    if not new_iban:
        frappe.throw(_("IBAN is required"))
    
    if not new_account_holder:
        frappe.throw(_("Account holder name is required"))
    
    # Validate IBAN format
    if not validate_iban_format(new_iban):
        frappe.throw(_("Invalid IBAN format"))
    
    # Auto-derive BIC for Dutch IBANs if not provided
    if not new_bic and new_iban.startswith('NL'):
        new_bic = derive_bic_from_dutch_iban(new_iban)
    
    # Check if bank details changed
    bank_details_changed = (
        member.iban != new_iban or
        member.bic != new_bic or
        member.bank_account_name != new_account_holder
    )
    
    # Get current SEPA mandate status
    current_mandate = get_active_sepa_mandate(member_name)
    current_payment_method = member.payment_method
    
    # Determine action needed
    action_needed = determine_mandate_action(
        current_mandate, 
        current_payment_method, 
        enable_dd, 
        bank_details_changed
    )
    
    # Prepare context for confirmation page
    context = {
        'member': member,
        'new_iban': new_iban,
        'new_bic': new_bic,
        'new_account_holder': new_account_holder,
        'enable_dd': enable_dd,
        'bank_details_changed': bank_details_changed,
        'current_mandate': current_mandate,
        'action_needed': action_needed,
        'current_payment_method': current_payment_method
    }
    
    # Store data in session for confirmation page
    frappe.session['bank_details_update'] = context
    
    # Redirect to confirmation page
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "/bank_details_confirm"

def validate_iban_format(iban):
    """Validate IBAN format"""
    if not iban or len(iban) < 15:
        return False
    
    # Basic pattern check
    pattern = r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}$'
    if not re.match(pattern, iban):
        return False
    
    return True

def derive_bic_from_dutch_iban(iban):
    """Derive BIC from Dutch IBAN bank code"""
    if not iban.startswith('NL') or len(iban) < 8:
        return None
    
    bank_code = iban[4:8]
    
    dutch_banks = {
        'ABNA': 'ABNANL2A',  # ABN AMRO
        'RABO': 'RABONL2U',  # Rabobank
        'INGB': 'INGBNL2A',  # ING Bank
        'TRIO': 'TRIONL2U',  # Triodos Bank
        'SNSB': 'SNSBNL2A',  # SNS Bank
        'ASNB': 'ASNBNL21',  # ASN Bank
        'RBRB': 'RBRBNL21',  # RegioBank
        'BUNQ': 'BUNQNL2A',  # bunq
        'KNAB': 'KNABNL2H',  # Knab
        'HAND': 'HANDNL2A'   # Svenska Handelsbanken
    }
    
    return dutch_banks.get(bank_code)

def get_active_sepa_mandate(member_name):
    """Get active SEPA mandate for member"""
    try:
        mandate = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member_name,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id", "iban", "account_holder_name", "status"],
            limit=1
        )
        return mandate[0] if mandate else None
    except Exception:
        return None

def determine_mandate_action(current_mandate, current_payment_method, enable_dd, bank_details_changed):
    """Determine what action is needed for SEPA mandate"""
    
    if enable_dd:
        if current_mandate:
            if bank_details_changed:
                return "replace_mandate"  # Cancel current, create new
            else:
                return "keep_mandate"     # Keep existing
        else:
            return "create_mandate"       # Create new
    else:
        if current_mandate:
            return "cancel_mandate"       # Cancel existing
        else:
            return "no_mandate"          # No mandate needed
    
    return "no_action"