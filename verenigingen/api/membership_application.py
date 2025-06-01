import frappe, re
from frappe import _
from frappe.utils import today, now_datetime, add_days, getdate, flt, validate_email_address
from verenigingen.verenigingen.doctype.chapter.chapter import suggest_chapter_for_member

@frappe.whitelist(allow_guest=True)
def validate_email(email):
    """Validate email format and check if it already exists"""
    if not email:
        return {"valid": False, "message": _("Email is required")}
    
    try:
        # Use Frappe's built-in email validation
        validate_email_address(email, throw=True)
        
        # Check if email already exists
        existing_member = frappe.db.exists("Member", {"email": email})
        existing_user = frappe.db.exists("User", {"email": email})
        
        if existing_member:
            return {
                "valid": False, 
                "message": _("A member with this email already exists. Please login or contact support."),
                "exists": True,
                "member_id": existing_member
            }
        
        if existing_user:
            # Check if user is linked to a member
            user_member = frappe.db.get_value("Member", {"user": existing_user}, "name")
            if user_member:
                return {
                    "valid": False,
                    "message": _("This email is already registered. Please login or contact support."),
                    "exists": True
                }
        
        return {"valid": True, "message": _("Email is available")}
        
    except Exception as e:
        return {"valid": False, "message": str(e)}

def determine_chapter_from_application(data):
    """Determine suggested chapter from application data"""
    suggested_chapter = None
    
    if data.get("selected_chapter"):
        suggested_chapter = data.get("selected_chapter")
    elif data.get("postal_code"):
        # Use existing chapter suggestion logic
        try:
            from verenigingen.verenigingen.doctype.chapter.chapter import suggest_chapter_for_member
            suggestion_result = suggest_chapter_for_member(
                None, 
                data.get("postal_code"),
                data.get("state"),
                data.get("city")
            )
            if suggestion_result.get("matches_by_postal"):
                suggested_chapter = suggestion_result["matches_by_postal"][0]["name"]
        except Exception as e:
            frappe.log_error(f"Error suggesting chapter: {str(e)}", "Chapter Suggestion Error")
    
    return suggested_chapter

@frappe.whitelist(allow_guest=True)
def validate_postal_code(postal_code, country="Netherlands"):
    """Validate postal code format and suggest chapters"""
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
    
    # Find matching chapters
    suggested_chapters = []
    try:
        from verenigingen.verenigingen.doctype.member.member import find_chapter_by_postal_code
        result = find_chapter_by_postal_code(postal_code)
        
        if result.get("success") and result.get("matching_chapters"):
            suggested_chapters = result["matching_chapters"]
    except Exception as e:
        frappe.log_error(f"Error finding chapters for postal code {postal_code}: {str(e)}")
    
    return {
        "valid": True,
        "message": _("Valid postal code"),
        "suggested_chapters": suggested_chapters
    }

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

