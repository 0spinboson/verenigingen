#!/usr/bin/env python3
"""
Simple test to verify the chapter membership fix is working
"""

import frappe

def test_chapter_membership_fix():
    """Simple test to verify the fix works"""
    
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("🧪 Simple Chapter Membership Fix Test")
    print("=" * 50)
    
    try:
        # Test 1: Check if get_user_volunteer_record includes member field
        print("\n1. Testing get_user_volunteer_record function...")
        
        from verenigingen.templates.pages.volunteer.expenses import get_user_volunteer_record
        import inspect
        
        # Get the source code to verify member field is included
        source = inspect.getsource(get_user_volunteer_record)
        
        if '"member"' in source or "'member'" in source:
            print("   ✅ Function source includes 'member' field in queries")
        else:
            print("   ❌ Function source missing 'member' field")
            return False
        
        # Test 2: Check if Foppe can submit expenses
        print("\n2. Testing Foppe's expense submission...")
        
        # Set session user to Foppe
        original_user = frappe.session.user
        frappe.session.user = "test@example.com"
        
        try:
            # Test volunteer lookup
            volunteer_record = get_user_volunteer_record()
            
            if volunteer_record and volunteer_record.member:
                print(f"   ✅ Volunteer lookup successful: {volunteer_record.name}")
                print(f"   ✅ Member field present: {volunteer_record.member}")
            else:
                print("   ❌ Volunteer lookup failed or missing member field")
                return False
            
            # Test expense submission
            from verenigingen.templates.pages.volunteer.expenses import submit_expense
            
            expense_data = {
                "description": "Simple test expense for chapter membership fix",
                "amount": 5.00,
                "expense_date": "2024-12-14",
                "organization_type": "Chapter",
                "chapter": "Zeist",
                "category": "Travel",
                "notes": "Testing the chapter membership fix"
            }
            
            result = submit_expense(expense_data)
            
            if result.get("success"):
                print(f"   ✅ Expense submission successful!")
                print(f"   Message: {result.get('message')}")
            else:
                print(f"   ❌ Expense submission failed: {result.get('message')}")
                return False
            
        finally:
            frappe.session.user = original_user
        
        print(f"\n🎉 Chapter membership fix VERIFIED WORKING!")
        print(f"✅ All tests passed")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        frappe.destroy()

if __name__ == "__main__":
    success = test_chapter_membership_fix()
    if success:
        print("\n✅ SIMPLE TEST PASSED - Chapter membership validation fix is working!")
    else:
        print("\n❌ SIMPLE TEST FAILED - Chapter membership validation needs attention")
    
    exit(0 if success else 1)