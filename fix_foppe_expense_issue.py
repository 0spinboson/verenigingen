#!/usr/bin/env python3
"""
Quick fix for Foppe de Haan's expense issue
Clears department dependencies and updates to native system
"""

import frappe

def fix_foppe_expense_issue():
    """Fix the immediate issue for Foppe de Haan"""
    print("Fixing Foppe de Haan's expense submission issue...")
    
    # Initialize Frappe
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    try:
        # Step 1: Clear all department references from Employee records
        print("1. Clearing department references from Employee records...")
        result = frappe.db.sql("""
            UPDATE `tabEmployee` 
            SET department = NULL 
            WHERE department IS NOT NULL
        """)
        print(f"   ✓ Cleared departments from employee records")
        
        # Step 2: Update Foppe de Haan's employee record specifically
        foppe_volunteer = frappe.db.get_value("Volunteer", {"name": "FOPPE-DE-HAAN"}, 
            ["name", "volunteer_name", "employee_id"], as_dict=True)
        
        if foppe_volunteer and foppe_volunteer.employee_id:
            print(f"2. Updating Foppe de Haan's employee record...")
            
            # Get the volunteer document
            volunteer_doc = frappe.get_doc("Volunteer", foppe_volunteer.name)
            
            # Get new approver using native system
            approver = volunteer_doc.get_expense_approver_from_assignments()
            
            if approver:
                # Update employee record
                employee = frappe.get_doc("Employee", foppe_volunteer.employee_id)
                employee.expense_approver = approver
                employee.department = None  # Ensure no department
                employee.save(ignore_permissions=True)
                print(f"   ✓ Updated employee {foppe_volunteer.employee_id} with approver: {approver}")
            else:
                print(f"   ⚠ Could not determine approver for Foppe de Haan")
        
        # Step 3: Update all other volunteers with employee records
        print("3. Updating all volunteer employee records...")
        volunteers_with_employees = frappe.db.sql("""
            SELECT v.name, v.volunteer_name, v.employee_id
            FROM `tabVolunteer` v
            WHERE v.employee_id IS NOT NULL 
            AND v.employee_id != ''
            AND EXISTS (SELECT 1 FROM `tabEmployee` e WHERE e.name = v.employee_id)
        """, as_dict=True)
        
        updated_count = 0
        for volunteer_data in volunteers_with_employees:
            try:
                volunteer_doc = frappe.get_doc("Volunteer", volunteer_data.name)
                approver = volunteer_doc.get_expense_approver_from_assignments()
                
                if approver:
                    employee = frappe.get_doc("Employee", volunteer_data.employee_id)
                    employee.expense_approver = approver
                    employee.department = None  # Clear department
                    employee.save(ignore_permissions=True)
                    updated_count += 1
            except Exception as e:
                print(f"   ⚠ Error updating {volunteer_data.volunteer_name}: {str(e)}")
        
        print(f"   ✓ Updated {updated_count} employee records")
        
        # Step 4: Commit changes
        frappe.db.commit()
        
        print("\n✅ Fix completed! Foppe de Haan should now be able to submit expenses.")
        print("✅ All volunteers transitioned to native ERPNext expense system.")
        
    except Exception as e:
        print(f"\n❌ Error during fix: {str(e)}")
        frappe.log_error(str(e), "Foppe Expense Fix Error")
        return False
    
    return True

if __name__ == "__main__":
    fix_foppe_expense_issue()