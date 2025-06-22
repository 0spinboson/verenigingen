#!/usr/bin/env python3
"""
Quick test to verify address members UI functionality is working
"""
import frappe

@frappe.whitelist()
def test_address_members_ui_quick():
    """Test the get_address_members_html method directly"""
    
    try:
        # Get the specific member
        member = frappe.get_doc("Member", "Assoc-Member-2025-06-0086")
        
        # Test the get_address_members_html method
        html_result = member.get_address_members_html()
        
        print("=== ADDRESS MEMBERS HTML RESULT ===")
        print(f"Type: {type(html_result)}")
        print(f"Length: {len(html_result) if html_result else 'None'}")
        print("Content preview (first 500 chars):")
        print(html_result[:500] if html_result else "No content")
        print("\n=== FULL HTML CONTENT ===")
        print(html_result)
        
        return {
            "success": True,
            "member_id": member.name,
            "member_name": f"{member.first_name} {member.last_name}",
            "primary_address": member.primary_address,
            "html_length": len(html_result) if html_result else 0,
            "html_preview": html_result[:200] if html_result else "No content",
            "has_content": bool(html_result and len(html_result) > 100)
        }
        
    except Exception as e:
        print(f"Error testing address members UI: {e}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    result = test_address_members_ui_quick()
    print("\n=== FINAL RESULT ===")
    print(result)