"""
API endpoints for reviewing and managing membership applications
"""

import frappe
from frappe import _
from frappe.utils import today, now_datetime, add_days

@frappe.whitelist()
def approve_membership_application(member_name, membership_type=None, chapter=None, notes=None):
    """
    Approve a membership application and create invoice
    Now directly processes payment instead of waiting
    """
    member = frappe.get_doc("Member", member_name)
    
    # Validate application can be approved
    if member.application_status not in ["Pending"]:
        frappe.throw(_("This application cannot be approved in its current state"))
    
    # Check permissions
    if not has_approval_permission(member):
        frappe.throw(_("You don't have permission to approve this application"))
    
    # Use provided membership type or fallback to selected
    if not membership_type:
        membership_type = member.selected_membership_type
    
    if not membership_type:
        frappe.throw(_("Please select a membership type"))
    
    # Update chapter if provided
    if chapter and chapter != member.primary_chapter:
        member.primary_chapter = chapter
    
    # Update member status
    member.application_status = "Active"  # Skip "Approved" state
    member.status = "Pending"  # Will become Active after payment
    member.reviewed_by = frappe.session.user
    member.review_date = now_datetime()
    if notes:
        member.review_notes = notes
    member.selected_membership_type = membership_type
    member.save()
    
    # Create membership record
    membership = frappe.get_doc({
        "doctype": "Membership",
        "member": member.name,
        "membership_type": membership_type,
        "start_date": today(),
        "status": "Draft",  # Will be activated after payment
        "auto_renew": 1
    })
    membership.insert()
    
    # Get membership type details
    membership_type_doc = frappe.get_doc("Membership Type", membership_type)
    
    # Create invoice
    from vereiningen.api.payment_processing import create_application_invoice, get_or_create_customer
    customer = get_or_create_customer(member)
    invoice = create_application_invoice(member, membership)
    
    # Send approval email with payment link
    send_approval_notification(member, invoice, membership_type_doc)
    
    return {
        "success": True,
        "message": _("Application approved. Invoice sent to applicant."),
        "invoice": invoice.name,
        "amount": membership_type_doc.amount
    }

@frappe.whitelist()
def reject_membership_application(member_name, reason, process_refund=False):
    """Reject a membership application"""
    member = frappe.get_doc("Member", member_name)
    
    # Validate application can be rejected
    if member.application_status not in ["Pending", "Payment Failed", "Payment Cancelled", "Active"]:
        frappe.throw(_("This application cannot be rejected in its current state"))
    
    # Check permissions
    if not has_approval_permission(member):
        frappe.throw(_("You don't have permission to reject this application"))
    
    # Update member status
    member.application_status = "Rejected"
    member.status = "Rejected"
    member.reviewed_by = frappe.session.user
    member.review_date = now_datetime()
    member.review_notes = reason
    member.save()
    
    # Process refund if payment was made
    refund_processed = False
    if process_refund and member.application_payment:
        from verenigingen.api.payment_processing import process_application_refund
        refund_result = process_application_refund(member_name, "Application Rejected: " + reason)
        refund_processed = refund_result.get("success", False)
    
    # Cancel any pending membership
    if frappe.db.exists("Membership", {"member": member.name, "status": ["in", ["Draft", "Pending", "Active"]]}):
        membership = frappe.get_doc("Membership", {"member": member.name})
        if membership.docstatus == 1:
            membership.cancel()
        else:
            frappe.delete_doc("Membership", membership.name)
    
    # Update CRM Lead status if exists
    if frappe.db.exists("Lead", {"member": member.name}):
        lead = frappe.get_doc("Lead", {"member": member.name})
        lead.status = "Do Not Contact"
        lead.save()
    
    # Send rejection notification
    send_rejection_notification(member, reason)
    
    return {
        "success": True,
        "message": _("Application rejected. Notification sent to applicant."),
        "refund_processed": refund_processed
    }

def has_approval_permission(member):
    """Check if current user can approve/reject applications"""
    user = frappe.session.user
    
    # System managers always have permission
    if "System Manager" in frappe.get_roles(user):
        return True
    
    # Association/Membership managers have permission
    if any(role in frappe.get_roles(user) for role in ["Association Manager", "Membership Manager"]):
        return True
    
    # Check if user is a board member of the member's chapter
    chapter = member.primary_chapter or member.suggested_chapter
    if chapter:
        # Get user's member record
        user_member = frappe.db.get_value("Member", {"user": user}, "name")
        if user_member:
            chapter_doc = frappe.get_doc("Chapter", chapter)
            # Check if user is a board member with appropriate permissions
            for board_member in chapter_doc.board_members:
                if board_member.is_active and board_member.member == user_member:
                    role = frappe.get_doc("Chapter Role", board_member.chapter_role)
                    if role.permissions_level in ["Admin", "Membership"]:
                        return True
    
    return False

