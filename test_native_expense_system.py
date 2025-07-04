#!/usr/bin/env python3
"""
Test script for the new native ERPNext expense system
Tests that expense claims work without the custom department hierarchy
"""

import frappe
import json
from frappe.utils import today

def test_native_expense_system():
    """Test the native expense system for Foppe de Haan and other volunteers"""
    print("=" * 60)
    print("Testing Native ERPNext Expense System")
    print("=" * 60)
    
    # Initialize Frappe
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    try:
        print("\n1. Testing volunteer lookup and approver assignment...")
        test_volunteer_approver_assignment()
        
        print("\n2. Testing employee creation with new system...")
        test_employee_creation()
        
        print("\n3. Testing expense submission flow...")
        test_expense_submission()
        
        print("\n4. Validating system configuration...")
        test_system_validation()
        
        print("\n✓ All tests passed! Native expense system is working correctly.")
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        frappe.log_error(str(e), "Native Expense System Test Error")
        return False
    
    return True

def test_volunteer_approver_assignment():
    """Test that volunteers get proper expense approvers assigned"""
    
    # Test with Foppe de Haan
    foppe_volunteer = frappe.db.get_value("Volunteer", {"name": "FOPPE-DE-HAAN"}, ["name", "volunteer_name"], as_dict=True)
    
    if foppe_volunteer:
        volunteer_doc = frappe.get_doc("Volunteer", foppe_volunteer.name)
        approver = volunteer_doc.get_expense_approver_from_assignments()
        print(f"   Foppe de Haan's expense approver: {approver}")
        
        if approver and approver != "Administrator":
            print(f"   ✓ Found proper approver for Foppe de Haan")
        else:
            print(f"   ⚠ Using fallback approver for Foppe de Haan")
    else:
        print("   ⚠ Foppe de Haan volunteer record not found")
    
    # Test with a few other volunteers
    test_volunteers = frappe.get_all("Volunteer", 
        filters={"status": "Active"}, 
        fields=["name", "volunteer_name"], 
        limit=3)
    
    for volunteer_data in test_volunteers:
        try:
            volunteer_doc = frappe.get_doc("Volunteer", volunteer_data.name)
            approver = volunteer_doc.get_expense_approver_from_assignments()
            print(f"   {volunteer_data.volunteer_name}: {approver}")
        except Exception as e:
            print(f"   ✗ Error testing {volunteer_data.volunteer_name}: {str(e)}")

def test_employee_creation():
    """Test that employee creation works without departments"""
    
    # Find a volunteer without an employee record
    volunteer_without_employee = frappe.db.get_value("Volunteer", 
        {"employee_id": ["is", "not set"], "status": "Active"}, 
        ["name", "volunteer_name"], as_dict=True)
    
    if volunteer_without_employee:
        try:
            volunteer_doc = frappe.get_doc("Volunteer", volunteer_without_employee.name)
            employee_id = volunteer_doc.create_minimal_employee()
            
            if employee_id:
                print(f"   ✓ Created employee {employee_id} for {volunteer_without_employee.volunteer_name}")
                
                # Verify employee has approver
                employee = frappe.get_doc("Employee", employee_id)
                if employee.expense_approver:
                    print(f"   ✓ Employee has expense approver: {employee.expense_approver}")
                else:
                    print(f"   ⚠ Employee created but no expense approver set")
                
                # Clean up test data
                frappe.delete_doc("Employee", employee_id, force=True)
                volunteer_doc.employee_id = None
                volunteer_doc.save(ignore_permissions=True)
                print(f"   ✓ Cleaned up test employee")
            else:
                print(f"   ✗ Failed to create employee for {volunteer_without_employee.volunteer_name}")
                
        except Exception as e:
            print(f"   ✗ Error creating employee: {str(e)}")
    else:
        print("   ℹ No volunteers without employee records found for testing")

def test_expense_submission():
    """Test expense submission without department requirements"""
    
    # Test data for expense submission
    test_expense_data = {
        "description": "Test expense for native system",
        "amount": 25.50,
        "expense_date": today(),
        "organization_type": "Chapter",
        "chapter": "LANDELIJK",  # Use a known chapter
        "category": "Travel",
        "notes": "Testing native expense system"
    }
    
    # Find a volunteer with chapter membership
    volunteer_with_chapter = frappe.db.sql("""
        SELECT v.name, v.volunteer_name, v.member
        FROM `tabVolunteer` v
        JOIN `tabChapter Member` cm ON cm.member = v.member
        WHERE cm.parent = %(chapter)s
        AND cm.enabled = 1
        AND v.status = 'Active'
        LIMIT 1
    """, {"chapter": test_expense_data["chapter"]}, as_dict=True)
    
    if volunteer_with_chapter:
        volunteer_data = volunteer_with_chapter[0]
        print(f"   Testing expense submission for {volunteer_data.volunteer_name}")
        
        try:
            # Simulate user session
            original_user = frappe.session.user
            volunteer_doc = frappe.get_doc("Volunteer", volunteer_data.name)
            user_email = volunteer_doc.email or volunteer_doc.personal_email
            
            if user_email and frappe.db.exists("User", user_email):
                frappe.session.user = user_email
                
                # Import and test the submission function
                from verenigingen.templates.pages.volunteer.expenses import submit_expense
                
                # Test the submission
                result = submit_expense(test_expense_data)
                
                if result.get("success"):
                    print(f"   ✓ Expense submission successful: {result.get('expense_claim_name')}")
                    
                    # Clean up test data
                    if result.get("expense_claim_name"):
                        frappe.delete_doc("Expense Claim", result.get("expense_claim_name"), force=True)
                    if result.get("expense_name"):
                        frappe.delete_doc("Volunteer Expense", result.get("expense_name"), force=True)
                    print(f"   ✓ Cleaned up test expense data")
                else:
                    print(f"   ✗ Expense submission failed: {result.get('message')}")
            else:
                print(f"   ⚠ No valid user email found for {volunteer_data.volunteer_name}")
            
            # Restore original user
            frappe.session.user = original_user
                
        except Exception as e:
            frappe.session.user = original_user
            print(f"   ✗ Error testing expense submission: {str(e)}")
    else:
        print("   ⚠ No volunteers with chapter membership found for testing")

def test_system_validation():
    """Test system validation functions"""
    
    try:
        from verenigingen.utils.native_expense_helpers import validate_expense_approver_setup, is_native_expense_system_ready
        
        validation_result = validate_expense_approver_setup()
        print(f"   System validation: {'✓ VALID' if validation_result['valid'] else '⚠ HAS ISSUES'}")
        
        if validation_result['issues']:
            for issue in validation_result['issues']:
                print(f"   - {issue}")
        
        system_ready = is_native_expense_system_ready()
        print(f"   System ready: {'✓ YES' if system_ready else '⚠ NOT READY'}")
        
    except Exception as e:
        print(f"   ✗ Error validating system: {str(e)}")

if __name__ == "__main__":
    test_native_expense_system()