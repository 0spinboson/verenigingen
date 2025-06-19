"""
Fix Address permissions for portal users
"""

import frappe

@frappe.whitelist()
def add_customer_address_permissions():
    """Add Customer role permissions to Address doctype for portal access"""
    try:
        # Get Address doctype
        address_meta = frappe.get_meta("Address")
        
        # Check if Customer permission already exists
        existing_perm = None
        for perm in address_meta.permissions:
            if perm.role == "Customer":
                existing_perm = perm
                break
        
        if existing_perm:
            return {
                "success": True,
                "message": "Customer role already has Address permissions",
                "existing_permissions": {
                    "read": existing_perm.read,
                    "write": existing_perm.write,
                    "create": existing_perm.create
                }
            }
        
        # Add Customer permission
        address_doc = frappe.get_doc("DocType", "Address")
        address_doc.append("permissions", {
            "role": "Customer",
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 0,
            "share": 0,
            "report": 0,
            "export": 0,
            "import": 0,
            "set_user_permissions": 0,
            "apply_user_permissions": 1,
            "if_owner": 0
        })
        
        address_doc.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Added Customer role permissions to Address doctype"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def test_user_address_access(user_email):
    """Test if a user can access addresses"""
    try:
        # Temporarily switch user context
        original_user = frappe.session.user
        frappe.session.user = user_email
        
        try:
            # Test basic doctype access
            can_read = frappe.has_permission("Address", "read")
            
            # Test getting address list
            addresses = frappe.get_list("Address", 
                                      fields=["name", "address_title"],
                                      limit_page_length=5)
            
            # Test member lookup
            member_name = frappe.db.get_value("Member", {"email": user_email}, "name")
            
            result = {
                "success": True,
                "user_email": user_email,
                "can_read_address": can_read,
                "addresses_found": len(addresses),
                "addresses": addresses,
                "member_name": member_name,
                "user_roles": frappe.get_roles(user_email)
            }
            
        finally:
            # Restore original user
            frappe.session.user = original_user
        
        return result
        
    except Exception as e:
        # Restore original user in case of error
        frappe.session.user = original_user
        return {
            "success": False,
            "error": str(e)
        }