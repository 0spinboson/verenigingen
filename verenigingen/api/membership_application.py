import frappe
from frappe import _
from frappe.utils import today, now_datetime

# Import refactored utility modules
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

# Simple test method to verify the API is working
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

# This function is now in application_helpers.py

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
def get_application_form_data():
    """Get data needed for application form"""
    
    # Get active membership types
    membership_types = frappe.get_all(
        "Membership Type",
        filters={"is_active": 1},
        fields=["name", "membership_type_name", "description", "amount", 
                "currency", "subscription_period"],
        order_by="amount"
    )
    
    # Get public chapters (only if chapter management is enabled)
    chapters = []
    try:
        if frappe.db.get_single_value("Verenigingen Settings", "enable_chapter_management"):
            chapters = frappe.get_all(
                "Chapter",
                filters={"published": 1},
                fields=["name", "region"],
                order_by="name"
            )
    except:
        pass  # Chapter management might not be enabled
    
    # Get volunteer interest areas
    volunteer_areas = []
    try:
        volunteer_areas = frappe.get_all(
            "Volunteer Interest Area",
            fields=["name", "description"],
            order_by="name"
        )
    except:
        pass  # Table might not exist
    
    # Get countries - try ERPNext Country doctype first, then fallback
    countries = []
    try:
        countries = frappe.get_all("Country", fields=["name"], order_by="name")
    except:
        # Fallback to hardcoded list if Country doctype doesn't exist
        country_list = [
            "Netherlands", "Germany", "Belgium", "France", "United Kingdom",
            "Spain", "Italy", "Austria", "Switzerland", "Denmark", "Sweden",
            "Norway", "Finland", "Poland", "Czech Republic", "Hungary",
            "Portugal", "Ireland", "Luxembourg", "Slovenia", "Slovakia",
            "Estonia", "Latvia", "Lithuania", "Malta", "Cyprus", "Other"
        ]
        countries = [{"name": country} for country in country_list]
    
    return {
        "membership_types": membership_types,
        "chapters": chapters,
        "volunteer_areas": volunteer_areas,
        "countries": countries
    }

@frappe.whitelist(allow_guest=True)
def validate_phone_number(phone, country="Netherlands"):
    """Validate phone number format"""
    if not phone:
        return {"valid": True, "message": ""}  # Phone is optional
    
    # Remove spaces, dashes, and plus signs for validation
    clean_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
    
    # Basic phone validation patterns by country
    phone_patterns = {
        "Netherlands": r"^(31|0)[0-9]{9}$",  # Dutch mobile/landline
        "Germany": r"^(49|0)[0-9]{10,11}$",
        "Belgium": r"^(32|0)[0-9]{8,9}$"
    }
    
    pattern = phone_patterns.get(country, r"^[0-9]{8,15}$")  # Default: 8-15 digits
    
    if not re.match(pattern, clean_phone):
        return {
            "valid": False,
            "message": _("Invalid phone number format")
        }
    
    return {"valid": True, "message": _("Valid phone number")}

@frappe.whitelist(allow_guest=True)
def validate_birth_date(birth_date):
    """Validate birth date and return age information"""
    if not birth_date:
        return {"valid": False, "message": _("Birth date is required")}
    
    try:
        birth = getdate(birth_date)
        today_date = getdate(today())
        
        # Check if birth date is not in the future
        if birth > today_date:
            return {"valid": False, "message": _("Birth date cannot be in the future")}
        
        # Calculate age
        age = today_date.year - birth.year - ((today_date.month, today_date.day) < (birth.month, birth.day))
        
        # Check minimum age (optional)
        if age < 0:
            return {"valid": False, "message": _("Invalid birth date")}
        
        # Age warnings - only show for edge cases
        warnings = []
        if age < 12:
            warnings.append(_("Applicant is under 12 years old - parental consent may be required"))
        elif age > 100:
            warnings.append(_("Please verify birth date - applicant would be over 100 years old"))
        
        # Return appropriate message based on warnings
        if warnings:
            return {
                "valid": True,
                "age": age,
                "warnings": warnings,
                "message": warnings[0]  # Show the warning as the message
            }
        else:
            return {
                "valid": True,
                "age": age,
                "warnings": [],
                "message": ""  # No message for valid birth dates
            }
        
    except Exception as e:
        return {"valid": False, "message": _("Invalid date format")}

def create_crm_lead_from_application(data):
    """Create CRM Lead from application data"""
    try:
        lead = frappe.get_doc({
            "doctype": "Lead",
            "lead_name": f"{data['first_name']} {data['last_name']}",
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "email_id": data["email"],
            "mobile_no": data.get("mobile_no", ""),
            "source": "Website",  # Use a standard source
            "status": "Open",
            "type": "Client",
            "request_type": "Other"
        })
        
        # Add notes after creation to avoid field conflicts
        notes_content = "Membership Application"
        if data.get("additional_notes"):
            notes_content += f" - {data['additional_notes']}"
        
        lead.insert(ignore_permissions=True)
        
        # Update notes after successful creation
        lead.notes = notes_content
        lead.save(ignore_permissions=True)
        
        return lead
        
    except Exception as e:
        # Log the error but don't fail the entire application process
        frappe.log_error(f"Error creating CRM Lead: {str(e)}", "Lead Creation Error")
        # Return a mock lead object so the process can continue
        return type('MockLead', (), {'name': 'LEAD-ERROR'})()  # Simple object with name attribute

@frappe.whitelist(allow_guest=True)
def validate_membership_amount_selection(membership_type, amount, uses_custom):
    """Validate membership amount selection before submission"""
    try:
        mt = frappe.get_doc("Membership Type", membership_type)
        amount = float(amount)
        
        # If using custom amount, validate it's allowed and meets minimum
        if uses_custom:
            if not getattr(mt, 'allow_custom_amount', False):
                return {
                    "valid": False,
                    "message": _("Custom amounts are not allowed for this membership type")
                }
            
            minimum_amount = getattr(mt, 'minimum_amount', None) or mt.amount
            if amount < minimum_amount:
                return {
                    "valid": False,
                    "message": _("Amount must be at least {0}").format(
                        frappe.format_value(minimum_amount, {"fieldtype": "Currency"})
                    )
                }
        
        # Calculate impact
        difference = amount - mt.amount
        percentage = (difference / mt.amount) * 100 if mt.amount else 0
        
        return {
            "valid": True,
            "amount": amount,
            "standard_amount": mt.amount,
            "difference": difference,
            "percentage": percentage,
            "impact_message": get_amount_impact_message(amount, mt.amount, percentage)
        }
        
    except Exception as e:
        return {
            "valid": False,
            "message": _("Error validating amount")
        }

def get_amount_impact_message(selected_amount, standard_amount, percentage):
    """Get a friendly message about the impact of the selected amount"""
    if abs(percentage) < 1:  # Less than 1% difference
        return _("Thank you for choosing the standard membership amount!")
    elif percentage > 50:
        return _("Thank you for your generous supporter contribution! Your extra support helps us grow.")
    elif percentage > 0:
        return _("Thank you for your additional contribution to support our mission!")
    elif percentage > -25:
        return _("Thank you for joining us! We're glad to accommodate your situation.")
    else:
        return _("Thank you for joining us! Please contact us if you need any assistance.")

# Add amount formatting helper
def format_currency_for_display(amount, currency="EUR"):
    """Format currency amount for display in UI"""
    return frappe.format_value(amount, {
        "fieldtype": "Currency", 
        "options": currency
    })

@frappe.whitelist(allow_guest=True)
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

