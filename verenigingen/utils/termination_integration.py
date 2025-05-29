# ===== File: verenigingen/utils/termination_integration.py =====
import frappe
from frappe import _
from frappe.utils import today, now

def cancel_membership_safe(membership_name, cancellation_date=None, cancellation_reason=None, cancellation_type="Immediate"):
    """
    Cancel membership safely without modifying ERPNext core
    Uses direct document manipulation
    """
    try:
        if not cancellation_date:
            cancellation_date = today()
            
        membership = frappe.get_doc("Membership", membership_name)
        
        # Validate cancellation is allowed
        if membership.status == "Cancelled":
            frappe.logger().info(f"Membership {membership_name} already cancelled")
            return True
        
        # Set cancellation details
        membership.status = "Cancelled"
        membership.cancellation_date = cancellation_date
        membership.cancellation_reason = cancellation_reason or "Membership cancelled"
        membership.cancellation_type = cancellation_type
        
        # Cancel associated subscription if exists
        if membership.subscription:
            cancel_subscription_safe(membership.subscription)
        
        # Save with proper flags
        membership.flags.ignore_validate_update_after_submit = True
        membership.flags.ignore_permissions = True
        membership.save()
        
        frappe.logger().info(f"Cancelled membership {membership_name}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to cancel membership {membership_name}: {str(e)}")
        return False

def cancel_subscription_safe(subscription_name):
    """
    Cancel subscription safely without modifying ERPNext core
    """
    try:
        subscription = frappe.get_doc("Subscription", subscription_name)
        if subscription.status != "Cancelled":
            subscription.flags.ignore_permissions = True
            subscription.cancel_subscription()  # Uses ERPNext's existing method
            frappe.logger().info(f"Cancelled subscription {subscription_name}")
        return True
    except Exception as e:
        frappe.logger().error(f"Failed to cancel subscription {subscription_name}: {str(e)}")
        return False

def cancel_sepa_mandate_safe(mandate_id, reason=None, cancellation_date=None):
    """
    Cancel SEPA mandate safely
    """
    try:
        if not cancellation_date:
            cancellation_date = today()
        
        mandate = frappe.get_doc("SEPA Mandate", mandate_id)
        
        # Update mandate status
        mandate.status = "Cancelled"
        mandate.is_active = 0
        mandate.cancelled_date = cancellation_date
        mandate.cancelled_reason = reason or "Mandate cancelled"
        
        # Add cancellation note
        cancellation_note = f"Cancelled on {cancellation_date}"
        if reason:
            cancellation_note += f" - Reason: {reason}"
        
        if mandate.notes:
            mandate.notes += f"\n\n{cancellation_note}"
        else:
            mandate.notes = cancellation_note
        
        # Save the mandate
        mandate.flags.ignore_permissions = True
        mandate.save()
        
        frappe.logger().info(f"Cancelled SEPA mandate {mandate.mandate_id}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to cancel SEPA mandate {mandate_id}: {str(e)}")
        return False

def update_customer_safe(customer_name, termination_note, disable_for_disciplinary=False):
    """
    Update customer record safely without modifying ERPNext core
    """
    try:
        customer = frappe.get_doc("Customer", customer_name)
        
        # Add to customer details field (standard ERPNext field)
        if hasattr(customer, 'customer_details'):
            if customer.customer_details:
                customer.customer_details += f"\n\n{termination_note}"
            else:
                customer.customer_details = termination_note
        
        # For disciplinary terminations, disable the customer
        if disable_for_disciplinary:
            customer.disabled = 1
        
        # Save customer
        customer.flags.ignore_permissions = True
        customer.save()
        
        frappe.logger().info(f"Updated customer {customer_name}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to update customer {customer_name}: {str(e)}")
        return False

def update_invoice_safe(invoice_name, termination_note):
    """
    Update invoice with termination note safely
    """
    try:
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Add to invoice remarks (standard ERPNext field)
        if invoice.remarks:
            invoice.remarks += f"\n\n{termination_note}"
        else:
            invoice.remarks = termination_note
        
        # Save invoice
        invoice.flags.ignore_validate_update_after_submit = True
        invoice.flags.ignore_permissions = True
        invoice.save()
        
        frappe.logger().info(f"Updated invoice {invoice_name}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to update invoice {invoice_name}: {str(e)}")
        return False

def update_member_status_safe(member_name, termination_type, termination_date, termination_request=None):
    """
    Update member status safely using standard fields
    """
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Map termination types to valid member status values
        status_mapping = {
            'Voluntary': 'Expired',      # Member chose to leave
            'Non-payment': 'Suspended',  # Could be temporary
            'Deceased': 'Deceased',      # Clear mapping
            'Policy Violation': 'Suspended',     # Disciplinary but not permanent ban
            'Disciplinary Action': 'Suspended',   # Disciplinary suspension
            'Expulsion': 'Banned'        # Permanent ban from organization
        }
        
        # Update member status
        if hasattr(member, 'status'):
            member.status = status_mapping.get(termination_type, 'Suspended')
        
        # Add termination information to notes (standard field)
        termination_note = f"Membership terminated on {termination_date} - Type: {termination_type}"
        if termination_request:
            termination_note += f" - Request: {termination_request}"
        
        if member.notes:
            member.notes += f"\n\n{termination_note}"
        else:
            member.notes = termination_note
        
        # Save the member
        member.flags.ignore_permissions = True
        member.save()
        
        frappe.logger().info(f"Updated member {member_name} status to {member.status}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to update member {member_name}: {str(e)}")
        return False

def end_board_positions_safe(member_name, end_date, reason):
    """
    End board positions safely using existing chapter methods
    """
    try:
        # Get volunteer records for this member
        volunteer_records = frappe.get_all("Volunteer", filters={"member": member_name}, fields=["name"])
        
        positions_ended = 0
        
        for volunteer_record in volunteer_records:
            # Get active board positions
            board_positions = frappe.get_all(
                "Chapter Board Member",
                filters={
                    "volunteer": volunteer_record.name,
                    "is_active": 1
                },
                fields=["name", "parent", "chapter_role", "from_date"]
            )
            
            for position in board_positions:
                try:
                    # Use direct document update (safest approach)
                    board_member = frappe.get_doc("Chapter Board Member", position.name)
                    board_member.is_active = 0
                    board_member.to_date = end_date
                    
                    # Add reason to notes if field exists
                    if hasattr(board_member, 'notes'):
                        if board_member.notes:
                            board_member.notes += f"\n\nEnded: {reason}"
                        else:
                            board_member.notes = f"Ended: {reason}"
                    
                    board_member.flags.ignore_permissions = True
                    board_member.save()
                    
                    positions_ended += 1
                    frappe.logger().info(f"Ended board position {position.chapter_role} at {position.parent}")
                    
                except Exception as e:
                    frappe.logger().error(f"Failed to end board position {position.name}: {str(e)}")
        
        return positions_ended
        
    except Exception as e:
        frappe.logger().error(f"Failed to end board positions for {member_name}: {str(e)}")
        return 0
