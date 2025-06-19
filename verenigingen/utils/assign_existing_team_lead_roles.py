import frappe

@frappe.whitelist()
def assign_roles_to_existing_team_leaders():
    """Assign Team Lead role to all existing team leaders"""
    
    results = {
        "assigned": [],
        "skipped": [],
        "errors": []
    }
    
    # Get all active Team Leaders
    team_leaders = frappe.db.sql("""
        SELECT 
            tm.name,
            tm.parent as team,
            tm.volunteer,
            tm.volunteer_name,
            v.member,
            m.user,
            m.full_name
        FROM `tabTeam Member` tm
        LEFT JOIN `tabVolunteer` v ON tm.volunteer = v.name
        LEFT JOIN `tabMember` m ON v.member = m.name
        WHERE tm.role_type = 'Team Leader'
        AND tm.is_active = 1
        AND (tm.to_date IS NULL OR tm.to_date >= CURDATE())
    """, as_dict=True)
    
    for team_leader in team_leaders:
        try:
            if not team_leader.user:
                results["errors"].append(f"No user account for {team_leader.volunteer_name} (volunteer: {team_leader.volunteer})")
                continue
                
            # Check if user already has the role
            existing_role = frappe.db.exists("Has Role", {
                "parent": team_leader.user,
                "role": "Team Lead"
            })
            
            if existing_role:
                results["skipped"].append(f"{team_leader.full_name} ({team_leader.user}) - already has role")
                continue
                
            # Create the role assignment
            role_doc = frappe.get_doc({
                "doctype": "Has Role",
                "parent": team_leader.user,
                "parenttype": "User",
                "parentfield": "roles", 
                "role": "Team Lead"
            })
            role_doc.insert(ignore_permissions=True)
            
            results["assigned"].append(f"{team_leader.full_name} ({team_leader.user}) - Team: {team_leader.team}")
            
        except Exception as e:
            results["errors"].append(f"Error processing {team_leader.volunteer_name}: {str(e)}")
    
    frappe.db.commit()
    
    # Return summary
    summary = f"""
Team Lead Role Assignment Complete:
- Assigned: {len(results['assigned'])} users
- Skipped: {len(results['skipped'])} users  
- Errors: {len(results['errors'])} users

Details:
ASSIGNED:
{chr(10).join(results['assigned']) if results['assigned'] else 'None'}

SKIPPED:
{chr(10).join(results['skipped']) if results['skipped'] else 'None'}

ERRORS: 
{chr(10).join(results['errors']) if results['errors'] else 'None'}
"""
    
    return summary