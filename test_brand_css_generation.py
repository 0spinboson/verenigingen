#!/usr/bin/env python3
"""
Test brand CSS generation system
"""

import sys
import os
sys.path.insert(0, '/home/frappe/frappe-bench')
sys.path.insert(0, '/home/frappe/frappe-bench/apps/frappe')
sys.path.insert(0, '/home/frappe/frappe-bench/sites')

import frappe

def test_brand_css_system():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("Testing Brand CSS Generation System")
    print("=" * 40)
    
    # Test 1: Check if Brand Settings exists
    if frappe.db.exists("Brand Settings", "Brand Settings"):
        settings = frappe.get_doc("Brand Settings", "Brand Settings")
        print(f"✓ Brand Settings found")
        print(f"  Primary: {settings.primary_color}")
        print(f"  Secondary: {settings.secondary_color}")
    else:
        print("Creating Brand Settings...")
        settings = frappe.get_doc({
            "doctype": "Brand Settings",
            "name": "Brand Settings",
            "primary_color": "#3b82f6",  # Nice blue
            "secondary_color": "#10b981",  # Green  
            "accent_color": "#8b5cf6",     # Purple
            "success_color": "#10b981",
            "warning_color": "#f59e0b", 
            "error_color": "#ef4444",
            "info_color": "#3b82f6",
            "text_color": "#1f2937",
            "background_color": "#ffffff"
        })
        settings.insert(ignore_permissions=True)
        frappe.db.commit()
        print("✓ Brand Settings created with nice blue colors")
    
    # Test 2: Generate CSS file
    try:
        from verenigingen.utils.brand_css_generator import generate_brand_css_file, get_brand_css_file_path
        
        css_path = generate_brand_css_file()
        print(f"✓ CSS file generated: {css_path}")
        
        # Check if file exists and has content
        if os.path.exists(css_path):
            with open(css_path, 'r') as f:
                content = f.read()
            print(f"✓ CSS file has {len(content)} characters")
            
            # Check for brand variables
            if "--brand-primary" in content:
                print("✓ Brand variables found in CSS file")
            else:
                print("✗ Brand variables NOT found in CSS file")
        else:
            print("✗ CSS file was not created")
            
    except Exception as e:
        print(f"✗ Error generating CSS: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 40)
    print("Test completed!")

if __name__ == "__main__":
    test_brand_css_system()