@frappe.whitelist(allow_guest=True)
def check_application_eligibility(data):
    """Check if applicant is eligible for membership"""
    import json
    
    if isinstance(data, str):
        data = json.loads(data)
    
    eligibility_issues = []
    
    # Age check
    if data.get("birth_date"):
        birth_validation = validate_birth_date(data["birth_date"])
        if not birth_validation["valid"]:
            eligibility_issues.append(birth_validation["message"])
        elif birth_validation.get("age", 0) < 12:
            eligibility_issues.append(_("Applicants under 12 require parental consent"))
    
    # Email uniqueness
    if data.get("email"):
        email_validation = validate_email(data["email"])
        if not email_validation["valid"]:
            eligibility_issues.append(email_validation["message"])
    
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
        "warnings": []
    }

def create_address_from_application(data):
    """Create address record from application data"""
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
    address.insert(ignore_permissions=True)
    return address

@frappe.whitelist()
def approve_membership_application(member_name, notes=None):
    """Approve a membership application"""
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
        "invoice": invoice.name,
        "amount": membership_type.amount
    }

@frappe.whitelist()
def reject_membership_application(member_name, reason):
    """Reject a membership application"""
    member = frappe.get_doc("Member", member_name)
    
    if member.application_status not in ["Pending", "Under Review"]:
        frappe.throw(_("This application cannot be rejected in its current state"))
    
    # Update member
    member.application_status = "Rejected"
    member.status = "Rejected"
    member.reviewed_by = frappe.session.user
    member.review_date = now_datetime()
    member.review_notes = reason
    member.save()
    
    # Update lead status
    if frappe.db.exists("Lead", {"member": member.name}):
        lead = frappe.get_doc("Lead", {"member": member.name})
        lead.status = "Do Not Contact"
        lead.save()
    
    # Send rejection email
    send_rejection_email(member, reason)
    
    return {"success": True}

def create_membership_invoice_with_amount(member, membership, amount):
    """Create invoice with specific amount (custom or standard)"""
    from verenigingen.utils import DutchTaxExemptionHandler
    
    settings = frappe.get_single("Verenigingen Settings")
    
    # Create or get customer
    if not member.customer:
        customer = create_customer_for_member(member)
        member.db_set("customer", customer.name)
    
    membership_type = frappe.get_doc("Membership Type", membership.membership_type)
    
    # Determine invoice description based on amount type
    description = f"Membership Fee - {membership_type.membership_type_name}"
    if membership.uses_custom_amount:
        if amount > membership_type.amount:
            description += " (Supporter Contribution)"
        elif amount < membership_type.amount:
            description += " (Reduced Rate)"
    
    # Create invoice
    invoice = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": member.customer,
        "member": member.name,
        "membership": membership.name,
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.add_days(frappe.utils.today(), 14),
        "items": [{
            "item_code": get_or_create_membership_item(membership_type),
            "qty": 1,
            "rate": amount,  # Use the specific amount (custom or standard)
            "description": description
        }],
        "remarks": f"Membership application invoice for {member.full_name}"
    })
    
    # Apply tax exemption if configured
    if settings.tax_exempt_for_contributions:
        try:
            handler = DutchTaxExemptionHandler()
            handler.apply_exemption_to_invoice(invoice, "EXEMPT_MEMBERSHIP")
        except Exception as e:
            frappe.log_error(f"Error applying tax exemption: {str(e)}", "Tax Exemption Error")
    
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    
    return invoice

def create_customer_for_member(member):
    """Create customer record for member"""
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": member.full_name,
        "customer_type": "Individual",
        "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual",
        "territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
        "email_id": member.email,
        "mobile_no": member.mobile_no
    })
    customer.insert(ignore_permissions=True)
    return customer

def get_or_create_membership_item(membership_type):
    """Get or create item for membership type"""
    item_code = f"MEMB-{membership_type.name}"
    
    if not frappe.db.exists("Item", item_code):
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": f"Membership - {membership_type.membership_type_name}",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "is_purchase_item": 0
        })
        item.insert()
    
    return item_code

@frappe.whitelist()
def process_application_payment(member_name, payment_method, payment_reference=None):
    """Process payment for approved application"""
    member = frappe.get_doc("Member", member_name)
    
    if member.application_status != "Approved":
        frappe.throw(_("Payment can only be processed for approved applications"))
    
    # Get the invoice
    invoice = frappe.get_doc("Sales Invoice", member.application_invoice)
    
    # Create payment entry
    payment_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": member.customer,
        "paid_amount": invoice.grand_total,
        "received_amount": invoice.grand_total,
        "target_exchange_rate": 1,
        "paid_from": frappe.db.get_value("Company", invoice.company, "default_receivable_account"),
        "paid_to": frappe.db.get_value("Mode of Payment", payment_method, "default_account"),
        "mode_of_payment": payment_method,
        "reference_no": payment_reference,
        "reference_date": today(),
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": invoice.grand_total
        }]
    })
    payment_entry.insert()
    payment_entry.submit()
    
    # Update member
    member.application_status = "Completed"
    member.application_payment_status = "Completed"
    member.application_payment_reference = payment_entry.name
    member.status = "Active"
    member.member_since = today()
    member.save()
    
    # Update membership
    membership = frappe.get_doc("Membership", {"member": member.name, "status": "Pending"})
    membership.status = "Active"
    membership.last_payment_date = today()
    membership.save()
    membership.submit()
    
    # Create volunteer record if interested
    if member.interested_in_volunteering:
        create_volunteer_record(member)
    
    # Send welcome email
    send_welcome_email(member)
    
    return {"success": True, "membership": membership.name}

def create_volunteer_record(member):
    """Create volunteer record for member"""
    volunteer = frappe.get_doc({
        "doctype": "Volunteer",
        "volunteer_name": member.full_name,
        "member": member.name,
        "email": f"{member.first_name.lower()}.{member.last_name.lower()}@volunteers.org",
        "status": "New",
        "start_date": today(),
        "commitment_level": member.volunteer_availability or "Occasional",
        "note": member.volunteer_skills or ""
    })
    
    # Add interests
    for interest in member.volunteer_interests:
        volunteer.append("interests", {"interest_area": interest.interest_area})
    
    volunteer.insert(ignore_permissions=True)
    return volunteer

# Notification functions
def send_application_confirmation_email(member, application_id):
    """Send confirmation email with application ID"""
    try:
        message = f"""
        <h3>Thank you for your membership application!</h3>
        
        <p>Dear {member.first_name},</p>
        
        <p>We have received your membership application and will review it shortly.</p>
        
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h4>Application Details:</h4>
            <ul>
                <li><strong>Application ID:</strong> {application_id}</li>
                <li><strong>Name:</strong> {member.full_name}</li>
                <li><strong>Status:</strong> Pending Review</li>
                <li><strong>Applied On:</strong> {frappe.format_datetime(member.application_date)}</li>
            </ul>
        </div>
        
        <p>You can check your application status at any time using your application ID.</p>
        
        <p>We will contact you within 2-3 business days with the next steps.</p>
        
        <p>Best regards,<br>The Membership Team</p>
        """
        
        frappe.sendmail(
            recipients=[member.email],
            subject=f"Membership Application Received - ID: {application_id}",
            message=message,
            now=True,
            reference_doctype="Member",
            reference_name=member.name
        )
    except Exception as e:
        frappe.log_error(f"Error sending confirmation email: {str(e)}", "Email Error")
