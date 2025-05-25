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
                "Association Manager" in approver_roles or
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
    
    # Enhanced notification system
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
            "status": ["in", ["Draft", "Pending Approval", "Approved"]]
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
    for status in ["Draft", "Pending Approval", "Approved", "Rejected", "Executed"]:
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
        "status": "Pending Approval"
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
        "Association Manager" in user_roles or 
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
            "Association Manager" in user_roles or 
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
            "status": ["in", ["Draft", "Pending Approval", "Approved"]]
        },
        limit=1
    )
    
    if existing_requests:
        result["existing_request"] = True
        result["reasons"].append("Member already has pending termination request")
    
    return result

# Add method to member.py for integration
def add_to_member_py():
    """
    Add this method to the Member class in member.py
    """
    @frappe.whitelist()
    def get_termination_readiness_check(self):
        """Check if member is ready for termination and what would be affected"""
        
        readiness = {
            "can_terminate": True,
            "warnings": [],
            "blockers": [],
            "impact": {}
        }
        
        # Check for active systems
        impact = get_termination_impact_preview(self.name)
        readiness["impact"] = impact
        
        # Check for blockers
        if impact["board_positions"] > 0:
            readiness["warnings"].append(f"Member holds {impact['board_positions']} board position(s)")
        
        if impact["outstanding_invoices"] > 5:  # More than 5 outstanding invoices
            readiness["warnings"].append(f"Member has {impact['outstanding_invoices']} outstanding invoices")
        
        # Check for pending termination requests
        pending = frappe.get_all(
            "Membership Termination Request",
            filters={
                "member": self.name,
                "status": ["in", ["Draft", "Pending Approval", "Approved"]]
            }
        )
        
        if pending:
            readiness["can_terminate"] = False
            readiness["blockers"].append("Member already has pending termination request")
        
        return readiness



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
