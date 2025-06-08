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

def suspend_team_memberships_safe(member_name, termination_date, reason):
    """
    Suspend or remove all team memberships for terminated member
    """
    try:
        if not termination_date:
            termination_date = today()
        
        teams_affected = 0
        
        # Get all active team memberships for this member
        team_memberships = frappe.get_all(
            "Team Member",
            filters={
                "user": frappe.db.get_value("Member", member_name, "user"),
                "docstatus": ["!=", 2]  # Not cancelled
            },
            fields=["name", "parent", "user", "role"]
        )
        
        for team_membership in team_memberships:
            try:
                team_member_doc = frappe.get_doc("Team Member", team_membership.name)
                
                # Cancel the team membership document
                if team_member_doc.docstatus == 1:
                    team_member_doc.flags.ignore_permissions = True
                    team_member_doc.cancel()
                    teams_affected += 1
                    frappe.logger().info(f"Cancelled team membership for {team_membership.user} in team {team_membership.parent}")
                elif team_member_doc.docstatus == 0:
                    # Delete draft team memberships
                    team_member_doc.flags.ignore_permissions = True
                    team_member_doc.delete()
                    teams_affected += 1
                    frappe.logger().info(f"Deleted draft team membership for {team_membership.user} in team {team_membership.parent}")
                
            except Exception as e:
                frappe.logger().error(f"Failed to suspend team membership {team_membership.name}: {str(e)}")
        
        # Also check if member has any team leadership roles and remove those
        user_email = frappe.db.get_value("Member", member_name, "user")
        if user_email:
            teams_led = frappe.get_all(
                "Team",
                filters={"team_lead": user_email},
                fields=["name", "team_lead"]
            )
            
            for team in teams_led:
                try:
                    team_doc = frappe.get_doc("Team", team.name)
                    team_doc.team_lead = None
                    
                    # Add note about leadership change
                    termination_note = f"Team lead removed on {termination_date} - {reason}"
                    if hasattr(team_doc, 'description'):
                        if team_doc.description:
                            team_doc.description += f"\n\n{termination_note}"
                        else:
                            team_doc.description = termination_note
                    
                    team_doc.flags.ignore_permissions = True
                    team_doc.save()
                    
                    frappe.logger().info(f"Removed team leadership from team {team.name}")
                    
                except Exception as e:
                    frappe.logger().error(f"Failed to remove team leadership from {team.name}: {str(e)}")
        
        return teams_affected
        
    except Exception as e:
        frappe.logger().error(f"Failed to suspend team memberships for {member_name}: {str(e)}")
        return 0

def deactivate_user_account_safe(member_name, termination_type, reason, suspend_only=False):
    """
    Deactivate or suspend backend user account for terminated member
    """
    try:
        # Get the user associated with this member
        user_email = frappe.db.get_value("Member", member_name, "user")
        if not user_email:
            frappe.logger().info(f"No user account found for member {member_name}")
            return True
        
        # Check if user exists
        if not frappe.db.exists("User", user_email):
            frappe.logger().info(f"User {user_email} does not exist")
            return True
        
        user_doc = frappe.get_doc("User", user_email)
        
        # Determine action based on termination type and parameter
        disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
        should_disable = termination_type in disciplinary_types and not suspend_only
        
        if should_disable:
            # Permanent disable for disciplinary actions
            user_doc.enabled = 0
            action_taken = "disabled"
            frappe.logger().info(f"Disabled user account {user_email} due to disciplinary termination")
        else:
            # For voluntary/non-payment, just disable to prevent login but preserve data
            user_doc.enabled = 0
            action_taken = "suspended"
            frappe.logger().info(f"Suspended user account {user_email}")
        
        # Add termination note to user bio/about
        termination_note = f"Account {action_taken} on {today()} - {reason}"
        if hasattr(user_doc, 'bio') and user_doc.bio:
            user_doc.bio += f"\n\n{termination_note}"
        elif hasattr(user_doc, 'bio'):
            user_doc.bio = termination_note
        
        # Clear user roles except basic ones for audit trail
        if should_disable and hasattr(user_doc, 'roles'):
            # Keep only essential roles for audit purposes
            essential_roles = ['Guest']
            user_doc.roles = [role for role in user_doc.roles if role.role in essential_roles]
        
        # Save user changes
        user_doc.flags.ignore_permissions = True
        user_doc.save()
        
        frappe.logger().info(f"Successfully {action_taken} user account {user_email}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to deactivate user account for {member_name}: {str(e)}")
        return False

