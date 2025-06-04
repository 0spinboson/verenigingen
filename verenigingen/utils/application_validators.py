"""
Validation utilities for membership applications
"""
import re
import frappe
from frappe import _
from frappe.utils import getdate, today, validate_email_address
from dateutil.relativedelta import relativedelta


def validate_email(email):
    """Validate email format and check if it already exists"""
    try:
        if not email:
            return {"valid": False, "message": _("Email is required")}

        # Use Frappe's built-in email validation
        validate_email_address(email, throw=True)

        # Check if email already exists
        existing_member = frappe.db.exists("Member", {"email": email})
        if existing_member:
            return {
                "valid": False,
                "message": _("A member with this email already exists. Please login or contact support."),
                "exists": True,
                "member_id": existing_member
            }

        return {"valid": True, "message": _("Email is available")}

    except Exception as e:
        return {"valid": False, "message": str(e)}


def validate_postal_code(postal_code, country="Netherlands"):
    """Validate postal code format"""
    if not postal_code:
        return {"valid": False, "message": _("Postal code is required")}
    
    # Basic format validation based on country
    postal_patterns = {
        "Netherlands": r"^[1-9][0-9]{3}\s?[A-Z]{2}$",
        "Germany": r"^[0-9]{5}$",
        "Belgium": r"^[1-9][0-9]{3}$",
        "France": r"^[0-9]{5}$"
    }
    
    pattern = postal_patterns.get(country, r"^.+$")  # Default: any non-empty
    
    if not re.match(pattern, postal_code.upper().strip()):
        return {
            "valid": False,
            "message": _("Invalid postal code format for {0}").format(country)
        }
    
    return {"valid": True, "message": _("Valid postal code")}


def validate_phone_number(phone, country="Netherlands"):
    """Validate phone number format"""
    if not phone:
        return {"valid": True, "message": _("Phone number is optional")}
    
    # Remove spaces and common characters
    clean_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
    
    # Basic patterns for different countries
    phone_patterns = {
        "Netherlands": r"^(06|0031|31)?[0-9]{8,9}$",
        "Germany": r"^(0049|49|0)?[1-9][0-9]{7,11}$",
        "Belgium": r"^(0032|32|0)?[1-9][0-9]{7,8}$",
    }
    
    pattern = phone_patterns.get(country, r"^[0-9\+]{8,15}$")  # Default: 8-15 digits
    
    if not re.match(pattern, clean_phone):
        return {
            "valid": False,
            "message": _("Invalid phone number format for {0}").format(country)
        }
    
    return {"valid": True, "message": _("Valid phone number")}


def validate_birth_date(birth_date):
    """Validate birth date"""
    try:
        if not birth_date:
            return {"valid": False, "message": _("Birth date is required")}
        
        birth_date_obj = getdate(birth_date)
        today_date = getdate(today())
        
        # Check if date is in the future
        if birth_date_obj > today_date:
            return {
                "valid": False,
                "message": _("Birth date cannot be in the future")
            }
        
        # Calculate age
        age_delta = relativedelta(today_date, birth_date_obj)
        age = age_delta.years
        
        # Check reasonable age limits (under 120, over 0)
        if age > 120:
            return {
                "valid": False,
                "message": _("Birth date indicates unrealistic age")
            }
        
        if age < 0:
            return {
                "valid": False,
                "message": _("Invalid birth date")
            }
        
        return {
            "valid": True,
            "message": _("Valid birth date"),
            "age": age
        }
        
    except Exception as e:
        return {"valid": False, "message": _("Invalid birth date format")}


def validate_name(name, field_name="Name"):
    """Validate name fields"""
    if not name:
        return {"valid": False, "message": _(f"{field_name} is required")}
    
    # Check length
    if len(name.strip()) < 2:
        return {"valid": False, "message": _(f"{field_name} must be at least 2 characters")}
    
    if len(name.strip()) > 50:
        return {"valid": False, "message": _(f"{field_name} must be less than 50 characters")}
    
    # Check for valid characters (letters, spaces, hyphens, apostrophes)
    if not re.match(r"^[a-zA-ZÀ-ÿ\s\-\'\.]+$", name):
        return {
            "valid": False,
            "message": _(f"{field_name} can only contain letters, spaces, hyphens, and apostrophes")
        }
    
    return {"valid": True, "message": _("Valid name")}