def notify_reviewers_of_new_application(member, application_id):
    """Notify reviewers with application ID"""
    reviewers = get_application_reviewers(member)
    
    if reviewers:
        message = f"""
        <h3>New Membership Application: {application_id}</h3>
        
        <p>A new membership application has been submitted:</p>
        
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Application ID:</strong></td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{application_id}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Name:</strong></td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{member.full_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Email:</strong></td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{member.email}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Chapter:</strong></td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{member.primary_chapter or 'Not assigned'}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Applied On:</strong></td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{frappe.format_datetime(member.application_date)}</td>
            </tr>
        </table>
        
        <p><a href="{frappe.utils.get_url()}/app/member/{member.name}" 
             style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Review Application
        </a></p>
        """
        
        frappe.sendmail(
            recipients=reviewers,
            subject=f"New Application: {application_id} - {member.full_name}",
            message=message,
            now=True
        )
def get_application_reviewers(member):
    """Get list of reviewers for application"""
    reviewers = []
    
    # 1. Chapter board members (if chapter assigned)
    chapter = member.selected_chapter or member.suggested_chapter
    if chapter:
        chapter_doc = frappe.get_doc("Chapter", chapter)
        for board_member in chapter_doc.board_members:
            if board_member.is_active and board_member.email:
                role = frappe.get_doc("Chapter Role", board_member.chapter_role)
                if role.permissions_level in ["Admin", "Membership"]:
                    reviewers.append(board_member.email)
    
    # 2. Association Managers
    managers = frappe.db.sql("""
        SELECT u.email
        FROM `tabUser` u
        JOIN `tabHas Role` r ON r.parent = u.name
        WHERE r.role = 'Association Manager'
        AND u.enabled = 1
    """, as_dict=True)
    
    reviewers.extend([m.email for m in managers])
    
    # 3. National board if no chapter
    if not chapter:
        settings = frappe.get_single("Verenigingen Settings")
        if settings.national_board_chapter:
            national_board = frappe.get_doc("Chapter", settings.national_board_chapter)
            for board_member in national_board.board_members:
                if board_member.is_active and board_member.email:
                    reviewers.append(board_member.email)
    
    return list(set(reviewers))

# Scheduled task to check overdue applications
def check_overdue_applications():
    """Check for applications pending more than 2 weeks"""
    two_weeks_ago = add_days(today(), -14)
    
    overdue = frappe.get_all(
        "Member",
        filters={
            "application_status": "Pending",
            "application_date": ["<", two_weeks_ago]
        },
        fields=["name", "full_name", "application_date", "suggested_chapter"]
    )
    
    if overdue:
        # Notify national board
        settings = frappe.get_single("Verenigingen Settings")
        if settings.national_board_chapter:
            national_board = frappe.get_doc("Chapter", settings.national_board_chapter)
            recipients = [bm.email for bm in national_board.board_members 
                         if bm.is_active and bm.email]
            
            if recipients:
                frappe.sendmail(
                    recipients=recipients,
                    subject="Overdue Membership Applications",
                    template="membership_applications_overdue",
                    args={"applications": overdue},
                    now=True
                )

@frappe.whitelist(allow_guest=True)
def get_membership_fee_info(membership_type):
    """Get detailed fee information for a membership type"""
    if not membership_type:
        return {"error": _("Membership type is required")}
    
    try:
        mt = frappe.get_doc("Membership Type", membership_type)
        
        # Calculate prorated amount if joining mid-year
        from frappe.utils import add_months, getdate, date_diff
        
        today_date = getdate(today())
        year_start = today_date.replace(month=1, day=1)
        year_end = today_date.replace(month=12, day=31)
        
        full_amount = mt.amount
        prorated_amount = full_amount
        
        # If joining after March, calculate prorated amount
        if today_date.month > 3:  # After Q1
            remaining_months = 12 - today_date.month + 1
            prorated_amount = (full_amount / 12) * remaining_months
        
        return {
            "membership_type": mt.membership_type_name,
            "full_amount": full_amount,
            "prorated_amount": prorated_amount,
            "currency": mt.currency,
            "period": mt.subscription_period,
            "description": mt.description,
            "is_prorated": prorated_amount != full_amount,
            "join_date": today(),
            "next_renewal": year_end if mt.subscription_period == "Annual" else add_months(today(), 1)
        }
        
    except frappe.DoesNotExistError:
        return {"error": _("Membership type not found")}
    except Exception as e:
        frappe.log_error(f"Error getting membership fee info: {str(e)}")
        return {"error": _("Error calculating fees")}

@frappe.whitelist(allow_guest=True)
def validate_address(data):
    """Validate address fields"""
    import json
    
    if isinstance(data, str):
        data = json.loads(data)
    
    required_fields = ["address_line1", "city", "postal_code", "country"]
    missing_fields = []
    
    for field in required_fields:
        if not data.get(field):
            missing_fields.append(field.replace("_", " ").title())
    
    if missing_fields:
        return {
            "valid": False,
            "message": _("Missing required fields: {0}").format(", ".join(missing_fields))
        }
    
    # Validate postal code for the country
    postal_validation = validate_postal_code(data["postal_code"], data["country"])
    
    return {
        "valid": postal_validation["valid"],
        "message": postal_validation["message"],
        "suggested_chapters": postal_validation.get("suggested_chapters", [])
    }

@frappe.whitelist(allow_guest=True) 
def save_draft_application(data):
    """Save application as draft for later completion"""
    import json
    
    if isinstance(data, str):
        data = json.loads(data)
    
    # Create a temporary draft record (you might want a separate DocType for this)
    draft_key = f"draft_application_{frappe.session.sid}"
    
    # Store in cache (expires in 24 hours)
    frappe.cache().set_value(draft_key, data, expires_in_sec=86400)
    
    return {
        "success": True,
        "draft_id": draft_key,
        "message": _("Application saved as draft")
    }

@frappe.whitelist(allow_guest=True)
def load_draft_application(draft_id):
    """Load previously saved draft application"""
    
    try:
        data = frappe.cache().get_value(draft_id)
        
        if data:
            return {
                "success": True,
                "data": data,
                "message": _("Draft loaded successfully")
            }
        else:
            return {
                "success": False,
                "message": _("Draft not found or expired")
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": _("Error loading draft")
        }
@frappe.whitelist()
def get_membership_amount_info(membership_name):
    """Get detailed amount information for a membership"""
    membership = frappe.get_doc("Membership", membership_name)
    membership_type = frappe.get_doc("Membership Type", membership.membership_type)
    
    return {
        "membership_type_amount": membership_type.amount,
        "effective_amount": membership.effective_amount,
        "uses_custom_amount": membership.uses_custom_amount,
        "custom_amount": membership.custom_amount,
        "amount_reason": membership.amount_reason,
        "amount_difference": membership.amount_difference,
        "allows_custom": getattr(membership_type, 'allow_custom_amount', False),
        "minimum_amount": getattr(membership_type, 'minimum_amount', None) or membership_type.amount,
        "currency": membership_type.currency
    }

@frappe.whitelist()
def suggest_membership_amounts(membership_type_name):
    """Get suggested amounts for a membership type"""
    membership_type = frappe.get_doc("Membership Type", membership_type_name)
    
    suggestions = [membership_type.amount]  # Always include standard amount
    
    if getattr(membership_type, 'allow_custom_amount', False):
        # Add suggested amounts if configured
        if getattr(membership_type, 'suggested_amounts', None):
            try:
                suggested = [float(x.strip()) for x in membership_type.suggested_amounts.split(",") if x.strip()]
                suggestions.extend(suggested)
            except:
                pass
        
        # Add some reasonable suggestions based on standard amount
        base = membership_type.amount
        auto_suggestions = [
            base * 0.5,  # 50% (student/hardship)
            base * 1.5,  # 150% (supporter)
            base * 2.0,  # 200% (patron)
            base * 3.0   # 300% (benefactor)
        ]
        
        # Only add if they're above minimum
        minimum = getattr(membership_type, 'minimum_amount', None) or membership_type.amount
        for amount in auto_suggestions:
            if amount >= minimum and amount not in suggestions:
                suggestions.append(amount)
    
    # Remove duplicates and sort
    suggestions = sorted(list(set(suggestions)))
    
    return {
        "standard_amount": membership_type.amount,
        "minimum_amount": getattr(membership_type, 'minimum_amount', None) or membership_type.amount,
        "suggested_amounts": suggestions,
        "allows_custom": getattr(membership_type, 'allow_custom_amount', False),
        "currency": membership_type.currency
    }

