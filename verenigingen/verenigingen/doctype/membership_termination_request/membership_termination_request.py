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
        elif new_status == "Rejected":
            self.handle_rejected_status()
    
    def execute_termination_internal(self):
        """Internal method for executing termination using safe integration methods"""
        try:
            frappe.logger().info(f"Starting termination execution for {self.name}")
            
            # Validate we can execute
            if self.status != "Executed":
                frappe.throw(_("Termination can only be executed when status is 'Executed'"))
            
            # Execute system updates using safe integration methods
            results = self.execute_system_updates_safely()
            
            # Update execution fields
            if not self.executed_by:
                self.executed_by = frappe.session.user
            if not self.execution_date:
                self.execution_date = now()
            
            # Update counters from results
            self.sepa_mandates_cancelled = results.get('sepa_mandates_cancelled', 0)
            self.positions_ended = results.get('positions_ended', 0)
            self.newsletters_updated = 1 if results.get('customer_updated') else 0
            
            # Save changes (use flags to avoid validation issues)
            self.flags.ignore_validate_update_after_submit = True
            self.save()
            
            self.add_audit_entry("Termination Executed", f"System updates completed: {len(results.get('actions_taken', []))} actions")
            
            frappe.logger().info(f"Termination execution completed for {self.name}")
            
            # Show success message
            if results.get('errors'):
                frappe.msgprint(
                    _("Membership termination executed with {0} warnings. Check logs for details.").format(len(results['errors'])),
                    indicator='orange'
                )
            else:
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
    
    def execute_system_updates_safely(self):
        """Execute system updates using safe integration methods from utils"""
        from verenigingen.utils.termination_integration import (
            cancel_membership_safe,
            cancel_sepa_mandate_safe,
            update_customer_safe,
            update_member_status_safe,
            end_board_positions_safe,
            cancel_subscription_safe,
            update_invoice_safe
        )
        
        results = {
            "actions_taken": [],
            "errors": [],
            "sepa_mandates_cancelled": 0,
            "memberships_cancelled": 0,
            "positions_ended": 0,
            "subscriptions_cancelled": 0,
            "invoices_updated": 0,
            "customer_updated": False,
            "member_updated": False
        }
        
        # Get member document
        member_doc = frappe.get_doc("Member", self.member)
        
        frappe.logger().info(f"Starting safe system updates for member {self.member}")
        
        # 1. Cancel active memberships
        active_memberships = frappe.get_all(
            "Membership",
            filters={
                "member": member_doc.name,
                "status": ["in", ["Active", "Pending"]],
                "docstatus": 1
            },
            fields=["name", "membership_type", "subscription"]
        )
        
        frappe.logger().info(f"Found {len(active_memberships)} active memberships to cancel")
        
        for membership_data in active_memberships:
            if cancel_membership_safe(
                membership_data.name,
                self.termination_date or today(),
                f"Member terminated - Request: {self.name}",
                "Immediate"
            ):
                results["memberships_cancelled"] += 1
                results["actions_taken"].append(f"Cancelled membership {membership_data.name}")
                
                # Also cancel associated subscription
                if membership_data.subscription:
                    if cancel_subscription_safe(membership_data.subscription):
                        results["subscriptions_cancelled"] += 1
                        results["actions_taken"].append(f"Cancelled subscription {membership_data.subscription}")
                    else:
                        results["errors"].append(f"Failed to cancel subscription {membership_data.subscription}")
            else:
                results["errors"].append(f"Failed to cancel membership {membership_data.name}")
        
        # 2. Cancel SEPA mandates if requested
        if self.cancel_sepa_mandates:
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
            
            for mandate_data in active_mandates:
                if cancel_sepa_mandate_safe(
                    mandate_data.name,
                    f"Member terminated - Request: {self.name}",
                    self.termination_date or today()
                ):
                    results["sepa_mandates_cancelled"] += 1
                    results["actions_taken"].append(f"Cancelled SEPA mandate {mandate_data.mandate_id}")
                else:
                    results["errors"].append(f"Failed to cancel SEPA mandate {mandate_data.mandate_id}")
        
        # 3. End board positions if requested
        if self.end_board_positions:
            positions_ended = end_board_positions_safe(
                member_doc.name,
                self.termination_date or today(),
                f"Member terminated - Request: {self.name}"
            )
            results["positions_ended"] = positions_ended
            if positions_ended > 0:
                results["actions_taken"].append(f"Ended {positions_ended} board position(s)")
        
        # 4. Update member status
        if update_member_status_safe(
            member_doc.name,
            self.termination_type,
            self.termination_date or today(),
            self.name
        ):
            results["member_updated"] = True
            results["actions_taken"].append("Updated member status")
        else:
            results["errors"].append("Failed to update member status")
        
        # 5. Update customer record if exists
        if member_doc.customer:
            termination_note = f"Member terminated on {self.termination_date or today()} - Type: {self.termination_type} - Request: {self.name}"
            disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
            disable_customer = self.termination_type in disciplinary_types
            
            if update_customer_safe(member_doc.customer, termination_note, disable_customer):
                results["customer_updated"] = True
                results["actions_taken"].append("Updated customer record")
            else:
                results["errors"].append("Failed to update customer record")
        
        # 6. Update outstanding invoices
        if member_doc.customer:
            outstanding_invoices = frappe.get_all(
                "Sales Invoice",
                filters={
                    "customer": member_doc.customer,
                    "docstatus": 1,
                    "status": ["in", ["Unpaid", "Overdue", "Partially Paid"]]
                },
                fields=["name"]
            )
            
            termination_note = f"Member terminated on {self.termination_date or today()} - Request: {self.name}"
            
            for invoice_data in outstanding_invoices:
                if update_invoice_safe(invoice_data.name, termination_note):
                    results["invoices_updated"] += 1
                else:
                    results["errors"].append(f"Failed to update invoice {invoice_data.name}")
            
            if results["invoices_updated"] > 0:
                results["actions_taken"].append(f"Updated {results['invoices_updated']} outstanding invoice(s)")
        
        # 7. Handle additional subscriptions not linked to memberships
        if member_doc.customer:
            remaining_subscriptions = frappe.get_all(
                "Subscription",
                filters={
                    "party_type": "Customer",
                    "party": member_doc.customer,
                    "status": ["in", ["Active", "Past Due"]]
                },
                fields=["name"]
            )
            
            for sub_data in remaining_subscriptions:
                if cancel_subscription_safe(sub_data.name):
                    results["subscriptions_cancelled"] += 1
                    results["actions_taken"].append(f"Cancelled additional subscription {sub_data.name}")
                else:
                    results["errors"].append(f"Failed to cancel subscription {sub_data.name}")
        
        # Log results
        frappe.logger().info(f"System updates completed: {results}")
        
        # Add detailed audit entries
        for action in results["actions_taken"]:
            self.add_audit_entry("System Update", action, is_system=True)
        
        for error in results["errors"]:
            self.add_audit_entry("System Update Error", error, is_system=True)
        
        return results
    
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
    
    def set_approval_requirements(self):
        """Set whether secondary approval is required based on termination type"""
        disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
        
        if self.termination_type in disciplinary_types:
            self.requires_secondary_approval = 1
        else:
            self.requires_secondary_approval = 0
    
    def handle_approved_status(self):
        """Handle when termination request is approved"""
        if not self.approved_by:
            self.approved_by = frappe.session.user
        if not self.approval_date:
            self.approval_date = now()
        
        # Set default termination date if not provided
        if not self.termination_date:
            self.termination_date = today()
        
        # Add to expulsion report if disciplinary
        if self.requires_secondary_approval:
            self.add_to_expulsion_report()
    
    def handle_rejected_status(self):
        """Handle when termination request is rejected"""
        if not self.approved_by:
            self.approved_by = frappe.session.user
        if not self.approval_date:
            self.approval_date = now()
    
    def add_to_expulsion_report(self):
        """Add disciplinary termination to expulsion report"""
        if self.termination_type not in ['Policy Violation', 'Disciplinary Action', 'Expulsion']:
            return
        
        try:
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
            
            expulsion_entry.flags.ignore_permissions = True
            expulsion_entry.insert()
            
            frappe.logger().info(f"Added expulsion report entry for {self.member_name}")
            
        except Exception as e:
            frappe.logger().error(f"Failed to create expulsion report entry: {str(e)}")
    
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
    
    @frappe.whitelist()
    def get_termination_preview(self):
        """Get preview of what will be affected by this termination"""
        from verenigingen.utils.termination_utils import validate_termination_readiness
        return validate_termination_readiness(self.member)
    
    @frappe.whitelist()
    def simulate_execution(self):
        """Simulate what would happen if this termination were executed"""
        from verenigingen.utils.termination_utils import get_termination_impact_summary
        return get_termination_impact_summary(self.member)

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

# Public API methods that can be called from outside
@frappe.whitelist()
def get_termination_impact_preview(member):
    """Public API to get termination impact preview"""
    from verenigingen.utils.termination_utils import validate_termination_readiness
    return validate_termination_readiness(member)

@frappe.whitelist()
def execute_safe_member_termination(member, termination_type, termination_date=None):
    """Public API to execute termination using safe methods"""
    from verenigingen.api.termination_api import execute_safe_termination
    return execute_safe_termination(member, termination_type, termination_date)
