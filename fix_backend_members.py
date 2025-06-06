#!/usr/bin/env python3
"""
One-time script to fix backend-created members showing as Pending
Run this with: bench execute verenigingen.fix_backend_members.fix_all_backend_members
"""

import frappe

def fix_all_backend_members():
    """Fix all backend-created members that are showing as Pending"""
    
    print("=== FIXING BACKEND MEMBER STATUSES ===")
    
    # Get all members with Pending application_status
    members = frappe.get_all(
        "Member",
        fields=["name", "application_status", "application_id", "status", "full_name"],
        filters={
            "application_status": "Pending"
        }
    )
    
    print(f"Found {len(members)} members with Pending application status")
    
    fixed_count = 0
    
    for member_data in members:
        # Check if this is a backend-created member (no application_id)
        if not member_data.application_id:
            print(f"Fixing backend member: {member_data.full_name} ({member_data.name})")
            
            try:
                member = frappe.get_doc("Member", member_data.name)
                
                # Update statuses
                member.application_status = "Active"
                member.status = "Active"
                
                # Save the member
                member.save()
                
                fixed_count += 1
                print(f"  ✅ Fixed: {member.full_name}")
                
            except Exception as e:
                print(f"  ❌ Error fixing {member_data.name}: {str(e)}")
        else:
            print(f"Skipping application member: {member_data.full_name} ({member_data.name})")
    
    frappe.db.commit()
    
    print(f"\n=== COMPLETED ===")
    print(f"Fixed {fixed_count} backend-created members")
    print(f"They should now show as 'Active' instead of 'Pending'")
    
    return {
        "success": True,
        "fixed_count": fixed_count,
        "message": f"Fixed {fixed_count} backend-created members"
    }

if __name__ == "__main__":
    fix_all_backend_members()