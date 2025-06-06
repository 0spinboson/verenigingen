import frappe

def debug_member():
    """Simple debug function for member approval"""
    try:
        # Get the member
        member = frappe.get_doc('Member', 'Assoc-Member-2025-06-0109')
        print(f"Member: {member.name} ({member.full_name})")
        print(f"Application status: {member.application_status}")
        print(f"Selected membership type: {getattr(member, 'selected_membership_type', 'FIELD_MISSING')}")
        print(f"Current membership type: {getattr(member, 'current_membership_type', 'FIELD_MISSING')}")
        
        # Get available membership types
        membership_types = frappe.get_all('Membership Type', fields=['name', 'membership_type_name'])
        print(f"Available membership types: {len(membership_types)}")
        
        # Fix if needed
        if membership_types and not getattr(member, 'selected_membership_type', None):
            default_type = membership_types[0].name
            print(f"Setting selected_membership_type to: {default_type}")
            member.selected_membership_type = default_type
            member.save()
            print("✅ Updated member with default membership type")
        
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Execute the function
debug_member()