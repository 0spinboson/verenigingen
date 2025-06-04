"""
Refactored membership application API with improved organization and error handling
"""
import frappe
from frappe import _
from frappe.utils import today, now_datetime

# Import our utility modules
from verenigingen.utils.application_validators import (
    validate_email, validate_postal_code, validate_phone_number, 
    validate_birth_date, validate_name, validate_address,
    validate_membership_amount_selection, validate_custom_amount,
    check_application_eligibility, validate_required_fields
)

from verenigingen.utils.application_notifications import (
    send_application_confirmation_email, notify_reviewers_of_new_application,
    send_approval_email, send_rejection_email, send_payment_confirmation_email,
    get_application_reviewers, check_overdue_applications, notify_admins_of_new_application
)

from verenigingen.utils.application_payments import (
    create_membership_invoice_with_amount, create_customer_for_member,
    process_application_payment, get_payment_methods, get_payment_instructions_html,
    create_membership_invoice, format_currency_for_display
)

from verenigingen.utils.application_helpers import (
    generate_application_id, parse_application_data, get_form_data,
    determine_chapter_from_application, create_address_from_application,
    create_member_from_application, create_volunteer_record,
    get_membership_fee_info, get_membership_type_details,
    suggest_membership_amounts, save_draft_application, load_draft_application,
    get_member_field_info, check_application_status
)


# API Endpoints

@frappe.whitelist(allow_guest=True)
def test_connection():
    """Simple test method to verify the API is working"""
    return {
        "success": True,
        "message": "Backend connection working",
        "timestamp": frappe.utils.now(),
        "user": frappe.session.user
    }


@frappe.whitelist(allow_guest=True)
def get_application_form_data():
    """Get data needed for application form"""
    return get_form_data()


@frappe.whitelist(allow_guest=True)
def validate_email_endpoint(email):
    """Validate email format and check if it already exists"""
    return validate_email(email)


@frappe.whitelist(allow_guest=True)
def validate_postal_code_endpoint(postal_code, country="Netherlands"):
    """Validate postal code format and suggest chapters"""
    result = validate_postal_code(postal_code, country)
    
    if result["valid"]:
        # Find matching chapters
        suggested_chapters = []
        try:
            from verenigingen.verenigingen.doctype.member.member import find_chapter_by_postal_code
            chapter_result = find_chapter_by_postal_code(postal_code)
            
            if chapter_result.get("success") and chapter_result.get("matching_chapters"):
                suggested_chapters = chapter_result["matching_chapters"]
        except Exception as e:
            frappe.log_error(f"Error finding chapters for postal code {postal_code}: {str(e)}")
        
        result["suggested_chapters"] = suggested_chapters
    
    return result


@frappe.whitelist(allow_guest=True)
def validate_phone_number_endpoint(phone, country="Netherlands"):
    """Validate phone number format"""
    return validate_phone_number(phone, country)


@frappe.whitelist(allow_guest=True)
def validate_birth_date_endpoint(birth_date):
    """Validate birth date"""
    return validate_birth_date(birth_date)


@frappe.whitelist(allow_guest=True)
def validate_name_endpoint(name, field_name="Name"):
    """Validate name fields"""
    return validate_name(name, field_name)


@frappe.whitelist(allow_guest=True)
def check_application_eligibility_endpoint(data):
    """Check if applicant is eligible for membership"""
    try:
        parsed_data = parse_application_data(data)
        return check_application_eligibility(parsed_data)
    except Exception as e:
        return {
            "eligible": False,
            "issues": [str(e)],
            "warnings": []
        }


@frappe.whitelist(allow_guest=True)
def submit_application(**kwargs):
    """Process membership application submission - Main entry point"""
    try:
        with frappe.init_site(frappe.local.site):
            frappe.set_user("Administrator")
            
            # Parse and validate data
            data = parse_application_data(kwargs.get('data', kwargs))
            
            # Validate required fields
            required_fields = ["first_name", "last_name", "email", "birth_date", 
                              "address_line1", "city", "postal_code", "country"]
            
            validation_result = validate_required_fields(data, required_fields)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Missing required fields: {', '.join(validation_result['missing_fields'])}",
                    "message": f"Missing required fields: {', '.join(validation_result['missing_fields'])}"
                }
            
            # Check eligibility
            eligibility = check_application_eligibility(data)
            if not eligibility["eligible"]:
                return {
                    "success": False,
                    "error": "Application not eligible",
                    "message": "; ".join(eligibility["issues"]),
                    "issues": eligibility["issues"]
                }
            
            # Check if member with email already exists
            existing = frappe.db.exists("Member", {"email": data.get("email")})
            if existing:
                return {
                    "success": False,
                    "error": "A member with this email already exists",
                    "message": "A member with this email already exists. Please login or contact support."
                }
            
            # Generate application ID
            application_id = generate_application_id()
            
            # Create address
            address = create_address_from_application(data)
            
            # Create member
            member = create_member_from_application(data, application_id, address)
            
            # Determine suggested chapter
            suggested_chapter = determine_chapter_from_application(data)
            if suggested_chapter:
                member.suggested_chapter = suggested_chapter
                member.save()
            
            # Create volunteer record if interested
            if data.get("interested_in_volunteering"):
                create_volunteer_record(member)
            
            frappe.db.commit()
            
            # Send notifications
            try:
                send_application_confirmation_email(member, application_id)
                notify_reviewers_of_new_application(member, application_id)
            except Exception as e:
                frappe.log_error(f"Error sending notifications: {str(e)}", "Notification Error")
            
            return {
                "success": True,
                "message": "Application submitted successfully! You will receive an email with your application ID.",
                "application_id": application_id,
                "member_id": member.name,
                "status": "pending_review"
            }
            
    except Exception as e:
        frappe.db.rollback()
        error_msg = str(e)
        frappe.log_error(f"Error in submit_application: {error_msg}", "Application Submission Error")
        
        return {
            "success": False,
            "error": error_msg,
            "message": f"Application submission failed: {error_msg}"
        }
    finally:
        try:
            frappe.set_user("Guest")
        except:
            pass