def send_approval_notification(member, invoice, membership_type):
    """Send approval notification with payment link"""
    # Create payment link
    payment_url = frappe.utils.get_url(f"/payment/membership/{member.name}/{invoice.name}")
    
    args = {
        "member": member,
        "invoice": invoice,
        "membership_type": membership_type,
        "payment_url": payment_url,
        "payment_amount": invoice.grand_total,
        "company": frappe.defaults.get_global_default('company')
    }
    
    # Send email
    if frappe.db.exists("Email Template", "membership_application_approved"):
        template = "membership_application_approved"
    else:
        template = "membership_application_confirmation"
    
    frappe.sendmail(
        recipients=[member.email],
        subject=_("Membership Application Approved - Payment Required"),
        template=template,
        args=args,
        now=True
    )

def send_rejection_notification(member, reason):
    """Send rejection notification to applicant"""
    args = {
        "member": member,
        "reason": reason,
        "company": frappe.defaults.get_global_default('company')
    }
    
    if frappe.db.exists("Email Template", "membership_application_rejected"):
        frappe.sendmail(
            recipients=[member.email],
            subject=_("Membership Application Update"),
            template="membership_application_rejected",
            args=args,
            now=True
        )
    else:
        # Simple rejection email
        message = f"""
        <p>Dear {member.first_name},</p>
        
        <p>Thank you for your interest in joining our association.</p>
        
        <p>After careful review, we regret to inform you that your membership application has not been approved at this time.</p>
        
        <p><strong>Reason:</strong> {reason}</p>
        
        <p>If you have any questions or would like to discuss this decision, please don't hesitate to contact us.</p>
        
        <p>Best regards,<br>The Membership Team</p>
        """
        
        frappe.sendmail(
            recipients=[member.email],
            subject=_("Membership Application Update"),
            message=message,
            now=True
        )

@frappe.whitelist()
def get_pending_applications(chapter=None, days_overdue=None):
    """Get list of pending membership applications"""
    filters = {
        "application_status": "Pending",
        "status": "Pending"
    }
    
    # Filter by chapter if specified
    if chapter:
        filters["primary_chapter"] = chapter
    
    # Filter by overdue if specified
    if days_overdue:
        cutoff_date = add_days(today(), -days_overdue)
        filters["application_date"] = ["<", cutoff_date]
    
    # Check user permissions
    user = frappe.session.user
    if not any(role in frappe.get_roles(user) for role in ["System Manager", "Association Manager", "Membership Manager"]):
        # Regular users can only see applications for their chapter
        user_member = frappe.db.get_value("Member", {"user": user}, "name")
        if user_member:
            # Get chapters where user is a board member
            board_chapters = frappe.db.sql("""
                SELECT DISTINCT c.name
                FROM `tabChapter` c
                JOIN `tabChapter Board Member` cbm ON cbm.parent = c.name
                WHERE cbm.member = %s AND cbm.is_active = 1
            """, user_member, as_dict=True)
            
            if board_chapters:
                chapter_list = [ch.name for ch in board_chapters]
                if "primary_chapter" in filters:
                    # Ensure requested chapter is in allowed list
                    if filters["primary_chapter"] not in chapter_list:
                        return []
                else:
                    filters["primary_chapter"] = ["in", chapter_list]
            else:
                return []  # No board memberships
    
    # Get applications
    applications = frappe.get_all(
        "Member",
        filters=filters,
        fields=[
            "name", "full_name", "email", "mobile_no",
            "application_date", "primary_chapter", "suggested_chapter",
            "selected_membership_type", "application_source",
            "interested_in_volunteering", "age"
        ],
        order_by="application_date desc"
    )
    
    # Add additional info
    for app in applications:
        app["days_pending"] = (getdate(today()) - getdate(app.application_date)).days
        
        # Get membership type amount
        if app.selected_membership_type:
            mt = frappe.get_cached_doc("Membership Type", app.selected_membership_type)
            app["membership_amount"] = mt.amount
            app["membership_currency"] = mt.currency
    
    return applications

@frappe.whitelist()
def get_application_stats():
    """Get statistics for membership applications"""
    # Check permissions
    if not any(role in frappe.get_roles() for role in ["System Manager", "Association Manager", "Membership Manager"]):
        frappe.throw(_("Insufficient permissions"))
    
    stats = {}
    
    # Total applications by status
    status_counts = frappe.db.sql("""
        SELECT application_status, COUNT(*) as count
        FROM `tabMember`
        WHERE application_status IS NOT NULL
        GROUP BY application_status
    """, as_dict=True)
    
    stats["by_status"] = {s.application_status: s.count for s in status_counts}
    
    # Applications in last 30 days
    stats["last_30_days"] = frappe.db.count("Member", {
        "application_date": [">=", add_days(today(), -30)]
    })
    
    # Average processing time (for approved applications)
    avg_time = frappe.db.sql("""
        SELECT AVG(TIMESTAMPDIFF(DAY, application_date, review_date)) as avg_days
        FROM `tabMember`
        WHERE application_status = 'Active'
        AND review_date IS NOT NULL
        AND application_date IS NOT NULL
    """, as_dict=True)
    
    stats["avg_processing_days"] = round(avg_time[0].avg_days or 0, 1)
    
    # Overdue applications (> 14 days)
    stats["overdue_count"] = frappe.db.count("Member", {
        "application_status": "Pending",
        "application_date": ["<", add_days(today(), -14)]
    })
    
    # Applications by chapter
    chapter_counts = frappe.db.sql("""
        SELECT primary_chapter, COUNT(*) as count
        FROM `tabMember`
        WHERE application_status = 'Pending'
        AND primary_chapter IS NOT NULL
        GROUP BY primary_chapter
        ORDER BY count DESC
        LIMIT 10
    """, as_dict=True)
    
    stats["by_chapter"] = chapter_counts
    
    # Volunteer interest rate
    total_apps = frappe.db.count("Member", {"application_status": ["!=", None]})
    volunteer_interested = frappe.db.count("Member", {
        "application_status": ["!=", None],
        "interested_in_volunteering": 1
    })
    
    stats["volunteer_interest_rate"] = round((volunteer_interested / total_apps * 100) if total_apps > 0 else 0, 1)
    
    return stats

