# ===== File: verenigingen/api/termination_api.py =====
import frappe
from frappe import _

@frappe.whitelist()
def get_termination_preview(member_name):
    """
    Public API to get termination impact preview
    """
    from verenigingen.utils.termination_utils import validate_termination_readiness
    return validate_termination_readiness(member_name)

@frappe.whitelist()
def get_impact_summary(member_name):
    """
    Public API to get termination impact summary
    """
    from verenigingen.utils.termination_utils import get_termination_impact_summary
    return get_termination_impact_summary(member_name)

@frappe.whitelist()
def execute_safe_termination(member_name, termination_type, termination_date=None, request_name=None):
    """
    Execute termination using safe integration methods
    """
    from verenigingen.utils.termination_integration import (
        cancel_membership_safe,
        cancel_sepa_mandate_safe,
        update_customer_safe,
        update_member_status_safe,
        end_board_positions_safe
    )
    
    if not termination_date:
        termination_date = frappe.utils.today()
    
    results = {
        "success": True,
        "actions_taken": [],
        "errors": []
    }
    
    try:
        member = frappe.get_doc("Member", member_name)
        
        # 1. Cancel active memberships
        active_memberships = frappe.get_all(
            "Membership",
            filters={
                "member": member_name,
                "status": ["in", ["Active", "Pending"]],
                "docstatus": 1
            },
            fields=["name"]
        )
        
        for membership in active_memberships:
            if cancel_membership_safe(
                membership.name,
                termination_date,
                f"Member terminated - Request: {request_name or 'Direct'}"
            ):
                results["actions_taken"].append(f"Cancelled membership {membership.name}")
            else:
                results["errors"].append(f"Failed to cancel membership {membership.name}")
        
        # 2. Cancel SEPA mandates
        active_mandates = frappe.get_all(
            "SEPA Mandate",
            filters={
                "member": member_name,
                "status": "Active",
                "is_active": 1
            },
            fields=["name", "mandate_id"]
        )
        
        for mandate in active_mandates:
            if cancel_sepa_mandate_safe(
                mandate.name,
                f"Member terminated - Request: {request_name or 'Direct'}",
                termination_date
            ):
                results["actions_taken"].append(f"Cancelled SEPA mandate {mandate.mandate_id}")
            else:
                results["errors"].append(f"Failed to cancel SEPA mandate {mandate.mandate_id}")
        
        # 3. End board positions
        positions_ended = end_board_positions_safe(
            member_name,
            termination_date,
            f"Member terminated - Request: {request_name or 'Direct'}"
        )
        if positions_ended > 0:
            results["actions_taken"].append(f"Ended {positions_ended} board position(s)")
        
        # 4. Update member status
        if update_member_status_safe(
            member_name,
            termination_type,
            termination_date,
            request_name
        ):
            results["actions_taken"].append(f"Updated member status")
        else:
            results["errors"].append("Failed to update member status")
        
        # 5. Update customer if exists
        if member.customer:
            termination_note = f"Member terminated on {termination_date} - Type: {termination_type}"
            if request_name:
                termination_note += f" - Request: {request_name}"
            
            disciplinary_types = ['Policy Violation', 'Disciplinary Action', 'Expulsion']
            disable_customer = termination_type in disciplinary_types
            
            if update_customer_safe(member.customer, termination_note, disable_customer):
                results["actions_taken"].append("Updated customer record")
            else:
                results["errors"].append("Failed to update customer record")
        
        # Final assessment
        if results["errors"]:
            results["success"] = False
            results["message"] = f"Termination completed with {len(results['errors'])} errors"
        else:
            results["message"] = "Termination completed successfully"
        
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Termination failed with critical error"
        }