# Report function for tracking custom amounts
@frappe.whitelist()
def get_custom_amount_report(from_date=None, to_date=None):
    """Generate report of memberships using custom amounts"""
    
    filters = {"uses_custom_amount": 1}
    
    if from_date:
        filters["start_date"] = [">=", from_date]
    if to_date:
        filters["start_date"] = ["<=", to_date]
    
    memberships = frappe.get_all(
        "Membership",
        filters=filters,
        fields=[
            "name", "member", "member_name", "membership_type", 
            "custom_amount", "amount_reason", "start_date", "status"
        ],
        order_by="start_date desc"
    )
    
    # Add membership type standard amounts for comparison
    for membership in memberships:
        mt = frappe.get_doc("Membership Type", membership.membership_type)
        membership["standard_amount"] = mt.amount
        membership["difference"] = membership.custom_amount - mt.amount
        membership["percentage_of_standard"] = round((membership.custom_amount / mt.amount) * 100, 1)
    
    return memberships

@frappe.whitelist(allow_guest=True)
def get_payment_methods():
    """Get available payment methods for membership applications"""
    
    # Get active payment methods from ERPNext if available
    erpnext_methods = []
    try:
        erpnext_methods = frappe.get_all(
            "Mode of Payment",
            filters={"enabled": 1},
            fields=["name", "type"],
            order_by="name"
        )
    except:
        # Mode of Payment doctype might not exist in all setups
        pass
    
    # Define membership-specific payment options with proper structure
    membership_payment_methods = [
        {
            "name": "Credit Card",
            "type": "Card",
            "description": _("Visa, Mastercard, American Express"),
            "processing_time": _("Immediate"),
            "requires_mandate": False,
            "icon": "fa-credit-card"
        },
        {
            "name": "Bank Transfer",
            "type": "Bank",
            "description": _("One-time bank transfer"),
            "processing_time": _("1-3 business days"),
            "requires_mandate": False,
            "icon": "fa-bank"
        },
        {
            "name": "Direct Debit",
            "type": "Bank",
            "description": _("SEPA Direct Debit (recurring)"),
            "processing_time": _("Immediate setup, 5-7 days first collection"),
            "requires_mandate": True,
            "icon": "fa-repeat",
            "note": _("Requires SEPA mandate setup")
        }
    ]
    
    # Merge with ERPNext methods if available
    for erpnext_method in erpnext_methods:
        # Check if we already have this method defined
        existing = next((m for m in membership_payment_methods if m["name"] == erpnext_method.name), None)
        if not existing:
            membership_payment_methods.append({
                "name": erpnext_method.name,
                "type": erpnext_method.type or "Other",
                "description": erpnext_method.name,
                "processing_time": _("Standard processing"),
                "requires_mandate": False,
                "icon": "fa-money"
            })
    
    return {
        "payment_methods": membership_payment_methods,
        "default_method": "Credit Card",
        "supports_recurring": True,
        "currency": "EUR"
    }

@frappe.whitelist(allow_guest=True)
def get_membership_type_details(membership_type):
    """Get detailed information about a membership type including custom amount options"""
    if not membership_type:
        return {"error": _("Membership type is required")}
    
    try:
        mt = frappe.get_doc("Membership Type", membership_type)
        
        # Get custom amount settings
        allow_custom = getattr(mt, 'allow_custom_amount', False)
        minimum_amount = getattr(mt, 'minimum_amount', None) or mt.amount
        
        # Calculate suggested amounts
        suggested_amounts = [mt.amount]  # Always include standard
        
        if allow_custom:
            # Add preset suggestions based on standard amount
            base = mt.amount
            suggestions = [
                {"amount": base * 0.5, "label": _("Student/Hardship (50%)")},
                {"amount": base, "label": _("Standard Amount")},
                {"amount": base * 1.5, "label": _("Supporter (150%)")},
                {"amount": base * 2.0, "label": _("Patron (200%)")},
                {"amount": base * 3.0, "label": _("Benefactor (300%)")}
            ]
            
            # Filter out suggestions below minimum
            suggestions = [s for s in suggestions if s["amount"] >= minimum_amount]
        else:
            suggestions = [{"amount": mt.amount, "label": _("Standard Amount")}]
        
        return {
            "name": mt.name,
            "membership_type_name": mt.membership_type_name,
            "description": mt.description,
            "amount": mt.amount,
            "currency": mt.currency,
            "subscription_period": mt.subscription_period,
            "allow_custom_amount": allow_custom,
            "minimum_amount": minimum_amount,
            "suggested_amounts": suggestions,
            "custom_amount_note": _("You can choose a custom amount to support our mission") if allow_custom else None
        }
        
    except frappe.DoesNotExistError:
        return {"error": _("Membership type not found")}
    except Exception as e:
        frappe.log_error(f"Error getting membership type details: {str(e)}")
        return {"error": _("Error loading membership type details")}

@frappe.whitelist(allow_guest=True)  
def validate_custom_amount(membership_type, amount):
    """Validate a custom membership amount"""
    try:
        mt = frappe.get_doc("Membership Type", membership_type)
        amount = float(amount)
        
        # Check if custom amounts are allowed
        if not getattr(mt, 'allow_custom_amount', False):
            return {
                "valid": False,
                "message": _("Custom amounts are not allowed for this membership type")
            }
        
        # Check minimum amount
        minimum_amount = getattr(mt, 'minimum_amount', None) or mt.amount
        if amount < minimum_amount:
            return {
                "valid": False,
                "message": _("Amount must be at least {0}").format(
                    frappe.format_value(minimum_amount, {"fieldtype": "Currency"})
                )
            }
        
        # Check reasonable maximum (10x standard amount)
        maximum_amount = mt.amount * 10
        if amount > maximum_amount:
            return {
                "valid": False,
                "message": _("Amount seems unusually high. Please contact us if you wish to contribute more than {0}").format(
                    frappe.format_value(maximum_amount, {"fieldtype": "Currency"})
                )
            }
        
        # Calculate difference from standard
        difference = amount - mt.amount
        percentage = (difference / mt.amount) * 100
        
        return {
            "valid": True,
            "amount": amount,
            "standard_amount": mt.amount,
            "difference": difference,
            "percentage": percentage,
            "message": _("Valid amount")
        }
        
    except Exception as e:
        return {
            "valid": False,
            "message": _("Error validating amount")
        }

def create_customer_for_member(member):
    """Create customer record for member"""
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": member.full_name,
        "customer_type": "Individual",
        "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual",
        "territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
        "email_id": member.email,
        "mobile_no": member.mobile_no
    })
    customer.insert(ignore_permissions=True)
    return customer

