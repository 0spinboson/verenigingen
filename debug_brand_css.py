#!/usr/bin/env python3
"""
Debug brand CSS issues
"""

import sys
import os
sys.path.insert(0, '/home/frappe/frappe-bench')
sys.path.insert(0, '/home/frappe/frappe-bench/apps/frappe')
sys.path.insert(0, '/home/frappe/frappe-bench/sites')

import frappe

def debug_brand_css():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("Debugging Brand CSS System...")
    
    # Check if Brand Settings exists
    brand_settings = frappe.db.exists("Brand Settings", "Brand Settings")
    print(f"Brand Settings exists: {brand_settings}")
    
    if brand_settings:
        settings = frappe.get_doc("Brand Settings", "Brand Settings")
        print(f"Primary color: {settings.primary_color}")
        print(f"Secondary color: {settings.secondary_color}")
        
        # Test generate_brand_css function
        try:
            from verenigingen.verenigingen.doctype.brand_settings.brand_settings import generate_brand_css
            css = generate_brand_css()
            print(f"Generated CSS length: {len(css)} characters")
            print(f"CSS preview: {css[:200]}...")
        except Exception as e:
            print(f"Error generating CSS: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("Creating default Brand Settings...")
        try:
            from verenigingen.verenigingen.doctype.brand_settings.brand_settings import create_default_brand_settings
            create_default_brand_settings()
            print("Default Brand Settings created")
        except Exception as e:
            print(f"Error creating Brand Settings: {str(e)}")

if __name__ == "__main__":
    debug_brand_css()