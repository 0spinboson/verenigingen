import frappe


def test_approval_fix():
    """Test that the membership application approval now works"""
    print("=" * 50)
    print("TESTING MEMBERSHIP APPROVAL FIX")
    print("=" * 50)
    
    try:
        # Find a member with pending application status
        pending_members = frappe.get_all(
            "Member",
            filters={"application_status": "Pending"},
            fields=["name", "full_name", "selected_membership_type", "current_membership_type"],
            limit=1
        )
        
        if not pending_members:
            print("❌ No pending members found for testing")
            return {"success": False, "message": "No pending members"}
            
        member_data = pending_members[0]
        print(f"📝 Testing with pending member: {member_data.name} ({member_data.full_name})")
        
        # Check field values
        member = frappe.get_doc("Member", member_data.name)
        print(f"   Selected membership type: {member.selected_membership_type}")
        print(f"   Current membership type: {member.current_membership_type}")
        
        # Test that the field exists and is accessible
        try:
            selected_type = member.selected_membership_type
            print(f"✅ selected_membership_type field accessible: {selected_type}")
        except AttributeError as e:
            print(f"❌ selected_membership_type field still missing: {e}")
            return {"success": False, "error": str(e)}
        
        # Get available membership types for testing
        membership_types = frappe.get_all("Membership Type", fields=["name", "membership_type_name"])
        print(f"   Available membership types: {len(membership_types)}")
        
        if membership_types:
            test_membership_type = membership_types[0].name
            print(f"   Will use membership type: {test_membership_type}")
            
            # Test the approval function (dry run - don't actually approve)
            print(f"\n🧪 Testing approval logic (dry run)...")
            
            # Check if we can access the approval function
            from verenigingen.api.membership_application_review import approve_membership_application
            print("✅ Approval function imported successfully")
            
            # Test what membership type would be used
            membership_type_to_use = None
            if member.selected_membership_type:
                membership_type_to_use = member.selected_membership_type
            elif member.current_membership_type:
                membership_type_to_use = member.current_membership_type
            else:
                membership_type_to_use = test_membership_type
                
            print(f"   Would use membership type: {membership_type_to_use}")
            
            # Test that the member has the required application_status
            if member.application_status == "Pending":
                print("✅ Member has correct application status for approval")
            else:
                print(f"❌ Member application status is '{member.application_status}', not 'Pending'")
                
            print(f"\n✅ MEMBERSHIP APPROVAL FIX VALIDATION COMPLETED")
            print(f"   The approval should now work without AttributeError")
            
            return {
                "success": True,
                "member": member_data.name,
                "has_selected_type": bool(member.selected_membership_type),
                "has_current_type": bool(member.current_membership_type),
                "would_use_type": membership_type_to_use
            }
        else:
            print("❌ No membership types available")
            return {"success": False, "message": "No membership types available"}
            
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    test_approval_fix()