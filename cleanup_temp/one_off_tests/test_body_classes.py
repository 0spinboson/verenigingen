#!/usr/bin/env python
"""Test script to verify body classes are being added correctly to portal pages"""

import frappe
from verenigingen.utils.portal_customization import add_brand_body_classes

def test_body_classes():
    """Test the add_brand_body_classes function"""
    
    # Test 1: Basic portal page
    context1 = {
        'path': '/member_portal',
        'pathname': '/member_portal'
    }
    result1 = add_brand_body_classes(context1)
    print("Test 1 - Member Portal Page:")
    print(f"  Body classes: {result1.get('body_class')}")
    print(f"  Data attribute: {result1.get('data_portal_page')}")
    print()
    
    # Test 2: Non-verenigingen page
    context2 = {
        'path': '/about',
        'pathname': '/about'
    }
    result2 = add_brand_body_classes(context2)
    print("Test 2 - Generic Page:")
    print(f"  Body classes: {result2.get('body_class')}")
    print()
    
    # Test 3: With existing body_class
    context3 = {
        'path': '/volunteer_portal',
        'pathname': '/volunteer_portal',
        'body_class': 'existing-class'
    }
    result3 = add_brand_body_classes(context3)
    print("Test 3 - With Existing Body Class:")
    print(f"  Body classes: {result3.get('body_class')}")
    print()
    
    # Test 4: Try to get brand class (may fail if no brand settings exist)
    try:
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_active_brand_settings
        brand_settings = get_active_brand_settings()
        if brand_settings:
            print("Test 4 - Active Brand Settings:")
            print(f"  Brand name: {brand_settings.get('settings_name')}")
            print(f"  Primary color: {brand_settings.get('primary_color')}")
    except Exception as e:
        print(f"Test 4 - Brand Settings Error: {str(e)}")

if __name__ == "__main__":
    frappe.connect()
    test_body_classes()
    frappe.destroy()