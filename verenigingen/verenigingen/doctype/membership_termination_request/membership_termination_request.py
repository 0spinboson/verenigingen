import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, now, add_days, date_diff

class MembershipTerminationRequest(Document):
    def validate(self):
        self.set_approval_requirements()
        self.validate_permissions()
        self.validate_dates()
    
    def before_save(self):
        self.add_audit_entry("Document Updated", f"Status: {self.status}")
    
    def after_insert(self):
        self.add_audit_entry("Request Created", f"Termination type: {self.termination_type}")
    
    def add_audit_entry(self, action, details, is_system=False):
        """Add an entry to the audit trail"""
        self.append("audit_trail", {
            "timestamp": now(),
            "action": action,
            "user": frappe.session.user if not is_system else "System",
            "details": details,
            "system_action": 1 if is_system else 0
        })
    
    def on_status_change(self):
        """Handle workflow status changes and their side effects"""
        
        # Only process if status has actually changed
        if not self.has_value_changed("status"):
            return
        
        old_status = self.get_db_value("status")
        new_status = self.status
        
        # Add audit trail entry for status change
        self.add_audit_entry(
            "Status Changed", 
            f"Status changed from {old_status} to {new_status}",
            is_system=True
        )
        
        # Handle specific status transitions
        if new_status == "Pending":
            self.handle_pending_status()
        elif new_status == "Approved":
            self.handle_approved_status()
        elif new_status == "Rejected":
            self.handle_rejected_status()
        elif new_status == "Executed":
            self.handle_executed_status()

    def handle_pending_status(self):
        """Handle when termination request moves to Pending status"""
        
        # For disciplinary terminations requiring secondary approval
        if self.requires_secondary_approval and self.secondary_approver:
            # Send approval notification to secondary approver
            self.send_approval_notification()
            
            self.add_audit_entry(
                "Approval Required", 
                f"Secondary approval required from {self.secondary_approver}",
                is_system=True
            )

    def handle_approved_status(self):
        """Handle when termination request is approved"""
        
        # Set approval fields if not already set by workflow
        if not self.approved_by:
            self.approved_by = frappe.session.user
        if not self.approval_date:
            self.approval_date = now()
        
        # Set default termination date if not provided
        if not self.termination_date:
            if self.requires_secondary_approval:
                # Immediate for disciplinary terminations
                self.termination_date = today()
            else:
                # Standard terminations may have grace period
                self.termination_date = today()
                if self.termination_type not in ['Deceased', 'Policy Violation', 'Disciplinary Action', 'Expulsion']:
                    self.grace_period_end = add_days(today(), 30)
        
        # Add to expulsion report if disciplinary
        if self.requires_secondary_approval:
            self.add_to_expulsion_report()
        
        # Send approval notification to requester
        self.send_approval_confirmation()
        
        self.add_audit_entry(
            "Request Approved", 
            f"Approved by {self.approved_by} on {frappe.utils.format_datetime(self.approval_date)}",
            is_system=True
        )

    def handle_rejected_status(self):
        """Handle when termination request is rejected"""
        
        # Set rejection fields if not already set
        if not self.approved_by:  # This field is used for both approval and rejection
            self.approved_by = frappe.session.user
        if not self.approval_date:
            self.approval_date = now()
        
        # Send rejection notification
        self.send_rejection_notification()
        
        self.add_audit_entry(
            "Request Rejected", 
            f"Rejected by {self.approved_by}. Reason: {self.approver_notes or 'No reason provided'}",
            is_system=True
        )

    def handle_executed_status(self):
        """Handle when termination request is executed"""
        
        # This status should typically be set by the execute_termination method
        # But we can handle any cleanup or notifications here
        
        if not self.executed_by:
            self.executed_by = frappe.session.user
        if not self.execution_date:
            self.execution_date = now()
        
        # Send execution confirmation
        self.send_execution_notification()
        
        self.add_audit_entry(
            "Termination Executed", 
            f"Termination executed by {self.executed_by} on {frappe.utils.format_datetime(self.execution_date)}",
            is_system=True
        )

    def send_approval_confirmation(self):
        """Send confirmation email when request is approved"""
        requester_email = frappe.db.get_value("User", self.requested_by, "email")
        
        if not requester_email:
            return
        
        subject = f"Termination Request Approved - {self.member_name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #16a34a;">Termination Request Approved</h2>
            
            <p>The membership termination request has been approved:</p>
            
            <div style="background: #f0f9ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Member:</strong></td><td style="padding: 5px;">{self.member_name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Termination Type:</strong></td><td style="padding: 5px;">{self.termination_type}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Approved By:</strong></td><td style="padding: 5px;">{self.approved_by}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Termination Date:</strong></td><td style="padding: 5px;">{frappe.utils.format_date(self.termination_date) if self.termination_date else 'TBD'}</td></tr>
                </table>
            </div>
            
            <p>The termination will be executed on the scheduled date.</p>
            
            <p><a href="{frappe.utils.get_url()}/app/membership-termination-request/{self.name}">View Request</a></p>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[requester_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        except Exception as e:
            frappe.log_error(f"Failed to send approval confirmation: {str(e)}", "Termination Approval Notification")

    def send_rejection_notification(self):
        """Send notification when request is rejected"""
        requester_email = frappe.db.get_value("User", self.requested_by, "email")
        
        if not requester_email:
            return
        
        subject = f"Termination Request Rejected - {self.member_name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #dc2626;">Termination Request Rejected</h2>
            
            <p>The membership termination request has been rejected:</p>
            
            <div style="background: #fef2f2; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Member:</strong></td><td style="padding: 5px;">{self.member_name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Termination Type:</strong></td><td style="padding: 5px;">{self.termination_type}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Rejected By:</strong></td><td style="padding: 5px;">{self.approved_by}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Reason:</strong></td><td style="padding: 5px;">{self.approver_notes or 'Not specified'}</td></tr>
                </table>
            </div>
            
            <p>Please review the rejection reason and contact the approver if you need clarification.</p>
            
            <p><a href="{frappe.utils.get_url()}/app/membership-termination-request/{self.name}">View Request</a></p>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[requester_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        except Exception as e:
            frappe.log_error(f"Failed to send rejection notification: {str(e)}", "Termination Rejection Notification")

    def send_execution_notification(self):
        """Send notification when termination is executed"""
        requester_email = frappe.db.get_value("User", self.requested_by, "email")
        
        if not requester_email:
            return
        
        subject = f"Termination Executed - {self.member_name}"
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #6b7280;">Termination Executed</h2>
            
            <p>The membership termination has been executed:</p>
            
            <div style="background: #f9fafb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Member:</strong></td><td style="padding: 5px;">{self.member_name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Termination Type:</strong></td><td style="padding: 5px;">{self.termination_type}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Executed By:</strong></td><td style="padding: 5px;">{self.executed_by}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Execution Date:</strong></td><td style="padding: 5px;">{frappe.utils.format_datetime(self.execution_date)}</td></tr>
                </table>
            </div>
            
            <p>All associated system updates have been completed.</p>
            
            <p><a href="{frappe.utils.get_url()}/app/membership-termination-request/{self.name}">View Request</a></p>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[requester_email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        except Exception as e:
            frappe.log_error(f"Failed to send execution notification: {str(e)}", "Termination Execution Notification")
    
    def set_approval_requirements(self):
        """Set whether secondary approval is required based on termination type"""
        disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
        
        if self.termination_type in disciplinary_types:
            self.requires_secondary_approval = 1
            
            # Set status to pending approval if not already set and we're past draft
            if self.status == "Draft" and not self.is_new():
                self.status = "Pending"
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
            self.is_chapter_board_member()
        )
        
        if not can_initiate and self.is_new():
            frappe.throw(_("You don't have permission to initiate membership terminations"))
        
        # For disciplinary terminations, check secondary approval permissions
        if self.requires_secondary_approval and self.secondary_approver:
            approver_roles = frappe.get_roles(self.secondary_approver)
            can_approve = (
                "System Manager" in approver_roles or
                "Association Manager" in approver_roles
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
            
            self.status = "Pending"
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
        if self.status != "Pending":
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
        """Execute comprehensive automatic system updates"""
        results = {}
        
        # Get member document
        member_doc = frappe.get_doc("Member", self.member)
        
        # 1. Enhanced SEPA mandate cancellation with payment processing cleanup
        if self.cancel_sepa_mandates:
            results['sepa_mandates'] = self.cancel_member_sepa_mandates_enhanced(member_doc)
        
        # 2. Cancel/update active memberships
        results['memberships'] = self.cancel_active_memberships(member_doc)
        
        # 3. Process outstanding invoices and payments  
        results['invoices'] = self.process_outstanding_invoices(member_doc)
        
        # 4. End board/committee positions with enhanced history tracking
        if self.end_board_positions:
            results['positions'] = self.end_all_positions_enhanced(member_doc)
        
        # 5. Update customer status and payment methods
        results['customer_updates'] = self.update_customer_status(member_doc)
        
        # 6. Handle subscription cancellations
        results['subscriptions'] = self.cancel_member_subscriptions(member_doc)
        
        # 7. Create comprehensive termination summary
        self.create_termination_summary(member_doc, results)
        
        return results
    
    def cancel_member_sepa_mandates_enhanced(self, member_doc):
        """Enhanced SEPA mandate cancellation with payment processing cleanup"""
        active_mandates = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member_doc.name,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id", "used_for_memberships", "used_for_donations"]
        )
        
        cancelled_mandates = []
        
        for mandate_data in active_mandates:
            mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
            
            # Store original details for logging
            original_details = {
                "mandate_id": mandate.mandate_id,
                "used_for_memberships": mandate.used_for_memberships,
                "used_for_donations": mandate.used_for_donations
            }
            
            # Cancel the mandate
            mandate.status = "Cancelled"
            mandate.is_active = 0
            mandate.cancelled_date = self.termination_date or today()
            mandate.cancelled_reason = f"Membership terminated - Request: {self.name}"
            
            # Add termination note
            if mandate.notes:
                mandate.notes += f"\n\nCancelled due to membership termination on {self.termination_date or today()}"
            else:
                mandate.notes = f"Cancelled due to membership termination on {self.termination_date or today()}"
            
            mandate.save()
            cancelled_mandates.append(original_details)
            
            # Log in audit trail
            self.add_audit_entry(
                "SEPA Mandate Cancelled", 
                f"Mandate {mandate.mandate_id} cancelled automatically",
                is_system=True
            )
        
        # Cancel any pending direct debit entries
        self.cancel_pending_direct_debits(member_doc)
        
        return len(cancelled_mandates)
    
    def cancel_pending_direct_debits(self, member_doc):
        """Cancel any pending direct debit entries for this member"""
        # Look for pending direct debit batch entries
        try:
            pending_entries = frappe.get_all(
                "Direct Debit Batch Entry",  # Assuming this doctype exists
                filters={
                    "member": member_doc.name,
                    "status": ["in", ["Pending", "Draft"]]
                },
                fields=["name", "parent"]
            )
            
            for entry in pending_entries:
                entry_doc = frappe.get_doc("Direct Debit Batch Entry", entry.name)
                entry_doc.status = "Cancelled"
                entry_doc.cancellation_reason = f"Member terminated - Request: {self.name}"
                entry_doc.save()
                
                self.add_audit_entry(
                    "Direct Debit Entry Cancelled", 
                    f"Cancelled pending direct debit entry in batch {entry.parent}",
                    is_system=True
                )
        except Exception as e:
            # Log error but don't fail the entire process
            frappe.log_error(f"Error cancelling direct debit entries: {str(e)}", "Termination Direct Debit Cleanup")
    
    def cancel_active_memberships(self, member_doc):
        """Cancel all active memberships for this member"""
        active_memberships = frappe.get_all(
            "Membership",
            filters={
                "member": member_doc.name,
                "status": ["in", ["Active", "Pending"]],
                "docstatus": 1
            },
            fields=["name", "status", "membership_type", "start_date"]
        )
        
        cancelled_memberships = []
        
        for membership_data in active_memberships:
            membership = frappe.get_doc("Membership", membership_data.name)
            
            # Set cancellation details
            membership.status = "Cancelled"
            membership.cancellation_date = self.termination_date or today()
            membership.cancellation_reason = f"Membership terminated - Request: {self.name}"
            membership.cancellation_type = "Immediate"
            
            # Use the flags to allow update after submit
            membership.flags.ignore_validate_update_after_submit = True
            membership.save()
            
            cancelled_memberships.append({
                "name": membership.name,
                "type": membership.membership_type,
                "start_date": membership.start_date
            })
            
            # Cancel associated subscription if exists
            if membership.subscription:
                self.cancel_membership_subscription(membership.subscription)
            
            self.add_audit_entry(
                "Membership Cancelled", 
                f"Cancelled membership {membership.name} ({membership.membership_type})",
                is_system=True
            )
        
        return len(cancelled_memberships)
    
    def cancel_membership_subscription(self, subscription_name):
        """Cancel a specific subscription"""
        try:
            subscription = frappe.get_doc("Subscription", subscription_name)
            if subscription.status != "Cancelled":
                subscription.flags.ignore_permissions = True
                subscription.cancel_subscription()
                
                self.add_audit_entry(
                    "Subscription Cancelled", 
                    f"Cancelled subscription {subscription_name}",
                    is_system=True
                )
        except Exception as e:
            frappe.log_error(f"Error cancelling subscription {subscription_name}: {str(e)}", "Termination Subscription Cancellation")
    
    def process_outstanding_invoices(self, member_doc):
        """Process outstanding invoices for terminated member"""
        if not member_doc.customer:
            return {"processed": 0, "action": "No customer linked"}
        
        # Get unpaid invoices
        outstanding_invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "customer": member_doc.customer,
                "docstatus": 1,
                "status": ["in", ["Unpaid", "Overdue", "Partially Paid"]]
            },
            fields=["name", "grand_total", "outstanding_amount", "posting_date"]
        )
        
        invoice_actions = []
        
        for invoice_data in outstanding_invoices:
            invoice = frappe.get_doc("Sales Invoice", invoice_data.name)
            
            # Add note to invoice about member termination
            if invoice.remarks:
                invoice.remarks += f"\n\nMember terminated on {self.termination_date or today()} - Request: {self.name}"
            else:
                invoice.remarks = f"Member terminated on {self.termination_date or today()} - Request: {self.name}"
            
            # For membership-related invoices, mark as uncollectable if configured
            if hasattr(invoice, 'membership') and invoice.membership:
                invoice.custom_uncollectable = 1
                invoice.custom_uncollectable_reason = "Member terminated"
                
            invoice.flags.ignore_validate_update_after_submit = True
            invoice.save()
            
            invoice_actions.append({
                "invoice": invoice.name,
                "outstanding": invoice.outstanding_amount,
                "action": "Marked with termination note"
            })
            
            self.add_audit_entry(
                "Invoice Updated", 
                f"Updated invoice {invoice.name} with termination note",
                is_system=True
            )
        
        return {
            "processed": len(invoice_actions),
            "invoices": invoice_actions
        }
    
    def end_all_positions_enhanced(self, member_doc):
        """Enhanced board position management with comprehensive history tracking"""
        
        # Get volunteer record for this member
        volunteer_records = frappe.get_all(
            "Volunteer",
            filters={"member": member_doc.name},
            fields=["name"]
        )
        
        positions_ended = []
        
        for volunteer_record in volunteer_records:
            # End board positions
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["name", "parent", "chapter_role", "from_date"]
            )
            
            for position in board_positions:
                board_member = frappe.get_doc("Chapter Board Member", position.name)
                
                # Store position details for logging
                position_details = {
                    "chapter": position.parent,
                    "role": position.chapter_role,
                    "from_date": position.from_date,
                    "to_date": self.termination_date or today()
                }
                
                # End the position
                board_member.is_active = 0
                board_member.to_date = self.termination_date or today()
                board_member.save()
                
                positions_ended.append(position_details)
                
                # Update volunteer assignment history using the existing method
                try:
                    frappe.call(
                        "verenigingen.verenigingen.doctype.chapter.chapter.update_volunteer_assignment_history",
                        volunteer_id=volunteer_record.name,
                        chapter_name=position.parent,
                        role=position.chapter_role,
                        start_date=position.from_date,
                        end_date=self.termination_date or today()
                    )
                except Exception as e:
                    frappe.log_error(f"Error updating volunteer history: {str(e)}", "Termination Volunteer History Update")
                
                self.add_audit_entry(
                    "Board Position Ended", 
                    f"Ended {position.chapter_role} at {position.parent}",
                    is_system=True
                )
        
        return len(positions_ended)
    
    def update_customer_status(self, member_doc):
        """Update customer record with termination information"""
        if not member_doc.customer:
            return {"action": "No customer to update"}
        
        try:
            customer = frappe.get_doc("Customer", member_doc.customer)
            
            # Add termination note to customer
            termination_note = f"Member terminated on {self.termination_date or today()} - Type: {self.termination_type}"
            
            if customer.customer_details:
                customer.customer_details += f"\n\n{termination_note}"  
            else:
                customer.customer_details = termination_note
            
            # Set customer as inactive for disciplinary terminations
            if self.requires_secondary_approval:
                customer.disabled = 1
                
            customer.save()
            
            self.add_audit_entry(
                "Customer Updated", 
                f"Updated customer {customer.name} with termination details",
                is_system=True
            )
            
            return {"action": "Customer updated", "disabled": customer.disabled}
            
        except Exception as e:
            frappe.log_error(f"Error updating customer: {str(e)}", "Termination Customer Update")
            return {"action": "Error updating customer", "error": str(e)}
    
    def cancel_member_subscriptions(self, member_doc):
        """Cancel all active subscriptions for this member"""
        if not member_doc.customer:
            return {"cancelled": 0}
        
        # Find subscriptions for this customer
        active_subscriptions = frappe.get_all(
            "Subscription",
            filters={
                "party_type": "Customer",
                "party": member_doc.customer,
                "status": ["in", ["Active", "Past Due"]]
            },
            fields=["name", "status"]
        )
        
        cancelled_count = 0
        
        for sub_data in active_subscriptions:
            try:
                subscription = frappe.get_doc("Subscription", sub_data.name)
                subscription.flags.ignore_permissions = True
                subscription.cancel_subscription()
                cancelled_count += 1
                
                self.add_audit_entry(
                    "Subscription Cancelled", 
                    f"Cancelled subscription {subscription.name}",
                    is_system=True
                )
                
            except Exception as e:
                frappe.log_error(f"Error cancelling subscription {sub_data.name}: {str(e)}", "Termination Subscription Cancellation")
        
        return {"cancelled": cancelled_count}
    
    def create_termination_summary(self, member_doc, results):
        """Create comprehensive termination summary"""
        
        summary_lines = [
            f"Membership Termination Summary for {member_doc.full_name}",
            f"Executed on: {now()}",
            f"Termination Type: {self.termination_type}",
            f"Request: {self.name}",
            "",
            "System Updates Performed:"
        ]
        
        if results.get('sepa_mandates', 0) > 0:
            summary_lines.append(f"• Cancelled {results['sepa_mandates']} SEPA mandate(s)")
        
        if results.get('memberships', 0) > 0:
            summary_lines.append(f"• Cancelled {results['memberships']} active membership(s)")
        
        if results.get('positions', 0) > 0:
            summary_lines.append(f"• Ended {results['positions']} board position(s)")
        
        if results.get('invoices', {}).get('processed', 0) > 0:
            summary_lines.append(f"• Updated {results['invoices']['processed']} outstanding invoice(s)")
        
        if results.get('subscriptions', {}).get('cancelled', 0) > 0:
            summary_lines.append(f"• Cancelled {results['subscriptions']['cancelled']} subscription(s)")
        
        summary_lines.append("")
        summary_lines.append("Customer Status:")
        if results.get('customer_updates', {}).get('disabled'):
            summary_lines.append("• Customer account disabled")
        else:
            summary_lines.append("• Customer account marked with termination note")
        
        # Store summary in execution notes
        self.execution_notes = "\n".join(summary_lines)
        
        # Also log as audit entry
        self.add_audit_entry(
            "Termination Summary Created", 
            f"Comprehensive termination completed with {sum([v for v in results.values() if isinstance(v, int)])} system updates",
            is_system=True
        )
    
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
        """Enhanced notification when approval is required"""
        if not self.secondary_approver:
            return
        
        # Get approver details
        approver = frappe.get_doc("User", self.secondary_approver)
        
        if not approver.email:
            return
        
        # Enhanced email with better formatting and more details
        subject = f"🚨 Urgent: Disciplinary Termination Approval Required - {self.member_name}"
        
        # Get member details for context
        member_doc = frappe.get_doc("Member", self.member)
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2 style="color: #d73527;">Disciplinary Termination Approval Required</h2>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Member Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Name:</strong></td><td style="padding: 5px;">{self.member_name}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Member ID:</strong></td><td style="padding: 5px;">{self.member}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Email:</strong></td><td style="padding: 5px;">{member_doc.email or 'Not provided'}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Primary Chapter:</strong></td><td style="padding: 5px;">{getattr(member_doc, 'primary_chapter', 'Not assigned') or 'Not assigned'}</td></tr>
                </table>
            </div>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h3>Termination Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px;"><strong>Type:</strong></td><td style="padding: 5px;"><span style="background: #dc3545; color: white; padding: 2px 8px; border-radius: 3px;">{self.termination_type}</span></td></tr>
                    <tr><td style="padding: 5px;"><strong>Requested By:</strong></td><td style="padding: 5px;">{self.requested_by}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Request Date:</strong></td><td style="padding: 5px;">{frappe.utils.format_date(self.request_date)}</td></tr>
                    <tr><td style="padding: 5px;"><strong>Reason:</strong></td><td style="padding: 5px;">{self.termination_reason}</td></tr>
                </table>
            </div>
            
            {f'<div style="background: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0;"><h4>Documentation:</h4><div style="white-space: pre-wrap;">{self.disciplinary_documentation}</div></div>' if self.disciplinary_documentation else ''}
            
            <div style="background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Required Action</h3>
                <p>This disciplinary termination requires your approval as an Association Manager. Please review the documentation and either approve or reject this request.</p>
                
                <p><strong>⚠️ Important:</strong> Approved disciplinary terminations will:</p>
                <ul>
                    <li>Cancel all SEPA mandates immediately</li>
                    <li>End all board/committee positions</li>
                    <li>Cancel active memberships and subscriptions</li>
                    <li>Be recorded in the expulsion report for governance oversight</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/app/membership-termination-request/{self.name}" 
                   style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Review and Approve/Reject Request
                </a>
            </div>
            
            <div style="font-size: 12px; color: #6c757d; margin-top: 30px;">
                <p>This is an automated notification from the membership termination system.</p>
                <p>Request ID: {self.name} | Generated: {now()}</p>
            </div>
        </div>
        """
        
        try:
            frappe.sendmail(
                recipients=[approver.email],
                subject=subject,
                message=message,
                reference_doctype=self.doctype,
                reference_name=self.name,
                header=["Termination Approval Required", "red"]
            )
            
            self.add_audit_entry(
                "Approval Notification Sent", 
                f"Enhanced notification sent to {approver.email}",
                is_system=True
            )
            
        except Exception as e:
            frappe.log_error(f"Failed to send enhanced approval notification: {str(e)}", "Termination Approval Notification")

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
                is_chapter_board_member(user)
            ),
            'requires_secondary_approval': True,
            'can_approve': (
                "System Manager" in user_roles or
                "Association Manager" in user_roles
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
            hr.role IN ('System Manager', 'Association Manager')
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

@frappe.whitelist()
def get_termination_impact_preview(member):
    """Get preview of what will be affected by termination"""
    member_doc = frappe.get_doc("Member", member)
    
    impact = {
        "sepa_mandates": 0,
        "active_memberships": 0,
        "board_positions": 0,
        "outstanding_invoices": 0,
        "subscriptions": 0,
        "customer_linked": bool(member_doc.customer)
    }
    
    # Count SEPA mandates
    impact["sepa_mandates"] = frappe.db.count("SEPA Mandate", {
        "member": member,
        "status": "Active",
        "is_active": 1
    })
    
    # Count active memberships
    impact["active_memberships"] = frappe.db.count("Membership", {
        "member": member,
        "status": ["in", ["Active", "Pending"]],
        "docstatus": 1
    })
    
    # Count board positions
    if volunteer_records := frappe.get_all("Volunteer", filters={"member": member}, fields=["name"]):
        for volunteer in volunteer_records:
            impact["board_positions"] += frappe.db.count("Chapter Board Member", {
                "volunteer": volunteer.name,
                "is_active": 1
            })
    
    # Count outstanding invoices
    if member_doc.customer:
        impact["outstanding_invoices"] = frappe.db.count("Sales Invoice", {
            "customer": member_doc.customer,
            "docstatus": 1,
            "status": ["in", ["Unpaid", "Overdue", "Partially Paid"]]
        })
        
        # Count active subscriptions
        impact["subscriptions"] = frappe.db.count("Subscription", {
            "party_type": "Customer",
            "party": member_doc.customer,
            "status": ["in", ["Active", "Past Due"]]
        })
    
    return impact

@frappe.whitelist()
def execute_termination_request(request_name):
    """Standalone method to execute a termination request"""
    request = frappe.get_doc("Membership Termination Request", request_name)
    return request.execute_termination()

@frappe.whitelist()
def get_member_termination_status_enhanced(member):
    """Get enhanced termination status for a member with detailed information"""
    
    # Check for active termination requests
    pending_requests = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member,
            "status": ["in", ["Draft", "Pending", "Approved"]]
        },
        fields=["name", "status", "termination_type", "request_date", "termination_date", "requested_by"],
        order_by="request_date desc"
    )
    
    # Check for executed terminations
    executed_requests = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member,
            "status": "Executed"
        },
        fields=["name", "termination_type", "execution_date", "termination_date", "executed_by"],
        limit=1,
        order_by="execution_date desc"
    )
    
    # Get additional context
    member_doc = frappe.get_doc("Member", member)
    
    # Check if member has any active system records
    active_systems = check_active_member_systems(member)
    
    result = {
        "pending_requests": pending_requests,
        "executed_requests": executed_requests,
        "is_terminated": len(executed_requests) > 0,
        "termination_date": executed_requests[0].execution_date if executed_requests else None,
        "termination_type": executed_requests[0].termination_type if executed_requests else None,
        "has_pending": len(pending_requests) > 0,
        "active_systems": active_systems,
        "member_name": member_doc.full_name
    }
    
    return result

def check_active_member_systems(member):
    """Check what systems still have active records for this member"""
    active_systems = {
        "sepa_mandates": 0,
        "memberships": 0,
        "board_positions": 0,
        "subscriptions": 0,
        "outstanding_invoices": 0
    }
    
    member_doc = frappe.get_doc("Member", member)
    
    # Count active SEPA mandates
    active_systems["sepa_mandates"] = frappe.db.count("SEPA Mandate", {
        "member": member,
        "status": "Active",
        "is_active": 1
    })
    
    # Count active memberships
    active_systems["memberships"] = frappe.db.count("Membership", {
        "member": member,
        "status": ["in", ["Active", "Pending"]],
        "docstatus": 1
    })
    
    # Count board positions
    volunteer_records = frappe.get_all("Volunteer", filters={"member": member}, fields=["name"])
    for volunteer in volunteer_records:
        active_systems["board_positions"] += frappe.db.count("Chapter Board Member", {
            "volunteer": volunteer.name,
            "is_active": 1
        })
    
    # Count customer-related records
    if member_doc.customer:
        active_systems["outstanding_invoices"] = frappe.db.count("Sales Invoice", {
            "customer": member_doc.customer,
            "docstatus": 1,
            "status": ["in", ["Unpaid", "Overdue", "Partially Paid"]]
        })
        
        active_systems["subscriptions"] = frappe.db.count("Subscription", {
            "party_type": "Customer",
            "party": member_doc.customer,
            "status": ["in", ["Active", "Past Due"]]
        })
    
    return active_systems

@frappe.whitelist()
def get_termination_statistics():
    """Get system-wide termination statistics for reporting"""
    
    # Get counts by status
    status_counts = {}
    for status in ["Draft", "Pending", "Approved", "Rejected", "Executed"]:
        status_counts[status] = frappe.db.count("Membership Termination Request", {"status": status})
    
    # Get counts by type
    type_counts = {}
    termination_types = ["Voluntary", "Non-payment", "Deceased", "Policy Violation", "Disciplinary Action", "Expulsion"]
    for t_type in termination_types:
        type_counts[t_type] = frappe.db.count("Membership Termination Request", {"termination_type": t_type})
    
    # Get recent activity (last 30 days)
    recent_requests = frappe.db.count("Membership Termination Request", {
        "request_date": [">=", add_days(today(), -30)]
    })
    
    recent_executions = frappe.db.count("Membership Termination Request", {
        "status": "Executed",
        "execution_date": [">=", add_days(today(), -30)]
    })
    
    # Get pending approvals
    pending_approvals = frappe.db.count("Membership Termination Request", {
        "status": "Pending"
    })
    
    return {
        "status_counts": status_counts,
        "type_counts": type_counts,
        "recent_activity": {
            "requests": recent_requests,
            "executions": recent_executions
        },
        "pending_approvals": pending_approvals,
        "total_requests": sum(status_counts.values())
    }

@frappe.whitelist()
def bulk_execute_termination_requests(request_names):
    """Execute multiple approved termination requests"""
    if isinstance(request_names, str):
        import json
        request_names = json.loads(request_names)
    
    results = {
        "successful": [],
        "failed": [],
        "total": len(request_names)
    }
    
    for request_name in request_names:
        try:
            request = frappe.get_doc("Membership Termination Request", request_name)
            
            if request.status != "Approved":
                results["failed"].append({
                    "request": request_name,
                    "error": "Request is not in approved status"
                })
                continue
            
            # Execute the termination
            success = request.execute_termination()
            
            if success:
                results["successful"].append({
                    "request": request_name,
                    "member": request.member_name
                })
            else:
                results["failed"].append({
                    "request": request_name,
                    "error": "Execution failed"
                })
                
        except Exception as e:
            results["failed"].append({
                "request": request_name,
                "error": str(e)
            })
            frappe.log_error(f"Bulk execution error for {request_name}: {str(e)}", "Bulk Termination Execution")
    
    return results

@frappe.whitelist()
def get_termination_audit_report(filters=None):
    """Generate comprehensive audit report of termination activities"""
    
    # Build base query
    query = """
        SELECT 
            mtr.name as request_id,
            mtr.member,
            mtr.member_name,
            mtr.termination_type,
            mtr.status,
            mtr.request_date,
            mtr.requested_by,
            mtr.approved_by,
            mtr.approval_date,
            mtr.executed_by,
            mtr.execution_date,
            mtr.sepa_mandates_cancelled,
            mtr.positions_ended,
            mtr.termination_reason
        FROM `tabMembership Termination Request` mtr
        WHERE 1=1
    """
    
    query_params = []
    
    # Apply filters if provided
    if filters:
        if filters.get('date_range'):
            start_date, end_date = filters['date_range'].split(',')
            query += " AND mtr.request_date BETWEEN %s AND %s"
            query_params.extend([start_date, end_date])
        
        if filters.get('status'):
            query += " AND mtr.status = %s"
            query_params.append(filters['status'])
        
        if filters.get('termination_type'):
            query += " AND mtr.termination_type = %s"
            query_params.append(filters['termination_type'])
        
        if filters.get('requested_by'):
            query += " AND mtr.requested_by = %s"
            query_params.append(filters['requested_by'])
    
    query += " ORDER BY mtr.request_date DESC"
    
    # Execute query
    data = frappe.db.sql(query, query_params, as_dict=True)
    
    # Enhance data with audit trail information
    for record in data:
        # Get audit trail count
        record['audit_entries'] = frappe.db.count("Termination Audit Entry", {
            "parent": record['request_id']
        })
        
        # Calculate processing time if executed
        if record['execution_date'] and record['request_date']:
            delta = frappe.utils.date_diff(record['execution_date'], record['request_date'])
            record['processing_days'] = delta
    
    return data

@frappe.whitelist()
def get_expulsion_governance_report(filters=None):
    """Generate governance report for expulsions and disciplinary actions"""
    
    query = """
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
            ere.under_appeal,
            ere.appeal_date,
            mtr.name as termination_request,
            mtr.disciplinary_documentation,
            mtr.execution_date
        FROM `tabExpulsion Report Entry` ere
        LEFT JOIN `tabMembership Termination Request` mtr ON ere.member_id = mtr.member
        WHERE ere.expulsion_type IN ('Policy Violation', 'Disciplinary Action', 'Expulsion')
    """
    
    query_params = []
    
    if filters:
        if filters.get('date_range'):
            start_date, end_date = filters['date_range'].split(',')
            query += " AND ere.expulsion_date BETWEEN %s AND %s"
            query_params.extend([start_date, end_date])
        
        if filters.get('chapter'):
            query += " AND ere.chapter_involved = %s"
            query_params.append(filters['chapter'])
        
        if filters.get('status'):
            query += " AND ere.status = %s"
            query_params.append(filters['status'])
    
    query += " ORDER BY ere.expulsion_date DESC"
    
    data = frappe.db.sql(query, query_params, as_dict=True)
    
    # Add summary statistics
    summary = {
        "total_expulsions": len(data),
        "by_type": {},
        "by_status": {},
        "under_appeal": len([r for r in data if r['under_appeal']]),
        "chapters_involved": len(set([r['chapter_involved'] for r in data if r['chapter_involved']]))
    }
    
    # Calculate breakdown by type and status
    for record in data:
        # By type
        if record['expulsion_type'] not in summary['by_type']:
            summary['by_type'][record['expulsion_type']] = 0
        summary['by_type'][record['expulsion_type']] += 1
        
        # By status
        if record['status'] not in summary['by_status']:
            summary['by_status'][record['status']] = 0
        summary['by_status'][record['status']] += 1
    
    return {
        "data": data,
        "summary": summary
    }

@frappe.whitelist()
def validate_termination_permissions_enhanced(member, termination_type, user=None):
    """Enhanced permission validation with detailed feedback"""
    if not user:
        user = frappe.session.user
    
    user_roles = frappe.get_roles(user)
    member_doc = frappe.get_doc("Member", member)
    
    result = {
        "can_initiate": False,
        "can_approve": False,
        "requires_secondary_approval": False,
        "reasons": [],
        "user_roles": user_roles,
        "member_details": {
            "name": member_doc.full_name,
            "primary_chapter": getattr(member_doc, 'primary_chapter', None)
        }
    }
    
    # Check basic initiation permissions
    if ("System Manager" in user_roles or 
        "Association Manager" in user_roles):
        result["can_initiate"] = True
        result["reasons"].append("User has administrative role")
    elif is_chapter_board_member(user):
        result["can_initiate"] = True
        result["reasons"].append("User is a chapter board member")
    else:
        result["reasons"].append("User lacks required roles or board membership")
    
    # Check termination type specific rules
    disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
    
    if termination_type in disciplinary_types:
        result["requires_secondary_approval"] = True
        result["reasons"].append("Disciplinary terminations require secondary approval")
        
        # Check approval permissions
        if ("System Manager" in user_roles or 
            "Association Manager" in user_roles):
            result["can_approve"] = True
            result["reasons"].append("User can approve disciplinary terminations")
        else:
            result["reasons"].append("User cannot approve disciplinary terminations")
    else:
        result["can_approve"] = result["can_initiate"]
        result["reasons"].append("Standard terminations can be self-approved")
    
    # Check for any existing termination requests
    existing_requests = frappe.get_all(
        "Membership Termination Request",
        filters={
            "member": member,
            "status": ["in", ["Draft", "Pending", "Approved"]]
        },
        limit=1
    )
    
    if existing_requests:
        result["existing_request"] = True
        result["reasons"].append("Member already has pending termination request")
    
    return result
