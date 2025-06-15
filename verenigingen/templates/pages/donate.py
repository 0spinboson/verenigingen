"""
Context and API for donation page
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, cstr
import json

def get_context(context):
    """Get context for donation page"""
    
    # Set page properties
    context.no_cache = 1
    context.show_sidebar = False
    context.title = _("Make a Donation")
    
    # Get verenigingen settings
    settings = frappe.get_single("Verenigingen Settings")
    context.settings = {
        "company_name": frappe.get_value("Company", settings.donation_company, "company_name"),
        "enable_chapter_management": settings.enable_chapter_management,
        "organization_email_domain": getattr(settings, "organization_email_domain", ""),
        "anbi_minimum_reportable_amount": flt(getattr(settings, "anbi_minimum_reportable_amount", 500))
    }
    
    # Get donation types
    donation_types = frappe.get_all("Donation Type", 
        fields=["name", "donation_type"],
        order_by="donation_type"
    )
    context.donation_types = donation_types
    context.default_donation_type = settings.default_donation_type
    
    # Get chapters for earmarking
    chapters = []
    if settings.enable_chapter_management:
        chapters = frappe.get_all("Chapter",
            filters={"published": 1},
            fields=["name"],
            order_by="name"
        )
    context.chapters = chapters
    
    # Get donor types for new donor creation (from Select field options)
    donor_types = [
        {"name": "Individual", "donor_type": "Individual"},
        {"name": "Organization", "donor_type": "Organization"}
    ]
    context.donor_types = donor_types
    context.default_donor_type = getattr(settings, "default_donor_type", "Individual")
    
    # Payment method configuration
    context.payment_methods = [
        {"value": "Bank Transfer", "label": _("Bank Transfer"), "description": _("Transfer money directly to our bank account")},
        {"value": "SEPA Direct Debit", "label": _("SEPA Direct Debit"), "description": _("Authorize us to collect the donation from your account")},
        {"value": "Mollie", "label": _("Online Payment"), "description": _("Pay online with iDEAL, credit card, or other methods")},
        {"value": "Cash", "label": _("Cash"), "description": _("Pay in cash at our office or events")},
    ]
    
    # Check if user is logged in and get existing donor info
    context.user_info = {}
    if frappe.session.user != "Guest":
        user = frappe.get_doc("User", frappe.session.user)
        context.user_info = {
            "email": user.email,
            "full_name": user.get_fullname(),
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
        # Check if user is already a donor
        existing_donor = frappe.db.get_value("Donor", {"donor_email": user.email})
        if existing_donor:
            donor_doc = frappe.get_doc("Donor", existing_donor)
            context.existing_donor = {
                "name": donor_doc.name,
                "donor_name": donor_doc.donor_name,
                "phone": getattr(donor_doc, "phone", ""),
                "donor_type": donor_doc.donor_type
            }
    
    return context


@frappe.whitelist(allow_guest=True)
def submit_donation(**kwargs):
    """Process donation form submission"""
    try:
        # Parse form data
        form_data = frappe._dict(kwargs)
        
        # Validate required fields
        required_fields = ["donor_name", "donor_email", "amount", "payment_method"]
        for field in required_fields:
            if not form_data.get(field):
                return {"success": False, "message": _("Missing required field: {0}").format(field)}
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, form_data.donor_email):
            return {"success": False, "message": _("Invalid email address")}
        
        # Validate amount
        amount = flt(form_data.amount)
        if amount <= 0:
            return {"success": False, "message": _("Donation amount must be greater than zero")}
        
        # Create or get donor
        donor = get_or_create_donor(form_data)
        if not donor:
            return {"success": False, "message": _("Failed to create donor record")}
        
        # Create donation
        donation = create_donation_record(donor, form_data)
        if not donation:
            return {"success": False, "message": _("Failed to create donation record")}
        
        # Process payment based on method
        payment_result = process_payment_method(donation, form_data)
        
        return {
            "success": True,
            "donation_id": donation.name,
            "message": _("Donation submitted successfully"),
            "payment_info": payment_result
        }
        
    except Exception as e:
        frappe.log_error(f"Donation submission error: {str(e)}", "Donation Form Error")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": _("An error occurred while processing your donation. Please try again."), "debug_error": str(e)}


def get_or_create_donor(form_data):
    """Get existing donor or create new one"""
    # Check if donor exists by email
    existing_donor = frappe.db.get_value("Donor", {"donor_email": form_data.donor_email})
    
    if existing_donor:
        # Update existing donor with any new information
        donor_doc = frappe.get_doc("Donor", existing_donor)
        if form_data.get("donor_phone") and not donor_doc.phone:
            donor_doc.phone = form_data.donor_phone
            donor_doc.save(ignore_permissions=True)
        return donor_doc
    else:
        # Create new donor
        settings = frappe.get_single("Verenigingen Settings")
        donor_type = form_data.get("donor_type") or getattr(settings, "default_donor_type", None)
        
        donor_doc = frappe.new_doc("Donor")
        donor_doc.update({
            "donor_name": form_data.donor_name,
            "donor_email": form_data.donor_email,
            "phone": form_data.get("donor_phone", "Not provided"),
            "donor_type": donor_type,
            "contact_person": form_data.donor_name,  # Use same name as contact person
            "contact_person_address": form_data.get("donor_address", "Not provided"),
            "donor_category": "Regular Donor"  # Default category
        })
        
        donor_doc.insert(ignore_permissions=True)
        return donor_doc


def create_donation_record(donor, form_data):
    """Create donation record"""
    settings = frappe.get_single("Verenigingen Settings")
    
    # Determine donation type
    donation_type = form_data.get("donation_type") or settings.default_donation_type
    
    # Determine purpose and earmarking
    purpose_type = form_data.get("donation_purpose_type", "General")
    
    # Create or get mode of payment
    mode_of_payment = get_or_create_mode_of_payment(form_data.payment_method)
    
    donation_doc = frappe.new_doc("Donation")
    donation_doc.update({
        "company": settings.donation_company,
        "donor": donor.name,
        "date": getdate(),
        "amount": flt(form_data.amount),
        "donation_type": donation_type,
        "payment_method": form_data.payment_method,
        "mode_of_payment": mode_of_payment,
        "donation_status": form_data.get("donation_status", "One-time"),
        "donation_purpose_type": purpose_type,
        "campaign_reference": form_data.get("campaign_reference"),
        "chapter_reference": form_data.get("chapter_reference"),
        "specific_goal_description": form_data.get("specific_goal_description"),
        "donation_notes": form_data.get("donation_notes", ""),
        "paid": 0  # Will be marked paid after payment processing
    })
    
    # Handle ANBI agreement if provided
    if form_data.get("anbi_agreement_number"):
        donation_doc.anbi_agreement_number = form_data.anbi_agreement_number
        donation_doc.anbi_agreement_date = getdate(form_data.get("anbi_agreement_date", getdate()))
    
    donation_doc.insert(ignore_permissions=True)
    return donation_doc


def process_payment_method(donation, form_data):
    """Process payment based on selected method"""
    payment_method = form_data.payment_method
    
    if payment_method == "Bank Transfer":
        return process_bank_transfer(donation, form_data)
    elif payment_method == "SEPA Direct Debit":
        return process_sepa_direct_debit(donation, form_data)
    elif payment_method == "Mollie":
        return process_mollie_payment(donation, form_data)
    elif payment_method == "Cash":
        return process_cash_payment(donation, form_data)
    else:
        return {"status": "pending", "message": _("Payment method not yet implemented")}


def process_bank_transfer(donation, form_data):
    """Handle bank transfer payment"""
    settings = frappe.get_single("Verenigingen Settings")
    company = frappe.get_doc("Company", settings.donation_company)
    
    # Generate payment reference
    payment_reference = f"DON-{donation.name}"
    
    # Get bank details (would typically come from company settings)
    bank_details = {
        "account_holder": company.company_name,
        "iban": getattr(settings, "company_iban", "NL00 BANK 0000 0000 00"),
        "bic": getattr(settings, "company_bic", "BANKBIC2A"),
        "reference": payment_reference,
        "amount": donation.amount
    }
    
    return {
        "status": "awaiting_transfer",
        "message": _("Please transfer the amount to our bank account"),
        "bank_details": bank_details,
        "instructions": _("Include the reference number in your transfer description")
    }


def process_sepa_direct_debit(donation, form_data):
    """Handle SEPA direct debit setup"""
    # Would integrate with existing SEPA mandate system
    return {
        "status": "mandate_required",
        "message": _("SEPA mandate setup required"),
        "next_step": "sepa_mandate_form",
        "info": _("You will be redirected to set up a SEPA mandate for future collections")
    }


def process_mollie_payment(donation, form_data):
    """Handle Mollie payment (placeholder for future integration)"""
    return {
        "status": "redirect_required",
        "message": _("Redirecting to payment provider"),
        "next_step": "mollie_redirect",
        "info": _("You will be redirected to complete payment with Mollie")
    }


def process_cash_payment(donation, form_data):
    """Handle cash payment"""
    return {
        "status": "cash_pending",
        "message": _("Cash payment registered"),
        "info": _("Please bring the cash to our office or pay at our next event"),
        "contact_info": _("Contact us for payment arrangements")
    }


@frappe.whitelist()
def get_donation_status(donation_id):
    """Get donation status for tracking"""
    if not donation_id:
        return {"error": "Donation ID required"}
    
    donation = frappe.get_doc("Donation", donation_id)
    
    return {
        "donation_id": donation.name,
        "amount": donation.amount,
        "status": "Paid" if donation.paid else "Pending",
        "payment_method": donation.payment_method,
        "date": donation.date,
        "purpose": donation.get_earmarking_summary() if hasattr(donation, 'get_earmarking_summary') else donation.donation_purpose_type
    }


@frappe.whitelist()
def mark_donation_paid(donation_id, payment_reference=None):
    """Mark donation as paid (for manual processing)"""
    if not frappe.has_permission("Donation", "write"):
        return {"error": "Insufficient permissions"}
    
    donation = frappe.get_doc("Donation", donation_id)
    donation.paid = 1
    donation.payment_id = payment_reference or f"MANUAL-{frappe.utils.now()}"
    
    if hasattr(donation, 'create_payment_entry'):
        donation.create_payment_entry()
    
    donation.save()
    
    return {"success": True, "message": "Donation marked as paid"}


def get_or_create_mode_of_payment(payment_method):
    """Get or create Mode of Payment for the given payment method"""
    mode_name = payment_method
    
    # Check if mode exists
    if not frappe.db.exists("Mode of Payment", mode_name):
        # Create the mode of payment
        mode_doc = frappe.new_doc("Mode of Payment")
        mode_doc.mode_of_payment = mode_name
        mode_doc.insert(ignore_permissions=True)
        return mode_name
    
    return mode_name


@frappe.whitelist()
def test_donation_system():
    """Test the donation system components"""
    
    results = {"status": "success", "tests": []}
    
    # Test 1: Check if Donation Type doctype exists
    try:
        donation_types = frappe.get_all("Donation Type", fields=["name", "donation_type"])
        results["tests"].append({
            "name": "Donation Types",
            "status": "pass", 
            "count": len(donation_types),
            "details": [{"name": dt.name, "type": dt.donation_type} for dt in donation_types]
        })
    except Exception as e:
        results["tests"].append({
            "name": "Donation Types", 
            "status": "fail", 
            "error": str(e)
        })
    
    # Test 2: Check donor types (using hardcoded options)
    try:
        donor_types = [
            {"name": "Individual", "donor_type": "Individual"},
            {"name": "Organization", "donor_type": "Organization"}
        ]
        results["tests"].append({
            "name": "Donor Types",
            "status": "pass",
            "count": len(donor_types), 
            "details": donor_types
        })
    except Exception as e:
        results["tests"].append({
            "name": "Donor Types",
            "status": "fail", 
            "error": str(e)
        })
    
    # Test 3: Check Verenigingen Settings
    try:
        settings = frappe.get_single("Verenigingen Settings")
        results["tests"].append({
            "name": "Settings",
            "status": "pass",
            "details": {
                "default_donation_type": getattr(settings, 'default_donation_type', None),
                "default_donor_type": getattr(settings, 'default_donor_type', None),
                "anbi_minimum_amount": getattr(settings, 'anbi_minimum_reportable_amount', None),
                "chapter_management": getattr(settings, 'enable_chapter_management', None)
            }
        })
    except Exception as e:
        results["tests"].append({
            "name": "Settings",
            "status": "fail", 
            "error": str(e)
        })
    
    # Test 4: Test donation page context
    try:
        context = frappe._dict()
        get_context(context)
        results["tests"].append({
            "name": "Page Context",
            "status": "pass",
            "details": {
                "payment_methods": len(context.get('payment_methods', [])),
                "donation_types": len(context.get('donation_types', [])),
                "donor_types": len(context.get('donor_types', [])),
                "chapters": len(context.get('chapters', []))
            }
        })
    except Exception as e:
        results["tests"].append({
            "name": "Page Context",
            "status": "fail", 
            "error": str(e)
        })
    
    # Test 5: Test payment gateway components
    try:
        from verenigingen.utils.payment_gateways import PaymentGatewayFactory
        supported_methods = PaymentGatewayFactory.get_supported_methods()
        results["tests"].append({
            "name": "Payment Gateways",
            "status": "pass",
            "methods": supported_methods
        })
    except Exception as e:
        results["tests"].append({
            "name": "Payment Gateways",
            "status": "fail", 
            "error": str(e)
        })
    
    # Test 6: Test email utilities
    try:
        from verenigingen.utils.donation_emails import get_donation_email_template
        template = get_donation_email_template()
        results["tests"].append({
            "name": "Email System",
            "status": "pass",
            "has_template": bool(template.get('subject'))
        })
    except Exception as e:
        results["tests"].append({
            "name": "Email System",
            "status": "fail", 
            "error": str(e)
        })
    
    return results


@frappe.whitelist()
def test_donation_submission():
    """Test the donation submission flow with sample data"""
    
    # Sample donation data
    test_data = {
        "donor_name": "Test Donor",
        "donor_email": "test@example.com",
        "donor_phone": "+31612345678",
        "donor_type": "Individual",
        "amount": "50.00",
        "donation_type": "General",
        "donation_status": "One-time",
        "payment_method": "Bank Transfer",
        "donation_purpose_type": "General",
        "donation_notes": "Test donation from system test"
    }
    
    try:
        # Test the submission function
        result = submit_donation(**test_data)
        
        if result.get("success"):
            # Verify the donation was created
            donation_id = result.get("donation_id")
            donation = frappe.get_doc("Donation", donation_id)
            
            # Clean up the test donation
            frappe.delete_doc("Donation", donation_id)
            
            # Check if a donor was created and clean it up too
            test_donor = frappe.db.get_value("Donor", {"donor_email": "test@example.com"})
            if test_donor:
                frappe.delete_doc("Donor", test_donor)
            
            return {
                "status": "success",
                "message": "Donation submission test passed",
                "donation_created": True,
                "payment_info": result.get("payment_info", {}),
                "cleanup": "completed"
            }
        else:
            return {
                "status": "fail",
                "message": result.get("message", "Unknown error"),
                "donation_created": False
            }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "donation_created": False
        }