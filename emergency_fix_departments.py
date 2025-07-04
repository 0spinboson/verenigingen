#!/usr/bin/env python3
"""
Emergency fix to remove all department references from Employee records
This will stop ERPNext from trying to validate non-existent departments
"""

import sys
import os
sys.path.insert(0, '/home/frappe/frappe-bench')
sys.path.insert(0, '/home/frappe/frappe-bench/apps/frappe')
sys.path.insert(0, '/home/frappe/frappe-bench/sites')

import frappe

def emergency_fix():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("Emergency fix: Clearing all department references...")
    
    # Clear all department references from Employee records
    frappe.db.sql("UPDATE `tabEmployee` SET department = NULL WHERE department IS NOT NULL")
    
    # Also clear any department references from Volunteer records
    frappe.db.sql("UPDATE `tabVolunteer` SET department = NULL WHERE department IS NOT NULL")
    
    # Check Foppe specifically
    foppe_employee = frappe.db.sql("""
        SELECT e.name, e.employee_name, e.department, e.expense_approver
        FROM `tabEmployee` e
        JOIN `tabVolunteer` v ON v.employee_id = e.name
        WHERE v.name = 'FOPPE-DE-HAAN'
    """, as_dict=True)
    
    if foppe_employee:
        emp = foppe_employee[0]
        print(f"Foppe's employee record: {emp.name}")
        print(f"  Department: {emp.department}")
        print(f"  Expense approver: {emp.expense_approver}")
        
        # Ensure no department and set a valid approver
        frappe.db.sql("UPDATE `tabEmployee` SET department = NULL, expense_approver = 'Administrator' WHERE name = %s", emp.name)
        print("  ✓ Cleared department and set Administrator as approver")
    
    frappe.db.commit()
    print("✓ Emergency fix completed")

if __name__ == "__main__":
    emergency_fix()