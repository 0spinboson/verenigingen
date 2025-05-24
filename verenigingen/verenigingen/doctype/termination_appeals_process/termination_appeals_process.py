import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, now, add_days, date_diff

class TerminationAppealsProcess(Document):
    def validate(self):
        self.validate_appeal_timeline()
        self.validate_review_deadlines()
        self.set_automatic_deadlines()
        
    def before_save(self):
        self.update_expulsion_entry_status()
        
    def after_insert(self):
        self.send_acknowledgment_notification()
        self.add_timeline_event("Appeal Submitted", "Appeal formally submitted to system")
        self.assign_initial_reviewer()
        
    def on_update(self):
        self.check_status_changes()
        
    def validate_appeal_timeline(self):
        """Validate appeal submission is within allowed timeframe"""
        if not self.termination_request:
            return
            
        termination_doc = frappe.get_doc("Membership Termination Request", self.termination_request)
        
        if termination_doc.execution_date:
            # Check if appeal is within statutory timeframe (typically 30 days)
            appeal_deadline = add_days(termination_doc.execution_date, 30)
            
            if getdate(self.appeal_date) > getdate(appeal_deadline):
                frappe.msgprint(
                    _("Warning: This appeal is being submitted after the standard 30-day deadline. "
                      "Late appeals may require special justification."),
                    indicator='yellow',
                    alert=True
                )
                
    def validate_review_deadlines(self):
        """Set and validate review deadlines"""
        if self.review_start_date and not self.review_deadline:
            # Set standard 60-day review deadline
            self.review_deadline = add_days(self.review_start_date, 60)
            
    def set_automatic_deadlines(self):
        """Set automatic deadlines based on appeal type and complexity"""
        if not self.review_deadline and self.appeal_status in ["Submitted", "Under Review"]:
            # Set deadline based on appeal type
            deadline_days = {
                "Procedural Appeal": 30,
                "Substantive Appeal": 60,
                "New Evidence Appeal": 45,
                "Full Review Appeal": 90
            }
            
            days = deadline_days.get(self.appeal_type, 60)
            self.review_deadline = add_days(self.appeal_date, days)
            
    def update_expulsion_entry_status(self):
        """Update related expulsion entry with appeal status"""
        if self.expulsion_entry:
            expulsion_doc = frappe.get_doc("Expulsion Report Entry", self.expulsion_entry)
            
            if self.appeal_status in ["Submitted", "Under Review", "Pending Decision"]:
                expulsion_doc.status = "Under Appeal"
                expulsion_doc.under_appeal = 1
                expulsion_doc.appeal_date = self.appeal_date
            elif self.appeal_status == "Decided - Upheld":
                expulsion_doc.status = "Reversed"
                expulsion_doc.reversal_date = self.decision_date
                expulsion_doc.reversal_reason = "Appeal upheld"
                expulsion_doc.under_appeal = 0
            elif self.appeal_status in ["Decided - Rejected", "Dismissed"]:
                expulsion_doc.status = "Active"
                expulsion_doc.under_appeal = 0
                
            expulsion_doc.save()
            
    @frappe.whitelist()
    def submit_appeal(self):
        """Submit the appeal for review"""
        if self.appeal_status != "Draft":
            frappe.throw(_("Only draft appeals can be submitted"))
            
        # Validate required fields
        self.validate_submission_requirements()
        
        # Update status
        self.appeal_status = "Submitted"
        self.save()
        
        # Add timeline event
        self.add_timeline_event("Appeal Submitted", "Appeal submitted for formal review")
        
        # Send notifications
        self.send_submission_notifications()
        
        # Assign reviewer if not already assigned
        if not self.assigned_reviewer:
            self.assign_initial_reviewer()
            
        return True
        
    def validate_submission_requirements(self):
        """Validate all required fields for submission"""
        required_fields = {
            'appellant_name': 'Appellant Name',
            'appellant_email': 'Appellant Email',
            'appeal_grounds': 'Grounds for Appeal',
            'remedy_sought': 'Remedy Sought'
        }
        
        for field, label in required_fields.items():
            if not getattr(self, field):
                frappe.throw(_("{0} is required for appeal submission").format(label))
                
    def assign_initial_reviewer(self):
        """Assign initial reviewer based on case complexity and availability"""
        
        # Get eligible reviewers (Association Managers and System Managers)
        eligible_reviewers = frappe.get_all(
            "Has Role",
            filters={
                "role": ["in", ["Association Manager", "System Manager"]],
                "parenttype": "User"
            },
            fields=["parent"]
        )
        
        if not eligible_reviewers:
            frappe.log_error("No eligible reviewers found for appeal assignment", "Appeal Assignment Error")
            return
            
        # Simple round-robin assignment based on current workload
        reviewer_workload = {}
        for reviewer_data in eligible_reviewers:
            reviewer = reviewer_data.parent
            workload = frappe.db.count("Termination Appeals Process", {
                "assigned_reviewer": reviewer,
                "appeal_status": ["in", ["Under Review", "Pending Decision"]]
            })
            reviewer_workload[reviewer] = workload
            
        # Assign to reviewer with lowest workload
        assigned_reviewer = min(reviewer_workload.keys(), key=lambda x: reviewer_workload[x])
        
        self.assigned_reviewer = assigned_reviewer
        self.review_start_date = today()
        self.appeal_status = "Under Review"
        self.review_status = "Document Review"
        self.save()
        
        # Add timeline event
        self.add_timeline_event(
            "Review Assigned", 
            f"Appeal assigned to {assigned_reviewer} for review"
        )
        
        # Send assignment notification
        self.send_reviewer_assignment_notification()
        
    @frappe.whitelist()
    def make_decision(self, outcome, rationale, implementation_required=False):
        """Record the appeal decision"""
        if self.appeal_status not in ["Under Review", "Pending Decision"]:
            frappe.throw(_("Appeals can only be decided when under review or pending decision"))
            
        self.decision_outcome = outcome
        self.decision_rationale = rationale
        self.decision_date = today()
        self.decided_by = frappe.session.user
        
        # Update appeal status based on outcome
        status_mapping = {
            "Upheld": "Decided - Upheld",
            "Rejected": "Decided - Rejected", 
            "Partially Upheld": "Decided - Partially Upheld",
            "Remanded for Rehearing": "Under Review"
        }
        
        self.appeal_status = status_mapping.get(outcome, "Decided - Rejected")
        
        # Set implementation status
        if outcome in ["Upheld", "Partially Upheld"]:
            self.implementation_status = "Pending"
            self.implementation_required = 1
        else:
            self.implementation_status = "Not Required"
            self.implementation_required = 0
        
        # Add timeline event
        self.add_timeline_event(
            f"Decision Made: {outcome}",
            f"Appeal decision recorded by {self.decided_by}"
        )
        
        self.save()
        
        # Send decision notification
        self.send_decision_notification()
        
        return True
        
    @frappe.whitelist()
    def implement_decision(self):
        """Implement the appeal decision"""
        if self.implementation_status != "Pending":
            frappe.throw(_("No implementation pending"))
            
        if self.decision_outcome == "Upheld":
            # Full reversal of termination
            self.reverse_termination()
        elif self.decision_outcome == "Partially Upheld":
            # Partial reversal or modification
            self.partial_reversal()
            
        self.implementation_status = "Completed"
        self.implementation_date = today()
        
        self.add_timeline_event(
            "Implementation Completed",
            f"Appeal decision implemented on {today()}"
        )
        
        self.save()
        return True
        
    def reverse_termination(self):
        """Reverse the termination decision"""
        if not self.termination_request:
            return
            
        termination_doc = frappe.get_doc("Membership Termination Request", self.termination_request)
        member_doc = frappe.get_doc("Member", termination_doc.member)
        
        # Restore member status
        member_doc.status = "Active"
        member_doc.save()
        
        # Log the reversal
        self.implementation_actions = f"Member {member_doc.full_name} status restored to Active"
        
    def partial_reversal(self):
        """Implement partial reversal"""
        self.implementation_actions = "Partial reversal implemented - manual review required"
        
    def add_timeline_event(self, event_type, description, responsible_party=None):
        """Add an event to the appeal timeline"""
        self.append("appeal_timeline", {
            "event_date": today(),
            "event_type": event_type,
            "event_description": description,
            "responsible_party": responsible_party or frappe.session.user,
            "completion_status": "Completed"
        })
        
    def add_communication_entry(self, comm_type, direction, from_party, to_party, subject, summary):
        """Add a communication entry to the appeals log"""
        self.append("appeal_communications", {
            "communication_date": now(),
            "communication_type": comm_type,
            "direction": direction,
            "from_party": from_party,
            "to_party": to_party, 
            "subject": subject,
            "content_summary": summary
        })
        
    def send_acknowledgment_notification(self):
        """Send acknowledgment email when appeal is submitted"""
        if not self.appellant_email:
            return
            
        subject = f"Appeal Acknowledgment - {self.name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #2563eb;">Appeal Acknowledgment</h2>
            
            <p>Dear {self.appellant_name},</p>
            
            <p>We acknowledge receipt of your appeal regarding the membership termination of <strong>{self.member_name}</strong>.</p>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Appeal Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Appeal Reference:</strong></td><td style="padding: 5px;">{self.name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Appeal Date:</strong></td><td style="padding: 5px;">{frappe.format_date(self.appeal_date)}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Appeal Type:</strong></td><td style="padding: 5px;">{self.appeal_type}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Remedy Sought:</strong></td><td style="padding: 5px;">{self.remedy_sought}</td></tr>
                </table>
            </div>
            
            <p>Your appeal will be reviewed according to our established procedures. You can expect:</p>
            <ul>
                <li>Initial review within 7 working days</li>
                <li>Assignment to a review panel</li>
                <li>Decision within {date_diff(self.review_deadline, self.appeal_date) if self.review_deadline else 60} days</li>
            </ul>
            
            <p>We will keep you informed of progress throughout the review process.</p>
            
            <p>Best regards,<br>
            Appeals Review Panel</p>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[self.appellant_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
            self.add_communication_entry(
                "Email",
                "Outgoing",
                "Appeals System",
                self.appellant_email,
                subject,
                "Acknowledgment email sent"
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send appeal acknowledgment: {str(e)}", "Appeal Acknowledgment Error")
            
    def send_decision_notification(self):
        """Send decision notification to appellant"""
        if not self.appellant_email:
            return
            
        outcome_colors = {
            "Upheld": "#16a34a",
            "Rejected": "#dc2626", 
            "Partially Upheld": "#ea580c"
        }
        
        color = outcome_colors.get(self.decision_outcome, "#6b7280")
        
        subject = f"Appeal Decision - {self.decision_outcome} - {self.name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: {color};">Appeal Decision</h2>
            
            <p>Dear {self.appellant_name},</p>
            
            <p>We are writing to inform you of the decision regarding your appeal for <strong>{self.member_name}</strong>.</p>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid {color};">
                <h3>Decision: {self.decision_outcome}</h3>
                <p><strong>Decision Date:</strong> {frappe.format_date(self.decision_date)}</p>
                <p><strong>Decided By:</strong> {self.decided_by}</p>
            </div>
            
            <div style="background: #ffffff; padding: 15px; border: 1px solid #e5e7eb; border-radius: 5px; margin: 20px 0;">
                <h4>Rationale</h4>
                <div style="white-space: pre-wrap;">{self.decision_rationale or 'Decision rationale provided separately.'}</div>
            </div>
            
            <p>Best regards,<br>Appeals Review Panel</p>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[self.appellant_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
            self.add_communication_entry(
                "Email",
                "Outgoing", 
                "Appeals Review Panel",
                self.appellant_email,
                subject,
                f"Decision notification sent: {self.decision_outcome}"
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send decision notification: {str(e)}", "Appeal Decision Notification Error")
            
    def send_reviewer_assignment_notification(self):
        """Send notification to assigned reviewer"""
        if not self.assigned_reviewer:
            return
            
        reviewer_email = frappe.db.get_value("User", self.assigned_reviewer, "email")
        if not reviewer_email:
            return
            
        subject = f"Appeal Review Assignment - {self.name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #2563eb;">Appeal Review Assignment</h2>
            
            <p>You have been assigned to review an appeal:</p>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Appeal Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Appeal Reference:</strong></td><td style="padding: 5px;">{self.name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Member:</strong></td><td style="padding: 5px;">{self.member_name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Appeal Date:</strong></td><td style="padding: 5px;">{frappe.format_date(self.appeal_date)}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Review Deadline:</strong></td><td style="padding: 5px;">{frappe.format_date(self.review_deadline) if self.review_deadline else 'TBD'}</td></tr>
                </table>
            </div>
            
            <div style="text-align: center; margin: 20px 0;">
                <a href="{frappe.utils.get_url()}/app/termination-appeals-process/{self.name}" 
                   style="background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px;">
                    Review Appeal
                </a>
            </div>
            
            <p>Best regards,<br>Appeals System</p>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[reviewer_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send reviewer assignment notification: {str(e)}", "Appeal Assignment Notification Error")
            
    def send_submission_notifications(self):
        """Send notifications when appeal is submitted"""
        # Send to governance team
        governance_users = frappe.get_all(
            "Has Role",
            filters={"role": "Association Manager"},
            fields=["parent"]
        )
        
        for user_role in governance_users:
            email = frappe.db.get_value("User", user_role.parent, "email")
            if email:
                subject = f"New Appeal Submitted - {self.name}"
                message = f"""
                <p>A new appeal has been submitted:</p>
                <p><strong>Member:</strong> {self.member_name}</p>
                <p><strong>Appeal Reference:</strong> {self.name}</p>
                <p><strong>Grounds:</strong> {self.appeal_grounds}</p>
                <p><a href="{frappe.utils.get_url()}/app/termination-appeals-process/{self.name}">Review Appeal</a></p>
                """
                
                try:
                    frappe.sendmail(
                        recipients=[email],
                        subject=subject,
                        message=message,
                        reference_doctype=self.doctype,
                        reference_name=self.name
                    )
                except Exception as e:
                    frappe.log_error(f"Failed to send submission notification: {str(e)}", "Appeal Submission Notification Error")
                    
    def check_status_changes(self):
        """Check for status changes and trigger appropriate actions"""
        if self.has_value_changed("appeal_status"):
            old_status = self.get_db_value("appeal_status")
            new_status = self.appeal_status
            
            self.add_timeline_event(
                f"Status Changed",
                f"Status changed from {old_status} to {new_status}"
            )

# Server-side methods for appeals management
@frappe.whitelist()
def get_appeals_dashboard_data():
    """Get dashboard data for appeals management"""
    
    # Get counts by status
    status_counts = {}
    for status in ["Draft", "Submitted", "Under Review", "Pending Decision", "Decided - Upheld", "Decided - Rejected", "Decided - Partially Upheld"]:
        status_counts[status] = frappe.db.count("Termination Appeals Process", {"appeal_status": status})
    
    # Get recent appeals
    recent_appeals = frappe.get_all(
        "Termination Appeals Process",
        fields=["name", "member_name", "appeal_status", "appeal_date", "appellant_name"],
        limit=10,
        order_by="appeal_date desc"
    )
    
    # Get appeals requiring attention (overdue reviews)
    overdue_appeals = frappe.get_all(
        "Termination Appeals Process",
        filters={
            "appeal_status": ["in", ["Under Review", "Pending Decision"]],
            "review_deadline": ["<", today()]
        },
        fields=["name", "member_name", "review_deadline", "assigned_reviewer"],
        order_by="review_deadline asc"
    )
    
    # Get implementation pending
    implementation_pending = frappe.db.count("Termination Appeals Process", {
        "implementation_status": "Pending"
    })
    
    return {
        "status_counts": status_counts,
        "recent_appeals": recent_appeals,
        "overdue_appeals": overdue_appeals,
        "implementation_pending": implementation_pending,
        "total_appeals": sum(status_counts.values())
    }

@frappe.whitelist()
def get_appeals_analytics():
    """Get analytics data for appeals reporting"""
    
    # Success rate analysis
    decided_appeals = frappe.get_all(
        "Termination Appeals Process",
        filters={"appeal_status": ["like", "Decided%"]},
        fields=["decision_outcome", "appeal_type", "decision_date", "appeal_date"]
    )
    
    success_rate = {}
    type_analysis = {}
    processing_times = []
    
    for appeal in decided_appeals:
        # Overall success rate
        outcome = appeal.decision_outcome
        if outcome not in success_rate:
            success_rate[outcome] = 0
        success_rate[outcome] += 1
        
        # By type analysis
        appeal_type = appeal.appeal_type
        if appeal_type not in type_analysis:
            type_analysis[appeal_type] = {"total": 0, "upheld": 0}
        
        type_analysis[appeal_type]["total"] += 1
        if outcome in ["Upheld", "Partially Upheld"]:
            type_analysis[appeal_type]["upheld"] += 1
            
        # Processing time
        if appeal.decision_date and appeal.appeal_date:
            days = date_diff(appeal.decision_date, appeal.appeal_date)
            processing_times.append(days)
    
    # Calculate success rates by type
    for appeal_type in type_analysis:
        total = type_analysis[appeal_type]["total"]
        upheld = type_analysis[appeal_type]["upheld"] 
        type_analysis[appeal_type]["success_rate"] = (upheld / total * 100) if total > 0 else 0
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    return {
        "success_rate": success_rate,
        "type_analysis": type_analysis,
        "avg_processing_time": avg_processing_time,
        "total_processed": len(decided_appeals)
    }
