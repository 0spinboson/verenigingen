#!/usr/bin/env python3

import frappe
from frappe import _

@frappe.whitelist()
def debug_portal_settings():
    """Debug portal settings to see what menu items are available"""
    try:
        portal_settings = frappe.get_single("Portal Settings")
        
        print(f"Portal Settings found: {portal_settings.name}")
        print(f"Number of menu items: {len(portal_settings.menu)}")
        
        for idx, item in enumerate(portal_settings.menu):
            print(f"\n{idx + 1}. Title: {item.title}")
            print(f"   Route: {item.route}")
            print(f"   Enabled: {item.enabled}")
            print(f"   Role: {getattr(item, 'role', 'None')}")
            print(f"   Reference Doctype: {getattr(item, 'reference_doctype', 'None')}")
        
        return {
            "success": True,
            "menu_items": [
                {
                    "title": item.title,
                    "route": item.route,
                    "enabled": item.enabled,
                    "role": getattr(item, 'role', None),
                    "reference_doctype": getattr(item, 'reference_doctype', None)
                }
                for item in portal_settings.menu
            ]
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    frappe.init()
    frappe.connect()
    debug_portal_settings()