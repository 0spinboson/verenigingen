import frappe

@frappe.whitelist()
def assign_roles_to_existing_board_members():
    """Assign Chapter Board Member role to all existing board members"""
    
    results = {
        "assigned": [],
        "skipped": [],
        "errors": []
    }
    
    # Get all active Chapter Board Members
    board_members = frappe.db.sql("""
        SELECT 
            cbm.name,
            cbm.parent as chapter,
            cbm.volunteer,
            cbm.volunteer_name,
            v.member,
            m.user,
            m.full_name
        FROM `tabChapter Board Member` cbm
        LEFT JOIN `tabVolunteer` v ON cbm.volunteer = v.name
        LEFT JOIN `tabMember` m ON v.member = m.name
        WHERE cbm.is_active = 1
        AND cbm.to_date IS NULL OR cbm.to_date >= CURDATE()
    """, as_dict=True)
    
    for board_member in board_members:
        try:
            if not board_member.user:
                results["errors"].append(f"No user account for {board_member.volunteer_name} (volunteer: {board_member.volunteer})")
                continue
                
            # Check if user already has the role
            existing_role = frappe.db.exists("Has Role", {
                "parent": board_member.user,
                "role": "Chapter Board Member"
            })
            
            if existing_role:
                results["skipped"].append(f"{board_member.full_name} ({board_member.user}) - already has role")
                continue
                
            # Create the role assignment
            role_doc = frappe.get_doc({
                "doctype": "Has Role",
                "parent": board_member.user,
                "parenttype": "User",
                "parentfield": "roles", 
                "role": "Chapter Board Member"
            })
            role_doc.insert(ignore_permissions=True)
            
            results["assigned"].append(f"{board_member.full_name} ({board_member.user}) - Chapter: {board_member.chapter}")
            
        except Exception as e:
            results["errors"].append(f"Error processing {board_member.volunteer_name}: {str(e)}")
    
    frappe.db.commit()
    
    # Return summary
    summary = f"""
Role Assignment Complete:
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