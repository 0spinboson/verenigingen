# File: verenigingen/verenigingen/doctype/membership_termination_request/membership_termination_request.py

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
    
    def on_update_after_submit(self):
        """Handle status changes after document is submitted (workflow changes)"""
        if self.has_value_changed("status"):
            self.handle_status_change()
    
    def on_submit(self):
        """Called when document is submitted via workflow"""
        if self.status == "Executed":
            self.execute_termination_internal()
    
    def handle_status_change(self):
        """Handle workflow status changes"""
        old_status = self.get_doc_before_save().status if self.get_doc_before_save() else None
        new_status = self.status
        
        frappe.logger().info(f"Termination request {self.name} status changed from {old_status} to {new_status}")
        
        # Add audit trail entry
        self.add_audit_entry(
            "Status Changed", 
            f"Status changed from {old_status} to {new_status}",
            is_system=True
        )
        
        # Handle specific status transitions
        if new_status == "Executed" and old_status != "Executed":
            frappe.logger().info(f"Executing termination for request {self.name}")
            self.execute_termination_internal()
        elif new_status == "Approved":
            self.handle_approved_status()
        elif new_Status == "Rejected":
            self.handle_rejected_status()
    
    def execute_termination_internal(self):
        """Internal method for executing termination using existing system methods"""
        try:
            frappe.logger().info(f"Starting termination execution for {self.name}")
            
            # Validate we can execute
            if self.status != "Executed":
                frappe.throw(_("Termination can only be executed when status is 'Executed'"))
            
            # Execute system updates using existing methods
            results = self.execute_system_updates_via_existing_methods()
            
            # Update execution fields
            if not self.executed_by:
                self.executed_by = frappe.session.user
            if not self.execution_date:
                self.execution_date = now()
            
            # Update counters
            self.sepa_mandates_cancelled = results.get('sepa_mandates', 0)
            self.positions_ended = results.get('positions', 0) 
            self.newsletters_updated = 1 if results.get('newsletters') else 0
            
            # Update member status using existing methods
            self.update_member_status_via_existing_methods()
            
            # Save changes (use flags to avoid validation issues)
            self.flags.ignore_validate_update_after_submit = True
            self.save()
            
            self.add_audit_entry("Termination Executed", f"System updates completed successfully")
            
            frappe.logger().info(f"Termination execution completed for {self.name}")
            
            # Show success message
            frappe.msgprint(_("Membership termination executed successfully"))
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            frappe.logger().error(f"Termination execution failed for {self.name}: {error_msg}")
            self.add_audit_entry("Execution Failed", f"Error: {error_msg}")
            
            # Revert status if execution failed
            self.status = "Approved"
            self.flags.ignore_validate_update_after_submit = True
            self.save()
            
            frappe.throw(_("Failed to execute termination: {0}").format(error_msg))
    
    def execute_system_updates_via_existing_methods(self):
        """Execute system updates using existing methods from other doctypes"""
        results = {}
        
        # Get member document
        member_doc = frappe.get_doc("Member", self.member)
        
        frappe.logger().info(f"Starting system updates for member {self.member}")
        
        # 1. Cancel memberships using existing membership methods
        results['memberships'] = self.cancel_memberships_via_existing_methods(member_doc)
        
        # 2. Cancel SEPA mandates using existing methods
        if self.cancel_sepa_mandates:
            results['sepa_mandates'] = self.cancel_sepa_mandates_via_existing_methods(member_doc)
        
        # 3. End board positions using chapter methods
        if self.end_board_positions:
            results['positions'] = self.end_positions_via_chapter_methods(member_doc)
        
        # 4. Handle subscriptions via existing methods
        results['subscriptions'] = self.cancel_subscriptions_via_existing_methods(member_doc)
        
        # 5. Update customer status
        results['customer_updates'] = self.update_customer_status_via_existing_methods(member_doc)
        
        # 6. Process outstanding invoices
        results['invoices'] = self.process_outstanding_invoices_via_existing_methods(member_doc)
        
        frappe.logger().info(f"System updates completed: {results}")
        
        return results
    
    def cancel_memberships_via_existing_methods(self, member_doc):
        """Cancel memberships using existing membership.py methods"""
        active_memberships = frappe.get_all(
            "Membership",
            filters={
                "member": member_doc.name,
                "status": ["in", ["Active", "Pending"]],
                "docstatus": 1
            },
            fields=["name", "membership_type"]
        )
        
        frappe.logger().info(f"Found {len(active_memberships)} active memberships to cancel")
        
        cancelled_count = 0
        
        for membership_data in active_memberships:
            try:
                # Use the existing cancel_membership method from membership.py
                result = frappe.call(
                    "verenigingen.verenigingen.doctype.membership.membership.cancel_membership",
                    membership_name=membership_data.name,
                    cancellation_date=self.termination_date or today(),
                    cancellation_reason=f"Member terminated - Request: {self.name}",
                    cancellation_type="Immediate"
                )
                
                if result:
                    cancelled_count += 1
                    self.add_audit_entry(
                        "Membership Cancelled", 
                        f"Cancelled membership {membership_data.name} ({membership_data.membership_type}) via existing method",
                        is_system=True
                    )
                    frappe.logger().info(f"Cancelled membership {membership_data.name} via existing method")
                
            except Exception as e:
                frappe.logger().error(f"Failed to cancel membership {membership_data.name}: {str(e)}")
                # Try direct method as fallback
                try:
                    membership = frappe.get_doc("Membership", membership_data.name)
                    membership.status = "Cancelled"
                    membership.cancellation_date = self.termination_date or today()
                    membership.cancellation_reason = f"Member terminated - Request: {self.name}"
                    membership.cancellation_type = "Immediate"
                    membership.flags.ignore_validate_update_after_submit = True
                    membership.flags.ignore_permissions = True
                    membership.save()
                    cancelled_count += 1
                    frappe.logger().info(f"Cancelled membership {membership_data.name} via fallback method")
                except Exception as e2:
                    frappe.logger().error(f"Fallback cancellation also failed for {membership_data.name}: {str(e2)}")
        
        return cancelled_count
    
    def cancel_sepa_mandates_via_existing_methods(self, member_doc):
        """Cancel SEPA mandates using existing methods if available"""
        active_mandates = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member_doc.name,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id"]
        )
        
        frappe.logger().info(f"Found {len(active_mandates)} SEPA mandates to cancel")
        
        cancelled_count = 0
        
        for mandate_data in active_mandates:
            try:
                mandate = frappe.get_doc("SEPA Mandate", mandate_data.name)
                
                # Check if SEPA Mandate has its own cancellation method
                if hasattr(mandate, 'cancel_mandate'):
                    mandate.cancel_mandate(
                        reason=f"Member terminated - Request: {self.name}",
                        cancellation_date=self.termination_date or today()
                    )
                    frappe.logger().info(f"Cancelled SEPA mandate {mandate_data.mandate_id} via existing method")
                else:
                    # Use direct update as standard approach
                    mandate.status = "Cancelled"
                    mandate.is_active = 0
                    mandate.cancelled_date = self.termination_date or today()
                    mandate.cancelled_reason = f"Member terminated - Request: {self.name}"
                    
                    # Add termination note
                    if mandate.notes:
                        mandate.notes += f"\n\nCancelled due to membership termination on {self.termination_date or today()}"
                    else:
                        mandate.notes = f"Cancelled due to membership termination on {self.termination_date or today()}"
                    
                    mandate.flags.ignore_permissions = True
                    mandate.save()
                    frappe.logger().info(f"Cancelled SEPA mandate {mandate_data.mandate_id} via direct method")
                
                cancelled_count += 1
                
                self.add_audit_entry(
                    "SEPA Mandate Cancelled", 
                    f"Mandate {mandate_data.mandate_id} cancelled",
                    is_system=True
                )
                
            except Exception as e:
                frappe.logger().error(f"Failed to cancel SEPA mandate {mandate_data.name}: {str(e)}")
        
        return cancelled_count
    
    def end_positions_via_chapter_methods(self, member_doc):
        """End board positions using existing chapter methods"""
        volunteer_records = frappe.get_all(
            "Volunteer",
            filters={"member": member_doc.name},
            fields=["name"]
        )
        
        positions_ended = 0
        
        for volunteer_record in volunteer_records:
            # Get chapters where this volunteer has active board positions
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["name", "parent", "chapter_role", "from_date"]
            )
            
            frappe.logger().info(f"Found {len(board_positions)} board positions to end for volunteer {volunteer_record.name}")
            
            # Group positions by chapter to use bulk operations
            positions_by_chapter = {}
            for position in board_positions:
                if position.parent not in positions_by_chapter:
                    positions_by_chapter[position.parent] = []
                positions_by_chapter[position.parent].append({
                    'volunteer': volunteer_record.name,
                    'chapter_role': position.chapter_role,
                    'from_date': position.from_date,
                    'end_date': self.termination_date or today(),
                    'reason': f"Member terminated - Request: {self.name}"
                })
            
            # Process each chapter
            for chapter_name, chapter_positions in positions_by_chapter.items():
                try:
                    chapter_doc = frappe.get_doc("Chapter", chapter_name)
                    
                    # Use bulk deactivation method if available
                    if hasattr(chapter_doc, 'bulk_deactivate_board_members'):
                        result = chapter_doc.bulk_deactivate_board_members(chapter_positions)
                        if result.get('success'):
                            positions_ended += result.get('processed', 0)
                            self.add_audit_entry(
                                "Board Positions Ended", 
                                f"Ended {result.get('processed', 0)} positions in {chapter_name} via bulk method",
                                is_system=True
                            )
                        else:
                            frappe.logger().error(f"Bulk deactivation failed for {chapter_name}: {result.get('error')}")
                    else:
                        # Fall back to individual position ending
                        for pos_data in chapter_positions:
                            if hasattr(chapter_doc, 'remove_board_member'):
                                try:
                                    chapter_doc.remove_board_member(
                                        volunteer=pos_data['volunteer'],
                                        end_date=pos_data['end_date']
                                    )
                                    positions_ended += 1
                                except Exception as e:
                                    frappe.logger().error(f"Failed to remove board member via chapter method: {str(e)}")
                            else:
                                # Direct update fallback
                                board_positions_to_update = frappe.get_all(
                                    "Chapter Board Member",
                                    filters={
                                        "volunteer": pos_data['volunteer'],
                                        "parent": chapter_name,
                                        "is_active": 1
                                    },
                                    fields=["name"]
                                )
                                
                                for bp in board_positions_to_update:
                                    board_member = frappe.get_doc("Chapter Board Member", bp.name)
                                    board_member.is_active = 0
                                    board_member.to_date = pos_data['end_date']
                                    board_member.flags.ignore_permissions = True
                                    board_member.save()
                                    positions_ended += 1
                        
                        self.add_audit_entry(
                            "Board Positions Ended", 
                            f"Ended {len(chapter_positions)} positions in {chapter_name} via individual methods",
                            is_system=True
                        )
                    
                except Exception as e:
                    frappe.logger().error(f"Failed to process board positions for chapter {chapter_name}: {str(e)}")
        
        return positions_ended
    
    def cancel_subscriptions_via_existing_methods(self, member_doc):
        """Cancel subscriptions using existing subscription methods"""
        if not member_doc.customer:
            return {"cancelled": 0}
        
        # Find active subscriptions
        active_subscriptions = frappe.get_all(
            "Subscription",
            filters={
                "party_type": "Customer",
                "party": member_doc.customer,
                "status": ["in", ["Active", "Past Due"]]
            },
            fields=["name", "status"]
        )
        
        frappe.logger().info(f"Found {len(active_subscriptions)} subscriptions to cancel")
        
        cancelled_count = 0
        
        for sub_data in active_subscriptions:
            try:
                subscription = frappe.get_doc("Subscription", sub_data.name)
                
                # Use existing cancellation method
                if hasattr(subscription, 'cancel_subscription'):
                    subscription.flags.ignore_permissions = True
                    subscription.cancel_subscription()
                    cancelled_count += 1
                    
                    self.add_audit_entry(
                        "Subscription Cancelled", 
                        f"Cancelled subscription {subscription.name} via existing method",
                        is_system=True
                    )
                    
                    frappe.logger().info(f"Cancelled subscription {subscription.name} via existing method")
                else:
                    # Direct status update fallback  
                    subscription.status = "Cancelled"
                    subscription.flags.ignore_permissions = True
                    subscription.save()
                    cancelled_count += 1
                    frappe.logger().info(f"Cancelled subscription {subscription.name} via direct method")
                
            except Exception as e:
                frappe.logger().error(f"Error cancelling subscription {sub_data.name}: {str(e)}")
        
        return {"cancelled": cancelled_count}
    
    def update_customer_status_via_existing_methods(self, member_doc):
        """Update customer using existing customer methods if available"""
        if not member_doc.customer:
            return {"action": "No customer to update"}
        
        try:
            customer = frappe.get_doc("Customer", member_doc.customer)
            
            # Check if customer has a termination method
            if hasattr(customer, 'mark_as_terminated'):
                customer.mark_as_terminated(
                    reason=f"Member terminated - {self.termination_type}",
                    termination_date=self.termination_date or today(),
                    request_reference=self.name
                )
                frappe.logger().info(f"Updated customer {customer.name} via existing method")
            else:
                # Direct update approach
                termination_note = f"Member terminated on {self.termination_date or today()} - Type: {self.termination_type} - Request: {self.name}"
                
                if hasattr(customer, 'customer_details'):
                    if customer.customer_details:
                        customer.customer_details += f"\n\n{termination_note}"  
                    else:
                        customer.customer_details = termination_note
                
                # Set customer as inactive for disciplinary terminations
                if self.requires_secondary_approval:
                    customer.disabled = 1
                
                customer.flags.ignore_permissions = True
                customer.save()
                frappe.logger().info(f"Updated customer {customer.name} via direct method")
            
            self.add_audit_entry(
                "Customer Updated", 
                f"Updated customer {customer.name} with termination details",
                is_system=True
            )
            
            return {"action": "Customer updated", "method": "existing" if hasattr(customer, 'mark_as_terminated') else "direct"}
            
        except Exception as e:
            frappe.logger().error(f"Error updating customer: {str(e)}")
            return {"action": "Error updating customer", "error": str(e)}
    
    def process_outstanding_invoices_via_existing_methods(self, member_doc):
        """Process outstanding invoices using existing methods if available"""
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
        
        frappe.logger().info(f"Found {len(outstanding_invoices)} outstanding invoices to process")
        
        processed_count = 0
        
        for invoice_data in outstanding_invoices:
            try:
                invoice = frappe.get_doc("Sales Invoice", invoice_data.name)
                
                # Check if invoice has a termination annotation method
                if hasattr(invoice, 'add_termination_note'):
                    invoice.add_termination_note(
                        termination_request=self.name,
                        termination_date=self.termination_date or today(),
                        termination_type=self.termination_type
                    )
                else:
                    # Direct update approach
                    termination_note = f"Member terminated on {self.termination_date or today()} - Type: {self.termination_type} - Request: {self.name}"
                    
                    if invoice.remarks:
                        invoice.remarks += f"\n\n{termination_note}"
                    else:
                        invoice.remarks = termination_note
                    
                    invoice.flags.ignore_validate_update_after_submit = True
                    invoice.flags.ignore_permissions = True
                    invoice.save()
                
                processed_count += 1
                
                self.add_audit_entry(
                    "Invoice Updated", 
                    f"Updated invoice {invoice.name} with termination note",
                    is_system=True
                )
                
            except Exception as e:
                frappe.logger().error(f"Failed to update invoice {invoice_data.name}: {str(e)}")
        
        return {"processed": processed_count}
    
    def update_member_status_via_existing_methods(self):
        """Update member status using existing member methods and correct status values"""
        try:
            member_doc = frappe.get_doc("Member", self.member)
            
            # Check if member has a termination method
            if hasattr(member_doc, 'terminate_membership'):
                member_doc.terminate_membership(
                    termination_type=self.termination_type,
                    termination_date=self.termination_date or today(),
                    termination_request=self.name
                )
                frappe.logger().info(f"Updated member {self.member} via existing terminate_membership method")
            else:
                # Use correct status values based on termination type
                member_status = self.get_appropriate_member_status()
                
                if hasattr(member_doc, 'status'):
                    member_doc.status = member_status
                
                # Add termination information to available fields
                if hasattr(member_doc, 'notes'):
                    termination_note = f"Terminated on {self.execution_date} - Type: {self.termination_type} - Request: {self.name}"
                    if member_doc.notes:
                        member_doc.notes += f"\n\n{termination_note}"
                    else:
                        member_doc.notes = termination_note
                
                # Use member's existing save method
                member_doc.flags.ignore_permissions = True
                member_doc.flags.ignore_validate_update_after_submit = True
                member_doc.save()
                
                frappe.logger().info(f"Updated member {self.member} status to {member_status} via direct method")
            
            self.add_audit_entry(
                "Member Status Updated", 
                f"Updated member status via {'existing method' if hasattr(member_doc, 'terminate_membership') else 'direct method'}",
                is_system=True
            )
            
        except Exception as e:
            frappe.logger().error(f"Failed to update member status: {str(e)}")
            # Don't fail the entire termination for this
    
    def get_appropriate_member_status(self):
        """Get the appropriate member status based on termination type"""
        # Map termination types to valid member status values
        status_mapping = {
            'Voluntary': 'Expired',      # Member chose to leave
            'Non-payment': 'Suspended',  # Could be temporary
            'Deceased': 'Deceased',      # Clear mapping
            'Policy Violation': 'Suspended',     # Disciplinary but not permanent ban
            'Disciplinary Action': 'Suspended',   # Disciplinary suspension
            'Expulsion': 'Banned'        # Permanent ban from organization
        }
        
        return status_mapping.get(self.termination_type, 'Suspended')
    
    def add_audit_entry(self, action, details, is_system=False):
        """Add an entry to the audit trail with proper user handling"""
        # Handle system entries properly - use Administrator instead of "System"
        audit_user = frappe.session.user if not is_system else "Administrator"
        
        # Ensure the user exists
        if not frappe.db.exists("User", audit_user):
            audit_user = "Administrator"
        
        self.append("audit_trail", {
            "timestamp": now(),
            "action": action,
            "user": audit_user,
            "details": details,
            "system_action": 1 if is_system else 0
        })
    
    # Keep existing methods for approval workflow, etc.
    def set_approval_requirements(self):
        """Set whether secondary approval is required based on termination type"""
        disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
        
        if self.termination_type in disciplinary_types:
            self.requires_secondary_approval = 1
        else:
            self.requires_secondary_approval = 0
    
    def validate_permissions(self):
        """Validate user permissions for different termination types"""
        user_roles = frappe.get_roles(frappe.session.user)
        
        # Check if user can initiate terminations
        can_initiate = (
            "System Manager" in user_roles or
            "Association Manager" in user_roles
        )
        
        if not can_initiate and self.is_new():
            frappe.throw(_("You don't have permission to initiate membership terminations"))
    
    def validate_dates(self):
        """Validate termination and grace period dates"""
        if self.termination_date and getdate(self.termination_date) < getdate(self.request_date):
            frappe.throw(_("Termination date cannot be before request date"))
        
        if self.grace_period_end and self.termination_date:
            if getdate(self.grace_period_end) < getdate(self.termination_date):
                frappe.throw(_("Grace period end cannot be before termination date"))

# Module-level function for workflow integration
def on_workflow_action(doc, action):
    """Called by workflow when action is taken"""
    frappe.logger().info(f"Workflow action '{action}' taken on {doc.name}")
    
    if action == "Execute" and doc.status == "Executed":
        frappe.logger().info(f"Executing termination via workflow for {doc.name}")
        doc.execute_termination_internal()

# Module-level function for document hooks  
def handle_status_change(doc, method=None):
    """Handle status changes for termination requests"""
    if hasattr(doc, 'handle_status_change'):
        doc.handle_status_change()