def send_application_confirmation_with_payment(member, invoice):
    """Send confirmation email with payment instructions"""
    try:
        # Generate payment URL
        payment_url = frappe.utils.get_url(f"/payment/membership/{member.name}/{invoice.name}")
        
        # Get membership type details
        membership_type_name = "your selected membership"
        try:
            if member.selected_membership_type:
                membership_type_doc = frappe.get_doc("Membership Type", member.selected_membership_type)
                membership_type_name = membership_type_doc.membership_type_name
        except:
            pass
        
        # Get company details
        company_name = "our association"
        try:
            company = frappe.defaults.get_global_default('company')
            if company:
                company_doc = frappe.get_doc("Company", company)
                company_name = company_doc.company_name
        except:
            pass
        
        # Prepare template arguments
        args = {
            "member": member,
            "invoice": invoice,
            "payment_url": payment_url,
            "payment_amount": invoice.grand_total,
            "company": company_name,
            "membership_type_name": membership_type_name,
            "due_date": frappe.format_date(invoice.due_date) if invoice.due_date else None,
            "application_id": member.name,
            "invoice_number": invoice.name
        }
        
        # Try to use template first
        template_sent = False
        if frappe.db.exists("Email Template", "membership_application_confirmation"):
            try:
                frappe.sendmail(
                    recipients=[member.email],
                    subject=_("Membership Application Received - Payment Required"),
                    template="membership_application_confirmation",
                    args=args,
                    now=True,
                    reference_doctype="Member",
                    reference_name=member.name
                )
                template_sent = True
                frappe.logger().info(f"Sent template confirmation email to {member.email}")
            except Exception as e:
                frappe.log_error(f"Error sending template email: {str(e)}", "Email Template Error")
                # Fall back to default email
        
        # Send default email if template failed or doesn't exist
        if not template_sent:
            # Enhanced default message with better formatting and information
            message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h2 style="color: #007bff; margin: 0;">Thank you for your membership application!</h2>
                </div>
                
                <p>Dear {member.first_name},</p>
                
                <p>We have received your membership application for <strong>{membership_type_name}</strong> and are excited to welcome you to {company_name}!</p>
                
                <div style="background: #e7f3ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #007bff; margin-top: 0;">Next Step: Complete Payment</h3>
                    <p style="margin-bottom: 10px;">To activate your membership, please complete the payment of <strong>{frappe.format_value(invoice.grand_total, {"fieldtype": "Currency"})}</strong>.</p>
                    {f'<p style="margin-bottom: 10px;"><strong>Payment Due Date:</strong> {frappe.format_date(invoice.due_date)}</p>' if invoice.due_date else ''}
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{payment_url}" 
                       style="background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        Complete Payment Now
                    </a>
                </div>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="margin-top: 0;">Application Details:</h4>
                    <ul style="margin: 0; padding-left: 20px;">
                        <li><strong>Application ID:</strong> {member.name}</li>
                        <li><strong>Invoice Number:</strong> {invoice.name}</li>
                        <li><strong>Membership Type:</strong> {membership_type_name}</li>
                        <li><strong>Amount:</strong> {frappe.format_value(invoice.grand_total, {"fieldtype": "Currency"})}</li>
                        {f'<li><strong>Chapter:</strong> {member.primary_chapter}</li>' if member.primary_chapter else ''}
                    </ul>
                </div>
                
                <p>Once your payment is processed, you will receive:</p>
                <ul>
                    <li>A welcome email with your member portal access details</li>
                    <li>Information about your local chapter activities</li>
                    <li>Access to member-only resources and events</li>
                    {f'<li>Volunteer coordinator contact (as requested)</li>' if member.interested_in_volunteering else ''}
                </ul>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <h4 style="margin-top: 0; color: #856404;">Payment Options & Information</h4>
                    <p style="margin-bottom: 10px;">You can pay using various methods including credit card, bank transfer, or SEPA direct debit.</p>
                    <p style="margin-bottom: 0;">If you experience any issues with payment, please contact us at 
                    <a href="mailto:membership@{frappe.utils.get_host_name()}" style="color: #007bff;">membership@{frappe.utils.get_host_name()}</a></p>
                </div>
                
                <p>If you have any questions about your application or membership, please don't hesitate to contact us.</p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                    <p style="margin-bottom: 5px;">Best regards,</p>
                    <p style="margin-bottom: 0;"><strong>The Membership Team</strong><br>{company_name}</p>
                </div>
                
                <div style="margin-top: 20px; padding: 10px; background: #f8f9fa; border-radius: 5px; font-size: 12px; color: #6c757d;">
                    <p style="margin: 0;">This email was sent regarding your membership application. If you did not apply for membership, please contact us immediately.</p>
                </div>
            </div>
            """
            
            try:
                frappe.sendmail(
                    recipients=[member.email],
                    subject=_("Membership Application Received - Payment Required"),
                    message=message,
                    now=True,
                    reference_doctype="Member",
                    reference_name=member.name
                )
                frappe.logger().info(f"Sent default confirmation email to {member.email}")
            except Exception as e:
                frappe.log_error(f"Error sending default confirmation email: {str(e)}", "Email Send Error")
                raise frappe.ValidationError(_("Could not send confirmation email. Please contact support."))
        
        # Log the email in member's timeline
        try:
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Member",
                "reference_name": member.name,
                "content": f"Application confirmation email sent with payment instructions. Invoice: {invoice.name}"
            }).insert(ignore_permissions=True)
        except:
            pass  # Don't fail if timeline entry fails
            
        # Also notify administrators (optional)
        try:
            notify_admins_of_new_application(member, invoice)
        except Exception as e:
            frappe.log_error(f"Error notifying admins: {str(e)}", "Admin Notification Error")
            # Don't fail the main process if admin notification fails
    
    except Exception as e:
        frappe.log_error(f"Error in send_application_confirmation_with_payment: {str(e)}", "Email Confirmation Error")
        raise frappe.ValidationError(_("Could not send confirmation email. Please contact support."))

def notify_admins_of_new_application(member, invoice):
    """Notify administrators about new membership application"""
    try:
        # Get membership managers and association managers
        admin_emails = []
        
        # Get users with Membership Manager role
        membership_managers = frappe.get_all(
            "Has Role",
            filters={"role": "Membership Manager"},
            fields=["parent"]
        )
        
        for manager in membership_managers:
            user = frappe.get_doc("User", manager.parent)
            if user.enabled and user.email:
                admin_emails.append(user.email)
        
        # Get users with Association Manager role
        association_managers = frappe.get_all(
            "Has Role", 
            filters={"role": "Association Manager"},
            fields=["parent"]
        )
        
        for manager in association_managers:
            user = frappe.get_doc("User", manager.parent)
            if user.enabled and user.email:
                admin_emails.append(user.email)
        
        # Remove duplicates
        admin_emails = list(set(admin_emails))
        
        if admin_emails:
            # Get membership type name
            membership_type_name = "Unknown"
            if member.selected_membership_type:
                try:
                    mt = frappe.get_doc("Membership Type", member.selected_membership_type)
                    membership_type_name = mt.membership_type_name
                except:
                    pass
            
            admin_message = f"""
            <h3>New Membership Application Received</h3>
            
            <p>A new membership application has been submitted and is ready for review.</p>
            
            <table style="border-collapse: collapse; width: 100%;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Applicant:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">{member.full_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Email:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">{member.email}</td>
                </tr>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Membership Type:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">{membership_type_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Amount:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">{frappe.format_value(invoice.grand_total, {"fieldtype": "Currency"})}</td>
                </tr>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Chapter:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">{member.primary_chapter or 'Not assigned'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Volunteer Interest:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">{'Yes' if member.interested_in_volunteering else 'No'}</td>
                </tr>
            </table>
            
            <p><a href="{frappe.utils.get_url()}/app/member/{member.name}" 
                 style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                Review Application
            </a></p>
            
            <p>The applicant has been sent payment instructions and will become an active member once payment is completed.</p>
            """
            
            frappe.sendmail(
                recipients=admin_emails,
                subject=f"New Membership Application: {member.full_name}",
                message=admin_message,
                now=True,
                reference_doctype="Member",
                reference_name=member.name
            )
    
    except Exception as e:
        frappe.log_error(f"Error notifying admins: {str(e)}", "Admin Notification Error")
        # Don't raise error as this is not critical

# Additional helper function for email templates
def get_payment_instructions_html(invoice, payment_url):
    """Generate HTML for payment instructions"""
    return f"""
    <div style="background: #e7f3ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <h3 style="color: #007bff; margin-top: 0;">Complete Your Payment</h3>
        <p>Amount Due: <strong>{frappe.format_value(invoice.grand_total, {"fieldtype": "Currency"})}</strong></p>
        {f'<p>Due Date: <strong>{frappe.format_date(invoice.due_date)}</strong></p>' if invoice.due_date else ''}
        <div style="text-align: center; margin: 20px 0;">
            <a href="{payment_url}" 
               style="background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                Pay Now
            </a>
        </div>
        <p><small>You can pay using credit card, bank transfer, or SEPA direct debit.</small></p>
    </div>
    """
@frappe.whitelist(allow_guest=True)
def submit_application_alt(data=None):
    """Alternative method signature for testing"""
    if data is None:
        return {"success": False, "error": "No data provided"}
    
    return submit_application(data=data)

@frappe.whitelist(allow_guest=True) 
def test_data_passing(**kwargs):
    """Test method to see how Frappe passes data"""
    return {
        "success": True,
        "received_kwargs": kwargs,
        "kwargs_keys": list(kwargs.keys()),
        "data_value": kwargs.get('data'),
        "data_type": type(kwargs.get('data')).__name__
    }

@frappe.whitelist(allow_guest=True)
def submit_application_bypass(**kwargs):
    """Completely permission-free application submission using direct SQL"""
    try:
        # Extract data
        data = kwargs.get('data')
        if isinstance(data, str):
            data = json.loads(data)
        if not data:
            data = kwargs
        
        # Validate required fields
        required = ["first_name", "last_name", "email", "birth_date"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return {
                "success": False,
                "error": f"Missing: {', '.join(missing)}",
                "message": f"Missing required fields: {', '.join(missing)}"
            }
        
        # Check if email exists using direct SQL
        existing = frappe.db.sql("""
            SELECT name FROM `tabMember` WHERE email = %s LIMIT 1
        """, (data.get("email"),))
        
        if existing:
            return {
                "success": False,
                "error": "Email already exists",
                "message": "A member with this email already exists"
            }
        
        # Generate unique member ID
        import time
        member_id = f"MEMB-{int(time.time())}-{frappe.generate_hash()[:6]}"
        now = frappe.utils.now()
        
        # Insert Member using direct SQL (bypasses ALL permissions and validations)
        frappe.db.sql("""
            INSERT INTO `tabMember` (
                name, creation, modified, modified_by, owner, docstatus,
                first_name, middle_name, last_name, full_name, email, 
                mobile_no, phone, birth_date, pronouns,
                status, application_status, application_date,
                selected_membership_type, interested_in_volunteering,
                newsletter_opt_in, application_source, notes, payment_method
            ) VALUES (
                %(name)s, %(now)s, %(now)s, 'Administrator', 'Administrator', 0,
                %(first_name)s, %(middle_name)s, %(last_name)s, %(full_name)s, %(email)s,
                %(mobile_no)s, %(phone)s, %(birth_date)s, %(pronouns)s,
                'Pending', 'Pending', %(now)s,
                %(selected_membership_type)s, %(interested_in_volunteering)s,
                %(newsletter_opt_in)s, %(application_source)s, %(notes)s, %(payment_method)s
            )
        """, {
            "name": member_id,
            "now": now,
            "first_name": data.get("first_name"),
            "middle_name": data.get("middle_name", ""),
            "last_name": data.get("last_name"),
            "full_name": f"{data.get('first_name')} {data.get('last_name')}",
            "email": data.get("email"),
            "mobile_no": data.get("mobile_no", ""),
            "phone": data.get("phone", ""),
            "birth_date": data.get("birth_date"),
            "pronouns": data.get("pronouns", ""),
            "selected_membership_type": data.get("selected_membership_type", ""),
            "interested_in_volunteering": 1 if data.get("interested_in_volunteering") else 0,
            "newsletter_opt_in": 1 if data.get("newsletter_opt_in") else 0,
            "application_source": data.get("application_source", "Website"),
            "notes": data.get("additional_notes", ""),
            "payment_method": data.get("payment_method", "")
        })
        
        # Create Address if provided
        address_id = None
        if data.get("address_line1"):
            address_id = f"ADDR-{int(time.time())}-{frappe.generate_hash()[:6]}"
            
            frappe.db.sql("""
                INSERT INTO `tabAddress` (
                    name, creation, modified, modified_by, owner, docstatus,
                    address_title, address_type, address_line1, address_line2,
                    city, state, country, pincode, email_id, phone,
                    is_primary_address
                ) VALUES (
                    %(name)s, %(now)s, %(now)s, 'Administrator', 'Administrator', 0,
                    %(address_title)s, 'Personal', %(address_line1)s, %(address_line2)s,
                    %(city)s, %(state)s, %(country)s, %(pincode)s, %(email_id)s, %(phone)s,
                    1
                )
            """, {
                "name": address_id,
                "now": now,
                "address_title": f"{data.get('first_name')} {data.get('last_name')}",
                "address_line1": data.get("address_line1"),
                "address_line2": data.get("address_line2", ""),
                "city": data.get("city"),
                "state": data.get("state", ""),
                "country": data.get("country"),
                "pincode": data.get("postal_code"),
                "email_id": data.get("email"),
                "phone": data.get("phone", "")
            })
            
            # Link address to member
            frappe.db.sql("""
                UPDATE `tabMember` SET primary_address = %s WHERE name = %s
            """, (address_id, member_id))
        
        # Commit the transaction
        frappe.db.commit()
        
        # Try to send notification email (but don't fail if it doesn't work)
        try:
            send_simple_notification(data, member_id)
        except Exception as email_error:
            frappe.log_error(f"Email notification failed: {str(email_error)}", "Email Error")
            # Don't fail the whole process for email issues
        
        return {
            "success": True,
            "message": "Application submitted successfully! You will be contacted soon.",
            "member_id": member_id,
            "status": "pending_review",
            "redirect_message": "Thank you for your application! We will review it and contact you within 2-3 business days."
        }
        
    except Exception as e:
        frappe.db.rollback()
        error_msg = str(e)
        frappe.log_error(f"Error in submit_application_bypass: {error_msg}", "Application Bypass Error")
        
        return {
            "success": False,
            "error": error_msg,
            "message": f"Application submission failed. Please try again or contact support."
        }
def send_simple_notification(data, member_id):
    """Send simple notification email"""
    try:
        # Get admin emails
        admin_emails = frappe.db.sql("""
            SELECT DISTINCT u.email 
            FROM `tabUser` u
            JOIN `tabHas Role` hr ON hr.parent = u.name
            WHERE hr.role IN ('System Manager', 'Administrator')
            AND u.enabled = 1
            AND u.email IS NOT NULL
            LIMIT 5
        """, as_dict=True)
        
        recipients = [admin.email for admin in admin_emails if admin.email]
        
        if recipients:
            subject = f"New Membership Application: {data.get('first_name')} {data.get('last_name')}"
            message = f"""
            <h3>New Membership Application Received</h3>
            <p>A new membership application has been submitted:</p>
            <ul>
                <li><strong>Name:</strong> {data.get('first_name')} {data.get('last_name')}</li>
                <li><strong>Email:</strong> {data.get('email')}</li>
                <li><strong>Member ID:</strong> {member_id}</li>
                <li><strong>Phone:</strong> {data.get('mobile_no', 'Not provided')}</li>
                <li><strong>City:</strong> {data.get('city', 'Not provided')}</li>
                <li><strong>Interested in Volunteering:</strong> {'Yes' if data.get('interested_in_volunteering') else 'No'}</li>
            </ul>
            <p>Please review this application in the system.</p>
            """
            
            frappe.sendmail(
                recipients=recipients,
                subject=subject,
                message=message,
                now=True
            )
    except Exception as e:
        # Log but don't raise - email failure shouldn't block application
        frappe.log_error(f"Notification email failed: {str(e)}", "Notification Error")


@frappe.whitelist(allow_guest=True)
def submit_application_debug(**kwargs):
    """
    Debug version of submit_application - provides detailed error information
    """
    try:
        # Log the raw input for debugging
        frappe.logger().info(f"=== SUBMISSION DEBUG START ===")
        frappe.logger().info(f"Received kwargs: {kwargs}")
        frappe.logger().info(f"Kwargs keys: {list(kwargs.keys())}")
        
        # Extract data
        data = kwargs.get('data')
        
        # If data is None, check if arguments were passed directly
        if data is None:
            data = kwargs
        
        # Handle JSON string data
        if isinstance(data, str):
            try:
                data = json.loads(data)
                frappe.logger().info(f"Parsed JSON data successfully")
            except json.JSONDecodeError as e:
                frappe.logger().error(f"JSON parse error: {str(e)}")
                return {
                    "success": False,
                    "error": f"Invalid JSON data: {str(e)}",
                    "debug_data": str(data)[:500]  # First 500 chars for debugging
                }
        
        frappe.logger().info(f"Final data type: {type(data)}")
        frappe.logger().info(f"Final data: {data}")
        
        # Validate we have data
        if not data or not isinstance(data, dict):
            return {
                "success": False,
                "error": "No valid application data received",
                "data_received": str(data),
                "data_type": str(type(data))
            }
        
        # Check required fields
        required_fields = ["first_name", "last_name", "email"]
        missing_fields = []
        for field in required_fields:
            if not data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}",
                "received_fields": list(data.keys())
            }
        
        # Test database access
        try:
            frappe.logger().info("Testing database access...")
            test_count = frappe.db.count("Member")
            frappe.logger().info(f"Current member count: {test_count}")
        except Exception as e:
            frappe.logger().error(f"Database access error: {str(e)}")
            return {
                "success": False,
                "error": f"Database access failed: {str(e)}"
            }
        
        # Check if email already exists
        try:
            existing = frappe.db.exists("Member", {"email": data.get("email")})
            if existing:
                return {
                    "success": False,
                    "error": f"A member with email {data.get('email')} already exists",
                    "existing_member": existing
                }
        except Exception as e:
            frappe.logger().error(f"Email check error: {str(e)}")
            return {
                "success": False,
                "error": f"Could not check existing email: {str(e)}"
            }
        
        # Get Member doctype meta to check available fields
        try:
            member_meta = frappe.get_meta("Member")
            available_fields = [field.fieldname for field in member_meta.fields]
            frappe.logger().info(f"Available Member fields: {available_fields}")
        except Exception as e:
            frappe.logger().error(f"Meta access error: {str(e)}")
            return {
                "success": False,
                "error": f"Could not access Member doctype: {str(e)}"
            }
        
        # Create member with only basic fields first
        try:
            frappe.logger().info("Creating member record...")
            
            # Start with absolutely minimal required fields
            member_data = {
                "doctype": "Member",
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email": data.get("email")
            }
            
            # Add optional fields if they exist in the doctype
            optional_field_mapping = {
                "middle_name": data.get("middle_name", ""),
                "mobile_no": data.get("mobile_no", ""),
                "phone": data.get("phone", ""),
                "birth_date": data.get("birth_date"),
                "pronouns": data.get("pronouns", ""),
                "status": "Pending"
            }
            
            # Only add fields that exist in the doctype
            for field_name, field_value in optional_field_mapping.items():
                if field_name in available_fields and field_value:
                    member_data[field_name] = field_value
                    frappe.logger().info(f"Added field {field_name}: {field_value}")
            
            frappe.logger().info(f"Final member data: {member_data}")
            
            # Create the member
            member = frappe.get_doc(member_data)
            member.insert(ignore_permissions=True)
            
            frappe.logger().info(f"Member created successfully: {member.name}")
            
            return {
                "success": True,
                "message": "Application submitted successfully! (Basic version)",
                "member_id": member.name,
                "debug_info": {
                    "fields_used": list(member_data.keys()),
                    "available_fields": available_fields
                }
            }
            
        except Exception as e:
            frappe.logger().error(f"Member creation error: {str(e)}")
            frappe.logger().error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": f"Could not create member: {str(e)}",
                "traceback": traceback.format_exc(),
                "attempted_data": member_data if 'member_data' in locals() else "No data"
            }
            
    except Exception as e:
        frappe.logger().error(f"=== SUBMISSION ERROR ===")
        frappe.logger().error(f"Error: {str(e)}")
        frappe.logger().error(f"Traceback: {traceback.format_exc()}")
        
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "traceback": traceback.format_exc()
        }
    finally:
        frappe.logger().info(f"=== SUBMISSION DEBUG END ===")

@frappe.whitelist(allow_guest=True)
def submit_application_minimal(**kwargs):
    """
    Minimal version that only creates basic member record
    """
    try:
        # Extract and validate data
        data = kwargs.get('data')
        if isinstance(data, str):
            data = json.loads(data)
        
        if not data or not isinstance(data, dict):
            data = kwargs
        
        # Validate required fields
        if not all(data.get(field) for field in ["first_name", "last_name", "email"]):
            return {
                "success": False,
                "error": "Missing required fields: first_name, last_name, email"
            }
        
        # Check existing email
        if frappe.db.exists("Member", {"email": data.get("email")}):
            return {
                "success": False,
                "error": "A member with this email already exists"
            }
        
        # Create minimal member record
        member = frappe.get_doc({
            "doctype": "Member",
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "mobile_no": data.get("mobile_no", ""),
            "phone": data.get("phone", ""),
            "birth_date": data.get("birth_date") if data.get("birth_date") else None,
            "status": "Active"  # Using a valid status from the Member doctype
        })
        
        member.insert(ignore_permissions=True)
        
        # Add notes about the application
        if data.get("additional_notes"):
            member.notes = f"Application notes: {data.get('additional_notes')}"
            member.save(ignore_permissions=True)
        
        return {
            "success": True,
            "message": "Application submitted successfully!",
            "member_id": member.name
        }
        
    except Exception as e:
        frappe.log_error(f"Minimal submission error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist(allow_guest=True)
def test_member_creation():
    """
    Test function to verify member creation works
    """
    try:
        # Test 1: Check if Member doctype exists and is accessible
        member_meta = frappe.get_meta("Member")
        
        # Test 2: Get field information
        fields = [{"fieldname": f.fieldname, "fieldtype": f.fieldtype, "reqd": f.reqd} 
                 for f in member_meta.fields if f.fieldname in ["first_name", "last_name", "email", "status"]]
        
        # Test 3: Try to create a test member
        test_email = f"test.{frappe.utils.random_string(5)}@example.com"
        
        test_member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Test",
            "last_name": "User",
            "email": test_email,
            "status": "Active"
        })
        
        # Don't actually insert, just validate
        test_member.run_method("validate")
        
        return {
            "success": True,
            "doctype_exists": True,
            "key_fields": fields,
            "validation_passed": True,
            "test_email": test_email
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist(allow_guest=True)
def get_member_field_info():
    """
    Get information about Member doctype fields
    """
    try:
        meta = frappe.get_meta("Member")
        fields_info = []
        
        for field in meta.fields:
            fields_info.append({
                "fieldname": field.fieldname,
                "fieldtype": field.fieldtype,
                "label": field.label,
                "reqd": field.reqd,
                "options": field.options if hasattr(field, 'options') else None
            })
        
        return {
            "success": True,
            "fields": fields_info,
            "total_fields": len(fields_info)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Enhanced version that handles address creation properly
@frappe.whitelist(allow_guest=True)
def submit_application_enhanced(**kwargs):
    """
    Enhanced version with proper error handling and field validation
    """
    try:
        # Extract and validate data
        data = kwargs.get('data')
        if isinstance(data, str):
            data = json.loads(data)
        if not data or not isinstance(data, dict):
            data = kwargs
        
        # Validate required fields
        required_fields = ["first_name", "last_name", "email"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return {
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }
        
        # Validate email format
        try:
            validate_email_address(data.get("email"))
        except Exception:
            return {
                "success": False,
                "error": "Invalid email format"
            }
        
        # Check if email already exists
        if frappe.db.exists("Member", {"email": data.get("email")}):
            return {
                "success": False,
                "error": "A member with this email already exists"
            }
        
        # Create address if address data is provided
        address = None
        if data.get("address_line1") and data.get("city"):
            try:
                address = frappe.get_doc({
                    "doctype": "Address",
                    "address_title": f"{data['first_name']} {data['last_name']}",
                    "address_type": "Personal",
                    "address_line1": data.get("address_line1"),
                    "address_line2": data.get("address_line2", ""),
                    "city": data.get("city"),
                    "state": data.get("state", ""),
                    "country": data.get("country", ""),
                    "pincode": data.get("postal_code", ""),
                    "email_id": data.get("email"),
                    "phone": data.get("phone", "")
                })
                address.insert(ignore_permissions=True)
                frappe.logger().info(f"Address created: {address.name}")
            except Exception as e:
                frappe.logger().error(f"Address creation failed: {str(e)}")
                # Continue without address if it fails
                address = None
        
        # Get available member fields
        member_meta = frappe.get_meta("Member")
        available_fields = [field.fieldname for field in member_meta.fields]
        
        # Create member with available fields only
        member_data = {
            "doctype": "Member",
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "email": data.get("email")
        }
        
        # Add optional fields if they exist
        optional_fields = {
            "middle_name": data.get("middle_name", ""),
            "mobile_no": data.get("mobile_no", ""),
            "phone": data.get("phone", ""),
            "birth_date": data.get("birth_date"),
            "pronouns": data.get("pronouns", ""),
            "status": "Active",  # Set to Active by default
            "notes": data.get("additional_notes", "")
        }
        
        # Application-specific fields (add only if they exist)
        if "application_status" in available_fields:
            member_data["application_status"] = "Pending"
        if "application_date" in available_fields:
            member_data["application_date"] = now_datetime()
        if "selected_membership_type" in available_fields:
            member_data["selected_membership_type"] = data.get("selected_membership_type", "")
        if "interested_in_volunteering" in available_fields:
            member_data["interested_in_volunteering"] = data.get("interested_in_volunteering", 0)
        if "newsletter_opt_in" in available_fields:
            member_data["newsletter_opt_in"] = data.get("newsletter_opt_in", 1)
        if "application_source" in available_fields:
            member_data["application_source"] = data.get("application_source", "Website")
        if "payment_method" in available_fields:
            member_data["payment_method"] = data.get("payment_method", "")
        if "primary_chapter" in available_fields:
            member_data["primary_chapter"] = data.get("selected_chapter", "")
        
        # Add address link if created
        if address and "primary_address" in available_fields:
            member_data["primary_address"] = address.name
        
        # Only add fields that exist and have values
        final_member_data = {k: v for k, v in member_data.items() 
                           if k == "doctype" or (k in available_fields and v is not None and v != "")}
        
        # Create member
        member = frappe.get_doc(final_member_data)
        member.insert(ignore_permissions=True)
        
        frappe.logger().info(f"Member created successfully: {member.name}")
        
        # Send simple confirmation (without complex email templates for now)
        try:
            frappe.sendmail(
                recipients=[member.email],
                subject="Membership Application Received",
                message=f"""
                <h3>Thank you for your membership application!</h3>
                <p>Dear {member.first_name},</p>
                <p>We have received your membership application and will review it shortly.</p>
                <p>Application ID: {member.name}</p>
                <p>You will receive another email once your application has been processed.</p>
                <p>Best regards,<br>The Membership Team</p>
                """,
                now=True
            )
        except Exception as e:
            frappe.logger().error(f"Email sending failed: {str(e)}")
            # Don't fail the whole process if email fails
        
        return {
            "success": True,
            "message": "Application submitted successfully! You will receive an email confirmation shortly.",
            "member_id": member.name,
            "debug_info": {
                "fields_used": list(final_member_data.keys()),
                "address_created": address is not None
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Enhanced submission error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@frappe.whitelist(allow_guest=True)
def submit_application_with_tracking(**kwargs):
    """Submit membership application with application tracking"""
    try:
        data = kwargs.get('data')
        if isinstance(data, str):
            data = json.loads(data)
        if not data or not isinstance(data, dict):
            data = kwargs
        
        # Validate required fields
        required = ["first_name", "last_name", "email"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return {"success": False, "error": f"Missing: {', '.join(missing)}"}
        
        # Check existing email
        if frappe.db.exists("Member", {"email": data.get("email")}):
            return {"success": False, "error": "Email already exists"}
        
        # Create member with application tracking
        member = frappe.get_doc({
            "doctype": "Member",
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"), 
            "email": data.get("email"),
            "mobile_no": data.get("mobile_no", ""),
            "birth_date": data.get("birth_date"),
            "status": "Pending",
            "application_status": "Pending",
            "application_date": frappe.utils.now_datetime(),
            "notes": data.get("additional_notes", "")
        })
        
        member.insert(ignore_permissions=True)
        
        # Send confirmation email
        frappe.sendmail(
            recipients=[member.email],
            subject="Application Received",
            message=f"""
            <h3>Thank you for your application!</h3>
            <p>Dear {member.first_name},</p>
            <p>Application ID: <strong>{member.application_id}</strong></p>
            <p>Status: Under Review</p>
            <p>You will hear from us within 2-3 business days.</p>
            """,
            now=True
        )
        
        return {
            "success": True,
            "message": "Application submitted successfully!",
            "application_id": member.application_id,
            "member_record": member.name,
            "status": "pending_review"
        }
        
    except Exception as e:
        frappe.log_error(str(e))
        return {"success": False, "error": str(e)}

@frappe.whitelist(allow_guest=True)
def check_application_status(application_id):
    """Check status using application ID"""
    member = frappe.db.get_value(
        "Member", 
        {"application_id": application_id},
        ["name", "full_name", "application_status", "application_date", 
         "review_date", "primary_chapter", "selected_membership_type"],
        as_dict=True
    )
    
    if not member:
        return {"found": False, "message": _("No application found with this ID")}
    
    return {
        "found": True,
        "member": member,
        "status": member.application_status,
        "can_retry_payment": member.application_status in ["Approved", "Payment Pending"]
    }
