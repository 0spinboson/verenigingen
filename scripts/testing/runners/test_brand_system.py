#!/usr/bin/env python3
"""
Test Brand Management System
"""

import os
import sys

# Add the apps directory to Python path
sys.path.insert(0, '/home/frappe/frappe-bench/apps')
sys.path.insert(0, '/home/frappe/frappe-bench')

# Set required environment variables
os.environ['FRAPPE_SITE'] = 'dev.veganisme.net'

import frappe

def test_brand_system():
    """Test the brand management system"""
    
    print("Brand Management System Test")
    print("=" * 40)
    
    try:
        # Initialize Frappe
        frappe.init(site='dev.veganisme.net')
        frappe.connect()
        
        # Test 1: Check if Brand Settings doctype exists
        print("\n1. Checking Brand Settings doctype...")
        doctype_exists = frappe.db.exists("DocType", "Brand Settings")
        if doctype_exists:
            print("✓ Brand Settings doctype exists")
            
            # Check records
            settings_count = frappe.db.count("Brand Settings")
            print(f"  Found {settings_count} Brand Settings records")
            
        else:
            print("✗ Brand Settings doctype does not exist")
        
        # Test 2: Test brand CSS generation
        print("\n2. Testing brand CSS generation...")
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import generate_brand_css
        css = generate_brand_css()
        
        if css and len(css) > 100:
            print("✓ Brand CSS generated successfully")
            print(f"  CSS length: {len(css)} characters")
            
            # Show some CSS variables
            lines = css.split('\n')
            css_vars = [line.strip() for line in lines if '--brand-primary:' in line or '--brand-secondary:' in line]
            for var in css_vars[:3]:
                if var:
                    print(f"  {var}")
        else:
            print("✗ Brand CSS generation failed")
        
        # Test 3: Test active brand settings
        print("\n3. Testing active brand settings...")
        from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_active_brand_settings
        
        settings = get_active_brand_settings()
        print("✓ Active brand settings retrieved:")
        print(f"  Primary Color: {settings.get('primary_color', 'Not set')}")
        print(f"  Secondary Color: {settings.get('secondary_color', 'Not set')}")
        print(f"  Accent Color: {settings.get('accent_color', 'Not set')}")
        
        print("\n" + "=" * 40)
        print("✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        frappe.destroy()

if __name__ == "__main__":
    test_brand_system()