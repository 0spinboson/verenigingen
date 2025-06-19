import frappe
import frappe.utils

@frappe.whitelist()
def cleanup_expired_board_member_roles():
    """Daily cleanup job to remove roles from expired board members"""
    board_results = cleanup_expired_board_roles()
    team_results = cleanup_expired_team_lead_roles()
    
    # Combine results
    combined_results = {
        "board_member_processed": board_results.get("processed", []),
        "board_member_errors": board_results.get("errors", []),
        "team_lead_processed": team_results.get("processed", []),
        "team_lead_errors": team_results.get("errors", [])
    }
    
    return combined_results

@frappe.whitelist()
def cleanup_expired_board_roles():
    """Daily cleanup job to remove roles from expired board members"""
    
    results = {
        "processed": [],
        "errors": []
    }
    
    try:
        # Find all users with Chapter Board Member role
        users_with_role = frappe.db.get_all("Has Role", 
            filters={"role": "Chapter Board Member"}, 
            fields=["parent"]
        )
        
        for user_role in users_with_role:
            user = user_role["parent"]
            
            try:
                # Find the member associated with this user
                member = frappe.db.get_value("Member", {"user": user}, "name")
                if not member:
                    continue
                    
                # Find the volunteer associated with this member
                volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
                if not volunteer:
                    continue
                
                # Check if this volunteer has any active board positions
                active_positions = frappe.db.count("Chapter Board Member", {
                    "volunteer": volunteer,
                    "is_active": 1,
                    "to_date": ["is", "null"]
                })
                
                # Also check for positions with future end dates
                future_positions = frappe.db.count("Chapter Board Member", {
                    "volunteer": volunteer,
                    "is_active": 1, 
                    "to_date": [">=", frappe.utils.today()]
                })
                
                total_active = active_positions + future_positions
                
                # If no active positions, remove the role
                if total_active == 0:
                    role_doc = frappe.db.get_value("Has Role", {
                        "parent": user,
                        "role": "Chapter Board Member"
                    }, "name")
                    
                    if role_doc:
                        frappe.delete_doc("Has Role", role_doc, ignore_permissions=True)
                        results["processed"].append(f"Removed role from {user} (no active board positions)")
                        
            except Exception as e:
                results["errors"].append(f"Error processing user {user}: {str(e)}")
                
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(f"General error: {str(e)}")
    
    # Log results
    if results["processed"] or results["errors"]:
        frappe.log_error(
            message=f"Board Role Cleanup Results:\nProcessed: {results['processed']}\nErrors: {results['errors']}",
            title="Board Member Role Cleanup"
        )
    
    return results

@frappe.whitelist()
def cleanup_expired_team_lead_roles():
    """Daily cleanup job to remove Team Lead roles from expired team leaders"""
    
    results = {
        "processed": [],
        "errors": []
    }
    
    try:
        # Find all users with Team Lead role
        users_with_role = frappe.db.get_all("Has Role", 
            filters={"role": "Team Lead"}, 
            fields=["parent"]
        )
        
        for user_role in users_with_role:
            user = user_role["parent"]
            
            try:
                # Find the member associated with this user
                member = frappe.db.get_value("Member", {"user": user}, "name")
                if not member:
                    continue
                    
                # Find the volunteer associated with this member
                volunteer = frappe.db.get_value("Volunteer", {"member": member}, "name")
                if not volunteer:
                    continue
                
                # Check if this volunteer has any active team leader positions
                active_leader_positions = frappe.db.count("Team Member", {
                    "volunteer": volunteer,
                    "role_type": "Team Leader",
                    "is_active": 1,
                    "to_date": ["is", "null"]
                })
                
                # Also check for positions with future end dates
                future_leader_positions = frappe.db.count("Team Member", {
                    "volunteer": volunteer,
                    "role_type": "Team Leader",
                    "is_active": 1, 
                    "to_date": [">=", frappe.utils.today()]
                })
                
                total_active = active_leader_positions + future_leader_positions
                
                # If no active team leader positions, remove the role
                if total_active == 0:
                    role_doc = frappe.db.get_value("Has Role", {
                        "parent": user,
                        "role": "Team Lead"
                    }, "name")
                    
                    if role_doc:
                        frappe.delete_doc("Has Role", role_doc, ignore_permissions=True)
                        results["processed"].append(f"Removed Team Lead role from {user} (no active team leader positions)")
                        
            except Exception as e:
                results["errors"].append(f"Error processing user {user}: {str(e)}")
                
        frappe.db.commit()
        
    except Exception as e:
        results["errors"].append(f"General error: {str(e)}")
    
    # Log results
    if results["processed"] or results["errors"]:
        frappe.log_error(
            message=f"Team Lead Role Cleanup Results:\nProcessed: {results['processed']}\nErrors: {results['errors']}",
            title="Team Lead Role Cleanup"
        )
    
    return results