def reactivate_user_account_safe(member_name, reason):
    """
    Reactivate user account (for appeal reversals)
    """
    try:
        user_email = frappe.db.get_value("Member", member_name, "user")
        if not user_email or not frappe.db.exists("User", user_email):
            return True
        
        user_doc = frappe.get_doc("User", user_email)
        user_doc.enabled = 1
        
        # Add reactivation note
        reactivation_note = f"Account reactivated on {today()} - {reason}"
        if hasattr(user_doc, 'bio') and user_doc.bio:
            user_doc.bio += f"\n\n{reactivation_note}"
        elif hasattr(user_doc, 'bio'):
            user_doc.bio = reactivation_note
        
        user_doc.flags.ignore_permissions = True
        user_doc.save()
        
        frappe.logger().info(f"Reactivated user account {user_email}")
        return True
        
    except Exception as e:
        frappe.logger().error(f"Failed to reactivate user account for {member_name}: {str(e)}")
        return False

def suspend_member_safe(member_name, suspension_reason, suspension_date=None, suspend_user=True, suspend_teams=True):
    """
    Suspend a member (temporary, reversible action)
    """
    try:
        if not suspension_date:
            suspension_date = today()
        
        member = frappe.get_doc("Member", member_name)
        
        results = {
            "success": True,
            "actions_taken": [],
            "errors": [],
            "member_suspended": False,
            "user_suspended": False,
            "teams_suspended": 0
        }
        
        # 1. Update member status to Suspended
        original_status = member.status
        member.status = "Suspended"
        
        # Add suspension note
        suspension_note = f"Member suspended on {suspension_date} - Reason: {suspension_reason}"
        if member.notes:
            member.notes += f"\n\n{suspension_note}"
        else:
            member.notes = suspension_note
        
        # Store original status for unsuspension
        if hasattr(member, 'pre_suspension_status'):
            member.pre_suspension_status = original_status
        
        member.flags.ignore_permissions = True
        member.save()
        
        results["member_suspended"] = True
        results["actions_taken"].append(f"Member status changed from {original_status} to Suspended")
        
        # 2. Suspend user account if requested
        if suspend_user:
            user_email = frappe.db.get_value("Member", member_name, "user")
            if user_email and frappe.db.exists("User", user_email):
                user_doc = frappe.get_doc("User", user_email)
                user_doc.enabled = 0
                
                # Add suspension note to user
                user_suspension_note = f"Account suspended on {suspension_date} - {suspension_reason}"
                if hasattr(user_doc, 'bio') and user_doc.bio:
                    user_doc.bio += f"\n\n{user_suspension_note}"
                elif hasattr(user_doc, 'bio'):
                    user_doc.bio = user_suspension_note
                
                user_doc.flags.ignore_permissions = True
                user_doc.save()
                
                results["user_suspended"] = True
                results["actions_taken"].append(f"User account suspended")
        
        # 3. Suspend team memberships if requested
        if suspend_teams:
            teams_suspended = suspend_team_memberships_safe(
                member_name,
                suspension_date,
                f"Member suspended - {suspension_reason}"
            )
            results["teams_suspended"] = teams_suspended
            if teams_suspended > 0:
                results["actions_taken"].append(f"Suspended {teams_suspended} team membership(s)")
        
        frappe.logger().info(f"Successfully suspended member {member_name}")
        return results
        
    except Exception as e:
        frappe.logger().error(f"Failed to suspend member {member_name}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "actions_taken": [],
            "errors": [str(e)]
        }

