"""
Refactored membership application API with improved organization and error handling
"""
import frappe
from frappe import _
from frappe.utils import today, now_datetime
import json
from datetime import datetime, timedelta

# Import our utility modules
from verenigingen.utils.application_validators import (
    validate_email as validate_email_util, validate_postal_code as validate_postal_code_util, 
    validate_phone_number as validate_phone_number_util, validate_birth_date as validate_birth_date_util, 
    validate_name as validate_name_util, validate_address as validate_address_util,
    validate_membership_amount_selection, validate_custom_amount as validate_custom_amount_util,
    check_application_eligibility as check_application_eligibility_util, validate_required_fields
)

from verenigingen.utils.application_notifications import (
    send_application_confirmation_email, notify_reviewers_of_new_application,
    send_approval_email, send_rejection_email, send_payment_confirmation_email,
    get_application_reviewers, check_overdue_applications, notify_admins_of_new_application
)

from verenigingen.utils.application_payments import (
    create_membership_invoice_with_amount, create_customer_for_member,
    process_application_payment, get_payment_methods as get_payment_methods_util, get_payment_instructions_html,
    create_membership_invoice, format_currency_for_display
)

from verenigingen.utils.application_helpers import (
    generate_application_id, parse_application_data, get_form_data,
    determine_chapter_from_application, create_address_from_application,
    create_member_from_application, create_volunteer_record,
    get_membership_fee_info as get_membership_fee_info_util, get_membership_type_details as get_membership_type_details_util,
    suggest_membership_amounts as suggest_membership_amounts_util, 
    save_draft_application as save_draft_application_util, load_draft_application as load_draft_application_util,
    get_member_field_info, check_application_status as check_application_status_util
)


# Utility functions

def check_rate_limit(endpoint, limit_per_hour=60):
    """Check if the current user/session has exceeded rate limits"""
    try:
        # Use IP address and session for rate limiting
        client_ip = frappe.local.request.environ.get('REMOTE_ADDR', 'unknown')
        cache_key = f"rate_limit:{endpoint}:{client_ip}"
        
        current_count = frappe.cache().get(cache_key) or 0
        if current_count >= limit_per_hour:
            return False
            
        # Increment counter with 1 hour expiry
        frappe.cache().setex(cache_key, 3600, current_count + 1)
        return True
        
    except Exception:
        # If rate limiting fails, allow the request
        return True

def handle_api_error(error, context="API"):
    """Standardized API error handling"""
    error_msg = str(error)
    frappe.log_error(f"Error in {context}: {error_msg}", f"{context} Error")
    
    return {
        "success": False,
        "error": error_msg,
        "type": "server_error",
        "timestamp": frappe.utils.now(),
        "context": context
    }

# API Endpoints

@frappe.whitelist(allow_guest=True)
def test_connection():
    """Simple test method to verify the API is working"""
    return {
        "success": True,
        "message": "Backend connection working",
        "timestamp": frappe.utils.now(),
        "user": frappe.session.user,
        "version": "2.0",
        "features": [
            "form_data", "validation", "draft_save", "submission", 
            "payment_methods", "error_handling", "tracking"
        ]
    }

@frappe.whitelist(allow_guest=True)
def test_all_endpoints():
    """Test that all critical endpoints are accessible"""
    endpoints_tested = []
    try:
        # Test form data
        form_data = get_form_data()
        endpoints_tested.append({"get_form_data": "✓" if form_data.get("success") else "✗"})
        
        # Test email validation
        email_test = validate_email_util("test@example.com")
        endpoints_tested.append({"validate_email": "✓" if email_test.get("valid") else "✗"})
        
        return {
            "success": True,
            "message": "All endpoints accessible",
            "tested": endpoints_tested
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "tested": endpoints_tested
        }


@frappe.whitelist(allow_guest=True)
def get_application_form_data():
    """Get data needed for application form"""
    try:
        result = get_form_data()
        # Ensure consistent success format
        if not result.get("success"):
            result["success"] = True
        return result
    except Exception as e:
        # Enhanced error logging and fallback
        frappe.log_error(f"Error in get_form_data: {str(e)}", "Application Form Data Error")
        return {
            "success": True,
            "error": False,  # Not critical error since we have fallbacks
            "membership_types": [],
            "chapters": [],
            "volunteer_areas": [],
            "countries": [
                {"name": "Netherlands"}, {"name": "Germany"}, {"name": "Belgium"},
                {"name": "France"}, {"name": "United Kingdom"}, {"name": "Other"}
            ],
            "payment_methods": [
                {"name": "Credit Card", "description": "Visa, Mastercard, American Express"},
                {"name": "Bank Transfer", "description": "One-time bank transfer"},
                {"name": "Direct Debit", "description": "SEPA Direct Debit (recurring)"}
            ]
        }


