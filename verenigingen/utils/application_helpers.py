"""
Helper utilities for membership application processing
"""
import json
import time
import frappe
from frappe import _
from frappe.utils import today, now_datetime, getdate, add_days
# Import moved inside function to avoid circular imports


def generate_application_id():
    """Generate unique application ID"""
    return f"APP-{frappe.utils.nowdate().replace('-', '')}-{int(time.time() % 10000):04d}"


def parse_application_data(data_input):
    """Parse and validate incoming application data"""
    if data_input is None:
        raise ValueError("No data provided")
    
    if isinstance(data_input, str):
        try:
            data = json.loads(data_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
    else:
        data = data_input
    
    return data


def get_form_data():
    """Get data needed for application form"""
    try:
        # Get active membership types
        membership_types = []
        try:
            membership_types = frappe.get_all(
                "Membership Type",
                filters={"is_active": 1},
                fields=["name", "membership_type_name", "description", "amount",
                        "currency", "subscription_period"],
                order_by="amount"
            )
        except Exception as e:
            frappe.log_error(f"Error getting membership types: {str(e)}")

        # Get countries - use a fallback list
        countries = [
            {"name": "Netherlands"}, {"name": "Germany"}, {"name": "Belgium"},
            {"name": "France"}, {"name": "United Kingdom"}, {"name": "Other"}
        ]

        # Try to get from database, fallback to hardcoded
        try:
            db_countries = frappe.get_all("Country", fields=["name"], order_by="name")
            if db_countries:
                countries = db_countries
        except Exception as e:
            frappe.log_error(f"Error getting countries: {str(e)}")
            pass  # Use fallback countries

        # Get chapters - with error handling
        chapters = []
        try:
            settings_enabled = frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management")
            if settings_enabled:
                chapters = frappe.get_all(
                    "Chapter",
                    filters={"published": 1},
                    fields=["name", "region"],
                    order_by="name"
                )
        except Exception as e:
            frappe.log_error(f"Error getting chapters: {str(e)}")
            pass  # Chapter management not enabled or error

        # Get volunteer areas - with error handling
        volunteer_areas = []
        try:
            volunteer_areas = frappe.get_all(
                "Volunteer Interest Category",
                fields=["name", "description"],
                order_by="name"
            )
        except Exception as e:
            frappe.log_error(f"Error getting volunteer areas: {str(e)}")
            pass  # Table might not exist

        return {
            "success": True,
            "membership_types": membership_types,
            "chapters": chapters,
            "volunteer_areas": volunteer_areas,
            "countries": countries
        }

    except Exception as e:
        frappe.log_error(f"Error in get_form_data: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error loading form data"
        }


def determine_chapter_from_application(data):
    """Determine suggested chapter from application data"""
    suggested_chapter = None
    
    if data.get("selected_chapter"):
        suggested_chapter = data.get("selected_chapter")
    elif data.get("postal_code"):
        # Use existing chapter suggestion logic
        try:
            # Import only when needed to avoid circular imports
            from verenigingen.verenigingen.doctype.chapter.chapter import suggest_chapter_for_member
            suggestion_result = suggest_chapter_for_member(
                None, 
                data.get("postal_code"),
                data.get("state"),
                data.get("city")
            )
            if suggestion_result.get("matches_by_postal"):
                suggested_chapter = suggestion_result["matches_by_postal"][0]["name"]
        except ImportError as e:
            frappe.log_error(f"Could not import chapter module: {str(e)}", "Chapter Import Error")
        except Exception as e:
            frappe.log_error(f"Error suggesting chapter: {str(e)}", "Chapter Suggestion Error")
    
    return suggested_chapter


def create_address_from_application(data):
    """Create address record from application data"""
    if not (data.get("address_line1") and data.get("city")):
        return None
        
    address = frappe.get_doc({
        "doctype": "Address",
        "address_title": f"{data['first_name']} {data['last_name']}",
        "address_type": "Personal",
        "address_line1": data.get("address_line1"),
        "address_line2": data.get("address_line2", ""),
        "city": data.get("city"),
        "state": data.get("state", ""),
        "country": data.get("country"),
        "pincode": data.get("postal_code"),
        "email_id": data.get("email"),
        "phone": data.get("phone", ""),
        "is_primary_address": 1
    })
    address.flags.ignore_permissions = True
    address.insert(ignore_permissions=True)
    return address


def create_member_from_application(data, application_id, address=None):
    """Create member record from application data"""
    member = frappe.get_doc({
        "doctype": "Member",
        "first_name": data.get("first_name"),
        "middle_name": data.get("middle_name", ""),
        "last_name": data.get("last_name"),
        "email": data.get("email"),
        "contact_number": data.get("contact_number", ""),
        "birth_date": data.get("birth_date"),
        "pronouns": data.get("pronouns", ""),
        "primary_address": address.name if address else None,
        "status": "Pending",
        # Application tracking fields
        "application_id": application_id,
        "application_status": "Pending",
        "application_date": now_datetime(),
        "selected_membership_type": data.get("selected_membership_type"),
        "interested_in_volunteering": data.get("interested_in_volunteering", 0),
        "newsletter_opt_in": data.get("newsletter_opt_in", 1),
        "application_source": data.get("application_source", "Website"),
        "notes": data.get("additional_notes", ""),
        "payment_method": data.get("payment_method", ""),
        "primary_chapter": data.get("selected_chapter", ""),
        # Bank details for bank transfer/direct debit
        "iban": data.get("iban", ""),
        "bic": data.get("bic", ""),
        "bank_account_name": data.get("bank_account_name", "")
    })
    
    # Handle custom membership amount using new fee override fields
    if data.get("membership_amount") or data.get("uses_custom_amount"):
        try:
            # Debug logging
            frappe.logger().info(f"Processing custom amount for application. membership_amount: {data.get('membership_amount')}, uses_custom_amount: {data.get('uses_custom_amount')}")
            
            # Safely convert membership_amount to float
            membership_amount = 0
            if data.get("membership_amount"):
                try:
                    membership_amount = float(data.get("membership_amount"))
                    frappe.logger().info(f"Converted membership_amount to: {membership_amount}")
                except (ValueError, TypeError) as e:
                    frappe.logger().error(f"Error converting membership_amount '{data.get('membership_amount')}' to float: {str(e)}")
                    membership_amount = 0
            
            # Set fee override fields if custom amount is specified
            if membership_amount > 0:
                member.membership_fee_override = membership_amount
                member.fee_override_reason = f"Custom amount selected during application: {data.get('custom_amount_reason', 'Member-specified contribution level')}"
                member.fee_override_date = today()
                
                # Use a safe fallback for fee_override_by - ensure the user exists
                override_user = None
                
                # Try current session user first
                if frappe.session.user and frappe.session.user != "Guest":
                    if frappe.db.exists("User", frappe.session.user):
                        override_user = frappe.session.user
                
                # Fallback to Administrator if it exists
                if not override_user and frappe.db.exists("User", "Administrator"):
                    override_user = "Administrator"
                
                # Final fallback - find any valid user
                if not override_user:
                    first_user = frappe.db.get_value("User", {"enabled": 1}, "name")
                    if first_user:
                        override_user = first_user
                
                # Only set the field if we found a valid user
                if override_user:
                    member.fee_override_by = override_user
                else:
                    # Log warning but don't fail - just skip the fee override fields
                    frappe.log_error("No valid user found for fee_override_by field", "Fee Override User Error")
                    member.membership_fee_override = None
                    member.fee_override_reason = None
                    member.fee_override_date = None
            
            # Store legacy data in notes for audit purposes
            custom_amount_data = {
                "membership_amount": membership_amount,
                "uses_custom_amount": bool(data.get("uses_custom_amount", False))
            }
            
            # Only store if there's actually custom amount data
            if membership_amount > 0 or custom_amount_data["uses_custom_amount"]:
                existing_notes = member.notes or ""
                if existing_notes:
                    existing_notes += "\n\n"
                
                member.notes = existing_notes + f"Custom Amount Data: {json.dumps(custom_amount_data)}"
        except Exception as e:
            # Log the error for debugging but don't fail the submission
            frappe.log_error(f"Error storing custom amount data: {str(e)}", "Custom Amount Storage Error")
            pass
    
    member.flags.ignore_permissions = True
    member.insert(ignore_permissions=True)
    return member


def create_volunteer_record(member):
    """Create volunteer record if member is interested"""
    if not member.interested_in_volunteering:
        return None
        
    try:
        volunteer = frappe.get_doc({
            "doctype": "Volunteer",
            "member": member.name,
            "email": member.email,
            "first_name": member.first_name,
            "last_name": member.last_name,
            "status": "Pending",
            "available": 1,
            "date_joined": today()
        })
        volunteer.insert(ignore_permissions=True)
        return volunteer
    except Exception as e:
        frappe.log_error(f"Error creating volunteer record: {str(e)}")
        return None


def get_membership_fee_info(membership_type):
    """Get membership fee information"""
    try:
        membership_type_doc = frappe.get_doc("Membership Type", membership_type)
        
        return {
            "success": True,
            "membership_type": membership_type,
            "standard_amount": membership_type_doc.amount,
            "currency": membership_type_doc.currency or "EUR",
            "description": membership_type_doc.description,
            "subscription_period": membership_type_doc.subscription_period
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error retrieving membership fee information"
        }


def get_membership_type_details(membership_type):
    """Get detailed membership type information"""
    try:
        membership_type_doc = frappe.get_doc("Membership Type", membership_type)
        
        # Calculate suggested amounts (if custom amounts allowed)
        suggested_amounts = []
        base_amount = float(membership_type_doc.amount)
        
        # Standard amount
        suggested_amounts.append({
            "amount": base_amount,
            "label": "Standard",
            "description": "Standard membership fee"
        })
        
        # Supporter amounts
        for multiplier, label in [(1.5, "Supporter"), (2.0, "Patron"), (3.0, "Benefactor")]:
            suggested_amounts.append({
                "amount": base_amount * multiplier,
                "label": label,
                "description": f"Support our mission with {int((multiplier - 1) * 100)}% extra"
            })
        
        return {
            "success": True,
            "name": membership_type_doc.name,
            "membership_type_name": membership_type_doc.membership_type_name,
            "description": membership_type_doc.description,
            "amount": membership_type_doc.amount,
            "currency": membership_type_doc.currency or "EUR",
            "subscription_period": membership_type_doc.subscription_period,
            "allow_custom_amount": True,  # Enable custom amounts for all membership types
            "minimum_amount": membership_type_doc.amount * 0.5,  # 50% of standard amount
            "maximum_amount": membership_type_doc.amount * 5,    # 5x standard amount
            "custom_amount_note": "You can adjust your contribution amount. Minimum is 50% of standard fee.",
            "suggested_amounts": suggested_amounts
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Error retrieving membership type details"
        }


def get_member_custom_amount_data(member):
    """Extract custom amount data from member notes"""
    try:
        import re
        
        if not hasattr(member, 'notes') or not member.notes:
            return None
            
        # Look for JSON data in notes - make pattern more specific
        pattern = r'Custom Amount Data: (\{[^}]*\})'
        match = re.search(pattern, member.notes, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
            
        return None
    except Exception as e:
        # Log error for debugging but don't fail
        frappe.log_error(f"Error parsing custom amount data: {str(e)}", "Custom Amount Parse Error")
        return None


def get_amount_impact_message(selected_amount, standard_amount, percentage):
    """Get message about amount impact"""
    if percentage > 100:
        extra_percentage = percentage - 100
        return f"Your {extra_percentage}% contribution helps fund additional programs and services."
    elif percentage < 100:
        reduction_percentage = 100 - percentage
        return f"Reduced rate ({reduction_percentage}% discount) - thank you for joining us!"
    else:
        return "Standard membership fee."


def suggest_membership_amounts(membership_type_name):
    """Suggest membership amounts based on type"""
    try:
        membership_type = frappe.get_doc("Membership Type", membership_type_name)
        base_amount = float(membership_type.amount)
        currency = membership_type.currency or "EUR"
        
        suggestions = [
            {
                "amount": base_amount,
                "label": _("Standard"),
                "description": _("Standard membership fee"),
                "percentage": 100,
                "is_default": True
            },
            {
                "amount": base_amount * 1.25,
                "label": _("Supporter"),
                "description": _("Support our mission with 25% extra"),
                "percentage": 125
            },
            {
                "amount": base_amount * 1.5,
                "label": _("Advocate"),
                "description": _("Help us grow with 50% extra"),
                "percentage": 150
            },
            {
                "amount": base_amount * 2,
                "label": _("Champion"),
                "description": _("Be a champion with 100% extra"),
                "percentage": 200
            }
        ]
        
        # Format amounts
        for suggestion in suggestions:
            suggestion["formatted_amount"] = frappe.utils.fmt_money(suggestion["amount"], currency=currency)
            suggestion["impact_message"] = get_amount_impact_message(
                suggestion["amount"], base_amount, suggestion["percentage"]
            )
        
        return {
            "success": True,
            "base_amount": base_amount,
            "currency": currency,
            "suggestions": suggestions
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestions": []
        }


def save_draft_application(data):
    """Save application as draft"""
    try:
        draft_id = f"DRAFT-{int(time.time())}"
        
        # Store in cache for 24 hours
        frappe.cache().set_value(
            f"application_draft:{draft_id}",
            json.dumps(data),
            expires_in_sec=86400  # 24 hours
        )
        
        return {
            "success": True,
            "draft_id": draft_id,
            "message": _("Draft saved successfully")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": _("Error saving draft")
        }


def load_draft_application(draft_id):
    """Load application draft"""
    try:
        draft_data = frappe.cache().get_value(f"application_draft:{draft_id}")
        
        if not draft_data:
            return {
                "success": False,
                "message": _("Draft not found or expired")
            }
        
        return {
            "success": True,
            "data": json.loads(draft_data),
            "message": _("Draft loaded successfully")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": _("Error loading draft")
        }


def get_member_field_info():
    """Get information about member fields for form generation"""
    try:
        member_meta = frappe.get_meta("Member")
        field_info = {}
        
        for field in member_meta.fields:
            if field.fieldname in ["first_name", "last_name", "email", "birth_date", "contact_number"]:
                field_info[field.fieldname] = {
                    "label": field.label,
                    "fieldtype": field.fieldtype,
                    "reqd": field.reqd,
                    "description": field.description
                }
        
        return {
            "success": True,
            "fields": field_info
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fields": {}
        }


def check_application_status(application_id):
    """Check the status of an application by ID"""
    try:
        member = frappe.get_value(
            "Member",
            {"application_id": application_id},
            ["name", "application_status", "application_date", "full_name", "email"],
            as_dict=True
        )
        
        if not member:
            return {
                "success": False,
                "message": _("Application not found")
            }
        
        return {
            "success": True,
            "application_id": application_id,
            "status": member.application_status,
            "applicant_name": member.full_name,
            "application_date": member.application_date,
            "member_id": member.name
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": _("Error checking application status")
        }