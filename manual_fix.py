#!/usr/bin/env python3
"""
Manual fix for backend members showing as Pending
Run with: bench execute verenigingen.manual_fix.fix_backend_members_now
"""

import frappe

def fix_backend_members_now():
    """Immediately fix backend-created members showing as Pending"""
    
    print("Starting backend member status fix...")
    
    try:
        # Direct SQL update for backend-created members
        result = frappe.db.sql("""
            UPDATE `tabMember` 
            SET application_status = 'Active', status = 'Active'
            WHERE application_status = 'Pending' 
            AND (application_id IS NULL OR application_id = '' OR application_id = 'None')
        """)
        
        # Get count of affected rows
        affected_rows = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        
        # Commit the changes
        frappe.db.commit()
        
        print(f"✅ Successfully updated {affected_rows} backend-created members")
        print("They should now show as 'Active' instead of 'Pending'")
        
        # Also update any members that have empty/null application_id but are still pending
        result2 = frappe.db.sql("""
            UPDATE `tabMember` 
            SET application_status = 'Active'
            WHERE application_status = 'Pending' 
            AND application_id IS NULL
        """)
        
        affected_rows2 = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
        frappe.db.commit()
        
        if affected_rows2 > 0:
            print(f"✅ Additionally fixed {affected_rows2} members with NULL application_id")
        
        return {
            "success": True,
            "fixed_count": affected_rows + affected_rows2,
            "message": f"Fixed {affected_rows + affected_rows2} backend-created members"
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        frappe.db.rollback()
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    fix_backend_members_now()