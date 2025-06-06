#!/usr/bin/env python3

import os
import sys

# Add the bench directory to Python path
sys.path.insert(0, '/home/frappe/frappe-bench')

# Change to the bench directory
os.chdir('/home/frappe/frappe-bench')

import frappe

def debug_and_fix_member():
    """Debug and fix the member approval issue"""
    print("=" * 60)
    print("DEBUGGING AND FIXING MEMBER APPROVAL ISSUE")
    print("=" * 60)
    
    try:
        # Initialize Frappe
        frappe.init(site='localhost')
        frappe.connect()
        
        # Get the problematic member
        member_name = 'Assoc-Member-2025-06-0109'
        member = frappe.get_doc('Member', member_name)
        
        print(f"✓ Found Member: {member.name}")
        print(f"  Full Name: {member.full_name}")
        print(f"  Application Status: {member.application_status}")
        print(f"  Selected Membership Type: {getattr(member, 'selected_membership_type', 'FIELD_MISSING')}")
        print(f"  Current Membership Type: {getattr(member, 'current_membership_type', 'FIELD_MISSING')}")
        
        # Check if member has any memberships
        memberships = frappe.get_all(
            'Membership', 
            filters={'member': member.name}, 
            fields=['name', 'membership_type', 'status', 'docstatus']
        )
        print(f"\n✓ Existing memberships: {len(memberships)}")
        for membership in memberships:
            print(f"  - {membership.name}: {membership.membership_type} ({membership.status}, docstatus: {membership.docstatus})")
        
        # Check available membership types in the system
        membership_types = frappe.get_all(
            'Membership Type', 
            fields=['name', 'membership_type_name', 'amount']
        )
        print(f"\n✓ Available membership types: {len(membership_types)}")
        for mt in membership_types:
            print(f"  - {mt.name}: {mt.membership_type_name} (€{mt.amount})")
        
        # Determine what needs to be fixed
        print(f"\n📋 DIAGNOSIS:")
        has_selected_type = bool(getattr(member, 'selected_membership_type', None))
        has_current_type = bool(getattr(member, 'current_membership_type', None))
        
        print(f"  - Has selected_membership_type: {has_selected_type}")
        print(f"  - Has current_membership_type: {has_current_type}")
        print(f"  - Available membership types: {len(membership_types) > 0}")
        
        # Apply fix if needed
        if not has_selected_type and not has_current_type and membership_types:
            default_type = membership_types[0].name
            print(f"\n🔧 APPLYING FIX:")
            print(f"  Setting selected_membership_type to: {default_type}")
            
            member.selected_membership_type = default_type
            member.save()
            
            print(f"✅ SUCCESS: Member updated with default membership type")
            print(f"   New selected_membership_type: {member.selected_membership_type}")
            
            return {
                "success": True,
                "action": "set_default_membership_type",
                "membership_type": default_type,
                "member": member.name
            }
            
        elif has_selected_type or has_current_type:
            print(f"\n✅ NO FIX NEEDED: Member already has a membership type")
            return {
                "success": True,
                "action": "no_fix_needed",
                "selected_type": getattr(member, 'selected_membership_type', None),
                "current_type": getattr(member, 'current_membership_type', None),
                "member": member.name
            }
            
        else:
            print(f"\n❌ CANNOT FIX: No membership types available in system")
            return {
                "success": False,
                "error": "No membership types available in system",
                "member": member.name
            }
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    result = debug_and_fix_member()
    print(f"\nFINAL RESULT: {result}")