#!/usr/bin/env python3

def test_fee_logic():
    """Simple test for fee logic"""
    import frappe
    from frappe.utils import random_string
    
    print("🧪 Testing fee override logic...")
    
    # Test 1: Create a new member with custom fee (should NOT trigger change tracking)
    print("\n1. Testing new member with custom fee...")
    try:
        member = frappe.get_doc({
            "doctype": "Member",
            "first_name": "Test",
            "last_name": "NewMember" + random_string(4),
            "email": f"test.new.{random_string(6)}@example.com",
            "birth_date": "1990-01-01",
            "membership_fee_override": 75.0,
            "fee_override_reason": "Custom contribution during application",
            "status": "Pending",
            "application_status": "Pending"
        })
        
        # Insert (this will trigger validation including handle_fee_override_changes)
        member.insert(ignore_permissions=True)
        
        # Check if _pending_fee_change was set (it shouldn't be for new members)
        if hasattr(member, '_pending_fee_change'):
            print("❌ ERROR: New member should not have _pending_fee_change!")
            return False
        else:
            print("✅ New member correctly skips fee change tracking")
            
        print(f"✅ New member created: {member.name}")
        print(f"   Fee override: €{member.membership_fee_override}")
        
    except Exception as e:
        print(f"❌ New member test failed: {str(e)}")
        return False
    
    # Test 2: Update existing member fee (should trigger change tracking)
    print("\n2. Testing existing member fee update...")
    try:
        # Get the member we just created and update their fee
        member.reload()
        
        # Modify the fee (this should trigger change tracking since member exists)
        member.membership_fee_override = 100.0
        member.fee_override_reason = "Upgraded to supporter level"
        
        # Save the changes
        member.save(ignore_permissions=True)
        
        # Check if _pending_fee_change was set (it should be for existing members)
        if hasattr(member, '_pending_fee_change'):
            print("✅ Existing member correctly triggers fee change tracking")
            pending = member._pending_fee_change
            print(f"   Old amount: {pending.get('old_amount')}")
            print(f"   New amount: {pending.get('new_amount')}")
        else:
            print("❌ ERROR: Existing member should have _pending_fee_change!")
            return False
            
    except Exception as e:
        print(f"❌ Existing member test failed: {str(e)}")
        return False
    
    print("\n✅ ALL TESTS PASSED: Fee logic working correctly!")
    return True

def run_test():
    return test_fee_logic()