@frappe.whitelist()
def approve_membership_application(member_name, notes=None):
    """Approve a membership application"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        if member.application_status not in ["Pending", "Under Review"]:
            frappe.throw(_("This application cannot be approved in its current state"))
        
        # Update member
        member.application_status = "Approved"
        member.reviewed_by = frappe.session.user
        member.review_date = now_datetime()
        if notes:
            member.review_notes = notes
        member.save()
        
        # Create membership record
        membership = frappe.get_doc({
            "doctype": "Membership",
            "member": member.name,
            "membership_type": member.selected_membership_type,
            "start_date": today(),
            "status": "Pending",  # Will become Active after payment
            "auto_renew": 1  # Default to auto-renew
        })
        membership.insert()
        
        # Get membership type details
        membership_type = frappe.get_doc("Membership Type", member.selected_membership_type)
        
        # Generate invoice
        invoice = create_membership_invoice(member, membership, membership_type)
        
        # Update member with invoice reference
        member.application_invoice = invoice.name
        member.application_payment_status = "Pending"
        member.save()
        
        # Send approval email with payment instructions
        send_approval_email(member, invoice)
        
        return {
            "success": True,
            "message": "Application approved and invoice generated",
            "invoice": invoice.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error approving application: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error approving application"
        }


@frappe.whitelist()
def reject_membership_application(member_name, reason):
    """Reject a membership application"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        if member.application_status not in ["Pending", "Under Review"]:
            frappe.throw(_("This application cannot be rejected in its current state"))
        
        # Update member
        member.application_status = "Rejected"
        member.reviewed_by = frappe.session.user
        member.review_date = now_datetime()
        member.rejection_reason = reason
        member.save()
        
        # Send rejection email
        send_rejection_email(member, reason)
        
        return {
            "success": True,
            "message": "Application rejected and notification sent"
        }
        
    except Exception as e:
        frappe.log_error(f"Error rejecting application: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error rejecting application"
        }


@frappe.whitelist()
def process_application_payment_endpoint(member_name, payment_method, payment_reference=None):
    """Process payment for approved application"""
    try:
        payment_entry = process_application_payment(member_name, payment_method, payment_reference)
        
        # Send confirmation email
        member = frappe.get_doc("Member", member_name)
        invoice = frappe.get_doc("Sales Invoice", member.application_invoice)
        send_payment_confirmation_email(member, invoice)
        
        return {
            "success": True,
            "message": "Payment processed successfully",
            "payment_entry": payment_entry.name
        }
        
    except Exception as e:
        frappe.log_error(f"Error processing payment: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error processing payment"
        }


@frappe.whitelist(allow_guest=True)
def get_membership_fee_info_endpoint(membership_type):
    """Get membership fee information"""
    return get_membership_fee_info(membership_type)


@frappe.whitelist(allow_guest=True)
def get_membership_type_details_endpoint(membership_type):
    """Get detailed membership type information"""
    return get_membership_type_details(membership_type)


@frappe.whitelist(allow_guest=True)
def suggest_membership_amounts_endpoint(membership_type_name):
    """Suggest membership amounts based on type"""
    return suggest_membership_amounts(membership_type_name)


@frappe.whitelist(allow_guest=True)
def validate_membership_amount_selection_endpoint(membership_type, amount, uses_custom):
    """Validate membership amount selection"""
    return validate_membership_amount_selection(membership_type, amount, uses_custom)


@frappe.whitelist(allow_guest=True)
def validate_custom_amount_endpoint(membership_type, amount):
    """Validate custom membership amount"""
    return validate_custom_amount(membership_type, amount)


@frappe.whitelist(allow_guest=True)
def get_payment_methods_endpoint():
    """Get available payment methods"""
    return get_payment_methods()


@frappe.whitelist(allow_guest=True)
def save_draft_application_endpoint(data):
    """Save application as draft"""
    try:
        parsed_data = parse_application_data(data)
        return save_draft_application(parsed_data)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error saving draft"
        }


@frappe.whitelist(allow_guest=True)
def load_draft_application_endpoint(draft_id):
    """Load application draft"""
    return load_draft_application(draft_id)


@frappe.whitelist(allow_guest=True)
def get_member_field_info_endpoint():
    """Get information about member fields for form generation"""
    return get_member_field_info()


@frappe.whitelist(allow_guest=True)
def check_application_status_endpoint(application_id):
    """Check the status of an application by ID"""
    return check_application_status(application_id)


# Scheduled tasks

def check_overdue_applications_task():
    """Scheduled task to check for overdue applications"""
    check_overdue_applications()


# Legacy endpoints for backward compatibility

@frappe.whitelist(allow_guest=True)
def get_application_form_data_legacy():
    """Legacy endpoint - use get_application_form_data instead"""
    return get_application_form_data()


@frappe.whitelist(allow_guest=True)
def validate_address_endpoint(data):
    """Validate address data"""
    try:
        parsed_data = parse_application_data(data)
        return validate_address(parsed_data)
    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)]
        }