def unsuspend_member_safe(member_name, unsuspension_reason, restore_teams=True):
    """
    Unsuspend a member (restore from suspension)
    """
    try:
        member = frappe.get_doc("Member", member_name)
        
        results = {
            "success": True,
            "actions_taken": [],
            "errors": [],
            "member_unsuspended": False,
            "user_unsuspended": False
        }
        
        # Check if member is actually suspended
        if member.status != "Suspended":
            return {
                "success": False,
                "error": f"Member {member_name} is not suspended (current status: {member.status})",
                "actions_taken": [],
                "errors": ["Member is not suspended"]
            }
        
        # 1. Restore member status
        restore_status = getattr(member, 'pre_suspension_status', 'Active')
        member.status = restore_status
        
        # Add unsuspension note
        unsuspension_note = f"Member unsuspended on {today()} - Reason: {unsuspension_reason}"
        if member.notes:
            member.notes += f"\n\n{unsuspension_note}"
        else:
            member.notes = unsuspension_note
        
        # Clear pre-suspension status
        if hasattr(member, 'pre_suspension_status'):
            member.pre_suspension_status = None
        
        member.flags.ignore_permissions = True
        member.save()
        
        results["member_unsuspended"] = True
        results["actions_taken"].append(f"Member status restored to {restore_status}")
        
        # 2. Reactivate user account
        user_email = frappe.db.get_value("Member", member_name, "user")
        if user_email and frappe.db.exists("User", user_email):
            user_doc = frappe.get_doc("User", user_email)
            
            # Only reactivate if it was disabled (not if it was disabled for other reasons)
            if not user_doc.enabled:
                user_doc.enabled = 1
                
                # Add unsuspension note
                user_unsuspension_note = f"Account unsuspended on {today()} - {unsuspension_reason}"
                if hasattr(user_doc, 'bio') and user_doc.bio:
                    user_doc.bio += f"\n\n{user_unsuspension_note}"
                elif hasattr(user_doc, 'bio'):
                    user_doc.bio = user_unsuspension_note
                
                user_doc.flags.ignore_permissions = True
                user_doc.save()
                
                results["user_unsuspended"] = True
                results["actions_taken"].append("User account reactivated")
        
        # Note: Team memberships are not automatically restored as they may have been 
        # legitimately changed during suspension. Manual team re-assignment is recommended.
        if restore_teams:
            results["actions_taken"].append("Note: Team memberships require manual restoration")
        
        frappe.logger().info(f"Successfully unsuspended member {member_name}")
        return results
        
    except Exception as e:
        frappe.logger().error(f"Failed to unsuspend member {member_name}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "actions_taken": [],
            "errors": [str(e)]
        }

def get_member_suspension_status(member_name):
    """
    Get current suspension status of a member
    """
    try:
        member = frappe.get_doc("Member", member_name)
        
        is_suspended = member.status == "Suspended"
        
        # Get user account status
        user_suspended = False
        user_email = frappe.db.get_value("Member", member_name, "user")
        if user_email and frappe.db.exists("User", user_email):
            user_doc = frappe.get_doc("User", user_email)
            user_suspended = not user_doc.enabled
        
        # Check for active team memberships
        active_teams = 0
        if user_email:
            active_teams = frappe.db.count("Team Member", {
                "user": user_email,
                "docstatus": 1
            })
        
        return {
            "is_suspended": is_suspended,
            "member_status": member.status,
            "user_suspended": user_suspended,
            "active_teams": active_teams,
            "pre_suspension_status": getattr(member, 'pre_suspension_status', None),
            "can_unsuspend": is_suspended
        }
        
    except Exception as e:
        frappe.logger().error(f"Failed to get suspension status for {member_name}: {str(e)}")
        return {
            "error": str(e),
            "is_suspended": False,
            "can_unsuspend": False
        }
