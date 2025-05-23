import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, now, add_days

class MembershipTerminationRequest(Document):
    def validate(self):
        self.set_approval_requirements()
        self.validate_permissions()
        self.validate_dates()
    
    def before_save(self):
        self.add_audit_entry("Document Updated", f"Status: {self.status}")
    
    def after_insert(self):
        self.add_audit_entry("Request Created", f"Termination type: {self.termination_type}")
    
    def set_approval_requirements(self):
        """Set whether secondary approval is required based on termination type"""
        disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
        
        if self.termination_type in disciplinary_types:
            self.requires_secondary_approval = 1
            
            # Set status to pending approval if not already set and we're past draft
            if self.status == "Draft" and not self.is_new():
                self.status = "Pending Approval"
        else:
            self.requires_secondary_approval = 0
            # Standard terminations can be approved immediately
            if self.status == "Draft" and not self.is_new():
                self.status = "Approved"
                self.approved_by = frappe.session.user
                self.approval_date = now()
    
    def validate_permissions(self):
        """Validate user permissions for different termination types"""
        user_roles = frappe.get_roles(frappe.session.user)
        
        # Check if user can initiate terminations
        can_initiate = (
            "System Manager" in user_roles or
            "Association Manager" in user_roles or
            "Verenigingen Manager" in user_roles or
            self.is_chapter_board_member()
        )
        
        if not can_initiate and self.is_new():
            frappe.throw(_("You don't have permission to initiate membership terminations"))
        
        # For disciplinary terminations, check secondary approval permissions
        if self.requires_secondary_approval and self.secondary_approver:
            approver_roles = frappe.get_roles(self.secondary_approver)
            can_approve = (
                "System Manager" in approver_roles or
                "Association Manager" in approver_roles or
                "Verenigingen Manager" in approver_roles
            )
            
            if not can_approve:
                frappe.throw(_("Secondary approver must be an Association Manager or System Manager"))
    
    def validate_dates(self):
        """Validate termination and grace period dates"""
        if self.termination_date and getdate(self.termination_date) < getdate(self.request_date):
            frappe.throw(_("Termination date cannot be before request date"))
        
        if self.grace_period_end and self.termination_date:
            if getdate(self.grace_period_end) < getdate(self.termination_date):
                frappe.throw(_("Grace period end cannot be before termination date"))
    
    def is_chapter_board_member(self):
        """Check if current user is a chapter board member"""
        if not self.member:
            return False
        
        # Get member's chapters
        member_doc = frappe.get_doc("Member", self.member)
        current_user_member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
        
        if not current_user_member:
            return False
        
        # Check if current user is a board member of any chapter where the target member belongs
        board_positions = frappe.get_all(
            "Chapter Board Member",
            filters={
                "volunteer": frappe.db.get_value("Volunteer", {"member": current_user_member}, "name"),
                "is_active": 1
            },
            fields=["parent", "chapter_role"]
        )
        
        return len(board_positions) > 0
    
    @frappe.whitelist()
    def submit_for_approval(self):
        """Submit the termination request for approval"""
        if self.status != "Draft":
            frappe.throw(_("Only draft requests can be submitted for approval"))
        
        if self.requires_secondary_approval:
            if not self.secondary_approver:
                frappe.throw(_("Secondary approver is required for disciplinary terminations"))
            
            self.status = "Pending Approval"
            self.send_approval_notification()
        else:
            # Standard terminations are auto-approved
            self.status = "Approved"
            self.approved_by = frappe.session.user
            self.approval_date = now()
        
        self.save()
        self.add_audit_entry("Submitted for Approval", f"Requires secondary approval: {self.requires_secondary_approval}")
        
        return True
    
    @frappe.whitelist()
    def approve_request(self, decision, notes=""):
        """Approve or reject the termination request"""
        if self.status != "Pending Approval":
            frappe.throw(_("Only pending requests can be approved"))
        
        # Validate approver permissions
        if self.requires_secondary_approval:
            if frappe.session.user != self.secondary_approver:
                user_roles = frappe.get_roles(frappe.session.user)
                if not ("System Manager" in user_roles or "Association Manager" in user_roles):
                    frappe.throw(_("You don't have permission to approve this request"))
        
        if decision.lower() == "approved":
            self.status = "Approved"
            self.approved_by = frappe.session.user
            self.approval_date = now()
            self.approver_notes = notes
            
            # Set default termination date if not provided
            if not self.termination_date:
                # Immediate for disciplinary, allow grace period for standard
                if self.requires_secondary_approval:
                    self.termination_date = today()
                else:
                    self.termination_date = today()
                    self.grace_period_end = add_days(today(), 30)  # 30-day grace period
            
            self.add_audit_entry("Request Approved", f"Approved by: {frappe.session.user}")
            
            # Add to expulsion report if disciplinary
            if self.requires_secondary_approval:
                self.add_to_expulsion_report()
                
        else:
            self.status = "Rejected"
            self.approved_by = frappe.session.user
            self.approval_date = now()
            self.approver_notes = notes
            
            self.add_audit_entry("Request Rejected", f"Rejected by: {frappe.session.user}, Reason: {notes}")
        
        self.save()
        return True
    
    @frappe.whitelist()
    def execute_termination(self):
        """Execute the approved termination"""
        if self.status != "Approved":
            frappe.throw(_("Only approved requests can be executed"))
        
        # Check if termination date has arrived (for non-immediate terminations)
        if self.termination_date and getdate(self.termination_date) > getdate(today()):
            frappe.throw(_("Termination date has not yet arrived"))
        
        try:
            # Execute system updates
            results = self.execute_system_updates()
            
            # Update status
            self.status = "Executed"
            self.executed_by = frappe.session.user
            self.execution_date = now()
            
            # Update counters
            self.sepa_mandates_cancelled = results.get('sepa_mandates', 0)
            self.positions_ended = results.get('positions', 0)
            self.newsletters_updated = 1 if results.get('newsletters') else 0
            
            self.save()
            self.add_audit_entry("Termination Executed", f"System updates completed")
            
            frappe.msgprint(_("Membership termination executed successfully"))
            return True
            
        except Exception as e:
            self.add_audit_entry("Execution Failed", f"Error: {str(e)}")
            frappe.log_error(f"Termination execution failed for {self.name}: {str(e)}", "Termination Execution Error")
            frappe.throw(_("Failed to execute termination: {0}").format(str(e)))
    
    def execute_system_updates(self):
        """Execute automatic system updates"""
        results = {}
        
        # Get member document
        member_doc = frappe.get_doc("Member", self.member)
        
        # 1. Cancel SEPA mandates
        if self.cancel_sepa_mandates:
            results['sepa_mandates'] = self.cancel_member_sepa_mandates(member_doc)
        
        # 2. Update newsletter subscriptions
        if self.unsubscribe_newsletters:
            results['newsletters'] = self.update_newsletter_subscriptions(member_doc)
        
        # 3. End board/committee positions
        if self.end_board_positions:
            results['positions'] = self.end_all_positions(member_doc)
        
        return results
    
    def cancel_member_sepa_mandates(self, member_doc):
        """Auto-cancel all SEPA mandates for the member"""
        active_mandates = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member_doc.name,
                "status": "Active",
                "is_active": 1
            }
        )
        
        cancelled_count = 0
        for mandate_data in active_mandates:
            mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
            mandate.status = "Cancelled"
            mandate.is_active = 0
            mandate.cancelled_date = self.termination_date or today()
            mandate.cancelled_reason = "Membership terminated"
            mandate.save()
            cancelled_count += 1
        
        return cancelled_count
    
    def update_newsletter_subscriptions(self, member_doc):
        """Selective newsletter unsubscription"""
        if not member_doc.email:
            return False
        
        # Auto-unsubscribe from member-specific newsletters
        member_newsletter_categories = [
            "Member Newsletter",
            "Chapter Updates", 
            "Member-Only Communications",
            "Membership Reminders"
        ]
        
        # Note: This would need to be implemented based on your newsletter system
        # For now, just log the action
        frappe.logger().info(f"Newsletter unsubscription requested for {member_doc.email}")
        
        # If you have a specific newsletter system, implement the unsubscription here
        # unsubscribe_from_newsletter(member_doc.email, category)
        
        return True
    
    def end_all_positions(self, member_doc):
        """End all board and committee positions automatically"""
        
        # Get volunteer record for this member
        volunteer_records = frappe.get_all(
            "Volunteer",
            filters={"member": member_doc.name},
            fields=["name"]
        )
        
        positions_ended = 0
        
        for volunteer_record in volunteer_records:
            # End board positions
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["name", "parent", "chapter_role"]
            )
            
            for position in board_positions:
                board_member = frappe.get_doc("Chapter Board Member", position.name)
                board_member.is_active = 0
                board_member.to_date = self.termination_date or today()
                board_member.save()
                
                positions_ended += 1
                
                frappe.logger().info(f"Ended board position: {position.chapter_role} at {position.parent}")
        
        return positions_ended
    
    def add_to_expulsion_report(self):
        """Add disciplinary termination to expulsion report"""
        if self.termination_type not in ['Policy Violation', 'Disciplinary Action', 'Expulsion']:
            return
        
        # Create expulsion report entry
        expulsion_entry = frappe.new_doc("Expulsion Report Entry")
        expulsion_entry.member_name = self.member_name
        expulsion_entry.member_id = self.member
        expulsion_entry.expulsion_date = self.termination_date or today()
        expulsion_entry.expulsion_type = self.termination_type
        expulsion_entry.initiated_by = self.requested_by
        expulsion_entry.approved_by = self.approved_by
        expulsion_entry.documentation = self.disciplinary_documentation
        expulsion_entry.status = "Active"
        
        # Get member's primary chapter if available
        member_doc = frappe.get_doc("Member", self.member)
        if hasattr(member_doc, 'primary_chapter') and member_doc.primary_chapter:
            expulsion_entry.chapter_involved = member_doc.primary_chapter
        
        expulsion_entry.insert()
    
    def send_approval_notification(self):
        """Send notification when approval is required"""
        if not self.secondary_approver:
            return
        
        # Get approver details
        approver = frappe.get_doc("User", self.secondary_approver)
        
        if not approver.email:
            return
        
        # Send email notification
        subject = f"Termination Approval Required: {self.member_name}"
        
        message = f"""
        <p>A membership termination request requires your approval:</p>
        
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr><td><strong>Member:</strong></td><td>{self.member_name}</td></tr>
            <tr><td><strong>Termination Type:</strong></td><td>{self.termination_type}</td></tr>
            <tr><td><strong>Requested By:</strong></td><td>{self.requested_by}</td></tr>
            <tr><td><strong>Request Date:</strong></td><td>{self.request_date}</td></tr>
            <tr><td><strong>Reason:</strong></td><td>{self.termination_reason}</td></tr>
        </table>
        
        <p><a href="/app/membership-termination-request/{self.name}">Click here to review and approve</a></p>
        """
        
        try:
            frappe.sendmail(
                recipients=[approver.email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        except Exception as e:
            frappe.log_error(f"Failed to send approval notification: {str(e)}", "Termination Approval Notification")
    
    def add_audit_entry(self, action, details, is_system=False):
        """Add an entry to the audit trail"""
        self.append("audit_trail", {
            "timestamp": now(),
            "action": action,
            "user": frappe.session.user if not is_system else "System",
            "details": details,
            "system_action": 1 if is_system else 0
        })

# Server-side methods
@frappe.whitelist()
def get_termination_permissions(termination_type, user=None):
    """Enhanced permission logic"""
    if not user:
        user = frappe.session.user
    
    user_roles = frappe.get_roles(user)
    
    # Standard terminations
    if termination_type in ['Voluntary', 'Non-payment', 'Deceased']:
        return {
            'can_initiate': (
                "System Manager" in user_roles or
                "Association Manager" in user_roles or
                "Verenigingen Manager" in user_roles or
                is_chapter_board_member(user)
            ),
            'requires_secondary_approval': False,
            'can_approve': True
        }
    
    # Disciplinary terminations  
    elif termination_type in ['Disciplinary', 'Expulsion', 'Policy Violation']:
        return {
            'can_initiate': (
                "System Manager" in user_roles or
                "Association Manager" in user_roles or
                "Verenigingen Manager" in user_roles or
                is_chapter_board_member(user)
            ),
            'requires_secondary_approval': True,
            'can_approve': (
                "System Manager" in user_roles or
                "Association Manager" in user_roles or
                "Verenigingen Manager" in user_roles
            ),
            'requires_documentation': True
        }

def is_chapter_board_member(user):
    """Check if user is a chapter board member"""
    member = frappe.db.get_value("Member", {"user": user}, "name")
    if not member:
        return False
    
    volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
    if not volunteer:
        return False
    
    board_positions = frappe.get_all(
        "Chapter Board Member",
        filters={
            "volunteer": volunteer,
            "is_active": 1
        }
    )
    
    return len(board_positions) > 0

@frappe.whitelist()
def initiate_disciplinary_termination(member_id, termination_data):
    """Start disciplinary termination requiring approval"""
    
    # Create pending termination record
    termination_request = frappe.get_doc({
        "doctype": "Membership Termination Request",
        "member": member_id,
        "termination_type": termination_data['termination_type'],
        "termination_reason": termination_data.get('termination_reason', ''),
        "disciplinary_documentation": termination_data.get('documentation', ''),
        "requested_by": frappe.session.user,
        "request_date": today(),
        "status": "Draft",
        "secondary_approver": termination_data.get('secondary_approver')
    })
    
    termination_request.insert()
    
    # Submit for approval
    termination_request.submit_for_approval()
    
    return {"status": "approval_pending", "request_id": termination_request.name}

@frappe.whitelist() 
def approve_disciplinary_termination(request_id, approval_decision, approver_notes=""):
    """Secondary approval for disciplinary terminations"""
    
    request = frappe.get_doc("Membership Termination Request", request_id)
    return request.approve_request(approval_decision, approver_notes)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_eligible_approvers(doctype, txt, searchfield, start, page_len, filters):
    """Get users eligible to approve disciplinary terminations"""
    
    # Get users with Association Manager or System Manager roles
    eligible_users = frappe.db.sql("""
        SELECT DISTINCT u.name, u.full_name, u.email
        FROM `tabUser` u
        JOIN `tabHas Role` hr ON u.name = hr.parent
        WHERE 
            hr.role IN ('Association Manager', 'System Manager', 'Verenigingen Manager')
            AND u.enabled = 1
            AND u.name != 'Administrator'
            AND u.name != 'Guest'
            AND (u.full_name LIKE %(txt)s OR u.name LIKE %(txt)s OR u.email LIKE %(txt)s)
        ORDER BY u.full_name
        LIMIT %(start)s, %(page_len)s
    """, {
        'txt': "%" + txt + "%",
        'start': start,
        'page_len': page_len
    })
    
    return eligible_users

@frappe.whitelist()
def generate_expulsion_report(date_range=None, chapter=None):
    """Generate report of all disciplinary terminations"""
    filters = ["ere.expulsion_type IN ('Policy Violation', 'Disciplinary Action', 'Expulsion')"]
    filter_values = []
    
    if date_range:
        start_date, end_date = date_range.split(',')
        filters.append("ere.expulsion_date BETWEEN %s AND %s")
        filter_values.extend([start_date, end_date])
    
    if chapter:
        filters.append("ere.chapter_involved = %s")
        filter_values.append(chapter)
    
    # Return detailed expulsion report for governance review
    query = f"""
        SELECT 
            ere.name,
            ere.member_name,
            ere.member_id,
            ere.expulsion_date,
            ere.expulsion_type,
            ere.chapter_involved,
            ere.initiated_by,
            ere.approved_by,
            ere.status,
            ere.documentation
        FROM `tabExpulsion Report Entry` ere
        WHERE {' AND '.join(filters)}
        ORDER BY ere.expulsion_date DESC
    """
    
    return frappe.db.sql(query, filter_values, as_dict=True)
