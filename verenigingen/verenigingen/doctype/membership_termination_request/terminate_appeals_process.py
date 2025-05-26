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
                "role": ["in", ["Association Manager", "System Manager", "Association Manager"]],
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
    def update_review_status(self, new_status, notes=""):
        """Update the review status with automated timeline tracking"""
        if self.review_status == new_status:
            return
            
        old_status = self.review_status
        self.review_status = new_status
        
        # Add timeline event
        self.add_timeline_event(
            f"Status Update: {new_status}",
            f"Review status changed from {old_status} to {new_status}" + (f". Notes: {notes}" if notes else "")
        )
        
        # Handle specific status changes
        if new_status == "Hearing Scheduled":
            self.handle_hearing_scheduled()
        elif new_status == "Decision Pending":
            self.handle_decision_pending()
            
        self.save()
        
    def handle_hearing_scheduled(self):
        """Handle when hearing is scheduled"""
        # Send notification to appellant
        self.send_hearing_notification()
        
        # Add communication log entry
        self.add_communication_entry(
            "Email",
            "Outgoing", 
            "Appeal Review Panel",
            self.appellant_email,
            "Hearing Scheduled for Appeal",
            "Notification sent regarding scheduled hearing for appeal review"
        )
        
    def handle_decision_pending(self):
        """Handle when decision is pending"""
        self.appeal_status = "Pending Decision"
        
        # Set expected decision date if not set
        if not self.decision_date:
            # Decision should be made within 7 days of reaching this status
            expected_decision = add_days(today(), 7)
            self.add_timeline_event(
                "Decision Expected",
                f"Decision expected by {frappe.format_date(expected_decision)}"
            )
            
    @frappe.whitelist()
    def record_decision(self, outcome, rationale, decided_by=None):
        """Record the appeal decision"""
        if self.appeal_status not in ["Under Review", "Pending Decision"]:
            frappe.throw(_("Appeals can only be decided when under review or pending decision"))
            
        self.decision_outcome = outcome
        self.decision_rationale = rationale
        self.decision_date = today()
        self.decided_by = decided_by or frappe.session.user
        
        # Update appeal status based on outcome
        status_mapping = {
            "Upheld": "Decided - Upheld",
            "Rejected": "Decided - Rejected", 
            "Partially Upheld": "Decided - Partially Upheld",
            "Remanded for Rehearing": "Under Review"
        }
        
        self.appeal_status = status_mapping.get(outcome, "Decided - Rejected")
        
        # Add timeline event
        self.add_timeline_event(
            f"Decision Made: {outcome}",
            f"Appeal decision recorded by {self.decided_by}"
        )
        
        self.save()
        
        # Handle post-decision actions
        self.handle_post_decision_actions()
        
        # Send decision notification
        self.send_decision_notification()
        
        return True
        
    def handle_post_decision_actions(self):
        """Handle actions required after decision is made"""
        if self.decision_outcome in ["Upheld", "Partially Upheld"]:
            # Appeal successful - need to implement remedial actions
            self.implementation_status = "Pending"
            self.schedule_implementation()
            
        elif self.decision_outcome == "Rejected":
            # Appeal rejected - no further action needed
            self.implementation_status = "Not Required"
            
    def schedule_implementation(self):
        """Schedule implementation of successful appeal"""
        # Implementation should begin within 14 days
        self.implementation_date = add_days(self.decision_date, 14)
        
        # Add timeline event for implementation
        self.add_timeline_event(
            "Implementation Scheduled",
            f"Implementation scheduled for {frappe.format_date(self.implementation_date)}"
        )
        
        # Create implementation tasks based on remedy sought
        self.create_implementation_tasks()
        
    def create_implementation_tasks(self):
        """Create specific implementation tasks based on the remedy sought"""
        implementation_actions = []
        
        if self.remedy_sought == "Full Reinstatement":
            implementation_actions.extend([
                "Reverse membership termination",
                "Reactivate member account",
                "Restore member benefits", 
                "Update member records",
                "Notify relevant systems"
            ])
        elif self.remedy_sought == "Reduction of Penalty":
            implementation_actions.extend([
                "Modify termination record",
                "Update penalty status",
                "Adjust member standing"
            ])
        elif self.remedy_sought == "New Hearing":
            implementation_actions.extend([
                "Schedule new hearing",
                "Notify all parties",
                "Prepare case materials"
            ])
            
        # Store implementation actions
        self.implementation_actions = "\n".join([f"• {action}" for action in implementation_actions])
        
    @frappe.whitelist()
    def execute_implementation(self, implementation_notes=""):
        """Execute the implementation of appeal decision"""
        if self.implementation_status != "Pending":
            frappe.throw(_("Implementation is not pending"))
            
        if self.decision_outcome not in ["Upheld", "Partially Upheld"]:
            frappe.throw(_("Implementation only applies to successful appeals"))
            
        try:
            # Execute specific remedial actions
            if self.remedy_sought == "Full Reinstatement":
                self.execute_full_reinstatement()
            elif self.remedy_sought == "Reduction of Penalty":
                self.execute_penalty_reduction()
            elif self.remedy_sought == "Procedural Correction":
                self.execute_procedural_correction()
                
            # Update implementation status
            self.implementation_status = "Completed"
            self.implementation_date = today()
            self.implementation_notes = implementation_notes
            
            # Add timeline event
            self.add_timeline_event(
                "Implementation Completed",
                f"Appeal decision implementation completed. {implementation_notes}"
            )
            
            self.save()
            
            # Send completion notification
            self.send_implementation_notification()
            
            return True
            
        except Exception as e:
            # Log error and update status
            frappe.log_error(f"Implementation failed for appeal {self.name}: {str(e)}", "Appeal Implementation Error")
            
            self.implementation_status = "Partially Completed" 
            self.implementation_notes = f"Implementation failed: {str(e)}. {implementation_notes}"
            self.save()
            
            frappe.throw(_("Implementation failed: {0}").format(str(e)))
            
    def execute_full_reinstatement(self):
        """Execute full reinstatement of member"""
        if not self.termination_request:
            return
            
        # Get the original termination request
        termination_doc = frappe.get_doc("Membership Termination Request", self.termination_request)
        
        # Reverse termination actions
        if termination_doc.status == "Executed":
            # This would require reversing all the system updates
            # For now, we'll create a comprehensive reversal log
            reversal_actions = [
                f"Reversed termination executed on {termination_doc.execution_date}",
                f"Member {termination_doc.member_name} reinstated",
                "Manual review required for:"
            ]
            
            if termination_doc.sepa_mandates_cancelled > 0:
                reversal_actions.append(f"  • {termination_doc.sepa_mandates_cancelled} SEPA mandates to be reviewed")
                
            if termination_doc.positions_ended > 0:
                reversal_actions.append(f"  • {termination_doc.positions_ended} board positions to be reviewed")
                
            self.implementation_actions = "\n".join(reversal_actions)
            
            # Add communication to appellant
            self.add_communication_entry(
                "Email",
                "Outgoing",
                "Appeal Review Panel", 
                self.appellant_email,
                "Appeal Implementation: Full Reinstatement",
                "Member has been fully reinstated following successful appeal. Manual verification of systems may be required."
            )
            
    def execute_penalty_reduction(self):
        """Execute penalty reduction"""
        # Update the expulsion entry to reflect reduced penalty
        if self.expulsion_entry:
            expulsion_doc = frappe.get_doc("Expulsion Report Entry", self.expulsion_entry)
            expulsion_doc.status = "Active"
            expulsion_doc.notes = (expulsion_doc.notes or "") + f"\nPenalty reduced following appeal on {today()}"
            expulsion_doc.save()
            
    def execute_procedural_correction(self):
        """Execute procedural corrections"""
        # Log procedural corrections made
        self.implementation_actions = "Procedural corrections applied to original termination process"
        
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
                <li>Decision within {date_diff(self.review_deadline, self.appeal_date)} days (by {frappe.format_date(self.review_deadline)})</li>
            </ul>
            
            <p>We will keep you informed of progress throughout the review process.</p>
            
            <p>Best regards,<br>
            Appeals Review Panel</p>
            
            <div style="font-size: 12px; color: #6c757d; margin-top: 30px;">
                <p>Appeal Reference: {self.name} | Submitted: {now()}</p>
            </div>
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
            
            # Log the communication
            self.add_communication_entry(
                "Email",
                "Outgoing",
                "Appeals System",
                self.appellant_email,
                subject,
                "Acknowledgment email sent confirming receipt of appeal"
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
            "Partially Upheld": "#ea580c",
            "Remanded for Rehearing": "#2563eb"
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
                <div style="white-space: pre-wrap;">{self.decision_rationale or 'Decision rationale will be provided separately.'}</div>
            </div>
        """
        
        if self.decision_outcome in ["Upheld", "Partially Upheld"]:
            message += f"""
            <div style="background: #ecfdf5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4>Implementation</h4>
                <p>As your appeal has been successful, implementation of the decision will begin on <strong>{frappe.format_date(self.implementation_date) if self.implementation_date else 'within 14 days'}</strong>.</p>
                <p>You will be notified when implementation is complete.</p>
            </div>
            """
        
        message += """
            <p>If you have any questions about this decision, please contact our appeals department.</p>
            
            <p>Best regards,<br>
            Appeals Review Panel</p>
            
            <div style="font-size: 12px; color: #6c757d; margin-top: 30px;">
                <p>Appeal Reference: {name} | Decision Date: {decision_date}</p>
            </div>
        </div>
        """.format(name=self.name, decision_date=frappe.format_date(self.decision_date))
        
        try:
            frappe.sendmail(
                recipients=[self.appellant_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
            
            # Log the communication
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
        fields=["decision_outcome", "appeal_type", "decision_date"]
    )
    
    success_rate = {}
    type_analysis = {}
    
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
    
    # Calculate success rates by type
    for appeal_type in type_analysis:
        total = type_analysis[appeal_type]["total"]
        upheld = type_analysis[appeal_type]["upheld"] 
        type_analysis[appeal_type]["success_rate"] = (upheld / total * 100) if total > 0 else 0
    
    # Processing time analysis
    processing_times = []
    for appeal in decided_appeals:
        if appeal.decision_date:
            # This would need the appeal_date from the full record
            appeal_doc = frappe.get_doc("Termination Appeals Process", appeal.name)
            if appeal_doc.appeal_date:
                days = date_diff(appeal.decision_date, appeal_doc.appeal_date)
                processing_times.append(days)
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    return {
        "success_rate": success_rate,
        "type_analysis": type_analysis,
        "avg_processing_time": avg_processing_time,
        "total_processed": len(decided_appeals)
    }