@frappe.whitelist(allow_guest=True)
def validate_email(email):
    """Validate email format and check if it already exists"""
    try:
        # Rate limiting for validation endpoints
        if not check_rate_limit("validate_email", 30):
            return {
                "valid": False,
                "message": "Too many validation requests. Please try again later.",
                "type": "rate_limit"
            }
            
        if not email:
            return {
                "valid": False,
                "message": "Email is required",
                "type": "required"
            }
        
        result = validate_email_util(email)
        
        # Ensure consistent response format
        if not isinstance(result, dict):
            return {
                "valid": False,
                "message": "Invalid validation response",
                "type": "server_error"
            }
            
        return result
        
    except Exception as e:
        return handle_api_error(e, "Email Validation")

@frappe.whitelist(allow_guest=True)
def validate_email_endpoint(email):
    """Validate email format and check if it already exists (legacy endpoint)"""
    return validate_email(email)


@frappe.whitelist(allow_guest=True)
def validate_postal_code(postal_code, country="Netherlands"):
    """Validate postal code format and suggest chapters"""
    result = validate_postal_code_util(postal_code, country)
    
    if result["valid"]:
        # Find matching chapters
        suggested_chapters = []
        try:
            from verenigingen.verenigingen.doctype.member.member_utils import find_chapter_by_postal_code
            chapter_result = find_chapter_by_postal_code(postal_code)
            
            if chapter_result.get("success") and chapter_result.get("matching_chapters"):
                suggested_chapters = chapter_result["matching_chapters"]
        except Exception as e:
            frappe.log_error(f"Error finding chapters for postal code {postal_code}: {str(e)}")
        
        result["suggested_chapters"] = suggested_chapters
    
    return result

@frappe.whitelist(allow_guest=True)
def validate_postal_code_endpoint(postal_code, country="Netherlands"):
    """Validate postal code format and suggest chapters (legacy endpoint)"""
    return validate_postal_code(postal_code, country)


@frappe.whitelist(allow_guest=True)
def validate_phone_number(phone, country="Netherlands"):
    """Validate phone number format"""
    return validate_phone_number_util(phone, country)

@frappe.whitelist(allow_guest=True)
def validate_phone_number_endpoint(phone, country="Netherlands"):
    """Validate phone number format (legacy endpoint)"""
    return validate_phone_number(phone, country)


@frappe.whitelist(allow_guest=True)
def validate_birth_date(birth_date):
    """Validate birth date"""
    return validate_birth_date_util(birth_date)

@frappe.whitelist(allow_guest=True)
def validate_birth_date_endpoint(birth_date):
    """Validate birth date (legacy endpoint)"""
    return validate_birth_date(birth_date)


@frappe.whitelist(allow_guest=True)
def validate_name(name, field_name="Name"):
    """Validate name fields"""
    return validate_name_util(name, field_name)

@frappe.whitelist(allow_guest=True)
def validate_name_endpoint(name, field_name="Name"):
    """Validate name fields (legacy endpoint)"""
    return validate_name(name, field_name)


@frappe.whitelist(allow_guest=True)
def check_application_eligibility_endpoint(data):
    """Check if applicant is eligible for membership"""
    try:
        parsed_data = parse_application_data(data)
        return check_application_eligibility_util(parsed_data)
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
        eligibility = check_application_eligibility_util(data)
        if not eligibility["eligible"]:
            return {
                "success": False,
                "error": "Application not eligible", 
                "message": f"Validation failed: {'; '.join(eligibility['issues'])}",
                "issues": eligibility["issues"],
                "warnings": eligibility.get("warnings", [])
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
            # Use getattr to safely set chapter field, fallback to primary_chapter
            if hasattr(member, 'suggested_chapter'):
                member.suggested_chapter = suggested_chapter
            else:
                member.primary_chapter = suggested_chapter
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
            "applicant_id": getattr(member, 'application_id', None),
            "member_record": member.name,
            "status": "pending_review"
        }
        
    except Exception as e:
        frappe.db.rollback()
        
        # Get full error details
        import traceback
        error_msg = str(e)
        full_traceback = traceback.format_exc()
        
        frappe.log_error(f"Error in submit_application: {error_msg}\n\nFull traceback:\n{full_traceback}", "Application Submission Error")
        
        # Also print to console for immediate debugging
        print(f"🚨 Application submission error: {error_msg}")
        print(f"📍 Full traceback:\n{full_traceback}")
        
        return {
            "success": False,
            "error": error_msg,
            "message": f"Application submission failed: {error_msg}",
            "type": "server_error",
            "timestamp": frappe.utils.now()
        }


