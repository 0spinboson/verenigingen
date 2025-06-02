"""
Payment processing for membership applications
"""

import frappe
from frappe import _
from frappe.utils import today, now_datetime, getdate, flt, add_days
from verenigingen.utils import DutchTaxExemptionHandler

@frappe.whitelist(allow_guest=True)
def process_application_payment(payment_id, payment_reference, payment_status, payment_data=None):
    """
    Process payment callback from payment gateway
    Args:
        payment_id: Internal payment request ID
        payment_reference: External payment gateway reference
        payment_status: Status from payment gateway (success/failed/cancelled)
        payment_data: Additional payment data from gateway
    """
    try:
        # Parse payment ID to get member and invoice
        parts = payment_id.split("-")
        if len(parts) < 3:
            frappe.throw(_("Invalid payment ID"))
        
        member_name = parts[1]
        invoice_name = parts[2]
        
        # Validate member and invoice
        if not frappe.db.exists("Member", member_name):
            frappe.throw(_("Invalid member reference"))
        
        if not frappe.db.exists("Sales Invoice", invoice_name):
            frappe.throw(_("Invalid invoice reference"))
        
        member = frappe.get_doc("Member", member_name)
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Process based on payment status
        if payment_status == "success":
            return process_successful_payment(member, invoice, payment_reference, payment_data)
        elif payment_status == "failed":
            return process_failed_payment(member, invoice, payment_reference)
        elif payment_status == "cancelled":
            return process_cancelled_payment(member, invoice)
        else:
            frappe.throw(_("Unknown payment status: {0}").format(payment_status))
            
    except Exception as e:
        frappe.log_error(f"Payment processing error: {str(e)}", "Payment Processing Error")
        return {
            "success": False,
            "message": str(e)
        }

def process_successful_payment(member, invoice, payment_reference, payment_data=None):
    """Process successful payment and activate membership"""
    
    frappe.db.begin()
    
    try:
        # Step 1: Create Payment Entry
        payment_entry = create_payment_entry(member, invoice, payment_reference, payment_data)
        
        # Step 2: Update Member status to Active (both regular and application status)
        member.application_status = "Active"
        member.status = "Active"
        member.member_since = today()
        member.payment_date = now_datetime()
        member.application_payment = payment_entry.name
        member.save()
        
        # Step 3: Get and activate the Membership
        membership = frappe.get_doc("Membership", {"member": member.name, "status": "Draft"})
        membership.status = "Active"
        membership.last_payment_date = today()
        
        # Set renewal date based on membership type
        membership_type = frappe.get_doc("Membership Type", membership.membership_type)
        if membership_type.subscription_period == "Annual":
            membership.renewal_date = add_days(membership.start_date, 365)
        elif membership_type.subscription_period == "Monthly":
            membership.renewal_date = add_days(membership.start_date, 30)
        elif membership_type.subscription_period == "Quarterly":
            membership.renewal_date = add_days(membership.start_date, 90)
        elif membership_type.subscription_period == "Biannual":
            membership.renewal_date = add_days(membership.start_date, 182)
        elif membership_type.subscription_period == "Custom" and membership_type.subscription_period_in_months:
            membership.renewal_date = add_days(membership.start_date, 
                                             membership_type.subscription_period_in_months * 30)
        
        membership.save()
        membership.submit()
        
        # Step 4: Create Volunteer record if interested
        if member.interested_in_volunteering:
            volunteer = create_volunteer_from_member(member)
        
        # Step 5: Update CRM Lead status
        if frappe.db.exists("Lead", {"member": member.name}):
            lead = frappe.get_doc("Lead", {"member": member.name})
            lead.status = "Converted"
            lead.save()
        
        # Step 6: Send notifications
        send_payment_success_notifications_with_app_id(member, membership, payment_entry)
        
        # Step 7: Add member to chapter if assigned
        if member.primary_chapter:
            add_member_to_chapter(member)
        
        # Log the payment and activation
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Member",
            "reference_name": member.name,
            "content": f"Application {member.application_id} payment received and membership activated"
        }).insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("Payment processed successfully. Welcome to our association!"),
            "application_id": member.application_id,
            "membership": membership.name,
            "redirect_url": f"/members/{member.name}"
        }
        
    except Exception as e:
        frappe.db.rollback()
        raise e

