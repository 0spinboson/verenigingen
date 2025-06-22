#!/usr/bin/env python3
"""
Test script to check if the other_members_at_address field gets populated
"""
import frappe

@frappe.whitelist()
def test_field_population(member_id="Assoc-Member-2025-06-0086"):
    """Test if the field gets populated when we load the member"""
    
    # Get the member document (this should trigger on_load)
    member = frappe.get_doc("Member", member_id)
    
    return {
        "member_id": member_id,
        "member_name": f"{member.first_name} {member.last_name}",
        "primary_address": member.primary_address,
        "field_value": member.other_members_at_address,
        "field_length": len(member.other_members_at_address or ""),
        "has_content": bool(member.other_members_at_address and len(member.other_members_at_address) > 50)
    }

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    result = test_field_population()
    print(result)