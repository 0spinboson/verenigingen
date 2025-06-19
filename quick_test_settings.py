#!/usr/bin/env python3
"""Quick test to verify settings fields were added correctly"""

import frappe

def quick_test():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    # Check if fields exist in the database
    print("Checking Verenigingen Settings doctype...")
    
    meta = frappe.get_meta("Verenigingen Settings")
    fields = [field.fieldname for field in meta.fields]
    
    required_fields = [
        'application_settings_section',
        'enable_income_calculator', 
        'income_percentage_rate',
        'calculator_description'
    ]
    
    print("Required fields:", required_fields)
    print("Found fields:", [field for field in required_fields if field in fields])
    print("Missing fields:", [field for field in required_fields if field not in fields])
    
    # Try to get the settings document
    try:
        settings = frappe.get_single("Verenigingen Settings")
        print(f"\nCurrent settings:")
        print(f"  Calculator enabled: {getattr(settings, 'enable_income_calculator', 'Field not found')}")
        print(f"  Percentage rate: {getattr(settings, 'income_percentage_rate', 'Field not found')}")
        print(f"  Description: {getattr(settings, 'calculator_description', 'Field not found')[:100]}...")
    except Exception as e:
        print(f"Error getting settings: {e}")
    
    print("\n=== Test completed ===")

if __name__ == "__main__":
    quick_test()