#!/usr/bin/env python3
"""
Test script to verify the complete membership application submission process
"""

import frappe
from frappe.utils import random_string

def test_application_submission():
    """Test complete application submission"""
    print("🧪 Testing complete application submission process...")
    
    # Set user context
    frappe.set_user("Administrator")
    
    # Create test data that mimics form submission
    form_data = {
        "first_name": "TestApp",
        "last_name": "User" + random_string(4),
        "email": f"testapp.user.{random_string(6)}@example.com",
        "contact_number": "+31612345678",
        "birth_date": "1990-05-15",
        "address_line1": "Test Application Street 123",
        "city": "Amsterdam",
        "postal_code": "1012AB",
        "country": "Netherlands",
        "selected_membership_type": "Standard",
        "membership_amount": 65.0,  # Custom amount
        "uses_custom_amount": True,
        "custom_amount_reason": "Supporter contribution",
        "payment_method": "SEPA Direct Debit",
        "iban": "NL91ABNA0417164300",
        "bic": "ABNANL2A", 
        "bank_account_name": "Test Application User",
        "terms": True,
        "newsletter": True
    }
    
    print(f"📝 Submitting application for: {form_data['first_name']} {form_data['last_name']}")
    print(f"   Email: {form_data['email']}")
    print(f"   Custom amount: €{form_data['membership_amount']}")
    
    try:
        # Call the API method that handles form submissions
        result = frappe.call(
            "verenigingen.api.membership_application.submit_membership_application",
            data=form_data
        )
        
        if result and result.get("success"):
            print("✅ Application submission successful!")
            print(f"   Application ID: {result.get('application_id')}")
            print(f"   Member ID: {result.get('member_id')}")
            print(f"   Message: {result.get('message', 'No message')}")
            
            # Verify the created member
            member_id = result.get('member_id')
            if member_id:
                member = frappe.get_doc("Member", member_id)
                print(f"✅ Member created successfully:")
                print(f"   Name: {member.full_name}")
                print(f"   Email: {member.email}")
                print(f"   Fee override: €{member.membership_fee_override}")
                print(f"   Fee reason: {member.fee_override_reason}")
                print(f"   Status: {member.application_status}")
                
                # Most importantly - check that NO _pending_fee_change was created
                if hasattr(member, '_pending_fee_change'):
                    print("❌ ERROR: New application should not create _pending_fee_change!")
                    return False
                else:
                    print("✅ Correctly skipped fee change tracking for new application")
                
                # Verify all fields are set correctly
                assert member.membership_fee_override == 65.0, f"Fee override wrong: {member.membership_fee_override}"
                assert member.fee_override_reason, f"Fee reason missing: {member.fee_override_reason}"
                assert member.application_status == "Pending", f"Status wrong: {member.application_status}"
                
                print("✅ All member fields verified correctly")
                return True
            else:
                print("❌ No member ID returned")
                return False
        else:
            print(f"❌ Application submission failed: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Application submission error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_backend_fee_adjustment():
    """Test backend fee adjustment for existing member"""
    print("\n🧪 Testing backend fee adjustment for existing member...")
    
    # Create an existing member first
    existing_member = frappe.get_doc({
        "doctype": "Member",
        "first_name": "Backend",
        "last_name": "TestMember" + random_string(4),
        "email": f"backend.test.{random_string(6)}@example.com",
        "birth_date": "1985-03-10",
        "status": "Active",
        "application_status": "Active"
    })
    existing_member.insert(ignore_permissions=True)
    
    print(f"✅ Created existing member: {existing_member.name} ({existing_member.full_name})")
    print(f"   Initial fee override: {existing_member.membership_fee_override}")
    
    # Now adjust their fee (this should trigger change tracking)
    print("📝 Adjusting fee from None to €150.0...")
    existing_member.membership_fee_override = 150.0
    existing_member.fee_override_reason = "Backend adjustment - Premium supporter"
    existing_member.save(ignore_permissions=True)
    
    # Check if change tracking was triggered
    if hasattr(existing_member, '_pending_fee_change'):
        print("✅ Backend fee adjustment correctly triggered change tracking")
        pending = existing_member._pending_fee_change
        print(f"   Old amount: {pending.get('old_amount')}")
        print(f"   New amount: {pending.get('new_amount')}")
        print(f"   Reason: {pending.get('reason')}")
        
        # Verify the change data
        assert pending.get('new_amount') == 150.0, f"New amount wrong: {pending.get('new_amount')}"
        assert pending.get('old_amount') is None, f"Old amount should be None: {pending.get('old_amount')}"
        
        print("✅ Backend fee adjustment working correctly")
        return True
    else:
        print("❌ ERROR: Backend fee adjustment should trigger change tracking!")
        return False

def run_comprehensive_tests():
    """Run comprehensive tests for both scenarios"""
    print("🚀 STARTING COMPREHENSIVE FEE LOGIC TESTS")
    print("="*60)
    
    results = []
    
    # Test 1: Application submission (should NOT trigger change tracking)
    print("\n" + "="*60)
    print("TEST 1: MEMBERSHIP APPLICATION SUBMISSION")
    print("="*60)
    result1 = test_application_submission()
    results.append(("Application Submission", result1))
    
    # Test 2: Backend fee adjustment (should trigger change tracking)
    print("\n" + "="*60)
    print("TEST 2: BACKEND FEE ADJUSTMENT")
    print("="*60)
    result2 = test_backend_fee_adjustment()
    results.append(("Backend Fee Adjustment", result2))
    
    # Report results
    print("\n" + "="*60)
    print("📊 COMPREHENSIVE TEST RESULTS")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 FINAL RESULT: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Both application and backend fee logic working correctly!")
        return True
    else:
        print("⚠️  SOME TESTS FAILED! Check the output above for details.")
        return False

if __name__ == "__main__":
    run_comprehensive_tests()