def create_payment_entry(member, invoice, payment_reference, payment_data=None):
    """Create payment entry for successful payment"""
    
    # Get payment account based on payment method
    settings = frappe.get_single("Verenigingen Settings")
    payment_account = settings.membership_payment_account
    if not payment_account:
        payment_account = frappe.db.get_value("Company", invoice.company, "default_cash_account")
    
    payment_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": invoice.customer,
        "paid_amount": invoice.grand_total,
        "received_amount": invoice.grand_total,
        "target_exchange_rate": 1,
        "paid_from": frappe.db.get_value("Company", invoice.company, "default_receivable_account"),
        "paid_to": payment_account,
        "mode_of_payment": "Online Payment",  # Or get from payment_data
        "reference_no": payment_reference,
        "reference_date": today(),
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": invoice.grand_total
        }],
        "remarks": f"Payment for membership application - {member.full_name}"
    })
    
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    return payment_entry

def create_volunteer_from_member(member):
    """Create volunteer record from member application data"""
    
    # Generate volunteer email
    settings = frappe.get_single("Verenigingen Settings")
    org_domain = settings.organization_email_domain or "volunteers.org"
    volunteer_email = f"{member.first_name.lower()}.{member.last_name.lower()}@{org_domain}"
    
    # Ensure unique email
    counter = 1
    while frappe.db.exists("Volunteer", {"email": volunteer_email}):
        volunteer_email = f"{member.first_name.lower()}.{member.last_name.lower()}{counter}@{org_domain}"
        counter += 1
    
    volunteer = frappe.get_doc({
        "doctype": "Volunteer",
        "volunteer_name": member.full_name,
        "member": member.name,
        "email": volunteer_email,
        "status": "New",
        "start_date": today(),
        "commitment_level": member.volunteer_availability or "Occasional",
        "experience_level": member.volunteer_experience_level or "Beginner",
        "preferred_work_style": "Hybrid"  # Default
    })
    
    # Copy volunteer interests from member
    if hasattr(member, 'volunteer_interests') and member.volunteer_interests:
        for interest in member.volunteer_interests:
            volunteer.append("interests", {
                "interest_area": interest.interest_area
            })
    
    # Copy volunteer skills from member
    if hasattr(member, 'volunteer_skills') and member.volunteer_skills:
        for skill in member.volunteer_skills:
            volunteer.append("skills_and_qualifications", {
                "skill_category": skill.get("skill_category"),
                "skill_name": skill.skill_name,
                "proficiency_level": skill.get("proficiency_level", "Beginner"),
                "years_experience": skill.get("years_experience", 0)
            })
    
    volunteer.insert(ignore_permissions=True)
    
    # Send volunteer onboarding email
    send_volunteer_welcome_email(volunteer)
    
    return volunteer

def add_member_to_chapter(member):
    """Add member to their assigned chapter"""
    if not member.primary_chapter:
        return
    
    chapter = frappe.get_doc("Chapter", member.primary_chapter)
    
    # Check if already a member
    for chapter_member in chapter.members:
        if chapter_member.member == member.name:
            # Already in chapter, just ensure enabled
            chapter_member.enabled = 1
            chapter.save()
            return
    
    # Add new member to chapter
    chapter.append("members", {
        "member": member.name,
        "member_name": member.full_name,
        "enabled": 1
    })
    chapter.save()

def send_payment_success_notifications_with_app_id(member, membership, payment_entry):
    """Send notifications after successful payment with application ID"""
    
    # Send welcome email to member
    send_welcome_email_to_member_with_app_id(member, membership)
    
    # Notify chapter board if member joined a chapter
    if member.primary_chapter:
        notify_chapter_of_new_member_with_app_id(member)
    
    # Send payment receipt
    send_payment_receipt_with_app_id(member, payment_entry)

def send_welcome_email_to_member_with_app_id(member, membership):
    """Send welcome email with application ID reference"""
    try:
        membership_type = frappe.get_doc("Membership Type", membership.membership_type)
        
        message = f"""
        <h2>Welcome to our Association, {member.first_name}!</h2>
        
        <p>Your membership application (ID: <strong>{member.application_id}</strong>) has been completed and your payment has been processed successfully.</p>
        
        <p><strong>Membership Details:</strong></p>
        <ul>
            <li>Member ID: {member.name}</li>
            <li>Application ID: {member.application_id}</li>
            <li>Membership Type: {membership_type.membership_type_name}</li>
            <li>Valid From: {membership.start_date}</li>
            <li>Valid Until: {membership.renewal_date}</li>
        </ul>
        
        <p>You can access your member portal at: <a href="{frappe.utils.get_url()}/members/{member.name}">Member Portal</a></p>
        
        <p>Best regards,<br>The Membership Team</p>
        """
        
        frappe.sendmail(
            recipients=[member.email],
            subject=f"Welcome! Application {member.application_id} Complete",
            message=message,
            now=True
        )
    except Exception as e:
        frappe.log_error(f"Error sending welcome email: {str(e)}")

