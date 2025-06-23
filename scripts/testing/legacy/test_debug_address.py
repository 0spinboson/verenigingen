#!/usr/bin/env python3
"""
Test script to call the debug_address_members method
"""
import frappe
import json

@frappe.whitelist()
def test_debug_method():
    """Test the debug_address_members method"""
    
    member = frappe.get_doc("Member", "Assoc-Member-2025-06-0086")
    result = member.debug_address_members()
    
    print("=== DEBUG ADDRESS MEMBERS RESULT ===")
    print(json.dumps(result, indent=2, default=str))
    
    return result

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    result = test_debug_method()