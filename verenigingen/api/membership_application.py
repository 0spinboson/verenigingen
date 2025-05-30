import frappe
from frappe import _
from frappe.utils import today, now_datetime, add_days, getdate, flt, validate_email_address
from verenigingen.verenigingen.doctype.chapter.chapter import suggest_chapter_for_member

frappe.whitelist(allow_guest=True)
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
    
    # Get public chapters
    chapters = frappe.get_all(
        "Chapter",
        filters={"published": 1},
        fields=["name", "region"],
        order_by="name"
    )
    
    # Get volunteer interest areas
    volunteer_areas = frappe.get_all(
        "Volunteer Interest Area",
        fields=["name", "description"],
        order_by="name"
    )
    
    # Get countries
    countries = frappe.get_all("Country", fields=["name"])
    
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
        
        # Age warnings
        warnings = []
        if age < 12:
            warnings.append(_("Applicant is under 12 years old - parental consent may be required"))
        elif age > 100:
            warnings.append(_("Please verify birth date - applicant would be over 100 years old"))
        
        return {
            "valid": True,
            "age": age,
            "warnings": warnings,
            "message": _("Valid birth date")
        }
        
    except Exception as e:
        return {"valid": False, "message": _("Invalid date format")}

@frappe.whitelist(allow_guest=True)
def submit_application(data):
    """Process membership application submission"""
    import json
    
    if isinstance(data, str):
        data = json.loads(data)
    
    # Validate required fields
    required_fields = ["first_name", "last_name", "email", "birth_date", 
                      "address_line1", "city", "postal_code", "country",
                      "selected_membership_type"]
    
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_("Please fill all required fields"))
    
    # Check if member with email already exists
    existing = frappe.db.exists("Member", {"email": data.get("email")})
    if existing:
        frappe.throw(_("A member with this email already exists. Please login or contact support."))
    
    try:
        # Step 1: Create CRM Lead
        lead = create_crm_lead_from_application(data)
        
        # Step 2: Create Address
        address = create_address(data)
        
        # Step 3: Determine chapter
        suggested_chapter = None
        if data.get("selected_chapter"):
            suggested_chapter = data.get("selected_chapter")
        elif data.get("postal_code"):
            # Use existing chapter suggestion logic
            suggestion_result = suggest_chapter_for_member(
                None, 
                data.get("postal_code"),
                data.get("state"),
                data.get("city")
            )
            if suggestion_result.get("matches_by_postal"):
                suggested_chapter = suggestion_result["matches_by_postal"][0]["name"]
        
        # Step 4: Create Member with Pending status
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
            "application_date": now_datetime(),
            "selected_chapter": data.get("selected_chapter"),
            "suggested_chapter": suggested_chapter,
            "primary_chapter": suggested_chapter or data.get("selected_chapter"),
            "selected_membership_type": data.get("selected_membership_type"),
            "interested_in_volunteering": data.get("interested_in_volunteering", 0),
            "volunteer_availability": data.get("volunteer_availability", ""),
            "volunteer_skills": data.get("volunteer_skills", ""),
            "newsletter_opt_in": data.get("newsletter_opt_in", 1),
            "application_source": data.get("application_source", ""),
            "application_source_details": data.get("application_source_details", ""),
            "notes": data.get("additional_notes", "")
        })
        
        # Add volunteer interests if provided
        if data.get("volunteer_interests"):
            for interest in data.get("volunteer_interests"):
                member.append("volunteer_interests", {"interest_area": interest})
        
        member.insert(ignore_permissions=True)
        
        # Step 5: Link lead to member
        lead.db_set("member", member.name)
        
        # Step 6: Send notifications
        send_application_notifications(member)
        send_application_confirmation(member)
        
        return {
            "success": True,
            "message": _("Thank you for your application! We will review it and get back to you soon."),
            "member_id": member.name,
            "lead_id": lead.name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Membership Application Error")
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

def create_address(data):
    """Create address record"""
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

def create_membership_invoice(member, membership, membership_type):
    """Create invoice for membership"""
    from verenigingen.utils import DutchTaxExemptionHandler
    
    settings = frappe.get_single("Verenigingen Settings")
    
    # Create or get customer
    if not member.customer:
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": member.full_name,
            "customer_type": "Individual",
            "customer_group": "Member",
            "territory": "All Territories"
        })
        customer.insert()
        member.customer = customer.name
        member.save()
    
    # Create invoice
    invoice = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": member.customer,
        "member": member.name,
        "membership": membership.name,
        "posting_date": today(),
        "due_date": add_days(today(), 14),  # 14 days payment term
        "items": [{
            "item_code": get_or_create_membership_item(membership_type),
            "qty": 1,
            "rate": membership_type.amount,
            "description": f"Membership Fee - {membership_type.membership_type_name}"
        }]
    })
    
    # Apply tax exemption if configured
    if settings.tax_exempt_for_contributions:
        handler = DutchTaxExemptionHandler()
        handler.apply_exemption_to_invoice(invoice, "EXEMPT_MEMBERSHIP")
    
    invoice.insert()
    invoice.submit()
    
    return invoice

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
def get_payment_methods():
    """Get available payment methods for membership applications"""
    
    # Get active payment methods from ERPNext
    payment_methods = frappe.get_all(
        "Mode of Payment",
        filters={"enabled": 1},
        fields=["name", "type"],
        order_by="name"
    )
    
    # Add membership-specific payment options
    membership_payment_methods = [
        {
            "name": "Bank Transfer",
            "type": "Bank",
            "description": _("One-time bank transfer"),
            "processing_time": _("1-3 business days")
        },
        {
            "name": "Direct Debit",
            "type": "Bank",
            "description": _("SEPA Direct Debit (recurring)"),
            "processing_time": _("Immediate setup, 5-7 days first collection"),
            "requires_mandate": True
        },
        {
            "name": "Credit Card",
            "type": "Card",
            "description": _("Visa, Mastercard, American Express"),
            "processing_time": _("Immediate")
        }
    ]
    
    return {
        "payment_methods": membership_payment_methods,
        "default_method": "Credit Card",
        "supports_recurring": True
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
