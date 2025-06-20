#!/usr/bin/env python3
"""
Test script for brand management system
"""

import frappe
from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_active_brand_settings, generate_brand_css

def test_brand_system():
    """Test the brand management system functionality"""
    
    print("Testing Brand Management System")
    print("=" * 50)
    
    # Test 1: Get active brand settings
    print("\n1. Testing active brand settings retrieval...")
    try:
        settings = get_active_brand_settings()
        print("✓ Active brand settings retrieved successfully")
        print(f"  Primary Color: {settings.get('primary_color', 'Not set')}")
        print(f"  Secondary Color: {settings.get('secondary_color', 'Not set')}")
        print(f"  Accent Color: {settings.get('accent_color', 'Not set')}")
    except Exception as e:
        print(f"✗ Error retrieving active brand settings: {e}")
    
    # Test 2: Generate brand CSS
    print("\n2. Testing brand CSS generation...")
    try:
        css = generate_brand_css()
        if css and len(css) > 100:  # Basic sanity check
            print("✓ Brand CSS generated successfully")
            print(f"  CSS length: {len(css)} characters")
            # Show first few CSS variables
            lines = css.split('\n')
            for line in lines[:10]:
                if '--brand-' in line:
                    print(f"  {line.strip()}")
        else:
            print("✗ Brand CSS generation failed or returned empty")
    except Exception as e:
        print(f"✗ Error generating brand CSS: {e}")
    
    # Test 3: Check if Brand Settings doctype exists
    print("\n3. Testing Brand Settings doctype...")
    try:
        doctype_exists = frappe.db.exists("DocType", "Brand Settings")
        if doctype_exists:
            print("✓ Brand Settings doctype exists")
            
            # Check if any brand settings records exist
            settings_count = frappe.db.count("Brand Settings")
            print(f"  Found {settings_count} Brand Settings records")
            
            if settings_count > 0:
                # Get the first brand setting
                first_setting = frappe.get_all("Brand Settings", 
                    fields=["name", "settings_name", "is_active", "primary_color"],
                    limit=1)
                if first_setting:
                    setting = first_setting[0]
                    print(f"  Example setting: {setting.settings_name} ({'Active' if setting.is_active else 'Inactive'})")
                    print(f"  Primary color: {setting.primary_color}")
        else:
            print("✗ Brand Settings doctype does not exist")
    except Exception as e:
        print(f"✗ Error checking Brand Settings doctype: {e}")
    
    print("\n" + "=" * 50)
    print("Brand Management System Test Complete")

if __name__ == "__main__":
    test_brand_system()