def send_volunteer_welcome_email(volunteer):
    """Send welcome email to new volunteer"""
    try:
        if frappe.db.exists("Email Template", "volunteer_welcome"):
            frappe.sendmail(
                recipients=[volunteer.email],
                subject=_("Welcome to our Volunteer Team!"),
                template="volunteer_welcome",
                args={"volunteer": volunteer},
                now=True
            )
    except Exception as e:
        frappe.log_error(f"Error sending volunteer welcome email: {str(e)}")

def notify_chapter_of_new_member(member):
    """Notify chapter board of new member"""
    try:
        chapter = frappe.get_doc("Chapter", member.primary_chapter)
        
        # Get board members with membership permissions
        recipients = []
        for board_member in chapter.board_members:
            if board_member.is_active and board_member.email:
                role = frappe.get_doc("Chapter Role", board_member.chapter_role)
                if role.permissions_level in ["Admin", "Membership"]:
                    recipients.append(board_member.email)
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("New Member Joined: {0}").format(member.full_name),
                message=f"""
                <p>A new member has joined your chapter:</p>
                <ul>
                    <li>Name: {member.full_name}</li>
                    <li>Email: {member.email}</li>
                    <li>Membership Type: {member.selected_membership_type}</li>
                    <li>Interested in Volunteering: {'Yes' if member.interested_in_volunteering else 'No'}</li>
                </ul>
                <p><a href="{frappe.utils.get_url()}/app/member/{member.name}">View Member Profile</a></p>
                """,
                now=True
            )
    except Exception as e:
        frappe.log_error(f"Error notifying chapter: {str(e)}")

def send_payment_receipt(member, payment_entry):
    """Send payment receipt to member"""
    try:
        # Get invoice details
        invoice_ref = payment_entry.references[0]
        invoice = frappe.get_doc("Sales Invoice", invoice_ref.reference_name)
        
        frappe.sendmail(
            recipients=[member.email],
            subject=_("Payment Receipt - Membership Fee"),
            message=f"""
            <h3>Payment Receipt</h3>
            
            <p>Thank you for your payment. Here are the details:</p>
            
            <ul>
                <li>Payment Reference: {payment_entry.name}</li>
                <li>Amount: {frappe.format_value(payment_entry.paid_amount, {'fieldtype': 'Currency'})}</li>
                <li>Date: {payment_entry.posting_date}</li>
                <li>Invoice: {invoice.name}</li>
            </ul>
            
            <p>You can download your invoice from your member portal.</p>
            
            <p>Best regards,<br>The Finance Team</p>
            """,
            now=True,
            attachments=[{
                "fname": f"Invoice_{invoice.name}.pdf",
                "fcontent": get_invoice_pdf(invoice)
            }] if frappe.db.exists("Print Format", "Sales Invoice") else []
        )
    except Exception as e:
        frappe.log_error(f"Error sending payment receipt: {str(e)}")

def get_invoice_pdf(invoice):
    """Generate PDF for invoice"""
    try:
        from frappe.utils.pdf import get_pdf
        html = frappe.get_print(invoice.doctype, invoice.name, print_format="Standard")
        return get_pdf(html)
    except:
        return None

def process_failed_payment(member, invoice, payment_reference):
    """Process failed payment"""
    
    # Update member status - use new application_status field
    member.application_status = "Payment Pending"  # Better than "Payment Failed"
    member.save()
    
    # Log the failed payment
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Member",
        "reference_name": member.name,
        "content": f"Payment failed for application {member.application_id}. Reference: {payment_reference}"
    }).insert(ignore_permissions=True)
    
    # Send notification to member
    send_payment_failed_email_with_app_id(member, invoice)
    
    return {
        "success": False,
        "message": _("Payment failed. Please try again or contact support."),
        "application_id": member.application_id,
        "retry_url": f"/payment/retry/{member.name}/{invoice.name}"
    }

def process_cancelled_payment(member, invoice):
    """Process cancelled payment"""
    
    # Update member status
    member.db_set("application_status", "Payment Cancelled")
    
    # Send reminder email
    send_payment_reminder_email(member, invoice)
    
    return {
        "success": False,
        "message": _("Payment was cancelled. You can complete payment anytime to activate your membership."),
        "retry_url": f"/payment/retry/{member.name}/{invoice.name}"
    }

