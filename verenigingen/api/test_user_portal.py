"""
Test portal address access with proper user switching
"""

import frappe

@frappe.whitelist()
def test_as_member_user(user_email):
    """Test portal functionality as a specific member user"""
    try:
        # Store original user
        original_user = frappe.session.user
        
        # Switch to member user
        frappe.session.user = user_email
        frappe.local.session_user = user_email
        
        try:
            # Test address access
            has_read = frappe.has_permission("Address", "read")
            addresses = frappe.get_list("Address",
                                      fields=["name", "address_title", "address_line1", "city"],
                                      limit_page_length=10)
            
            # Test member lookup
            member_name = frappe.db.get_value("Member", {"email": user_email}, "name")
            
            result = {
                "success": True,
                "test_user": user_email,
                "has_address_read": has_read,
                "addresses_found": len(addresses),
                "addresses": addresses,
                "member_record": member_name,
                "user_roles": frappe.get_roles(user_email)
            }
            
        finally:
            # Restore original user
            frappe.session.user = original_user
            frappe.local.session_user = original_user
        
        return result
        
    except Exception as e:
        # Ensure user is restored even on error
        frappe.session.user = original_user
        frappe.local.session_user = original_user
        return {
            "success": False,
            "error": str(e)
        }