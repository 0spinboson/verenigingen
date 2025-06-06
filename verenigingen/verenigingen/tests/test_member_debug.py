import frappe


def debug_member_approval():
    """Debug the specific member that's failing approval"""
    print("=" * 50)
    print("DEBUGGING MEMBER APPROVAL ISSUE")
    print("=" * 50)
    
    try:
        member = frappe.get_doc('Member', 'Assoc-Member-2025-06-0109')
        print(f"Member: {member.name} ({member.full_name})")
        print(f"Application status: {member.application_status}")
        print(f"Selected membership type: {member.selected_membership_type}")
        print(f"Current membership type: {member.current_membership_type}")
        print(f"Current membership details: {member.current_membership_details}")
        
        # Check if there are any memberships for this member
        memberships = frappe.get_all(
            'Membership', 
            filters={'member': member.name}, 
            fields=['name', 'membership_type', 'status', 'docstatus']
        )
        print(f"\nExisting memberships: {len(memberships)}")
        for membership in memberships:
            print(f"  - {membership.name}: {membership.membership_type} ({membership.status}, docstatus: {membership.docstatus})")
        
        # Check available membership types
        membership_types = frappe.get_all(
            'Membership Type', 
            fields=['name', 'membership_type_name', 'amount']
        )
        print(f"\nAvailable membership types: {len(membership_types)}")
        for mt in membership_types:
            print(f"  - {mt.name}: {mt.membership_type_name} (€{mt.amount})")
        
        # Check if this member should have a default membership type
        print(f"\nDetermining membership type priority:")
        print(f"1. API parameter: (not provided)")
        print(f"2. Selected membership type: {member.selected_membership_type}")
        print(f"3. Current membership type: {member.current_membership_type}")
        
        # Propose solution
        if membership_types:
            default_type = membership_types[0].name
            print(f"\n💡 SOLUTION: Use default membership type: {default_type}")
            
            # Test setting it
            print(f"\n🔧 FIXING: Setting selected_membership_type to {default_type}")
            member.selected_membership_type = default_type
            member.save()
            print(f"✅ Updated member with default membership type")
            
            return {
                "success": True,
                "member": member.name,
                "set_membership_type": default_type
            }
        else:
            print(f"\n❌ No membership types available in system")
            return {"success": False, "error": "No membership types available"}
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    debug_member_approval()