def send_payment_failed_email_with_app_id(member, invoice):
    """Send email for failed payment with application ID"""
    try:
        frappe.sendmail(
            recipients=[member.email],
            subject=f"Payment Failed - Application {member.application_id}",
            message=f"""
            <p>Dear {member.first_name},</p>
            
            <p>Unfortunately, your payment for membership application {member.application_id} could not be processed.</p>
            
            <p>You can retry the payment using this link: 
            <a href="{frappe.utils.get_url()}/payment/retry/{member.name}/{invoice.name}">Retry Payment</a></p>
            
            <p>If you continue to experience issues, please contact our support team.</p>
            
            <p>Best regards,<br>The Membership Team</p>
            """,
            now=True
        )
    except Exception as e:
        frappe.log_error(f"Error sending payment failed email: {str(e)}")

def send_payment_reminder_email(member, invoice):
    """Send payment reminder email"""
    try:
        frappe.sendmail(
            recipients=[member.email],
            subject=_("Complete Your Membership Application"),
            message=f"""
            <p>Dear {member.first_name},</p>
            
            <p>Your membership application is pending payment.</p>
            
            <p>To complete your application and activate your membership, please complete the payment using this link: 
            <a href="{frappe.utils.get_url()}/payment/complete/{member.name}/{invoice.name}">Complete Payment</a></p>
            
            <p>Amount due: {frappe.format_value(invoice.grand_total, {'fieldtype': 'Currency'})}</p>
            
            <p>If you have any questions, please don't hesitate to contact us.</p>
            
            <p>Best regards,<br>The Membership Team</p>
            """,
            now=True
        )
    except Exception as e:
        frappe.log_error(f"Error sending payment reminder: {str(e)}")

# Refund handling for rejected applications

@frappe.whitelist()
def process_application_refund(member_name, reason="Application Rejected"):
    """Process refund for rejected application with payment"""
    
    member = frappe.get_doc("Member", member_name)
    
    # Check if member has made a payment
    if not member.application_payment:
        return {
            "success": False,
            "message": _("No payment found for this application")
        }
    
    # Get the payment entry
    payment_entry = frappe.get_doc("Payment Entry", member.application_payment)
    
    # Create a reverse payment entry (refund)
    refund_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Pay",  # Reverse of Receive
        "party_type": "Customer",
        "party": payment_entry.party,
        "paid_amount": payment_entry.received_amount,
        "received_amount": payment_entry.received_amount,
        "target_exchange_rate": 1,
        "paid_from": payment_entry.paid_to,  # Reverse accounts
        "paid_to": payment_entry.paid_from,
        "mode_of_payment": "Bank Transfer",  # Or appropriate refund method
        "reference_no": f"REFUND-{payment_entry.reference_no}",
        "reference_date": today(),
        "remarks": f"Refund for {reason} - Original payment: {payment_entry.name}"
    })
    
    # Link to original invoice with negative amount
    for ref in payment_entry.references:
        refund_entry.append("references", {
            "reference_doctype": ref.reference_doctype,
            "reference_name": ref.reference_name,
            "allocated_amount": -ref.allocated_amount
        })
    
    refund_entry.insert(ignore_permissions=True)
    refund_entry.submit()
    
    # Update member record
    member.refund_status = "Processed"
    member.refund_reference = refund_entry.name
    member.save()
    
    # Cancel the membership if it exists
    if frappe.db.exists("Membership", {"member": member.name, "status": ["in", ["Draft", "Active"]]}):
        membership = frappe.get_doc("Membership", {"member": member.name})
        if membership.docstatus == 1:
            membership.cancel()
        else:
            membership.delete()
    
    # Send refund notification
    send_refund_notification(member, refund_entry)
    
    return {
        "success": True,
        "message": _("Refund processed successfully"),
        "refund_entry": refund_entry.name
    }

def send_refund_notification(member, refund_entry):
    """Send refund notification to member"""
    try:
        frappe.sendmail(
            recipients=[member.email],
            subject=_("Membership Application Refund Processed"),
            message=f"""
            <p>Dear {member.first_name},</p>
            
            <p>Your membership application payment has been refunded.</p>
            
            <p>Refund Details:</p>
            <ul>
                <li>Refund Reference: {refund_entry.name}</li>
                <li>Amount: {frappe.format_value(refund_entry.paid_amount, {'fieldtype': 'Currency'})}</li>
                <li>Date: {refund_entry.posting_date}</li>
            </ul>
            
            <p>The refund should appear in your account within 5-7 business days.</p>
            
            <p>If you have any questions, please contact our support team.</p>
            
            <p>Best regards,<br>The Membership Team</p>
            """,
            now=True
        )
    except Exception as e:
        frappe.log_error(f"Error sending refund notification: {str(e)}")