@frappe.whitelist()
def approve_membership_application(member_name, notes=None):
    """Approve a membership application"""
    try:
        member = frappe.get_doc("Member", member_name)
        
        if member.application_status not in ["Pending", "Under Review"]:
            frappe.throw(_("This application cannot be approved in its current state"))
        
        # Add notes if provided
        if notes:
            member.review_notes = notes
        
        # Use the new approve_application method which handles member ID assignment
        membership = member.approve_application()
        
        # Send approval email with payment instructions
        invoice = frappe.get_doc("Sales Invoice", member.application_invoice)
        send_approval_email(member, invoice)
        
        return {
            "success": True,
            "message": f"Application approved! Member ID {member.member_id} assigned and invoice {invoice.name} generated",
            "member_id": member.member_id,
            "applicant_id": getattr(member, 'application_id', None),
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
    try:
        return get_membership_fee_info_util(membership_type)
    except Exception as e:
        return handle_api_error(e, "Membership Fee Info")


@frappe.whitelist(allow_guest=True)
def get_membership_type_details_endpoint(membership_type):
    """Get detailed membership type information"""
    try:
        return get_membership_type_details_util(membership_type)
    except Exception as e:
        return handle_api_error(e, "Membership Type Details")


@frappe.whitelist(allow_guest=True)
def suggest_membership_amounts_endpoint(membership_type_name):
    """Suggest membership amounts based on type"""
    try:
        return suggest_membership_amounts_util(membership_type_name)
    except Exception as e:
        return handle_api_error(e, "Suggest Membership Amounts")


@frappe.whitelist(allow_guest=True)
def validate_membership_amount_selection_endpoint(membership_type, amount, uses_custom):
    """Validate membership amount selection"""
    return validate_membership_amount_selection(membership_type, amount, uses_custom)


@frappe.whitelist(allow_guest=True)
def validate_custom_amount_endpoint(membership_type, amount):
    """Validate custom membership amount"""
    return validate_custom_amount_util(membership_type, amount)


@frappe.whitelist(allow_guest=True)
def get_payment_methods_endpoint():
    """Get available payment methods"""
    try:
        return get_payment_methods_util()
    except Exception as e:
        return handle_api_error(e, "Payment Methods")


@frappe.whitelist(allow_guest=True)
def save_draft_application_endpoint(data):
    """Save application as draft"""
    try:
        parsed_data = parse_application_data(data)
        return save_draft_application_util(parsed_data)
    except Exception as e:
        return handle_api_error(e, "Save Draft")


@frappe.whitelist(allow_guest=True)
def load_draft_application_endpoint(draft_id):
    """Load application draft"""
    try:
        return load_draft_application_util(draft_id)
    except Exception as e:
        return handle_api_error(e, "Load Draft")


@frappe.whitelist(allow_guest=True)
def get_member_field_info_endpoint():
    """Get information about member fields for form generation"""
    return get_member_field_info()


@frappe.whitelist(allow_guest=True)
def check_application_status_endpoint(application_id):
    """Check the status of an application by ID"""
    try:
        return check_application_status_util(application_id)
    except Exception as e:
        return handle_api_error(e, "Check Application Status")


# Scheduled tasks

def check_overdue_applications_task():
    """Scheduled task to check for overdue applications"""
    check_overdue_applications()


# Test endpoint
@frappe.whitelist(allow_guest=True)
def test_submit():
    """Simple test submission function"""
    try:
        return {
            "success": True,
            "message": "Test submission working",
            "timestamp": frappe.utils.now()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Legacy endpoints for backward compatibility

# Legacy validation endpoints removed - main functions already defined above

@frappe.whitelist(allow_guest=True)
def validate_custom_amount(membership_type, amount):
    """Legacy endpoint - validate custom membership amount"""
    return validate_custom_amount_util(membership_type, amount)

@frappe.whitelist(allow_guest=True)
def save_draft_application(data):
    """Legacy endpoint - save application as draft"""
    return save_draft_application_endpoint(data)

@frappe.whitelist(allow_guest=True)
def load_draft_application(draft_id):
    """Legacy endpoint - load application draft"""
    return load_draft_application_endpoint(draft_id)

@frappe.whitelist(allow_guest=True)
def get_membership_type_details(membership_type):
    """Legacy endpoint - get detailed membership type information"""
    return get_membership_type_details_endpoint(membership_type)

@frappe.whitelist(allow_guest=True)
def get_membership_fee_info(membership_type):
    """Legacy endpoint - get membership fee information"""
    return get_membership_fee_info_endpoint(membership_type)

@frappe.whitelist(allow_guest=True)
def suggest_membership_amounts(membership_type_name):
    """Legacy endpoint - suggest membership amounts based on type"""
    return suggest_membership_amounts_endpoint(membership_type_name)

@frappe.whitelist(allow_guest=True)
def get_payment_methods():
    """Legacy endpoint - get available payment methods"""
    return get_payment_methods_endpoint()

@frappe.whitelist(allow_guest=True)
def check_application_status(application_id):
    """Legacy endpoint - check the status of an application by ID"""
    return check_application_status_endpoint(application_id)

@frappe.whitelist(allow_guest=True)
def submit_application_with_tracking(**kwargs):
    """Legacy endpoint - same as submit_application"""
    return submit_application(**kwargs)

@frappe.whitelist(allow_guest=True)
def check_application_eligibility(data):
    """Legacy endpoint - check if applicant is eligible for membership"""
    return check_application_eligibility_endpoint(data)

@frappe.whitelist(allow_guest=True)
def get_application_form_data_legacy():
    """Legacy endpoint - use get_application_form_data instead"""
    return get_application_form_data()

@frappe.whitelist(allow_guest=True)
def validate_address_endpoint(data):
    """Validate address data"""
    try:
        parsed_data = parse_application_data(data)
        return validate_address_util(parsed_data)
    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)]
        }
