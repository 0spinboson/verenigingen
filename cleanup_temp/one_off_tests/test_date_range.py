#!/usr/bin/env python3
"""
Test the E-Boekhouden date range detection
"""

import frappe
import sys


def test_date_range():
    """Test the actual date range detection"""
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    try:
        from verenigingen.utils.eboekhouden_date_analyzer import get_actual_date_range
        
        print("Testing E-Boekhouden date range detection...")
        print("-" * 50)
        
        result = get_actual_date_range()
        
        if result["success"]:
            print(f"✅ Date range detected successfully!")
            print(f"   Earliest date: {result['earliest_formatted']} ({result['earliest_date']})")
            print(f"   Latest date: {result['latest_formatted']} ({result['latest_date']})")
            print(f"   Total mutations: {result['total_mutations']}")
            print(f"   Samples analyzed: {result['samples_analyzed']}")
        else:
            print(f"❌ Failed to detect date range: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        frappe.destroy()


if __name__ == "__main__":
    test_date_range()