def validate_address(data):
    """Validate address data"""
    required_fields = ["address_line1", "city", "postal_code", "country"]
    errors = []
    
    for field in required_fields:
        if not data.get(field):
            errors.append(_(f"{field.replace('_', ' ').title()} is required"))
    
    # Validate postal code format
    if data.get("postal_code") and data.get("country"):
        postal_validation = validate_postal_code(data["postal_code"], data["country"])
        if not postal_validation["valid"]:
            errors.append(postal_validation["message"])
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def validate_membership_amount_selection(membership_type, amount, uses_custom):
    """Validate membership amount selection"""
    try:
        membership_type_doc = frappe.get_doc("Membership Type", membership_type)
        standard_amount = membership_type_doc.amount
        
        # Convert to float for comparison
        amount = float(amount) if amount else 0
        standard_amount = float(standard_amount) if standard_amount else 0
        
        if uses_custom:
            # Custom amount validation
            if amount <= 0:
                return {
                    "valid": False,
                    "message": _("Custom amount must be greater than 0")
                }
            
            # Check if custom amount is reasonable (not less than 50% of standard)
            min_amount = standard_amount * 0.5
            if amount < min_amount:
                return {
                    "valid": False,
                    "message": _("Custom amount cannot be less than {0}% of standard amount ({1})").format(
                        50, frappe.utils.fmt_money(min_amount, currency="EUR")
                    )
                }
        else:
            # Standard amount validation
            if abs(amount - standard_amount) > 0.01:  # Allow for small rounding differences
                return {
                    "valid": False,
                    "message": _("Amount does not match membership type standard amount")
                }
        
        return {"valid": True, "message": _("Valid amount selection")}
        
    except Exception as e:
        return {"valid": False, "message": str(e)}


def validate_custom_amount(membership_type, amount):
    """Validate custom membership amount"""
    try:
        membership_type_doc = frappe.get_doc("Membership Type", membership_type)
        standard_amount = float(membership_type_doc.amount)
        custom_amount = float(amount)
        
        if custom_amount <= 0:
            return {
                "valid": False,
                "message": _("Amount must be greater than 0")
            }
        
        # Check minimum threshold (50% of standard)
        min_amount = standard_amount * 0.5
        if custom_amount < min_amount:
            return {
                "valid": False,
                "message": _("Minimum amount is {0}").format(frappe.utils.fmt_money(min_amount, currency="EUR"))
            }
        
        # Check if it's significantly higher than standard (flag for review)
        max_reasonable = standard_amount * 5
        warning = None
        if custom_amount > max_reasonable:
            warning = _("Amount is significantly higher than standard - will require review")
        
        return {
            "valid": True,
            "message": _("Valid custom amount"),
            "warning": warning
        }
        
    except Exception as e:
        return {"valid": False, "message": str(e)}


def check_application_eligibility(data):
    """Check if applicant is eligible for membership"""
    eligibility_issues = []
    warnings = []
    
    # Age check
    if data.get("birth_date"):
        birth_validation = validate_birth_date(data["birth_date"])
        if not birth_validation["valid"]:
            eligibility_issues.append(birth_validation["message"])
        elif birth_validation.get("age", 0) < 12:
            warnings.append(_("Applicants under 12 require parental consent"))
        elif birth_validation.get("age", 0) > 100:
            warnings.append(_("Age verification may be required"))
    
    # Email uniqueness
    if data.get("email"):
        email_validation = validate_email(data["email"])
        if not email_validation["valid"]:
            eligibility_issues.append(email_validation["message"])
    
    # Name validation
    for field, label in [("first_name", "First Name"), ("last_name", "Last Name")]:
        if data.get(field):
            name_validation = validate_name(data[field], label)
            if not name_validation["valid"]:
                eligibility_issues.append(name_validation["message"])
    
    # Address validation
    address_validation = validate_address(data)
    if not address_validation["valid"]:
        eligibility_issues.extend(address_validation["errors"])
    
    # Check if membership types are available
    available_types = frappe.get_all(
        "Membership Type",
        filters={"is_active": 1},
        fields=["name"]
    )
    
    if not available_types:
        eligibility_issues.append(_("No membership types are currently available"))
    
    return {
        "eligible": len(eligibility_issues) == 0,
        "issues": eligibility_issues,
        "warnings": warnings
    }


def validate_required_fields(data, required_fields):
    """Validate that all required fields are present and not empty"""
    missing_fields = []
    
    for field in required_fields:
        if not data.get(field) or str(data.get(field)).strip() == "":
            missing_fields.append(field.replace("_", " ").title())
    
    return {
        "valid": len(missing_fields) == 0,
        "missing_fields": missing_fields
    }