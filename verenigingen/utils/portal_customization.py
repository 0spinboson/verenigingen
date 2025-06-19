"""
Portal customization utilities for association members
"""

import frappe

@frappe.whitelist()
def setup_member_portal_menu():
    """Set up portal menu specifically for association members"""
    try:
        # Get or create Portal Settings
        portal_settings = frappe.get_single("Portal Settings")
        
        # Disable irrelevant standard menu items
        items_to_disable = [
            "Projects", "Quotations", "Orders", "Invoices", 
            "Shipments", "Timesheets", "Material Request"
        ]
        
        # Clear existing standard menu items and re-add only relevant ones
        portal_settings.menu = []
        
        # Add relevant standard items
        relevant_items = [
            {
                "title": "Issues",
                "route": "/issues", 
                "reference_doctype": "Issue",
                "role": "",
                "enabled": 1
            },
            {
                "title": "Addresses",
                "route": "/addresses",
                "reference_doctype": "Address", 
                "role": "",
                "enabled": 1
            },
            {
                "title": "Newsletter",
                "route": "/newsletters",
                "reference_doctype": "Newsletter",
                "role": "",
                "enabled": 1
            }
        ]
        
        # Add member-specific menu items
        member_items = [
            {
                "title": "Member Portal",
                "route": "/member_portal",
                "reference_doctype": "",
                "role": "Member",
                "enabled": 1
            },
            {
                "title": "My Memberships",
                "route": "/memberships",
                "reference_doctype": "Membership",
                "role": "Member", 
                "enabled": 1
            },
            {
                "title": "Volunteer Portal",
                "route": "/volunteer_portal",
                "reference_doctype": "",
                "role": "Volunteer",
                "enabled": 1
            },
            {
                "title": "My Expenses", 
                "route": "/my_expenses",
                "reference_doctype": "Volunteer Expense",
                "role": "Volunteer",
                "enabled": 1
            }
        ]
        
        # Add all items to portal settings
        for item in relevant_items + member_items:
            portal_settings.append("menu", item)
        
        # Save portal settings
        portal_settings.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Portal menu configured for association members",
            "items_added": len(relevant_items + member_items)
        }
        
    except Exception as e:
        frappe.log_error(f"Error setting up member portal menu: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_current_portal_menu():
    """Get current portal menu configuration"""
    try:
        portal_settings = frappe.get_single("Portal Settings")
        
        menu_items = []
        for item in portal_settings.menu:
            menu_items.append({
                "title": item.title,
                "route": item.route,
                "reference_doctype": item.reference_doctype,
                "role": item.role,
                "enabled": item.enabled
            })
        
        return {
            "success": True,
            "menu_items": menu_items,
            "total_items": len(menu_items)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()  
def reset_portal_menu_to_member_only():
    """Reset portal menu to show only member-relevant items"""
    try:
        portal_settings = frappe.get_single("Portal Settings")
        
        # Clear all existing menu items
        portal_settings.menu = []
        
        # Add only member-relevant items
        member_menu_items = [
            {
                "title": "Member Portal",
                "route": "/member_portal", 
                "reference_doctype": "",
                "role": "",
                "enabled": 1
            },
            {
                "title": "Issues & Support",
                "route": "/issues",
                "reference_doctype": "Issue",
                "role": "",
                "enabled": 1
            },
            {
                "title": "My Addresses", 
                "route": "/my_addresses",
                "reference_doctype": "",
                "role": "",
                "enabled": 1
            },
            {
                "title": "Newsletter",
                "route": "/newsletters", 
                "reference_doctype": "Newsletter",
                "role": "",
                "enabled": 1
            },
            {
                "title": "Projects",
                "route": "/projects",
                "reference_doctype": "Project",
                "role": "Projects User",
                "enabled": 1
            },
            {
                "title": "Volunteer Portal",
                "route": "/volunteer_portal",
                "reference_doctype": "",
                "role": "Volunteer", 
                "enabled": 1
            }
        ]
        
        for item in member_menu_items:
            portal_settings.append("menu", item)
        
        portal_settings.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Portal menu reset to member-only items",
            "items_configured": len(member_menu_items)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_member_context(context):
    """Add member-specific context to portal pages"""
    try:
        # Check if user is a member
        if frappe.session.user and frappe.session.user != "Guest":
            member = frappe.db.get_value("Member", {"email": frappe.session.user}, ["name", "member_name"])
            if member:
                context["is_member"] = True
                context["member_name"] = member[1] if len(member) > 1 else member[0]
                context["member_id"] = member[0]
            else:
                context["is_member"] = False
        
        return context
        
    except Exception as e:
        frappe.log_error(f"Error getting member context: {str(e)}")
        return context