@frappe.whitelist()
def send_overdue_notifications():
    """Send notifications for overdue applications (> 2 weeks)"""
    # This would be called by a scheduled job
    
    two_weeks_ago = add_days(today(), -14)
    
    # Get overdue applications
    overdue = frappe.get_all(
        "Member",
        filters={
            "application_status": "Pending",
            "application_date": ["<", two_weeks_ago]
        },
        fields=["name", "full_name", "application_date", "primary_chapter", "suggested_chapter"]
    )
    
    if not overdue:
        return
    
    # Group by chapter
    by_chapter = {}
    no_chapter = []
    
    for app in overdue:
        chapter = app.primary_chapter or app.suggested_chapter
        if chapter:
            if chapter not in by_chapter:
                by_chapter[chapter] = []
            by_chapter[chapter].append(app)
        else:
            no_chapter.append(app)
    
    # Send notifications to chapter boards
    for chapter_name, apps in by_chapter.items():
        notify_chapter_of_overdue_applications(chapter_name, apps)
    
    # Send notification for applications without chapters to association managers
    if no_chapter:
        notify_managers_of_overdue_applications(no_chapter)
    
    return {"notified_chapters": len(by_chapter), "no_chapter_apps": len(no_chapter)}

def notify_chapter_of_overdue_applications(chapter_name, applications):
    """Notify chapter board of overdue applications"""
    chapter = frappe.get_doc("Chapter", chapter_name)
    
    # Get board members with membership permissions
    recipients = []
    for board_member in chapter.board_members:
        if board_member.is_active and board_member.email:
            role = frappe.get_doc("Chapter Role", board_member.chapter_role)
            if role.permissions_level in ["Admin", "Membership"]:
                recipients.append(board_member.email)
    
    if recipients:
        # Create application list HTML
        app_list = "\n".join([
            f"<li>{app.full_name} - Applied {frappe.format_date(app.application_date)} "
            f"({(getdate(today()) - getdate(app.application_date)).days} days ago)</li>"
            for app in applications
        ])
        
        frappe.sendmail(
            recipients=recipients,
            subject=f"Action Required: {len(applications)} Overdue Membership Applications",
            message=f"""
            <h3>Overdue Membership Applications for {chapter_name}</h3>
            
            <p>The following membership applications have been pending for more than 2 weeks:</p>
            
            <ul>
            {app_list}
            </ul>
            
            <p>Please review these applications as soon as possible.</p>
            
            <p><a href="{frappe.utils.get_url()}/app/member?application_status=Pending&primary_chapter={chapter_name}">
            View All Pending Applications</a></p>
            """,
            now=True
        )

def notify_managers_of_overdue_applications(applications):
    """Notify association managers of overdue applications without chapters"""
    # Get all association managers
    managers = frappe.get_all(
        "Has Role",
        filters={"role": "Association Manager"},
        pluck="parent"
    )
    
    if managers:
        recipients = [frappe.get_value("User", m, "email") for m in managers if frappe.get_value("User", m, "enabled")]
        
        if recipients:
            app_list = "\n".join([
                f"<li>{app.full_name} - Applied {frappe.format_date(app.application_date)} "
                f"({(getdate(today()) - getdate(app.application_date)).days} days ago)</li>"
                for app in applications
            ])
            
            frappe.sendmail(
                recipients=recipients,
                subject=f"Action Required: {len(applications)} Unassigned Overdue Applications",
                message=f"""
                <h3>Overdue Membership Applications Without Chapter Assignment</h3>
                
                <p>The following membership applications have been pending for more than 2 weeks 
                and have no chapter assignment:</p>
                
                <ul>
                {app_list}
                </ul>
                
                <p>Please review and assign these applications to appropriate chapters.</p>
                
                <p><a href="{frappe.utils.get_url()}/app/member?application_status=Pending&primary_chapter=">
                View Unassigned Applications</a></p>
                """,
                now=True
            )
    
