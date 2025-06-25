#!/usr/bin/env python3

import frappe

def debug_settings():
    """Debug E-Boekhouden Settings"""
    try:
        frappe.init(site='dev.veganisme.net')
        frappe.connect()
        
        # Check if settings exist
        settings = frappe.get_single("E-Boekhouden Settings")
        print(f"Settings found: {settings.name}")
        print(f"API URL: {settings.api_url}")
        print(f"Source Application: {settings.source_application}")
        
        # Check if api_token field has a value (but don't print it)
        has_token = bool(settings.get("api_token"))
        print(f"API Token field populated: {has_token}")
        
        # Try to get the password
        try:
            token = settings.get_password('api_token')
            has_password = bool(token)
            print(f"API Token password accessible: {has_password}")
            if token:
                print(f"Token length: {len(token)} characters")
        except Exception as e:
            print(f"Error getting password: {e}")
        
        # Check the raw database value
        raw_token = frappe.db.get_value("E-Boekhouden Settings", "E-Boekhouden Settings", "api_token")
        print(f"Raw token value exists: {bool(raw_token)}")
        
        return settings
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    debug_settings()