@frappe.whitelist(allow_guest=True)
def submit_application(data):
    """Process membership application submission with custom amount support"""
    import json
    import re
    
    if isinstance(data, str):
        data = json.loads(data)
    
    # Validate required fields
    required_fields = ["first_name", "last_name", "email", "birth_date", 
                      "address_line1", "city", "postal_code", "country",
                      "selected_membership_type"]
    
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_("Please fill all required fields: {0}").format(field))
    
    # Check if member with email already exists
    existing = frappe.db.exists("Member", {"email": data.get("email")})
    if existing:
        frappe.throw(_("A member with this email already exists. Please login or contact support."))
    
    try:
        # Step 1: Validate membership type and custom amount
        membership_type_doc = frappe.get_doc("Membership Type", data.get("selected_membership_type"))
        
        # Determine final membership amount
        final_amount = membership_type_doc.amount  # Default to standard amount
        uses_custom_amount = False
        amount_reason = ""
        
        if data.get("uses_custom_amount") and data.get("membership_amount"):
            custom_amount = float(data.get("membership_amount"))
            
            # Validate custom amount if allowed
            if getattr(membership_type_doc, 'allow_custom_amount', False):
                minimum_amount = getattr(membership_type_doc, 'minimum_amount', None) or membership_type_doc.amount
                
                if custom_amount >= minimum_amount:
                    final_amount = custom_amount
                    uses_custom_amount = True
                    
                    # Generate reason based on amount difference
                    if custom_amount > membership_type_doc.amount:
                        percentage = ((custom_amount - membership_type_doc.amount) / membership_type_doc.amount) * 100
                        amount_reason = f"Supporter contribution (+{percentage:.1f}% above standard)"
                    elif custom_amount < membership_type_doc.amount:
                        percentage = ((membership_type_doc.amount - custom_amount) / membership_type_doc.amount) * 100
                        amount_reason = f"Reduced contribution (-{percentage:.1f} % from standard)"
                    else:
                        uses_custom_amount = False  # Same as standard, no need for custom flag
                else:
                    frappe.throw(_("Custom amount {0} is below minimum allowed amount {1}").format(
                        frappe.format_value(custom_amount, {"fieldtype": "Currency"}),
                        frappe.format_value(minimum_amount, {"fieldtype": "Currency"})
                    ))
            else:
                frappe.throw(_("Custom amounts are not allowed for this membership type"))
        
        # Step 2: Create CRM Lead
        lead = create_crm_lead_from_application(data)
        
        # Step 3: Create Address
        address = create_address_from_application(data)
        
        # Step 4: Determine chapter
        suggested_chapter = determine_chapter_from_application(data)
        
        # Step 5: Create Member with Pending status
        member = frappe.get_doc({
            "doctype": "Member",
            "first_name": data.get("first_name"),
            "middle_name": data.get("middle_name", ""),
            "last_name": data.get("last_name"),
            "email": data.get("email"),
            "mobile_no": data.get("mobile_no", ""),
            "phone": data.get("phone", ""),
            "birth_date": data.get("birth_date"),
            "pronouns": data.get("pronouns", ""),
            "primary_address": address.name,
            "status": "Pending",
            "application_status": "Pending",
            "application_date": frappe.utils.now_datetime(),
            "selected_chapter": data.get("selected_chapter"),
            "suggested_chapter": suggested_chapter,
            "primary_chapter": suggested_chapter or data.get("selected_chapter"),
            "selected_membership_type": data.get("selected_membership_type"),
            "interested_in_volunteering": data.get("interested_in_volunteering", 0),
            "volunteer_availability": data.get("volunteer_availability", ""),
            "volunteer_experience_level": data.get("volunteer_experience_level", ""),
            "newsletter_opt_in": data.get("newsletter_opt_in", 1),
            "application_source": data.get("application_source", ""),
            "application_source_details": data.get("application_source_details", ""),
            "notes": data.get("additional_notes", ""),
            "payment_method": data.get("payment_method", "")
        })
        
        # Add volunteer interests if provided
        if data.get("volunteer_interests"):
            for interest in data.get("volunteer_interests", []):
                member.append("volunteer_interests", {"interest_area": interest})
        
        member.insert(ignore_permissions=True)
        
        # Step 6: Create Membership record with custom amount support
        membership_data = {
            "doctype": "Membership",
            "member": member.name,
            "membership_type": data.get("selected_membership_type"),
            "start_date": frappe.utils.today(),
            "status": "Pending",  # Will become Active after payment
            "auto_renew": 1
        }
        
        # Add custom amount information if applicable
        if uses_custom_amount:
            membership_data.update({
                "uses_custom_amount": 1,
                "custom_amount": final_amount,
                "amount_reason": amount_reason
            })
        
        membership = frappe.get_doc(membership_data)
        membership.insert(ignore_permissions=True)
        
        # Step 7: Create invoice with correct amount
        invoice = create_membership_invoice_with_amount(member, membership, final_amount)
        
        # Step 8: Link everything together
        lead.db_set("member", member.name)
        member.db_set("application_invoice", invoice.name)
        
        # Step 9: Send notifications
        send_application_notifications(member)
        send_application_confirmation_with_payment(member, invoice)
        
        return {
            "success": True,
            "message": _("Thank you for your application! Please complete payment to activate your membership."),
            "member_id": member.name,
            "lead_id": lead.name,
            "invoice_id": invoice.name,
            "amount": final_amount,
            "payment_url": f"/payment/membership/{member.name}/{invoice.name}"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Membership Application Error")
        if isinstance(e, frappe.ValidationError):
            frappe.throw(str(e))
        else:
            frappe.throw(_("An error occurred while processing your application. Please try again."))

def create_crm_lead_from_application(data):
    """Create CRM Lead from application data"""
    lead = frappe.get_doc({
        "doctype": "Lead",
        "lead_name": f"{data['first_name']} {data['last_name']}",
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "email_id": data["email"],
        "mobile_no": data.get("mobile_no", ""),
        "source": "Membership Application",
        "status": "Open",
        "type": "Client",
        "request_type": "Membership Application",
        "unsubscribed": 0,  # Always subscribed to mandatory communications
        "blog_subscriber": 1 if data.get("newsletter_opt_in") else 0
    })
    lead.insert(ignore_permissions=True)
    return lead

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
def send_application_notifications(member):
    """Send notifications to reviewers"""
    reviewers = get_application_reviewers(member)
    
    if reviewers:
        frappe.sendmail(
            recipients=reviewers,
            subject=f"New Membership Application: {member.full_name}",
            template="membership_application_review_required",
            args={
                "member": member,
                "review_url": frappe.utils.get_url(f"/app/member/{member.name}")
            },
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
