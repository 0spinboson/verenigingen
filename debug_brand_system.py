#!/usr/bin/env python3
"""
Debug brand system to see why colors aren't updating
"""

import sys
import os
sys.path.insert(0, '/home/frappe/frappe-bench')
sys.path.insert(0, '/home/frappe/frappe-bench/apps/frappe')
sys.path.insert(0, '/home/frappe/frappe-bench/sites')

import frappe

def debug_brand_system():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    frappe.set_user("Administrator")
    
    print("=" * 50)
    print("Brand System Debug")
    print("=" * 50)
    
    # Check 1: Brand Settings record
    try:
        if frappe.db.exists("Brand Settings", "Brand Settings"):
            settings = frappe.get_doc("Brand Settings", "Brand Settings")
            print("✓ Brand Settings found:")
            print(f"  Primary: {settings.primary_color}")
            print(f"  Secondary: {settings.secondary_color}")
            print(f"  Accent: {settings.accent_color}")
        else:
            print("✗ Brand Settings not found")
    except Exception as e:
        print(f"✗ Error reading Brand Settings: {e}")
    
    # Check 2: CSS file path and existence
    try:
        from verenigingen.utils.brand_css_generator import get_brand_css_file_path
        css_path = get_brand_css_file_path()
        print(f"\nCSS file path: {css_path}")
        
        if os.path.exists(css_path):
            with open(css_path, 'r') as f:
                content = f.read()
            print(f"✓ CSS file exists ({len(content)} chars)")
            
            # Check for specific colors
            if "#3b82f6" in content:
                print("  Contains blue fallback colors")
            if settings and settings.primary_color in content:
                print(f"  ✓ Contains actual primary color: {settings.primary_color}")
            else:
                print("  ✗ Does NOT contain Brand Settings colors")
                
        else:
            print("✗ CSS file does not exist")
    except Exception as e:
        print(f"✗ Error checking CSS file: {e}")
    
    # Check 3: Test manual CSS generation
    try:
        print("\nTesting manual CSS generation...")
        from verenigingen.utils.brand_css_generator import generate_brand_css_file
        css_path = generate_brand_css_file()
        print(f"✓ Manual generation successful: {css_path}")
        
        # Check the generated content
        if os.path.exists(css_path):
            with open(css_path, 'r') as f:
                content = f.read()[:200]  # First 200 chars
            print(f"Generated content preview:\n{content}...")
        
    except Exception as e:
        print(f"✗ Manual generation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_brand_system()